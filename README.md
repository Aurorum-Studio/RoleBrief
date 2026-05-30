# RoleBrief AI — Final Hackathon Release

**One project. Many audiences.**

RoleBrief AI turns messy project notes and external web evidence into role-specific project intelligence. It collects external evidence with Apify, stores sources and generated artifacts as a Box project memory, and produces different reports for engineers, PMs, executives, sales/GTM, legal/compliance, and hackathon judges.

Core story:

> **Box is the memory. Apify is the eyes. AI is the translator.**

The project is intentionally built for a hackathon demo: it has a stable no-token sample mode, optional live Apify crawling, optional live Box export, and generated judging/submission materials.

---

## Why this is not just another summarizer

Most AI knowledge-base demos summarize documents. RoleBrief AI makes a sharper claim:

> Teams do not only have a documentation problem. They have an audience mismatch problem.

The same project evidence should become different outputs for different people:

- **Engineers** need architecture, APIs, data contracts, fallbacks, and implementation risks.
- **PMs** need users, MVP scope, tradeoffs, roadmap, and success metrics.
- **Executives** need strategic value, decision risk, and business leverage.
- **Sales/GTM** needs positioning, demo narrative, and objection handling.
- **Legal/compliance** needs provenance, privacy, access control, and auditability.
- **Judges** need sponsor fit, demo clarity, and a memorable pitch.

---

## What the final release includes

- Flask web app with a polished local demo flow
- Deterministic sample demo that does not need API keys
- Optional live Apify Website Content Crawler integration
- Optional Box source-folder import and live Box REST upload integration
- Optional Gemini role-brief enhancement with deterministic fallback
- Existing Box folder files can be imported as input evidence
- Local Box-style project-memory mirror for every run
- Role-specific markdown reports
- Evidence map and source IDs
- Sponsor-fit scoring
- Hackathon submission package generator
- Box Task Inbox and role router showcase layer
- Demo rescue cards for live judging
- Smoke tests and final readiness checks

Generated project memory:

```text
project-box-memory/
├── sources/
├── role_briefs/
│   ├── engineer_brief.md
│   ├── pm_brief.md
│   ├── executive_brief.md
│   ├── sales_brief.md
│   ├── legal_brief.md
│   ├── judge_brief.md
│   ├── _role_comparison_matrix.md
│   └── judge_pitch_pack.md
├── task_inbox/
│   ├── 00_box_task_inbox.md
│   ├── 01_role_router.md
│   └── 02_demo_rescue_cards.md
├── submission_package/
│   ├── submission_readme.md
│   ├── devpost_luma_submission.md
│   ├── three_minute_demo_script.md
│   ├── judge_qa_cheatsheet.md
│   ├── sponsor_story.md
│   ├── screenshot_checklist.md
│   └── roadmap_and_scope.md
└── metadata/
    ├── manifest.json
    ├── sponsor_fit.json
    ├── evidence_map.json
    ├── role_strategy.json
    ├── llm_generation.json
    ├── box_read.json
    ├── evidence_collection.json
    ├── demo_checklist.json
    ├── task_router.json
    ├── showcase_readiness.json
    ├── rescue_cards.json
    └── box_sync.json
```

---

## Project structure

```text
rolebrief_ai_final/
├── app.py                    # Flask app and routes
├── apify_client.py            # Mock + live Apify REST client
├── box_client.py              # Local mirror + live Box REST uploader
├── report_generator.py        # Role-aware evidence engine
├── llm_client.py              # Optional Gemini enhancement layer
├── hackathon_packager.py      # Submission/demo package generator
├── showcase_features.py       # Task inbox, readiness score, rescue cards
├── demo_data.py               # Curated sample project and evidence
├── final_check.py             # Final release validation script
├── run_demo.sh                # macOS/Linux helper
├── run_demo.ps1               # Windows PowerShell helper
├── requirements.txt
├── .env.example
├── FINAL_DEMO_GUIDE.md
├── SUBMISSION_CHEATSHEET.md
├── RELEASE_NOTES.md
├── smoke_test.py
├── templates/
├── static/
├── sample_data/
└── output_runs/               # Generated outputs appear here
```

---

## Quick start

### macOS / Linux

```bash
cd rolebrief_ai_final
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Or use the helper:

```bash
bash run_demo.sh
```

### Windows PowerShell

```powershell
cd rolebrief_ai_final
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Or use the helper:

```powershell
.\run_demo.ps1
```

Open:

```text
http://127.0.0.1:5000
```

Click **Run sample demo** for the safest judging path.

---

## Enable live Apify crawling

Edit `.env`:

```env
USE_REAL_APIFY=true
APIFY_API_TOKEN=your_apify_token_here
APIFY_ACTOR_ID=apify/website-content-crawler
APIFY_MAX_CRAWL_PAGES=3
APIFY_MAX_CRAWL_DEPTH=0
APIFY_TIMEOUT_SECONDS=180
```

For a live demo, keep crawl scope small. A depth of `0` only crawls the submitted start URLs.

---

## Enable Gemini role-brief enhancement

Edit `.env`:

```env
USE_REAL_LLM=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.35
GEMINI_MAX_OUTPUT_TOKENS=2600
```

How it works:

1. The local deterministic role engine still creates a structured draft first.
2. Gemini receives the draft plus source summaries, source IDs, and the evidence map.
3. Gemini rewrites each selected role brief into a more natural, role-specific report.
4. If Gemini is unavailable, the app keeps the deterministic draft and records the fallback in `metadata/llm_generation.json`.

This is the recommended high-quality mode for judging, but keep the sample fallback ready.

---

## Enable Box source import

This is the input side of Box. It lets existing Box files become source evidence before Gemini generates the role-specific reports.

Edit `.env`:

```env
USE_BOX_READ=true
BOX_DEVELOPER_TOKEN=your_box_developer_token_here
BOX_SOURCE_FOLDER_ID=your_existing_box_folder_id
BOX_READ_RECURSIVE=false
BOX_READ_MAX_FILES=8
BOX_READ_MAX_BYTES=120000
```

Supported text-like files are controlled by:

```env
BOX_READ_ALLOWED_EXTENSIONS=.md,.txt,.json,.csv,.py,.js,.ts,.html,.css,.yml,.yaml,.xml
```

For the demo, keep `BOX_READ_MAX_FILES` small. The app imports Box files as evidence sources with IDs like `[B1]`, then Gemini can cite those IDs in role briefs.

---

## Enable live Box export

This is the output side of Box. It writes generated project-memory artifacts back into Box.

Edit `.env`:

```env
USE_REAL_BOX=true
BOX_DEVELOPER_TOKEN=your_box_developer_token_here
BOX_PARENT_FOLDER_ID=0
BOX_CREATE_SHARED_LINK=true
BOX_SHARED_LINK_ACCESS=open
BOX_TIMEOUT_SECONDS=90
```

`BOX_PARENT_FOLDER_ID=0` writes to the root of the token user's Box account. For a production version, replace developer tokens with OAuth 2.0 or server-to-server auth.

---

## Validation

Run the deterministic smoke test:

```bash
python smoke_test.py
```

Run the final release check:

```bash
python final_check.py
```

Expected output includes:

```text
Smoke tests passed.
Final release checks passed.
```

The tests intentionally avoid live Apify and live Box calls.

---

## Recommended 3-minute judging demo

1. Open the homepage.
2. Say: “Teams do not only have a documentation problem. They have an audience mismatch problem.”
3. Click **Run sample demo**.
4. Show **Evidence collection status** and explain Apify.
5. Show **Box source import status** if reading an existing Box folder, or explain that sample mode skips Box input.
6. Show **Gemini AI generation status**. If Gemini is enabled, show enhanced roles; if not, explain deterministic fallback.
7. Show **Box sync status** and the generated project-memory tree.
8. Show **Hackathon package**.
9. Show **Final showcase command center**.
10. Compare Engineer, Executive, and Judge briefs.
11. Download the full showcase package.
12. Close with: “Box is the memory. Apify is the eyes. Gemini is the translator.”

---

## Judge-facing positioning

- **Not a Box AI clone:** Box AI understands content in Box; RoleBrief AI brings external web evidence into Box and packages it by audience.
- **Not a generic summarizer:** each role receives different decisions, not the same summary with different headings.
- **Box is core:** the output is a structured, auditable project memory.
- **Apify is core:** the app can collect live external evidence instead of only using uploaded files.
- **AI is core:** Gemini can enhance the structured local drafts into higher-quality role-specific decisions, while deterministic fallback preserves demo reliability.

---

## Safe demo fallback

The sample demo works without tokens. Even if live Apify, Gemini, or Box fails, the app still writes a local project-memory folder and shows a complete generated package.

Use live integrations only after verifying your tokens before judging.
