# RoleBrief AI — Batch 3

**One project. Many audiences.**

RoleBrief AI turns messy project context into role-specific project briefs. Batch 3 adds the real Box export layer: after the app generates sources, role briefs, and metadata locally, it can upload the same project-memory tree into a real Box folder.

Core story:

> **Box is the memory. Apify is the eyes. AI is the translator.**

Batch 3 still preserves deterministic fallback behavior. If the Box token is missing or Box upload fails, the local Box-style mirror is still created and downloadable, so the hackathon demo does not break on stage.

---

## Why this is designed for a hackathon

Most AI knowledge-base demos summarize documents. RoleBrief AI makes a sharper claim:

> Companies do not only have a documentation problem. They have an audience mismatch problem.

The same project evidence should become different outputs for different people:

- Engineers need architecture, APIs, implementation risks, and next steps.
- PMs need users, MVP scope, roadmap, and success metrics.
- Executives need strategic value and decision risk.
- Sales teams need positioning, demo story, and objections.
- Legal/compliance teams need provenance, privacy, and auditability.
- Hackathon judges need sponsor fit and a clear demo path.

Batch 3 makes the Box sponsor usage real: every generated source snapshot, role brief, manifest, sponsor-fit file, evidence status file, and Box sync file can be written to a real Box folder.

---

## Batch 3 features

Batch 3 includes everything from Batch 2 plus:

- Real Box REST upload path using `BOX_DEVELOPER_TOKEN`
- Configurable Box parent folder ID
- Automatic Box folder creation per run
- Subfolder creation for:
  - `sources/`
  - `role_briefs/`
  - `metadata/`
- Direct upload of generated Markdown and JSON artifacts
- Optional shared link creation for the generated Box folder
- Result page showing:
  - Box mode
  - created folder count
  - uploaded file count
  - parent folder ID
  - generated Box folder link
  - uploaded artifact list
- `metadata/box_sync.json` saved locally and uploaded when live Box succeeds
- Local mirror fallback when Box upload is disabled or fails
- Updated smoke tests for Box-disabled and Box-missing-token fallback paths

---

## Project structure

```text
rolebrief_ai_batch3/
├── app.py                  # Flask app and routes
├── apify_client.py          # Mock + live Apify REST client
├── box_client.py            # Local mirror + live Box REST uploader
├── report_generator.py      # Role-specific report generator
├── demo_data.py             # Curated sample project and evidence
├── requirements.txt
├── .env.example
├── README.md
├── smoke_test.py
├── templates/
│   ├── index.html
│   └── result.html
├── static/
│   └── style.css
├── sample_data/
│   └── sample_project.json
└── output_runs/             # Created outputs appear here
```

---

## Quick start

### macOS / Linux

```bash
cd rolebrief_ai_batch3
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### Windows PowerShell

```powershell
cd rolebrief_ai_batch3
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Click **Run sample demo** for the cleanest no-token demo.

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

For hackathon demos, keep `APIFY_MAX_CRAWL_PAGES` small. The default depth is `0`, so it only crawls the submitted start URLs instead of recursively crawling a whole site.

---

## Enable live Box export

Edit `.env`:

```env
USE_REAL_BOX=true
BOX_DEVELOPER_TOKEN=your_box_developer_token_here
BOX_PARENT_FOLDER_ID=0
BOX_CREATE_SHARED_LINK=true
BOX_SHARED_LINK_ACCESS=open
BOX_TIMEOUT_SECONDS=90
```

Then restart:

```bash
python app.py
```

You can also leave `USE_REAL_BOX=false` and tick **Upload generated project memory to real Box** in the UI.

### How to get a quick developer token

For hackathon/demo use:

1. Create or open a Box app in the Box Developer Console.
2. Use a developer token for quick testing.
3. Paste it into `.env` as `BOX_DEVELOPER_TOKEN`.
4. Keep `BOX_PARENT_FOLDER_ID=0` to create the generated folder at the root of the token user's Box account, or copy a folder ID from a Box URL and use that as the parent.

Developer tokens are temporary and are not the production auth path. For a production version, replace this with OAuth 2.0 or JWT/server-to-server auth.

---

## Smoke test

```bash
python smoke_test.py
```

Expected output:

```text
Smoke tests passed.
```

The smoke test intentionally does not call the live Apify or Box APIs.

---

## Demo script for Batch 3

### Safe demo path

1. Open the homepage.
2. Say: "RoleBrief AI solves audience mismatch in project documentation."
3. Click **Run sample demo**.
4. Show the evidence collection status panel.
5. Show the Box sync status panel.
6. Show the local project-memory layout:
   - `sources/`
   - `role_briefs/`
   - `metadata/manifest.json`
   - `metadata/evidence_collection.json`
   - `metadata/box_sync.json`
7. Compare Engineer, Executive, and Judge briefs.
8. Click **Download generated Box mirror**.

### Live Box demo path

1. Add `BOX_DEVELOPER_TOKEN` to `.env`.
2. Set `USE_REAL_BOX=true`.
3. Start the app.
4. Click **Run sample demo** or create a custom project.
5. Show that `Box sync status` says `box_live`.
6. Click **Open generated Box folder**.
7. In Box, show the generated subfolders and uploaded Markdown/JSON artifacts.
8. Explain: "Apify gathers external evidence; Box stores the trusted project memory; RoleBrief AI translates it for each role."

---

## What Batch 3 intentionally does not do

To preserve quality, Batch 3 only solves the Box export risk.

It does not include:

- production OAuth/JWT auth flow
- large binary/chunked uploads
- multi-user workspace
- database
- live RAG
- background jobs
- complex agent framework
- LLM report generation

Those are later-batch concerns.

---

## Batch 4 target

Batch 4 should improve the intelligence layer without changing the Box/Apify contracts:

- stronger role-specific prompting
- optional OpenAI/LLM generation
- more distinct Engineer / PM / Executive / Legal / Judge reports
- evidence references inside each generated section
- a sharper Judge Brief for hackathon presentation

---

## Pitch line

> RoleBrief AI turns one messy project folder into role-specific briefings for every stakeholder, using Apify to collect external evidence and Box to store the trusted project memory.
