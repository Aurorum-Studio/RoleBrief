"""Curated demo data for RoleBrief AI.

The sample project is intentionally strong enough for a no-token hackathon demo.
It simulates event rules, Box docs, Apify docs, and internal project notes so the
role-specific intelligence layer can show useful outputs even offline.
"""

SAMPLE_PROJECT = {
    "project_name": "RoleBrief AI",
    "tagline": "One project. Many audiences.",
    "project_goal": (
        "Build a Box-centered project intelligence workspace that reads external "
        "web evidence and internal project notes, then generates role-specific "
        "briefings for engineers, PMs, executives, sales, legal/compliance, and "
        "hackathon judges."
    ),
    "internal_notes": (
        "We want the demo to prove three things: Box is the trusted project memory, "
        "Apify is the external research engine, and AI translates the same evidence "
        "into different outputs for different roles. The first hackathon use case is "
        "a team trying to turn messy research, sponsor docs, and notes into a polished "
        "submission package. The MVP should avoid enterprise complexity and focus on "
        "a fast, memorable demo."
    ),
    "external_urls": [
        "https://luma.com/cascadia-ai-hackathon-2026",
        "https://developer.box.com/ai/box-ai-api",
        "https://apify.com/apify/website-content-crawler",
    ],
    "roles": [
        "engineer",
        "pm",
        "executive",
        "sales",
        "legal",
        "judge",
    ],
    "sources": [
        {
            "id": "S1",
            "title": "Hackathon Rules and Sponsor Fit",
            "url": "https://luma.com/cascadia-ai-hackathon-2026",
            "source_type": "event_rules",
            "summary": (
                "The hackathon requires submissions to use Box and at least one of "
                "AWS or Apify. The judging story should make sponsor usage visible, "
                "not merely attached as an afterthought."
            ),
            "key_points": [
                "The demo needs to show Box as a core project memory layer.",
                "Apify should be used for live external evidence collection.",
                "A clear sponsor-fit explanation is part of the winning narrative.",
            ],
        },
        {
            "id": "S2",
            "title": "Box AI and Content Platform Capabilities",
            "url": "https://developer.box.com/ai/box-ai-api",
            "source_type": "box_docs",
            "summary": (
                "Box can serve as the trusted content system where raw evidence, "
                "generated briefs, metadata, and audit-friendly project artifacts are stored."
            ),
            "key_points": [
                "Box is strongest when used as more than a passive file bucket.",
                "Generated reports should be written back into a structured Box folder.",
                "Box's content model supports a project-memory story that is easy for judges to understand.",
            ],
        },
        {
            "id": "S3",
            "title": "Apify Website Content Crawler",
            "url": "https://apify.com/apify/website-content-crawler",
            "source_type": "apify_docs",
            "summary": (
                "Apify can collect web pages and convert them into AI-ready content. "
                "That makes it a natural source acquisition layer for a project intelligence system."
            ),
            "key_points": [
                "Apify is the external-world ingestion engine.",
                "It can turn sponsor pages, docs, competitor pages, and research pages into usable evidence.",
                "This avoids making the app feel like a simple Box AI clone.",
            ],
        },
        {
            "id": "S4",
            "title": "Internal Project Notes",
            "url": "box://project-notes/internal-notes.md",
            "source_type": "internal_notes",
            "summary": (
                "The team wants a high-impact hackathon demo, not a full enterprise platform. "
                "The strongest positioning is role-specific translation of the same project knowledge."
            ),
            "key_points": [
                "Different roles do not need the same report.",
                "The MVP should produce visibly different outputs for each audience.",
                "A stable demo matters more than adding too many integrations early.",
            ],
        },
    ],
}
