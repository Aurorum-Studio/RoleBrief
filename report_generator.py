"""Role-specific intelligence generation for RoleBrief AI.

This generator focuses on output quality. It stays deterministic so the
hackathon demo is stable, but the sections are now evidence-aware, role-aware,
and presentation-ready. The important product claim is not "AI summarizes
files"; it is "the same evidence becomes different decisions for different
roles."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from textwrap import dedent
import re

from llm_client import create_llm_enhancer, should_use_live_llm


ROLE_LABELS = {
    "engineer": "Engineer Brief",
    "pm": "Product Manager Brief",
    "executive": "Executive Brief",
    "sales": "Sales / GTM Brief",
    "legal": "Legal & Compliance Brief",
    "judge": "Hackathon Judge Brief",
}

ROLE_DESCRIPTIONS = {
    "engineer": "Architecture, API boundaries, data contracts, reliability, and implementation risk.",
    "pm": "User problem, MVP scope, product tradeoffs, roadmap, and success metrics.",
    "executive": "Strategic value, business logic, decision risk, and investment narrative.",
    "sales": "Positioning, customer story, demo narrative, and objection handling.",
    "legal": "Source provenance, privacy, access control, data retention, and auditability.",
    "judge": "Hackathon pitch, sponsor fit, demo choreography, wow factor, and likely judge questions.",
}

DEFAULT_ROLES = ["engineer", "pm", "executive", "sales", "legal", "judge"]

ROLE_PROFILES = {
    "engineer": {
        "primary_question": "Can we build this reliably before the demo and explain the system boundary?",
        "deliverable": "Architecture and implementation brief",
        "cares_about": ["APIs", "data contracts", "fallbacks", "errors", "security", "deployment"],
        "avoid": "Do not sell vague business value without implementation path.",
    },
    "pm": {
        "primary_question": "What problem does this solve, for whom, and what is the smallest winning scope?",
        "deliverable": "MVP scope and product decision brief",
        "cares_about": ["users", "scope", "workflow", "tradeoffs", "success metrics", "roadmap"],
        "avoid": "Do not drown the product story in backend details.",
    },
    "executive": {
        "primary_question": "Why should the company care, and what decision does this enable?",
        "deliverable": "Strategic decision memo",
        "cares_about": ["value", "risk", "market", "cost", "why now", "differentiation"],
        "avoid": "Do not require the reader to understand every technical integration.",
    },
    "sales": {
        "primary_question": "How do we make a buyer or judge want this in two minutes?",
        "deliverable": "Positioning and demo talk track",
        "cares_about": ["pain", "story", "objections", "proof", "differentiation", "demo"],
        "avoid": "Do not use internal implementation vocabulary as the main value proposition.",
    },
    "legal": {
        "primary_question": "Can every generated claim be traced, reviewed, and governed?",
        "deliverable": "Provenance and risk review",
        "cares_about": ["source labels", "permissions", "retention", "privacy", "scraping", "audit"],
        "avoid": "Do not mix public web evidence and private notes without labels.",
    },
    "judge": {
        "primary_question": "Is the idea memorable, sponsor-native, and demoable in three minutes?",
        "deliverable": "Pitch, demo, and Q&A pack",
        "cares_about": ["wow factor", "clarity", "Box usage", "Apify usage", "AI role", "execution"],
        "avoid": "Do not sound like a generic file summarizer or a Box AI clone.",
    },
}


KEYWORD_ALIASES = {
    "box": ["box", "folder", "memory", "content", "storage", "artifact", "shared link"],
    "apify": ["apify", "crawler", "scrape", "web", "external", "website", "url"],
    "ai": ["ai", "llm", "agent", "generate", "summary", "brief", "translate"],
    "role": ["role", "audience", "engineer", "pm", "executive", "sales", "legal", "judge"],
    "risk": ["risk", "security", "privacy", "compliance", "token", "secret", "copyright"],
    "hackathon": ["hackathon", "demo", "judge", "sponsor", "prize", "submission"],
}


def normalize_roles(roles: list[str] | None) -> list[str]:
    selected = [role for role in (roles or DEFAULT_ROLES) if role in ROLE_LABELS]
    return selected or DEFAULT_ROLES


def _clean(text: str, fallback: str = "") -> str:
    text = (text or "").strip()
    return text if text else fallback


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered_list(items: list[str]) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def _source_label(source: dict) -> str:
    sid = source.get("id", "S?")
    title = source.get("title", "Untitled source")
    return f"[{sid}] {title}"


def _all_source_text(source: dict) -> str:
    parts = [
        source.get("title", ""),
        source.get("summary", ""),
        source.get("excerpt", ""),
        " ".join(source.get("key_points") or []),
    ]
    return "\n".join(parts).lower()


def _evidence_refs(sources: list[dict]) -> str:
    if not sources:
        return "- No evidence sources were provided."
    rows = []
    for source in sources:
        stype = source.get("source_type", "unknown")
        rows.append(f"- {_source_label(source)} — `{stype}` — {source.get('summary', 'No summary provided.')}")
    return "\n".join(rows)


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


def build_evidence_map(project: dict, sources: list[dict]) -> dict:
    """Create a compact evidence map used by every role brief."""
    source_types = Counter(source.get("source_type", "unknown") for source in sources)
    collector_types = Counter(source.get("collector", "unknown") for source in sources)

    category_hits = Counter()
    for source in sources:
        text = _all_source_text(source)
        for category, words in KEYWORD_ALIASES.items():
            if any(word in text for word in words):
                category_hits[category] += 1

    claims = []
    for source in sources:
        sid = source.get("id", "S?")
        title = source.get("title", "Untitled source")
        points = source.get("key_points") or []
        if points:
            for point in points[:3]:
                claims.append({"source_id": sid, "title": title, "claim": point})
        elif source.get("summary"):
            claims.append({"source_id": sid, "title": title, "claim": source["summary"][:180]})

    public_sources = [s for s in sources if s.get("source_type") not in {"internal_notes"}]
    internal_sources = [s for s in sources if s.get("source_type") == "internal_notes" or str(s.get("url", "")).startswith("box://")]
    live_web_sources = [s for s in sources if s.get("source_type") == "apify_external_web"]

    missing = []
    if not sources:
        missing.append("No evidence sources are attached; add at least one URL or internal note.")
    if not public_sources:
        missing.append("No external source is visible; Apify will be hard to explain.")
    if not internal_sources:
        missing.append("No internal project note is visible; Box as trusted company memory is weaker.")
    if "risk" not in category_hits:
        missing.append("Add at least one source or note about privacy, security, or governance risk.")
    if "hackathon" not in category_hits:
        missing.append("Add the hackathon rules or sponsor page so the Judge Brief can cite it directly.")

    red_flags = []
    combined = "\n".join(_all_source_text(s) for s in sources)
    for risky in ["api key", "secret", "token", ".env", "password", "private key"]:
        if risky in combined:
            red_flags.append(f"Potential sensitive term detected: `{risky}`. Keep it out of public demo artifacts.")
    if len(sources) > 0 and len(claims) < 3:
        red_flags.append("Evidence is thin; generated reports may sound generic without more source claims.")

    return {
        "source_count": len(sources),
        "source_types": dict(source_types),
        "collector_types": dict(collector_types),
        "category_hits": dict(category_hits),
        "public_source_count": len(public_sources),
        "internal_source_count": len(internal_sources),
        "live_web_source_count": len(live_web_sources),
        "top_claims": claims[:12],
        "missing_evidence": missing,
        "red_flags": red_flags,
    }


def _claims_for_role(role: str, sources: list[dict], evidence_map: dict, limit: int = 5) -> list[str]:
    priorities = {
        "engineer": ["box", "apify", "ai", "risk"],
        "pm": ["role", "hackathon", "ai", "box"],
        "executive": ["role", "box", "hackathon", "ai"],
        "sales": ["role", "hackathon", "ai", "apify"],
        "legal": ["risk", "box", "apify"],
        "judge": ["hackathon", "box", "apify", "ai", "role"],
    }.get(role, [])

    scored: list[tuple[int, str]] = []
    for source in sources:
        text = _all_source_text(source)
        sid = source.get("id", "S?")
        for point in source.get("key_points") or [source.get("summary", "")]:
            if not point:
                continue
            score = 1
            for i, category in enumerate(priorities):
                words = KEYWORD_ALIASES.get(category, [])
                if any(word in text or word in point.lower() for word in words):
                    score += max(1, 5 - i)
            scored.append((score, f"{point} [{sid}]"))
    scored.sort(key=lambda item: item[0], reverse=True)

    seen = set()
    selected = []
    for _, claim in scored:
        normalized = claim.lower()
        if normalized in seen:
            continue
        selected.append(claim)
        seen.add(normalized)
        if len(selected) >= limit:
            break
    return selected or ["No role-specific evidence was found; add targeted sources or notes."]


def build_role_strategy(roles: list[str], evidence_map: dict) -> dict:
    rows = []
    for role in roles:
        profile = ROLE_PROFILES[role]
        rows.append({
            "role": role,
            "label": ROLE_LABELS[role],
            "primary_question": profile["primary_question"],
            "deliverable": profile["deliverable"],
            "cares_about": profile["cares_about"],
            "avoid": profile["avoid"],
        })
    return {
        "strategy": "Generate different decisions, not different wordings of one summary.",
        "roles": rows,
        "evidence_health": {
            "source_count": evidence_map["source_count"],
            "missing_evidence": evidence_map["missing_evidence"],
            "red_flags": evidence_map["red_flags"],
        },
    }


def role_matrix_markdown(role_strategy: dict) -> str:
    header = "| Role | Primary question | Output | Avoid |\n|---|---|---|---|"
    rows = []
    for row in role_strategy["roles"]:
        rows.append(
            f"| {row['label']} | {row['primary_question']} | {row['deliverable']} | {row['avoid']} |"
        )
    return "# Role Differentiation Matrix\n\n" + role_strategy["strategy"] + "\n\n" + header + "\n" + "\n".join(rows) + "\n"


def _project_summary(project: dict) -> dict:
    return {
        "name": _clean(project.get("project_name"), "Untitled Project"),
        "tagline": _clean(project.get("tagline"), "One project. Many audiences."),
        "goal": _clean(project.get("project_goal"), "Create role-specific project briefings from shared evidence."),
        "notes": _clean(project.get("internal_notes"), "No internal notes provided."),
    }


def _evidence_section(role: str, sources: list[dict], evidence_map: dict) -> tuple[str, str]:
    claims = _claims_for_role(role, sources, evidence_map)
    return ("Evidence-backed claims to use", _bullet_list(claims))


def _role_sections(role: str, project: dict, sources: list[dict], evidence_map: dict) -> list[tuple[str, str]]:
    p = _project_summary(project)
    profile = ROLE_PROFILES[role]
    name = p["name"]
    core = (
        f"{name} should be positioned as a role-aware project intelligence layer, not a generic summarizer. "
        "Its defensible move is converting one shared evidence base into different decisions for different audiences."
    )

    if role == "engineer":
        return [
            ("Role lens", f"**Question:** {profile['primary_question']}\n\n**Output:** {profile['deliverable']}."),
            ("Technical interpretation", core + " The engineering version should make system boundaries, failure modes, and integration contracts explicit."),
            ("Reference architecture", _bullet_list([
                "Input layer: project goal, internal notes, role selection, and external URLs.",
                "Apify layer: crawls external pages and normalizes them into source objects with title, URL, type, summary, key points, and excerpt.",
                "Intelligence layer: evidence map + role strategy generate audience-specific Markdown briefs.",
                "Box layer: stores `/sources`, `/role_briefs`, and `/metadata` so the run is inspectable and shareable.",
                "Fallback layer: mock Apify, local Box mirror, and deterministic generation keep the live demo stable even without API keys.",
            ])),
            ("Data contract", _bullet_list([
                "`source.id`: stable evidence reference used inside reports.",
                "`source.source_type`: separates internal notes, Apify web pages, sponsor docs, and curated demo evidence.",
                "`manifest.outputs`: tells Box sync exactly which artifacts should exist.",
                "`evidence_map`: stores claims, source mix, missing evidence, and red flags.",
                "`role_strategy`: stores why each role receives a different report.",
            ])),
            ("Implementation risk and mitigation", _bullet_list([
                "Crawler noise → keep crawl depth low for demo and store raw source snapshots for review.",
                "Generic outputs → generate from role profiles and role-specific evidence filters.",
                "Token failure → local fallback should still produce the full run package.",
                "Box visibility risk → show Box sync status and generated folder tree in the result page.",
            ])),
            _evidence_section(role, sources, evidence_map),
        ]

    if role == "pm":
        return [
            ("Role lens", f"**Question:** {profile['primary_question']}\n\n**Output:** {profile['deliverable']}."),
            ("Product interpretation", core + " The PM framing is the audience mismatch problem: different stakeholders need different versions of project truth."),
            ("Target users and jobs", _bullet_list([
                "Hackathon teams: turn rules, sponsor docs, project notes, and links into a submission package.",
                "Engineering/product teams: onboard stakeholders without forcing everyone through the same technical document.",
                "Cross-functional leaders: preserve a trusted project memory while giving each role the right view.",
            ])),
            ("MVP boundary", _bullet_list([
                "Must have: project input, Apify evidence collection, role brief generation, Box export, downloadable run package.",
                "Should have: role comparison matrix, evidence health, judge pitch pack.",
                "Not now: enterprise permissions, Slack bot, multi-user workspace, production OAuth, long-running monitor jobs.",
            ])),
            ("Roadmap after demo", _numbered_list([
                "Add real Box file picker and persistent project IDs.",
                "Add scheduled Apify recrawls to update the same Box project memory.",
                "Add company role templates and custom audience profiles.",
                "Add review/approval workflow before reports are shared externally.",
            ])),
            ("Success metrics", _bullet_list([
                "A judge understands the product in 30 seconds.",
                "Engineer and Executive briefs are clearly different without manual editing.",
                "The Box folder contains enough artifacts to audit what happened.",
                "The generated Judge Brief is usable as a final pitch outline.",
            ])),
            _evidence_section(role, sources, evidence_map),
        ]

    if role == "executive":
        return [
            ("Role lens", f"**Question:** {profile['primary_question']}\n\n**Output:** {profile['deliverable']}."),
            ("Decision memo", f"{name} converts scattered project evidence into role-specific briefings. The executive value is not more content; it is faster alignment and lower communication loss across technical, product, business, and compliance teams."),
            ("Strategic thesis", _bullet_list([
                "Knowledge work is increasingly cross-functional, but documentation is usually single-audience.",
                "External evidence and internal project context are often split between browser tabs, chats, and file systems.",
                "Box becomes the trusted memory layer; Apify supplies live external evidence; AI turns that evidence into audience-specific decisions.",
                "The product differentiates from generic knowledge bases by optimizing for role-specific consumption, not only retrieval.",
            ])),
            ("Business value", _bullet_list([
                "Shorter stakeholder onboarding.",
                "Less repeated explanation from technical teams.",
                "More auditable research-to-decision trail inside Box.",
                "Better executive visibility without requiring executives to read raw technical docs.",
            ])),
            ("Investment risk", _bullet_list([
                "If positioned as a generic knowledge base, it competes with too many existing tools.",
                "If Apify is invisible, the external intelligence story is weak.",
                "If Box is only described as storage, the enterprise trust story is weak.",
                "If role outputs are too similar, the core differentiation collapses.",
            ])),
            ("Recommendation", "Proceed with a narrow wedge: project-level role briefings for teams that already manage project artifacts in Box and need external web evidence captured with provenance."),
            _evidence_section(role, sources, evidence_map),
        ]

    if role == "sales":
        return [
            ("Role lens", f"**Question:** {profile['primary_question']}\n\n**Output:** {profile['deliverable']}."),
            ("Positioning", f"{name} is an audience-aware project intelligence assistant: one evidence base enters Box, and each team receives the version of the project they can actually act on."),
            ("Customer pain story", "A team has sponsor rules, product docs, competitor pages, internal notes, and technical plans scattered everywhere. The engineer wants APIs, the PM wants scope, the executive wants strategy, the legal reviewer wants provenance, and the judge wants a memorable pitch. RoleBrief AI turns that mess into a shared Box project memory plus role-specific outputs."),
            ("Demo talk track", _numbered_list([
                "Start with the messy project: notes plus URLs.",
                "Show Apify evidence collection or the fallback evidence status.",
                "Show the generated Box memory layout.",
                "Open Engineer vs Executive vs Judge outputs to prove role differentiation.",
                "End on the Judge Brief: this is the pitch pack the team can use immediately.",
            ])),
            ("Objection handling", _bullet_list([
                "`Is this just summarization?` No: the same evidence is transformed into different role-specific decisions and stored as an auditable Box project memory.",
                "`Why Box?` Box is where the trusted sources, reports, manifests, and shareable artifacts live.",
                "`Why Apify?` Apify brings external web evidence into the project instead of limiting the app to already-uploaded files.",
                "`Why now?` Teams already use AI to read documents; the missing layer is audience-aware project packaging.",
            ])),
            _evidence_section(role, sources, evidence_map),
        ]

    if role == "legal":
        return [
            ("Role lens", f"**Question:** {profile['primary_question']}\n\n**Output:** {profile['deliverable']}."),
            ("Governance interpretation", f"{name} should be presented as traceable generation, not autonomous truth. Every report should preserve the source list, internal/external labels, and generated artifact manifest."),
            ("Source provenance controls", _bullet_list([
                "Store raw source snapshots separately from generated briefs.",
                "Keep `source_type` visible so public web pages and private internal notes are not blended silently.",
                "Write `metadata/manifest.json` to record roles, generated files, and run time.",
                "Write `metadata/evidence_map.json` to expose missing evidence and red flags.",
            ])),
            ("Privacy and sharing controls", _bullet_list([
                "Do not put API keys, tokens, `.env` files, or private credentials in demo artifacts.",
                "Use Box permissions intentionally when enabling shared links.",
                "Treat developer tokens as temporary hackathon credentials, not production auth.",
                "For production, add OAuth/JWT auth, access logging, and approval before external sharing.",
            ])),
            ("Review questions", _bullet_list([
                "Which sources are internal vs external?",
                "Can a reviewer trace every important generated claim back to a stored source?",
                "Does Apify crawl only intended URLs and respect the demo scope?",
                "Are generated reports clearly labeled as AI-produced analysis rather than official policy?",
            ])),
            ("Evidence health flags", _bullet_list(evidence_map["red_flags"] or ["No obvious sensitive-term flag detected in current evidence."])),
            _evidence_section(role, sources, evidence_map),
        ]

    if role == "judge":
        return [
            ("30-second pitch", f"{name} solves the audience mismatch problem in project knowledge. Apify pulls live external evidence into the workspace, Box stores the trusted project memory, and AI turns the same evidence into different briefings for engineers, PMs, executives, sales, legal, and judges."),
            ("Why this is not a Box AI clone", _bullet_list([
                "Box AI can understand content already inside Box; RoleBrief AI brings external evidence into Box and packages it by audience.",
                "The differentiator is not a single summary. It is role-specific transformation plus auditable source storage.",
                "The generated Box folder is the product surface: sources, role briefs, evidence map, sponsor-fit metadata, and judge pitch pack.",
            ])),
            ("Sponsor-native architecture", _bullet_list([
                "Apify = external-world ingestion: hackathon rules, docs, competitor pages, sponsor pages, and project references.",
                "Box = trusted project memory: raw evidence, generated role reports, manifests, and shareable artifacts.",
                "AI = role translator: same evidence, different decisions for different audiences.",
            ])),
            ("Three-minute demo choreography", _numbered_list([
                "Show the input screen with a project goal, URLs, and selected roles.",
                "Run the sample or live Apify crawl and point to Evidence Collection Status.",
                "Show Box Sync Status and the project-memory folder layout.",
                "Open Engineer Brief, Executive Brief, and Judge Brief side by side to prove they are not the same summary.",
                "Finish with the Judge Brief Q&A and say: `One project. Many audiences.`",
            ])),
            ("Likely judge Q&A", _bullet_list([
                "Q: Why does this need Box? A: Box is the trusted content system where sources, reports, manifests, and shareable project artifacts live.",
                "Q: Why does this need Apify? A: Apify gives the project eyes on the external web instead of limiting it to uploaded files.",
                "Q: How is this AI? A: AI transforms the evidence into role-specific decisions, not just one generic summary.",
                "Q: What is the first real customer? A: Any team with project docs in Box that also needs external web research turned into stakeholder-specific briefs.",
                "Q: What is next? A: scheduled Apify recrawls, Box file picker, custom company roles, and approval workflow.",
            ])),
            _evidence_section(role, sources, evidence_map),
        ]

    return [("Summary", core), _evidence_section(role, sources, evidence_map)]


def brief_to_markdown(role: str, project: dict, sources: list[dict], sections: list[tuple[str, str]], generated_at: str) -> str:
    project_name = _clean(project.get("project_name"), "Untitled Project")
    goal = _clean(project.get("project_goal"), "No project goal provided.")
    profile = ROLE_PROFILES.get(role, {})
    section_text = "\n\n".join(f"## {title}\n\n{body}" for title, body in sections)
    return dedent(
        f"""\
        # {ROLE_LABELS.get(role, role.title())}: {project_name}

        **Generated at:** {generated_at}  
        **Role focus:** {ROLE_DESCRIPTIONS.get(role, 'Role-specific project briefing.')}  
        **Audience question:** {profile.get('primary_question', 'What does this role need from the project?')}

        ## Project Goal

        {goal}

        {section_text}

        ## Evidence Used

        {_evidence_refs(sources)}

        ## Box Memory Placement

        This brief belongs in `role_briefs/{role}_brief.md`. Raw evidence belongs in `sources/`.
        The evidence map belongs in `metadata/evidence_map.json` and the role strategy belongs in
        `metadata/role_strategy.json`, so the run is reviewable instead of being a black-box summary.
        """
    )


def judge_pitch_pack_markdown(project: dict, evidence_map: dict, generated_at: str) -> str:
    name = _clean(project.get("project_name"), "RoleBrief AI")
    missing = evidence_map["missing_evidence"] or ["Evidence coverage is demo-ready."]
    return dedent(
        f"""\
        # Judge Pitch Pack: {name}

        **Generated at:** {generated_at}

        ## Opening line

        {name} turns one project into many audience-specific briefings: Apify brings in external evidence, Box stores the trusted project memory, and AI translates the same evidence for each stakeholder.

        ## Core problem

        Teams do not only have a documentation problem. They have an audience mismatch problem. Engineers, PMs, executives, sales, legal, and judges all need different answers from the same project evidence.

        ## Why Box

        Box is the source-of-truth layer. The demo writes raw sources, generated reports, evidence maps, sponsor-fit scoring, and run metadata into a structured Box project folder.

        ## Why Apify

        Apify gives the workspace live external context. It can collect sponsor pages, API docs, competitor pages, and research pages so the project is not limited to files the user manually uploaded.

        ## Best demo sequence

        {_numbered_list([
            "Run the sample project to avoid token risk.",
            "Point to Evidence Collection Status and explain Apify live mode.",
            "Point to Box Sync Status and the generated project-memory tree.",
            "Compare Engineer Brief vs Executive Brief vs Judge Brief.",
            "End with the sentence: `One project. Many audiences.`",
        ])}

        ## Evidence health

        {_bullet_list(missing)}
        """
    )


def generate_role_briefs(project: dict, sources: list[dict] | None = None, roles: list[str] | None = None) -> dict:
    sources = sources or project.get("sources") or []
    roles = normalize_roles(roles or project.get("roles"))
    generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    project_name = _clean(project.get("project_name"), "Untitled Project")

    evidence_map = build_evidence_map(project, sources)
    role_strategy = build_role_strategy(roles, evidence_map)
    matrix_markdown = role_matrix_markdown(role_strategy)
    judge_pack = judge_pitch_pack_markdown(project, evidence_map, generated_at)

    use_live_llm = bool(project.get("use_live_llm")) or should_use_live_llm(None)
    llm_enhancer = create_llm_enhancer(use_live_llm)

    briefs = {}
    for role in roles:
        sections = _role_sections(role, project, sources, evidence_map)
        draft_markdown = brief_to_markdown(role, project, sources, sections, generated_at)
        markdown, llm_status = llm_enhancer.enhance(
            role=role,
            role_label=ROLE_LABELS[role],
            role_profile=ROLE_PROFILES[role],
            project=project,
            sources=sources,
            evidence_map=evidence_map,
            draft_markdown=draft_markdown,
        )
        briefs[role] = {
            "role": role,
            "label": ROLE_LABELS[role],
            "description": ROLE_DESCRIPTIONS[role],
            "profile": ROLE_PROFILES[role],
            "sections": sections,
            "markdown": markdown,
            "draft_markdown": draft_markdown,
            "generation_mode": "gemini" if llm_status.get("enhanced") else "deterministic_fallback",
            "llm_status": llm_status,
        }

    llm_generation = llm_enhancer.state.to_dict()

    manifest = {
        "project_name": project_name,
        "generated_at": generated_at,
        "roles": roles,
        "source_count": len(sources),
        "live_apify_source_count": sum(1 for s in sources if s.get("source_type") == "apify_external_web"),
        "outputs": {
            "sources": [f"sources/{s.get('id', 'source')}_{slugify(s.get('title', 'source'))}.md" for s in sources],
            "role_briefs": [f"role_briefs/{role}_brief.md" for role in roles] + [
                "role_briefs/_role_comparison_matrix.md",
                "role_briefs/judge_pitch_pack.md",
            ],
            "metadata": [
                "metadata/manifest.json",
                "metadata/sponsor_fit.json",
                "metadata/evidence_map.json",
                "metadata/role_strategy.json",
                "metadata/llm_generation.json",
            ],
        },
        "sponsor_story": {
            "box": "Trusted project memory for source snapshots, generated briefs, evidence maps, and manifest metadata.",
            "apify": "External evidence collection from live web pages and docs.",
            "ai": "Audience-aware translation into role-specific reports and judge-ready pitch artifacts, with optional Gemini enhancement and deterministic fallback.",
        },
    }

    sponsor_fit = calculate_sponsor_fit(project, sources, roles, evidence_map)

    return {
        "project": project,
        "sources": sources,
        "briefs": briefs,
        "manifest": manifest,
        "sponsor_fit": sponsor_fit,
        "evidence_map": evidence_map,
        "role_strategy": role_strategy,
        "llm_generation": llm_generation,
        "role_matrix_markdown": matrix_markdown,
        "judge_pitch_pack": judge_pack,
    }


def calculate_sponsor_fit(project: dict, sources: list[dict], roles: list[str], evidence_map: dict | None = None) -> dict:
    evidence_map = evidence_map or build_evidence_map(project, sources)
    box_score = 36 if evidence_map.get("internal_source_count", 0) else 31
    live_apify_sources = [s for s in sources if s.get("source_type") == "apify_external_web"]
    mock_sources = [s for s in sources if s.get("source_type") == "mock_external_url"]
    apify_doc_sources = [s for s in sources if "apify" in _all_source_text(s)]
    if live_apify_sources:
        apify_score = 34
        apify_why = "Live Apify crawler output is normalized into evidence sources."
    elif mock_sources or apify_doc_sources:
        apify_score = 28
        apify_why = "The Apify evidence path is visible and mock fallback keeps the demo stable."
    elif sources:
        apify_score = 20
        apify_why = "Sources exist, but live or mock external collection should be shown more clearly."
    else:
        apify_score = 10
        apify_why = "Add external URLs or sample sources to make the Apify story visible."

    role_score = 21 if len(roles) >= 4 else 14
    evidence_score = 9 if evidence_map.get("top_claims") else 4
    total = min(100, box_score + apify_score + role_score + evidence_score)
    return {
        "total_score": total,
        "items": [
            {"label": "Box as trusted project memory", "score": box_score, "why": "Outputs are organized into sources, role briefs, evidence map, role strategy, manifest, and sync metadata."},
            {"label": "Apify as external evidence layer", "score": apify_score, "why": apify_why},
            {"label": "AI as role translator", "score": role_score, "why": "The same evidence is transformed into different audience-specific decisions, not one generic summary."},
            {"label": "Evidence-backed reporting", "score": evidence_score, "why": "Briefs now cite source IDs and include an evidence health map."},
        ],
    }


def source_to_markdown(source: dict) -> str:
    return _source_markdown(source)
