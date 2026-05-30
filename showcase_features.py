"""Showcase features for RoleBrief AI.

The showcase layer deliberately avoids destabilizing the Box/Apify integrations. It adds
judge-facing product polish: a Box-style task inbox, sponsor rescue cards, and a
showcase readiness score. These artifacts are generated from the same result
object and are saved into the project-memory folder so they can be uploaded to
Box by the existing sync path.
"""

from __future__ import annotations

from datetime import datetime
from textwrap import dedent
import re


ROLE_TASK_TEMPLATES = {
    "engineer": [
        "Confirm the integration boundary between Apify collection, report generation, and Box export.",
        "Prepare a one-slide architecture explanation with fallback behavior and local demo mode.",
        "Verify that generated artifacts are deterministic enough for judging.",
    ],
    "pm": [
        "Trim the MVP story to one user journey: messy project evidence becomes role-specific decisions.",
        "Define the first paid user segment and the success metric for one project workspace.",
        "Keep the roadmap focused on recrawls, role templates, and review workflow.",
    ],
    "executive": [
        "Lead with the audience-mismatch problem instead of the file-summary problem.",
        "Explain why Box owns trusted memory while Apify owns external context.",
        "Frame the product as decision acceleration for cross-functional teams.",
    ],
    "sales": [
        "Use the phrase 'one project, many audiences' as the repeatable customer story.",
        "Prepare objections for 'Box already has AI' and 'why not just use a doc summarizer?'.",
        "Show before/after: messy evidence in, role-ready briefings out.",
    ],
    "legal": [
        "Separate public Apify-collected evidence from private internal notes in every report.",
        "Call out provenance, reviewability, retention, and access control as Box-native strengths.",
        "Check generated demo data for secrets, tokens, credentials, or private links.",
    ],
    "judge": [
        "Open with the problem: teams need different documents from the same project evidence.",
        "Demo the evidence status, Box memory tree, and role differentiation in under three minutes.",
        "End with: Box is the memory, Apify is the eyes, AI is the translator.",
    ],
}

ROLE_LABELS = {
    "engineer": "Engineer",
    "pm": "Product Manager",
    "executive": "Executive",
    "sales": "Sales / GTM",
    "legal": "Legal / Compliance",
    "judge": "Hackathon Judge",
}


def _slug(value: str) -> str:
    value = (value or "item").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbers(items: list[str]) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def _top_evidence_claims(result: dict, limit: int = 6) -> list[str]:
    claims = result.get("evidence_map", {}).get("top_claims", [])[:limit]
    output = []
    for claim in claims:
        output.append(f"[{claim.get('source_id', 'S?')}] {claim.get('claim', 'No claim available')}")
    return output or ["Add at least one external URL and one internal note to create stronger evidence-backed claims."]


def build_task_inbox(result: dict) -> dict:
    """Create role-routed action items that feel like a Box task inbox."""
    project = result.get("project", {})
    roles = list(result.get("briefs", {}).keys()) or project.get("roles", []) or ["judge"]
    evidence = result.get("evidence_map", {})
    gaps = evidence.get("missing_evidence", [])
    red_flags = evidence.get("red_flags", [])
    tasks = []

    priority_seed = 1
    for role in roles:
        label = ROLE_LABELS.get(role, role.title())
        role_tasks = ROLE_TASK_TEMPLATES.get(role, ["Review the generated brief and identify the next decision."])
        for task_text in role_tasks:
            priority = "high" if role in {"judge", "legal"} and priority_seed % 2 == 1 else "normal"
            tasks.append(
                {
                    "id": f"T{len(tasks) + 1:02d}",
                    "role": role,
                    "role_label": label,
                    "priority": priority,
                    "task": task_text,
                    "why": "Keeps the demo focused on role-aware decision making, not generic summarization.",
                    "box_destination": f"task_inbox/{role}_{_slug(task_text)[:42]}.md",
                }
            )
            priority_seed += 1

    if gaps:
        tasks.append(
            {
                "id": f"T{len(tasks) + 1:02d}",
                "role": "judge",
                "role_label": "Hackathon Judge",
                "priority": "high",
                "task": f"Patch evidence gap before presenting: {gaps[0]}",
                "why": "A visible evidence gap weakens the sponsor-native story.",
                "box_destination": "task_inbox/judge_patch_evidence_gap.md",
            }
        )

    if red_flags:
        tasks.append(
            {
                "id": f"T{len(tasks) + 1:02d}",
                "role": "legal",
                "role_label": "Legal / Compliance",
                "priority": "high",
                "task": f"Review possible sensitive content before sharing: {red_flags[0]}",
                "why": "The product must feel enterprise-safe when writing artifacts into Box.",
                "box_destination": "task_inbox/legal_review_red_flag.md",
            }
        )

    return {
        "title": "Box Task Inbox",
        "description": "Generated action items routed to the people who should act on each project insight.",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "task_count": len(tasks),
        "high_priority_count": sum(1 for t in tasks if t["priority"] == "high"),
        "roles": sorted({t["role"] for t in tasks}),
        "tasks": tasks,
    }


def task_inbox_markdown(task_inbox: dict, result: dict) -> str:
    project_name = result.get("project", {}).get("project_name", "RoleBrief AI")
    rows = []
    for task in task_inbox["tasks"]:
        rows.append(
            f"| {task['id']} | {task['role_label']} | {task['priority']} | {task['task']} |"
        )
    return dedent(
        f"""\
        # Box Task Inbox — {project_name}

        **Generated at:** {task_inbox['generated_at']}  
        **Task count:** {task_inbox['task_count']}  
        **High priority:** {task_inbox['high_priority_count']}

        RoleBrief AI does not stop at writing reports. The final showcase layer turns insights into routed next actions, as if the generated Box folder became a lightweight task inbox for the team.

        | ID | Owner role | Priority | Task |
        |---|---|---|---|
        {chr(10).join(rows)}

        ## Evidence claims to keep visible

        {_bullets(_top_evidence_claims(result))}
        """
    )


def role_router_markdown(task_inbox: dict, result: dict) -> str:
    grouped: dict[str, list[dict]] = {}
    for task in task_inbox["tasks"]:
        grouped.setdefault(task["role_label"], []).append(task)

    sections = []
    for label, tasks in grouped.items():
        sections.append(f"## {label}\n\n" + _bullets([f"{t['id']} — {t['task']}" for t in tasks]))

    return dedent(
        f"""\
        # Role Router

        The same project memory creates different action queues for different stakeholders. This is the final showcase layer: it proves the system can route work, not only generate prose.

        {chr(10).join(sections)}
        """
    )


def build_showcase_readiness(result: dict, task_inbox: dict) -> dict:
    collector = result.get("collector_status", {})
    box = result.get("box_sync_status", {})
    evidence = result.get("evidence_map", {})
    briefs = result.get("briefs", {})
    package = result.get("hackathon_package", {})

    checks = [
        {
            "label": "Apify story visible",
            "ok": collector.get("mode") in {"curated_sample", "mock", "apify_live", "live"},
            "why": "Judges can see how external evidence enters the project.",
        },
        {
            "label": "Box memory visible",
            "ok": bool(box.get("mode")),
            "why": "Generated artifacts are organized as a Box-style project memory.",
        },
        {
            "label": "Role differentiation visible",
            "ok": len(briefs) >= 4,
            "why": "The product is about audience-specific outputs, not one summary.",
        },
        {
            "label": "Evidence-backed claims visible",
            "ok": len(evidence.get("top_claims", [])) >= 3,
            "why": "Reports can point back to source IDs.",
        },
        {
            "label": "Hackathon package generated",
            "ok": len(package.get("docs", {})) >= 5,
            "why": "The project can produce its own submission and demo materials.",
        },
        {
            "label": "Task inbox generated",
            "ok": task_inbox.get("task_count", 0) >= 6,
            "why": "The showcase layer adds routed next actions for a more product-like demo.",
        },
    ]

    score = round(sum(1 for c in checks if c["ok"]) / len(checks) * 100)
    risks = []
    if not collector.get("ok", True):
        risks.append("Live evidence collection did not complete; use sample demo mode for judging.")
    if evidence.get("missing_evidence"):
        risks.extend(evidence["missing_evidence"][:2])
    if evidence.get("red_flags"):
        risks.extend(evidence["red_flags"][:2])
    if not risks:
        risks.append("No blocking showcase risk detected in deterministic demo mode.")

    next_actions = [
        "Use the sample demo first, then optionally show live Apify/Box if tokens are stable.",
        "Compare Engineer, Executive, and Judge outputs side-by-side.",
        "Open the Box Task Inbox to show that reports become routed action items.",
        "End with the sponsor line: Box is the memory, Apify is the eyes, AI is the translator.",
    ]

    return {
        "score": score,
        "label": "showcase ready" if score >= 85 else "needs polish",
        "checks": checks,
        "risks": risks,
        "next_actions": next_actions,
    }


def build_rescue_cards(result: dict) -> list[dict]:
    """Short cards for common judge or live-demo failure moments."""
    return [
        {
            "trigger": "Box already has AI. Why is this different?",
            "answer": "Box AI understands content inside Box. RoleBrief AI brings external Apify evidence into the project memory first, then generates role-specific decision documents.",
        },
        {
            "trigger": "Live Apify crawl is slow or blocked.",
            "answer": "Switch to curated sample mode and explain that the pipeline has deterministic fallback so the judging demo remains reliable.",
        },
        {
            "trigger": "The judge asks what is stored in Box.",
            "answer": "Show sources, role_briefs, task_inbox, submission_package, and metadata. The output is a reviewable project memory, not a temporary chat response.",
        },
        {
            "trigger": "The judge asks who would use this.",
            "answer": "Cross-functional project teams: engineering, product, GTM, legal, leadership, and hackathon teams that need different versions of the same project truth.",
        },
    ]


def rescue_cards_markdown(cards: list[dict]) -> str:
    return dedent(
        """\
        # Demo Rescue Cards

        Use these if the live demo or judging conversation turns sideways.

        """
    ) + "\n\n".join(f"## {card['trigger']}\n\n{card['answer']}" for card in cards)


def generate_showcase_features(result: dict) -> dict:
    task_inbox = build_task_inbox(result)
    readiness = build_showcase_readiness(result, task_inbox)
    rescue_cards = build_rescue_cards(result)
    return {
        "task_inbox": task_inbox,
        "task_inbox_markdown": task_inbox_markdown(task_inbox, result),
        "role_router_markdown": role_router_markdown(task_inbox, result),
        "showcase_readiness": readiness,
        "rescue_cards": rescue_cards,
        "rescue_cards_markdown": rescue_cards_markdown(rescue_cards),
    }
