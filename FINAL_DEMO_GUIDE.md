# Final Demo Guide — RoleBrief AI

Use this as the official judging route. Do not improvise unless live APIs are already verified.

## 30-second opening

> Teams do not only have a documentation problem. They have an audience mismatch problem. Engineers, PMs, executives, sales, legal, and judges all need different versions of the same project truth. RoleBrief AI uses Apify to collect external evidence, Box to store the trusted project memory, and Gemini to translate that memory into role-specific decisions.

## Safe demo route

1. Start the app.
2. Open `http://127.0.0.1:5000`.
3. Click **Run sample demo**.
4. Point to **Evidence collection status**.
   - Say: Apify is the live web evidence layer; sample mode keeps judging reliable.
5. Point to **Box source import status**.
   - Say: this is the input side of Box; existing Box files can become evidence sources. Sample mode can skip it for reliability.
6. Point to **Gemini AI generation status**.
   - Say: Gemini is the high-quality role translator built on a deterministic local engine.
7. Point to **Box sync status**.
   - Say: every run produces a Box-style project memory and can upload to real Box with a token.
8. Open **Project memory layout**.
   - Show `sources/`, `role_briefs/`, `task_inbox/`, `submission_package/`, and `metadata/`.
9. Compare these briefs:
   - Engineer Brief: architecture and implementation risk.
   - Executive Brief: business decision memo.
   - Hackathon Judge Brief: pitch, sponsor story, demo flow.
10. Show **Hackathon package**.
   - Say: the product generates the materials needed to submit and explain the project.
11. Show **Final showcase command center**.
   - Say: generated reports become routed tasks with a readiness score.
12. Click **Download full showcase package**.

## Closing line

> Box is the memory. Apify is the eyes. Gemini is the translator.

## Only show live integrations if stable

Live Apify:

- Turn on `USE_REAL_APIFY=true`.
- Add `APIFY_API_TOKEN`.
- Keep `APIFY_MAX_CRAWL_DEPTH=0` and `APIFY_MAX_CRAWL_PAGES=3`.

Live Gemini:

- Turn on `USE_REAL_LLM=true`.
- Add `GEMINI_API_KEY`.
- Keep `GEMINI_MODEL=gemini-2.5-flash` for fast judging output.
- The deterministic local engine and run details are recorded in `metadata/llm_generation.json`.

Live Box read/import:

- Turn on `USE_BOX_READ=true`.
- Add `BOX_DEVELOPER_TOKEN`.
- Set `BOX_SOURCE_FOLDER_ID` to an existing Box folder containing small text-like files.
- Keep `BOX_READ_MAX_FILES` small for judging.

Live Box export:

- Turn on `USE_REAL_BOX=true`.
- Add `BOX_DEVELOPER_TOKEN`.
- Keep sample demo ready as the reliable alternative.

## Judge Q&A answers

**Box already has AI. Why is this different?**

Box AI understands content already inside Box. RoleBrief AI brings external web evidence into the Box project memory first, then translates the combined evidence for different audiences.

**Is this just summarization?**

No. The same evidence becomes different decision artifacts: architecture for engineers, scope for PMs, strategic memo for executives, provenance review for legal, and pitch material for judges. In live mode, Gemini improves those role-specific drafts instead of generating one generic answer.

**Why Apify?**

Because teams need current external context: sponsor docs, product pages, competitor pages, rules, and API docs. Apify is the web evidence collection layer.

**Why Box?**

Because the outputs should not disappear in a chat. They become a structured, auditable project memory that teams can review, share, and govern.
