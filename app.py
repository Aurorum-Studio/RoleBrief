from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os
import uuid

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, send_file, abort

from apify_client import ApifyEvidenceClient, MockApifyClient, should_use_live_apify
from llm_client import should_use_live_llm
from box_client import BoxContentReader, BoxRestUploader, LocalBoxMemory, slugify, should_read_live_box, should_use_live_box
from demo_data import SAMPLE_PROJECT
from report_generator import (
    DEFAULT_ROLES,
    ROLE_LABELS,
    generate_role_briefs,
    source_to_markdown,
)
from hackathon_packager import generate_hackathon_package
from showcase_features import generate_showcase_features

load_dotenv()

APP_ROOT = Path(__file__).parent
OUTPUT_ROOT = APP_ROOT / "output_runs"
OUTPUT_ROOT.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["DEMO_MODE"] = os.getenv("DEMO_MODE", "true").lower() == "true"


def parse_urls(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def selected_roles(form) -> list[str]:
    roles = form.getlist("roles")
    return [role for role in roles if role in ROLE_LABELS] or DEFAULT_ROLES


def build_project_from_form(form) -> dict:
    use_live_apify = form.get("use_live_apify") == "on" or should_use_live_apify(None)
    use_live_box = form.get("use_live_box") == "on" or should_use_live_box(None)
    use_box_read = form.get("use_box_read") == "on" or should_read_live_box(None)
    use_live_llm = form.get("use_live_llm") == "on" or should_use_live_llm(None)
    return {
        "project_name": form.get("project_name", "").strip() or "Untitled Project",
        "tagline": form.get("tagline", "").strip() or "One project. Many audiences.",
        "project_goal": form.get("project_goal", "").strip(),
        "internal_notes": form.get("internal_notes", "").strip(),
        "external_urls": parse_urls(form.get("external_urls", "")),
        "roles": selected_roles(form),
        "use_live_apify": use_live_apify,
        "use_live_box": use_live_box,
        "use_box_read": use_box_read,
        "box_source_folder_id": form.get("box_source_folder_id", "").strip() or os.getenv("BOX_SOURCE_FOLDER_ID", "").strip(),
        "use_live_llm": use_live_llm,
    }


def collect_sources(project: dict) -> tuple[list[dict], dict]:
    """Collect external and internal evidence.

    The live Apify path can use the real REST API, but every path returns normalized
    source objects so the report generator and Box memory stay stable.
    """
    if project.get("_use_sample_sources"):
        return project.get("sources", []), {
            "mode": "curated_sample",
            "ok": True,
            "message": "Using curated sample evidence for the fastest local demo.",
            "actor_id": None,
            "requested_urls": len(project.get("external_urls", [])),
            "returned_items": len(project.get("sources", [])),
            "normalized_sources": len(project.get("sources", [])),
            "fallback_used": False,
            "warnings": [],
        }

    external_urls = project.get("external_urls", [])
    if project.get("use_live_apify"):
        sources, status = ApifyEvidenceClient().collect_sources(
            external_urls,
            project.get("project_goal", ""),
        )
        collector_status = status.to_dict()
    else:
        client = MockApifyClient()
        sources = client.collect_sources(external_urls, project.get("project_goal", ""))
        collector_status = {
            "mode": "mock",
            "ok": True,
            "message": "Live Apify is disabled. Using deterministic mock evidence for a stable demo.",
            "actor_id": os.getenv("APIFY_ACTOR_ID", "apify/website-content-crawler"),
            "requested_urls": len(external_urls),
            "returned_items": 0,
            "normalized_sources": len(sources),
            "fallback_used": True,
            "warnings": ["Enable USE_REAL_APIFY=true and add APIFY_API_TOKEN to crawl live pages."],
        }

    if project.get("internal_notes"):
        sources.append(
            {
                "id": f"N{len(sources) + 1}",
                "title": "Internal Project Notes",
                "url": "box://project-memory/internal-notes.md",
                "source_type": "internal_notes",
                "summary": project["internal_notes"][:650],
                "key_points": [
                    "Internal notes are treated as private project context.",
                    "Live Box mode can store this source inside a real Box folder.",
                    "Role briefs combine internal notes with external evidence.",
                ],
                "collector": "user_input",
            }
        )
        collector_status["normalized_sources"] = len(sources)

    return sources, collector_status


def collect_box_sources(project: dict) -> tuple[list[dict], dict]:
    """Import existing Box files as evidence sources.

    This complements Box export. Export writes generated project memory to Box;
    read/import lets an existing Box folder become input knowledge for Gemini.
    """
    reader = BoxContentReader(
        folder_id=project.get("box_source_folder_id") or None,
        use_live=project.get("use_box_read", False),
    )
    sources, status = reader.collect_sources(project.get("project_goal", ""))
    return sources, status.to_dict()


def write_local_box_run(run_id: str, result: dict) -> Path:
    run_root = OUTPUT_ROOT / run_id
    box = LocalBoxMemory(run_root)
    project_folder = box.create_project_folder(result["project"]["project_name"])

    for source in result["sources"]:
        source_name = f"{source.get('id', 'source')}_{slugify(source.get('title', 'source'))}.md"
        box.write_markdown(project_folder, f"sources/{source_name}", source_to_markdown(source))

    for role, brief in result["briefs"].items():
        box.write_markdown(project_folder, f"role_briefs/{role}_brief.md", brief["markdown"])

    # Role-differentiation artifacts make
    # the project look less like a generic summarizer and more like a product.
    box.write_markdown(project_folder, "role_briefs/_role_comparison_matrix.md", result["role_matrix_markdown"])
    box.write_markdown(project_folder, "role_briefs/judge_pitch_pack.md", result["judge_pitch_pack"])

    # The final release adds hackathon packaging artifacts: the docs a team can
    # copy directly into GitHub, Devpost/Luma, and the judging presentation.
    for filename, markdown in result.get("hackathon_package", {}).get("docs", {}).items():
        box.write_markdown(project_folder, f"submission_package/{filename}", markdown)

    # The final release adds judge-facing showcase artifacts. They are intentionally
    # written as normal Box project-memory files so the existing Box sync path
    # uploads them without introducing a risky new integration.
    showcase = result.get("showcase_features", {})
    if showcase:
        box.write_markdown(project_folder, "task_inbox/00_box_task_inbox.md", showcase.get("task_inbox_markdown", ""))
        box.write_markdown(project_folder, "task_inbox/01_role_router.md", showcase.get("role_router_markdown", ""))

    box.write_json(project_folder, "metadata/manifest.json", result["manifest"])
    box.write_json(project_folder, "metadata/sponsor_fit.json", result["sponsor_fit"])
    box.write_json(project_folder, "metadata/evidence_map.json", result["evidence_map"])
    box.write_json(project_folder, "metadata/role_strategy.json", result["role_strategy"])
    box.write_json(project_folder, "metadata/llm_generation.json", result.get("llm_generation", {}))
    box.write_json(project_folder, "metadata/evidence_collection.json", result["collector_status"])
    box.write_json(project_folder, "metadata/box_read.json", result.get("box_read_status", {}))
    box.write_json(project_folder, "metadata/demo_checklist.json", result.get("hackathon_package", {}).get("checklist", {}))
    if result.get("showcase_features"):
        box.write_json(project_folder, "metadata/task_router.json", result["showcase_features"].get("task_inbox", {}))
        box.write_json(project_folder, "metadata/showcase_readiness.json", result["showcase_features"].get("showcase_readiness", {}))
    if "box_sync_status" in result:
        box.write_json(project_folder, "metadata/box_sync.json", result["box_sync_status"])
    box.write_json(run_root, "result.json", result)
    return project_folder


def sync_to_box_and_persist(run_id: str, result: dict, project_folder: Path) -> dict:
    uploader = BoxRestUploader(use_live=result["project"].get("use_live_box", False))
    box_status = uploader.sync_directory(
        project_folder,
        result["project"].get("project_name", "Untitled Project"),
        run_id,
    ).to_dict()
    result["box_sync_status"] = box_status
    if "metadata/box_sync.json" not in result["manifest"]["outputs"]["metadata"]:
        result["manifest"]["outputs"]["metadata"].append("metadata/box_sync.json")
    result["manifest"]["box_sync_status"] = box_status

    # Re-write metadata and result.json after the live Box sync status is known.
    box = LocalBoxMemory(OUTPUT_ROOT / run_id)
    box.write_json(project_folder, "metadata/manifest.json", result["manifest"])
    box.write_json(project_folder, "metadata/llm_generation.json", result.get("llm_generation", {}))
    box.write_json(project_folder, "metadata/box_read.json", result.get("box_read_status", {}))
    box.write_json(project_folder, "metadata/box_sync.json", box_status)
    box.write_json(OUTPUT_ROOT / run_id, "result.json", result)
    return result


def read_result(run_id: str) -> dict | None:
    path = OUTPUT_ROOT / run_id / "result.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_project(project: dict) -> str:
    sources, collector_status = collect_sources(project)
    box_sources, box_read_status = collect_box_sources(project)
    sources.extend(box_sources)
    result = generate_role_briefs(project, sources, project["roles"])
    result["collector_status"] = collector_status
    result["box_read_status"] = box_read_status
    # Final release turns the generated analysis into a submit-ready package.
    result["hackathon_package"] = generate_hackathon_package(result)
    result["manifest"]["outputs"]["submission_package"] = [
        f"submission_package/{filename}"
        for filename in result["hackathon_package"]["docs"].keys()
    ]
    # Final showcase layer: routed task inbox and readiness score.
    result["showcase_features"] = generate_showcase_features(result)
    result["manifest"]["outputs"]["task_inbox"] = [
        "task_inbox/00_box_task_inbox.md",
        "task_inbox/01_role_router.md",
    ]
    for metadata_path in [
        "metadata/evidence_collection.json",
        "metadata/evidence_map.json",
        "metadata/role_strategy.json",
        "metadata/llm_generation.json",
        "metadata/box_read.json",
        "metadata/demo_checklist.json",
        "metadata/task_router.json",
        "metadata/showcase_readiness.json",
    ]:
        if metadata_path not in result["manifest"]["outputs"]["metadata"]:
            result["manifest"]["outputs"]["metadata"].append(metadata_path)
    result["manifest"]["collector_status"] = collector_status
    run_id = uuid.uuid4().hex[:10]
    project_folder = write_local_box_run(run_id, result)
    sync_to_box_and_persist(run_id, result, project_folder)
    return run_id


@app.get("/")
def index():
    return render_template(
        "index.html",
        roles=ROLE_LABELS,
        default_roles=DEFAULT_ROLES,
        sample=SAMPLE_PROJECT,
        demo_mode=app.config["DEMO_MODE"],
        use_real_apify_env=should_use_live_apify(None),
        has_apify_token=bool(os.getenv("APIFY_API_TOKEN", "").strip()),
        use_real_box_env=should_use_live_box(None),
        use_box_read_env=should_read_live_box(None),
        has_box_token=bool(os.getenv("BOX_DEVELOPER_TOKEN", "").strip()),
        box_source_folder_id=os.getenv("BOX_SOURCE_FOLDER_ID", "").strip(),
        use_real_llm_env=should_use_live_llm(None),
        has_gemini_key=bool(os.getenv("GEMINI_API_KEY", "").strip()),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        box_parent_folder_id=os.getenv("BOX_PARENT_FOLDER_ID", "0").strip() or "0",
    )


@app.post("/analyze")
def analyze():
    project = build_project_from_form(request.form)
    run_id = run_project(project)
    return redirect(url_for("show_result", run_id=run_id))


@app.get("/demo")
def demo():
    project = dict(SAMPLE_PROJECT)
    project["use_live_box"] = should_use_live_box(None)
    project["use_box_read"] = should_read_live_box(None)
    project["box_source_folder_id"] = os.getenv("BOX_SOURCE_FOLDER_ID", "").strip()
    project["use_live_llm"] = should_use_live_llm(None)
    project["_use_sample_sources"] = True
    run_id = run_project(project)
    return redirect(url_for("show_result", run_id=run_id))


@app.get("/run/<run_id>")
def show_result(run_id: str):
    result = read_result(run_id)
    if not result:
        abort(404)
    project_folder = OUTPUT_ROOT / run_id / f"{slugify(result['project']['project_name'])}-box-memory"
    return render_template(
        "result.html",
        run_id=run_id,
        result=result,
        project_folder=str(project_folder),
        role_labels=ROLE_LABELS,
    )


@app.get("/download/<run_id>")
def download_run(run_id: str):
    result = read_result(run_id)
    if not result:
        abort(404)

    run_root = OUTPUT_ROOT / run_id
    zip_path = run_root / f"rolebrief_output_{run_id}.zip"
    if not zip_path.exists():
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
            for path in run_root.rglob("*"):
                if path.is_file() and path != zip_path:
                    zf.write(path, path.relative_to(run_root))
    return send_file(zip_path, as_attachment=True, download_name=zip_path.name)


if __name__ == "__main__":
    app.run(debug=True)
