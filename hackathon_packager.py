"""Hackathon submission packaging for RoleBrief AI.

The hackathon packager focuses on presentation, not more infrastructure. It turns
an analysis run into the exact artifacts a team needs to submit and demo a
hackathon project: README copy, Devpost/Luma description, demo script, sponsor
story, judge Q&A, screenshot checklist, and implementation roadmap.
"""

from __future__ import annotations

from textwrap import dedent
from datetime import datetime
import re


def _clean(text: str, fallback: str = "") -> str:
    text = (text or "").strip()
    return text if text else fallback


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbers(items: list[str]) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def _slug(value: str) -> str:
    value = (value or "item").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def _box_status_line(result: dict) -> str:
    status = result.get("box_sync_status") or {}
    mode = status.get("mode")
    if status.get("root_folder_url"):
        return f"Box sync mode: `{mode}`. Generated Box folder: {status['root_folder_url']}"
    if mode:
        return f"Box sync mode: `{mode}`. The app still creates a local Box-style project memory for deterministic demos."
    return "The app writes a local Box-style memory first, then uploads the same artifact tree to real Box when live Box mode is enabled."


def _apify_status_line(result: dict) -> str:
    status = result.get("collector_status") or {}
    return (
        f"Evidence collection mode: `{status.get('mode', 'unknown')}`. "
        f"Requested URLs: {status.get('requested_urls', 0)}. "
        f"Normalized sources: {status.get('normalized_sources', len(result.get('sources', [])))}."
    )


def _selected_role_labels(result: dict) -> list[str]:
    return [brief.get("label", role) for role, brief in result.get("briefs", {}).items()]


def _top_claims(result: dict, limit: int = 6) -> list[str]:
    claims = result.get("evidence_map", {}).get("top_claims", [])[:limit]
    output = []
    for claim in claims:
        output.append(f"[{claim.get('source_id','S?')}] {claim.get('claim','No claim')}")
    return output or ["Add live Apify sources or internal notes to strengthen the evidence-backed story."]


def build_demo_checklist(result: dict) -> dict:
    """Machine-readable checklist shown in the result page and saved to Box."""
    box_status = result.get("box_sync_status") or {}
    collector = result.get("collector_status") or {}
    evidence = result.get("evidence_map") or {}
    return {
        "demo_mode_ready": True,
        "live_apify_visible": collector.get("mode") in {"apify_live", "live", "mock", "curated_sample"},
        "box_story_visible": bool(box_status.get("mode")),
        "role_differentiation_visible": len(result.get("briefs", {})) >= 3,
        "judge_pitch_available": "judge" in result.get("briefs", {}) or bool(result.get("judge_pitch_pack")),
        "download_package_available": True,
        "recommended_demo_path": [
            "Start on the homepage and say the one-line pitch.",
            "Run the sample demo or a small live crawl with 1-3 URLs.",
            "Show evidence collection status to explain Apify.",
            "Show Box sync status and the generated project-memory tree.",
            "Compare Engineer, Executive, and Judge briefs.",
            "Open the Hackathon Package panel and use the 3-minute script.",
        ],
        "risk_flags": evidence.get("red_flags", []),
        "evidence_gaps": evidence.get("missing_evidence", []),
    }


def build_submission_readme(result: dict) -> str:
    project = result["project"]
    name = _clean(project.get("project_name"), "RoleBrief AI")
    tagline = _clean(project.get("tagline"), "One project. Many audiences.")
    roles = ", ".join(_selected_role_labels(result))
    sponsor_score = result.get("sponsor_fit", {}).get("total_score", "N/A")
    return dedent(f"""\
    # {name}

    **{tagline}**

    {name} is a role-aware project intelligence layer for Box. It collects external web evidence with Apify, stores the evidence and generated artifacts in a Box project memory, then turns the same evidence into different briefings for different stakeholders.

    ## Problem

    Teams do not only have a documentation problem. They have an audience mismatch problem. Engineers, PMs, executives, sales teams, legal reviewers, and hackathon judges all need different answers from the same project knowledge.

    ## Solution

    {name} creates a structured project memory with:

    {_bullets([
        "raw source snapshots from external URLs and internal notes",
        "role-specific briefs for the selected audiences",
        "an evidence map that exposes claims, gaps, and red flags",
        "a role strategy matrix proving that each audience receives a different output",
        "a judge-ready pitch pack and hackathon submission package",
    ])}

    ## Why Box

    Box is the trusted project memory. The app writes a reviewable artifact tree into Box-style folders:

    ```text
    sources/
    role_briefs/
    submission_package/
    metadata/
    ```

    {_box_status_line(result)}

    ## Why Apify

    Apify is the external evidence layer. It gives the product live web context instead of limiting it to files already uploaded by the user.

    {_apify_status_line(result)}

    ## Why AI

    The AI value is not one generic summary. The AI value is role translation: the same evidence becomes different decisions for different audiences.

    Selected audience outputs: {roles}.

    ## Demo

    1. Create or load a project.
    2. Collect evidence from URLs and notes.
    3. Export generated project memory to Box or local Box-style mirror.
    4. Compare Engineer, Executive, and Judge briefs.
    5. Open the generated hackathon package.

    ## Sponsor Fit Score

    Local sponsor-fit score for the current run: **{sponsor_score}/100**.

    ## Current Prototype Scope

    This hackathon prototype focuses on one project at a time. It intentionally keeps auth, permissions, long-running scheduling, and enterprise admin controls out of scope so the demo remains stable.
    """)


def build_devpost_description(result: dict) -> str:
    project = result["project"]
    name = _clean(project.get("project_name"), "RoleBrief AI")
    return dedent(f"""\
    # Devpost / Luma Submission Draft

    ## Project name
    {name}

    ## One-liner
    One project. Many audiences. RoleBrief AI turns shared project evidence into role-specific briefings for engineers, PMs, executives, sales, legal, and judges.

    ## Inspiration
    Project knowledge is usually written for one audience, then reused badly by everyone else. Engineers need architecture, PMs need scope, executives need strategy, legal needs provenance, and judges need a crisp story. We wanted to make a Box-centered workspace that turns the same evidence into the right version for each role.

    ## What it does
    RoleBrief AI takes a project goal, internal notes, and external URLs. Apify collects web evidence. The app normalizes sources, generates an evidence map, creates role-specific reports, and exports everything into a structured Box project memory.

    ## How we built it
    - Flask web app for the prototype UI.
    - Apify Website Content Crawler path for live external evidence collection, with deterministic mock fallback.
    - Box REST upload path for generated sources, reports, metadata, and submission package, with local fallback.
    - Deterministic role-aware intelligence generator for stable hackathon demos.

    ## Best use of Box
    Box is not just a dump folder. It is the trusted memory layer where raw sources, generated role briefs, manifests, evidence maps, and submission artifacts live together in an auditable structure.

    ## Best use of Apify
    Apify gives the workspace external-world awareness. Instead of only summarizing files already in Box, the system can collect sponsor docs, product pages, competitor pages, and API references before generating the reports.

    ## What makes it different
    Many AI tools summarize documents. RoleBrief AI solves audience mismatch: the same evidence becomes different outputs for different teams.

    ## What is next
    - Box file picker and OAuth/JWT production auth.
    - Scheduled Apify recrawls for updated project intelligence.
    - Custom company roles and approval workflow.
    - Side-by-side role diff view.
    - Source-level citation viewer inside Box.
    """)


def build_three_minute_script(result: dict) -> str:
    name = _clean(result["project"].get("project_name"), "RoleBrief AI")
    return dedent(f"""\
    # 3-Minute Demo Script

    ## 0:00–0:20 — Hook
    "Teams do not only have a documentation problem. They have an audience mismatch problem. The same project means something different to an engineer, a PM, an executive, a legal reviewer, and a judge. {name} solves that."

    ## 0:20–0:45 — Product idea
    "{name} uses Apify to collect live external evidence, stores the evidence and generated artifacts in Box, then uses AI to turn that shared project memory into role-specific briefings. Box is the memory. Apify is the eyes. AI is the translator."

    ## 0:45–1:20 — Input and evidence
    Show the homepage. Point to project goal, external URLs, internal notes, and role selection. Click the sample demo or run a small live crawl.

    Say: "This can run in live Apify mode, but the demo also has a deterministic fallback so the project remains presentable even if a token or network call fails."

    ## 1:20–1:55 — Box memory
    Show Evidence Collection Status and Box Sync Status. Then show the generated folder tree.

    Say: "The output is not just a chat response. It becomes a project memory: sources, role briefs, submission package, and metadata. In live mode, these artifacts are uploaded to Box."

    ## 1:55–2:35 — Role differentiation
    Open Engineer Brief, Executive Brief, and Judge Brief.

    Say: "These are not the same summary with different titles. The engineer gets architecture and data contracts. The executive gets a decision memo. The judge gets sponsor fit, demo choreography, and likely Q&A."

    ## 2:35–2:55 — Sponsor story
    "Box is the trusted project memory. Apify brings in external evidence. AI performs audience-aware translation. All three are necessary for the product story."

    ## 2:55–3:00 — Close
    "One project. Many audiences. That is RoleBrief AI."
    """)


def build_judge_qa(result: dict) -> str:
    return dedent("""\
    # Judge Q&A Cheat Sheet

    ## Q: Why does this need Box instead of a normal database?
    Box is the product surface and trusted memory layer. The generated evidence, reports, manifest, and submission artifacts are stored as shareable, reviewable content instead of disappearing inside a chat session.

    ## Q: Why does this need Apify?
    Apify gives the system external-world awareness. The app can collect live webpages, sponsor docs, API docs, competitor pages, and research sources before generating role-specific reports.

    ## Q: How is this different from Box AI?
    We are not replacing Box AI. Box AI is great at understanding content in Box. RoleBrief AI extends the workflow by collecting external evidence first, storing it as project memory, and generating role-specific decision documents.

    ## Q: Why is this not just a summarizer?
    A summarizer compresses information for one generic reader. RoleBrief AI transforms one evidence base into different outputs for different stakeholders. That is the core product wedge.

    ## Q: What is the first user?
    Hackathon teams, product teams, and engineering teams that already keep project artifacts in Box but need to explain the same project to different audiences.

    ## Q: What would production need?
    Production auth, role permissions, scheduled recrawls, review/approval workflow, citation viewer, and configurable role templates.

    ## Q: What is the biggest risk?
    If the role outputs look too similar, the product loses its differentiation. That is why the prototype includes role profiles, role strategy, evidence map, and judge package artifacts.
    """)


def build_screenshot_checklist(result: dict) -> str:
    return dedent("""\
    # Screenshot Checklist

    Capture these for the final submission page or README:

    1. Homepage with slogan: `One project. Many audiences.`
    2. Input form showing project goal, URLs, notes, and roles.
    3. Evidence Collection Status panel.
    4. Box Sync Status panel or generated Box folder.
    5. Project memory layout tree.
    6. Evidence Health Map.
    7. Engineer Brief open.
    8. Executive Brief open.
    9. Judge Brief open.
    10. Hackathon Package panel.
    11. Downloaded output zip contents.

    Optional live-demo screenshot: the generated folder inside Box with `sources/`, `role_briefs/`, `submission_package/`, and `metadata/`.
    """)


def build_final_roadmap(result: dict) -> str:
    return dedent("""\
    # Roadmap and Product Scope

    ## Hackathon prototype scope
    - One project per run.
    - External URL collection through Apify or deterministic mock fallback.
    - Local Box-style memory plus optional live Box upload.
    - Role-specific Markdown reports.
    - Evidence map, role matrix, judge pitch pack, and submission package.

    ## Immediate next features
    1. Box file picker for selecting existing project folders.
    2. OAuth/JWT/server-to-server Box auth instead of developer tokens.
    3. Scheduled Apify recrawls for watchtower-style updates.
    4. Custom role templates for different companies.
    5. Review/approve workflow before reports become externally shareable.

    ## Things intentionally not built during the hackathon
    - Full enterprise permission model.
    - Multi-tenant database.
    - Slack/Teams bot.
    - Continuous background monitoring.
    - Full RAG retrieval across all company files.

    The hackathon goal is not to build the entire enterprise platform. The goal is to prove the wedge: role-specific project intelligence on top of Box, powered by external evidence from Apify.
    """)


def build_sponsor_story(result: dict) -> str:
    score = result.get("sponsor_fit", {}).get("total_score", "N/A")
    return dedent(f"""\
    # Sponsor Story

    ## One sentence
    Box is the trusted project memory, Apify is the external evidence engine, and AI is the role translator.

    ## Box
    - Stores raw source snapshots.
    - Stores generated role briefs.
    - Stores hackathon package artifacts.
    - Stores manifest and evidence metadata.
    - Makes the output shareable and auditable.

    ## Apify
    - Collects live web evidence.
    - Lets the app ingest sponsor pages, docs, product pages, and external research.
    - Prevents the system from being limited to files the user manually uploaded.

    ## AI
    - Converts one evidence base into role-specific reports.
    - Produces different outputs for engineering, product, executive, sales, legal, and judge audiences.
    - Helps users submit, explain, and defend the project.

    ## Current sponsor-fit score
    {score}/100

    ## Strongest judging line
    "We are not building another document summarizer. We are building an audience-aware project intelligence layer where Box becomes the memory, Apify becomes the eyes, and AI translates the project for every stakeholder."
    """)


def generate_hackathon_package(result: dict) -> dict:
    """Return package markdown artifacts and display metadata."""
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    project_name = _clean(result["project"].get("project_name"), "RoleBrief AI")
    docs = {
        "submission_readme.md": build_submission_readme(result),
        "devpost_luma_submission.md": build_devpost_description(result),
        "three_minute_demo_script.md": build_three_minute_script(result),
        "judge_qa_cheatsheet.md": build_judge_qa(result),
        "sponsor_story.md": build_sponsor_story(result),
        "screenshot_checklist.md": build_screenshot_checklist(result),
        "roadmap_and_scope.md": build_final_roadmap(result),
    }
    checklist = build_demo_checklist(result)
    return {
        "generated_at": generated_at,
        "project_slug": _slug(project_name),
        "one_liner": "One project. Many audiences.",
        "closing_line": "Box is the memory. Apify is the eyes. AI is the translator.",
        "docs": docs,
        "checklist": checklist,
        "top_claims": _top_claims(result),
        "display_cards": [
            {
                "title": "Submission README",
                "path": "submission_package/submission_readme.md",
                "why": "Copy this into the GitHub README or final project page.",
            },
            {
                "title": "3-minute demo script",
                "path": "submission_package/three_minute_demo_script.md",
                "why": "Use this for the live judging presentation.",
            },
            {
                "title": "Sponsor story",
                "path": "submission_package/sponsor_story.md",
                "why": "Explains why Box and Apify are both central.",
            },
            {
                "title": "Judge Q&A",
                "path": "submission_package/judge_qa_cheatsheet.md",
                "why": "Prepare answers for the questions judges are likely to ask.",
            },
        ],
    }
