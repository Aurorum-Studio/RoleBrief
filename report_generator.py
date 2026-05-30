"""Role-specific report generation for RoleBrief AI.

The generator is deliberately deterministic in Batch 1. This makes the demo
stable and reviewable. Batch 4 can swap selected sections to LLM-generated text
while preserving the same data contracts.
"""

from __future__ import annotations

from datetime import datetime
from textwrap import dedent
import re


ROLE_LABELS = {
    "engineer": "Engineer Brief",
    "pm": "Product Manager Brief",
    "executive": "Executive Brief",
    "sales": "Sales / GTM Brief",
    "legal": "Legal & Compliance Brief",
    "judge": "Hackathon Judge Brief",
}

ROLE_DESCRIPTIONS = {
    "engineer": "Architecture, implementation boundaries, APIs, reliability, and technical risk.",
    "pm": "User problem, MVP scope, roadmap, success metrics, and tradeoffs.",
    "executive": "Strategic value, market logic, business risk, and decision-making summary.",
    "sales": "Positioning, customer story, demo narrative, and objection handling.",
    "legal": "Source provenance, privacy, data retention, scraping risk, and auditability.",
    "judge": "Hackathon pitch, sponsor fit, demo path, wow factor, and likely judge questions.",
}

DEFAULT_ROLES = ["engineer", "pm", "executive", "sales", "legal", "judge"]


def normalize_roles(roles: list[str] | None) -> list[str]:
    selected = [role for role in (roles or DEFAULT_ROLES) if role in ROLE_LABELS]
    return selected or DEFAULT_ROLES


def _clean(text: str, fallback: str = "") -> str:
    text = (text or "").strip()
    return text if text else fallback


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _evidence_refs(sources: list[dict]) -> str:
    if not sources:
        return "- No evidence sources were provided."
    return "\n".join(f"- [{s['id']}] {s['title']} — {s.get('summary', '')}" for s in sources)


def _source_markdown(source: dict) -> str:
    points = source.get("key_points") or []
    return dedent(
        f"""\
        # {source.get('title', 'Untitled source')}

        **Source ID:** {source.get('id', 'N/A')}  
        **URL:** {source.get('url', 'N/A')}  
        **Type:** {source.get('source_type', 'unknown')}  
        **Collector:** {source.get('collector', 'unknown')}  
        **Extracted at:** {source.get('extracted_at', 'N/A')}

        ## Summary

        {source.get('summary', 'No summary provided.')}

        ## Key Points

        {_bullet_list(points) if points else '- No key points provided.'}

        ## Excerpt

        {source.get('excerpt', 'No excerpt stored for this source.')}
        """
    )


def _project_context(project: dict, sources: list[dict]) -> dict:
    goal = _clean(project.get("project_goal"), "Create role-specific project briefings from shared evidence.")
    notes = _clean(project.get("internal_notes"), "No internal notes provided.")
    source_titles = [s.get("title", "Untitled source") for s in sources]
    sponsor_story = (
        "Box is the trusted project memory where sources, generated briefs, and metadata are archived. "
        "Apify is the external evidence collector that gives the workspace live web context."
    )
    return {
        "goal": goal,
        "notes": notes,
        "source_titles": source_titles,
        "sponsor_story": sponsor_story,
    }


def _role_sections(role: str, project: dict, sources: list[dict]) -> list[tuple[str, str]]:
    ctx = _project_context(project, sources)
    name = project.get("project_name", "Untitled Project")

    shared_problem = (
        f"{name} is not trying to create another generic document summarizer. "
        "The sharper problem is audience mismatch: the same project evidence needs "
        "to become different briefings for different teams."
    )

    if role == "engineer":
        return [
            ("Technical Interpretation", shared_problem + " For engineering, the app should expose a clean data flow: external URLs and project notes become normalized evidence, evidence becomes role prompts, and role briefs become Box-stored artifacts."),
            ("Suggested Architecture", _bullet_list([
                "Flask web app for the Batch 1 demo and simple deployment path.",
                "Apify ingestion boundary: collect external pages and convert them into source objects.",
                "Report generator boundary: turn normalized evidence into audience-specific Markdown.",
                "Box memory boundary: write /sources, /role_briefs, and /metadata outputs.",
                "Local demo mode remains available even when external API keys are missing.",
            ])),
            ("Implementation Risks", _bullet_list([
                "Crawler output can be noisy, so source summaries should be short and evidence-linked.",
                "Reports must differ by role; otherwise the project feels like a generic summarizer.",
                "The Box integration must be visible in the UI, not hidden inside backend logs.",
            ])),
            ("Next Engineering Moves", _bullet_list([
                "Batch 2: replace mock sources with real Apify Website Content Crawler output.",
                "Batch 3: replace local Box mirror with real Box folder creation and file upload.",
                "Batch 4: upgrade deterministic report sections with LLM-generated role reasoning.",
            ])),
        ]

    if role == "pm":
        return [
            ("Product Interpretation", shared_problem + " The MVP should be framed as a role-aware project intelligence tool, not a full company knowledge base."),
            ("Target Users", _bullet_list([
                "Hackathon teams turning messy research into a polished submission.",
                "Product teams onboarding stakeholders to a new project.",
                "Cross-functional teams that need different versions of the same evidence.",
            ])),
            ("MVP Scope", _bullet_list([
                "Create project workspace.",
                "Collect external sources through Apify.",
                "Combine source evidence with internal notes.",
                "Generate role-specific briefs.",
                "Export every artifact to Box as the project memory.",
            ])),
            ("Success Metrics", _bullet_list([
                "A judge can understand the product in under 30 seconds.",
                "Each role report has visibly different priorities.",
                "The demo proves Box and Apify are both essential.",
                "The output is useful enough to copy into a real README or pitch script.",
            ])),
        ]

    if role == "executive":
        return [
            ("Executive Summary", f"{name} turns fragmented project information into decision-ready briefings. The value is not just faster summarization; it is reducing communication loss between technical, product, business, and compliance audiences."),
            ("Strategic Value", _bullet_list([
                "Shortens onboarding time for new stakeholders.",
                "Improves alignment by giving each role the version of knowledge it actually needs.",
                "Creates an auditable project memory in Box rather than leaving research scattered across tabs and chats.",
                "Differentiates from generic knowledge bases through role-aware output generation.",
            ])),
            ("Why Now", "Teams increasingly rely on external web evidence, sponsor docs, API docs, competitor pages, and internal notes at the same time. The bottleneck is no longer access to information; it is converting mixed evidence into role-specific action."),
            ("Decision Risks", _bullet_list([
                "If positioned too broadly, it will sound like another enterprise knowledge base.",
                "If Box is only used for storage, the sponsor story weakens.",
                "If Apify is only a hidden crawler, the agent story weakens.",
            ])),
        ]

    if role == "sales":
        return [
            ("Positioning", f"{name} is a project intelligence assistant that creates different briefings for different stakeholders from the same evidence base."),
            ("Customer Story", "A team starts with scattered links, notes, docs, and sponsor requirements. Instead of forcing everyone to read the same long document, RoleBrief AI creates an engineer view, PM view, executive view, sales view, legal view, and judge view, then archives them in Box."),
            ("Demo Script Angle", _bullet_list([
                "Show a messy project input.",
                "Show Apify-style evidence collection.",
                "Show very different role briefs.",
                "Show the Box memory output layout.",
                "End with the judge brief as the hackathon punchline.",
            ])),
            ("Likely Objections", _bullet_list([
                "Isn't this just a summarizer? → No, the core is role-specific translation and project-memory packaging.",
                "Why Box? → Box is the trusted memory and shareable artifact layer.",
                "Why Apify? → Apify brings external web evidence into the system.",
            ])),
        ]

    if role == "legal":
        return [
            ("Compliance Interpretation", f"{name} should emphasize traceability: every generated claim should connect back to stored sources, internal notes, or explicit assumptions."),
            ("Data & Source Risks", _bullet_list([
                "External URLs may contain copyrighted, stale, or terms-restricted content.",
                "Generated reports should preserve source references instead of pretending all conclusions are original.",
                "Internal notes may include confidential information and should be stored with clear access controls in the real Box integration.",
                "The system should avoid silently mixing public and private sources without labels.",
            ])),
            ("Recommended Controls", _bullet_list([
                "Store raw source snapshots separately from generated reports.",
                "Label each source as external, internal, sponsor, competitor, or user-provided.",
                "Include a manifest that records run time, input URLs, roles, and generated files.",
                "For Batch 3, use Box permissions and shared links intentionally rather than defaulting everything public.",
            ])),
            ("Audit-Friendly Output", "The local Box mirror already separates /sources, /role_briefs, and /metadata. In the real Box version, the same structure becomes an auditable workspace."),
        ]

    if role == "judge":
        return [
            ("One-Sentence Pitch", f"{name} turns one messy project folder into role-specific briefings for every stakeholder, using Apify to collect external evidence and Box to store the trusted project memory."),
            ("Why This Wins", _bullet_list([
                "It avoids being a generic Box AI clone by focusing on external evidence plus audience-aware transformation.",
                "It makes sponsor usage visible: Apify collects; Box remembers; AI translates.",
                "The demo is simple: input project context, generate multiple role views, export to Box.",
                "The output is immediately useful to hackathon teams and also believable for companies.",
            ])),
            ("Three-Minute Demo Flow", _bullet_list([
                "Minute 1: Show messy project inputs and source URLs.",
                "Minute 2: Generate role-specific briefs and compare Engineer vs Executive vs Judge outputs.",
                "Minute 3: Show the Box-style project memory and explain the sponsor architecture.",
            ])),
            ("Likely Judge Questions", _bullet_list([
                "How is this different from a normal summarizer?",
                "Why does this need Box?",
                "Why does this need Apify?",
                "What would be required to deploy this inside a real company?",
                "How do you prevent hallucinated or unsupported claims?",
            ])),
        ]

    return [("Summary", shared_problem)]


def generate_role_briefs(project: dict, sources: list[dict] | None = None, roles: list[str] | None = None) -> dict:
    sources = sources or project.get("sources") or []
    roles = normalize_roles(roles or project.get("roles"))
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    project_name = _clean(project.get("project_name"), "Untitled Project")

    briefs = {}
    for role in roles:
        sections = _role_sections(role, project, sources)
        markdown = brief_to_markdown(role, project, sources, sections, generated_at)
        briefs[role] = {
            "role": role,
            "label": ROLE_LABELS[role],
            "description": ROLE_DESCRIPTIONS[role],
            "sections": sections,
            "markdown": markdown,
        }

    manifest = {
        "project_name": project_name,
        "generated_at": generated_at,
        "roles": roles,
        "source_count": len(sources),
        "live_apify_source_count": sum(1 for s in sources if s.get("source_type") == "apify_external_web"),
        "outputs": {
            "sources": [f"sources/{s.get('id', 'source')}_{slugify(s.get('title', 'source'))}.md" for s in sources],
            "role_briefs": [f"role_briefs/{role}_brief.md" for role in roles],
            "metadata": ["metadata/manifest.json", "metadata/sponsor_fit.json"],
        },
        "sponsor_story": {
            "box": "Trusted project memory for source snapshots, generated briefs, and manifest metadata.",
            "apify": "External evidence collection from live web pages and docs.",
            "ai": "Audience-aware translation into role-specific reports.",
        },
    }

    sponsor_fit = calculate_sponsor_fit(project, sources, roles)

    return {
        "project": project,
        "sources": sources,
        "briefs": briefs,
        "manifest": manifest,
        "sponsor_fit": sponsor_fit,
    }


def calculate_sponsor_fit(project: dict, sources: list[dict], roles: list[str]) -> dict:
    box_score = 35
    live_apify_sources = [s for s in sources if s.get("source_type") == "apify_external_web"]
    mock_sources = [s for s in sources if s.get("source_type") == "mock_external_url"]
    if live_apify_sources:
        apify_score = 35
        apify_why = "Live Apify crawler output is normalized into evidence sources."
    elif mock_sources:
        apify_score = 26
        apify_why = "The Apify integration path is visible and mock fallback keeps the demo stable."
    elif sources:
        apify_score = 18
        apify_why = "Sources exist, but external web collection should be shown more clearly."
    else:
        apify_score = 10
        apify_why = "Add external URLs or sample sources to make the Apify story visible."
    ai_score = 20 if len(roles) >= 3 else 12
    demo_score = 10 if "judge" in roles else 7
    total = min(100, box_score + apify_score + ai_score + demo_score)
    return {
        "total_score": total,
        "items": [
            {"label": "Box as project memory", "score": box_score, "why": "Outputs are organized into sources, role briefs, manifest, and evidence-collection metadata."},
            {"label": "Apify as external evidence layer", "score": apify_score, "why": apify_why},
            {"label": "AI as role translator", "score": ai_score, "why": "The same evidence is transformed into different audience-specific briefs."},
            {"label": "Hackathon demo clarity", "score": demo_score, "why": "Judge Brief explains the product, sponsor fit, and demo path."},
        ],
    }


def brief_to_markdown(role: str, project: dict, sources: list[dict], sections: list[tuple[str, str]], generated_at: str) -> str:
    project_name = _clean(project.get("project_name"), "Untitled Project")
    goal = _clean(project.get("project_goal"), "No project goal provided.")
    section_text = "\n\n".join(f"## {title}\n\n{body}" for title, body in sections)
    return dedent(
        f"""\
        # {ROLE_LABELS.get(role, role.title())}: {project_name}

        **Generated at:** {generated_at}  
        **Role focus:** {ROLE_DESCRIPTIONS.get(role, 'Role-specific project briefing.')}

        ## Project Goal

        {goal}

        {section_text}

        ## Evidence Used

        {_evidence_refs(sources)}

        ## Box Memory Placement

        This brief belongs in `role_briefs/{role}_brief.md`. Raw evidence belongs in `sources/`.
        A manifest should be stored in `metadata/manifest.json` so the run is auditable.
        """
    )


def source_to_markdown(source: dict) -> str:
    return _source_markdown(source)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"
