"""Minimal smoke tests for the final release.

Run:
    python smoke_test.py

The tests avoid live Apify and live Box calls so they stay deterministic.
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["USE_REAL_APIFY"] = "false"
os.environ["USE_REAL_BOX"] = "false"
os.environ["USE_BOX_READ"] = "false"
os.environ["USE_REAL_LLM"] = "false"
os.environ["BOX_DEVELOPER_TOKEN"] = ""
os.environ["GEMINI_API_KEY"] = ""

from app import app, collect_sources  # noqa: E402
from apify_client import MockApifyClient, normalize_apify_items  # noqa: E402
from box_client import BoxContentReader, BoxRestUploader, LocalBoxMemory  # noqa: E402
from demo_data import SAMPLE_PROJECT  # noqa: E402
from report_generator import generate_role_briefs  # noqa: E402
from hackathon_packager import generate_hackathon_package  # noqa: E402
from showcase_features import generate_showcase_features  # noqa: E402


def test_generator():
    result = generate_role_briefs(SAMPLE_PROJECT, SAMPLE_PROJECT["sources"], SAMPLE_PROJECT["roles"])
    assert "engineer" in result["briefs"]
    assert "judge" in result["briefs"]
    assert result["sponsor_fit"]["total_score"] >= 90
    assert len(result["sources"]) >= 3
    assert "evidence_map" in result
    assert "role_strategy" in result
    assert "judge_pitch_pack" in result
    assert "role_briefs/_role_comparison_matrix.md" in result["manifest"]["outputs"]["role_briefs"]
    assert "metadata/evidence_map.json" in result["manifest"]["outputs"]["metadata"]
    assert "metadata/llm_generation.json" in result["manifest"]["outputs"]["metadata"]
    assert result["llm_generation"]["enabled"] is False
    assert result["briefs"]["engineer"]["generation_mode"] == "deterministic_local"
    assert "data contract" in result["briefs"]["engineer"]["markdown"].lower()
    assert "decision memo" in result["briefs"]["executive"]["markdown"].lower()
    assert "three-minute demo choreography" in result["briefs"]["judge"]["markdown"].lower()


def test_gemini_missing_key_fallback():
    project = dict(SAMPLE_PROJECT)
    project["use_live_llm"] = True
    project["roles"] = ["engineer"]
    old_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = ""
    try:
        result = generate_role_briefs(project, SAMPLE_PROJECT["sources"], ["engineer"])
    finally:
        if old_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = old_key
    assert result["llm_generation"]["enabled"] is True
    assert result["llm_generation"]["provider"] == "gemini"
    assert result["llm_generation"]["fallback_roles"] == ["engineer"]
    assert result["briefs"]["engineer"]["generation_mode"] == "deterministic_local"
    assert "GEMINI_API_KEY" in result["llm_generation"]["warnings"][0]


def test_hackathon_packager():
    result = generate_role_briefs(SAMPLE_PROJECT, SAMPLE_PROJECT["sources"], SAMPLE_PROJECT["roles"])
    result["collector_status"] = {
        "mode": "curated_sample",
        "requested_urls": 3,
        "returned_items": 3,
        "normalized_sources": len(SAMPLE_PROJECT["sources"]),
    }
    package = generate_hackathon_package(result)
    assert "submission_readme.md" in package["docs"]
    assert "three_minute_demo_script.md" in package["docs"]
    assert "judge_qa_cheatsheet.md" in package["docs"]
    assert "sponsor_story.md" in package["docs"]
    assert "Box is the memory" in package["closing_line"]
    assert package["checklist"]["role_differentiation_visible"] is True


def test_showcase_features():
    result = generate_role_briefs(SAMPLE_PROJECT, SAMPLE_PROJECT["sources"], SAMPLE_PROJECT["roles"])
    result["collector_status"] = {
        "mode": "curated_sample",
        "ok": True,
        "requested_urls": 3,
        "returned_items": 3,
        "normalized_sources": len(SAMPLE_PROJECT["sources"]),
    }
    result["box_sync_status"] = {
        "mode": "local_only",
        "ok": True,
        "message": "Local only",
    }
    result["hackathon_package"] = generate_hackathon_package(result)
    showcase = generate_showcase_features(result)
    assert showcase["task_inbox"]["task_count"] >= 12
    assert showcase["showcase_readiness"]["score"] >= 80
    assert "Box Task Inbox" in showcase["task_inbox_markdown"]
    assert "rescue_cards" not in showcase


def test_mock_apify_client():
    sources = MockApifyClient().collect_sources(["https://example.com/docs"], "demo goal")
    assert len(sources) == 1
    assert sources[0]["source_type"] == "mock_external_url"
    assert sources[0]["collector"] == "mock"


def test_apify_item_normalizer():
    items = [
        {
            "url": "https://example.com/product",
            "title": "Example Product",
            "markdown": "# Example Product\nThis page explains a product for project teams. It has APIs, use cases, and security notes.",
        }
    ]
    sources = normalize_apify_items(items, ["https://example.com/product"])
    assert len(sources) == 1
    assert sources[0]["source_type"] == "apify_external_web"
    assert sources[0]["id"] == "A1"


def test_collect_sources_mock_path():
    project = {
        "external_urls": ["https://example.com/docs"],
        "project_goal": "Test goal",
        "internal_notes": "Internal note for smoke test.",
        "use_live_apify": False,
    }
    sources, status = collect_sources(project)
    assert status["mode"] == "mock"
    assert status["normalized_sources"] == 2
    assert any(s["source_type"] == "internal_notes" for s in sources)


def test_local_box_memory():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        box = LocalBoxMemory(root)
        folder = box.create_project_folder("Smoke Test Project")
        box.write_markdown(folder, "sources/source.md", "# Source")
        box.write_json(folder, "metadata/test.json", {"ok": True})
        assert (folder / "sources/source.md").exists()
        assert (folder / "metadata/test.json").exists()


def test_box_disabled_status():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        local = root / "project-box-memory"
        (local / "metadata").mkdir(parents=True)
        (local / "metadata/manifest.json").write_text('{"ok": true}', encoding="utf-8")
        status = BoxRestUploader(use_live=False).sync_directory(local, "Smoke Project", "abc123").to_dict()
        assert status["mode"] == "local_only"
        assert status["fallback_used"] is True


def test_box_missing_token_status():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        local = root / "project-box-memory"
        (local / "metadata").mkdir(parents=True)
        (local / "metadata/manifest.json").write_text('{"ok": true}', encoding="utf-8")
        status = BoxRestUploader(token="", use_live=True).sync_directory(local, "Smoke Project", "abc123").to_dict()
        assert status["mode"] == "local_mirror"
        assert status["ok"] is False
        assert "BOX_DEVELOPER_TOKEN" in status["message"]


def test_box_read_disabled_status():
    sources, status = BoxContentReader(use_live=False).collect_sources("demo goal")
    data = status.to_dict()
    assert sources == []
    assert data["mode"] == "disabled"
    assert data["ok"] is True


def test_box_read_missing_token_status():
    reader = BoxContentReader(token="", folder_id="123", use_live=True)
    sources, status = reader.collect_sources("demo goal")
    data = status.to_dict()
    assert sources == []
    assert data["mode"] == "missing_token"
    assert data["ok"] is False


def test_box_read_missing_folder_status():
    reader = BoxContentReader(token="fake-token", folder_id="", use_live=True)
    sources, status = reader.collect_sources("demo goal")
    data = status.to_dict()
    assert sources == []
    assert data["mode"] == "missing_folder"
    assert data["ok"] is False


def test_flask_demo_route():
    app.testing = True
    client = app.test_client()
    response = client.get("/demo", follow_redirects=True)
    assert response.status_code == 200
    assert b"Role-specific briefs" in response.data
    assert b"Project memory layout" in response.data
    assert b"Evidence collection status" in response.data
    assert b"Box sync status" in response.data
    assert b"Box source import status" in response.data
    assert b"Gemini AI generation status" in response.data
    assert b"Evidence health map" in response.data
    assert b"Judge-ready extras" in response.data
    assert b"Hackathon package" in response.data
    assert b"Download full showcase package" in response.data
    assert b"Final showcase command center" in response.data
    assert b"Box Task Inbox preview" in response.data


if __name__ == "__main__":
    test_generator()
    test_gemini_missing_key_fallback()
    test_hackathon_packager()
    test_showcase_features()
    test_mock_apify_client()
    test_apify_item_normalizer()
    test_collect_sources_mock_path()
    test_local_box_memory()
    test_box_disabled_status()
    test_box_missing_token_status()
    test_box_read_disabled_status()
    test_box_read_missing_token_status()
    test_box_read_missing_folder_status()
    test_flask_demo_route()
    print("Smoke tests passed.")
