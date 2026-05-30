# Final Demo Guide — RoleBrief AI

Use this as the official judging route. Do not improvise unless live APIs are already verified.

## 30-second opening

> Teams do not only have a documentation problem. They have an audience mismatch problem. Engineers, PMs, executives, sales, legal, and judges all need different versions of the same project truth. RoleBrief AI uses Apify to collect external evidence, Box to store the trusted project memory, and AI to translate that memory into role-specific decisions.

## Safe demo route

1. Start the app.
2. Open `http://127.0.0.1:5000`.
3. Click **Run sample demo**.
4. Point to **Evidence collection status**.
   - Say: Apify is the live web evidence layer; sample mode keeps judging reliable.
5. Point to **Box sync status**.
   - Say: every run produces a Box-style project memory and can upload to real Box with a token.
6. Open **Project memory layout**.
   - Show `sources/`, `role_briefs/`, `task_inbox/`, `submission_package/`, and `metadata/`.
7. Compare these briefs:
   - Engineer Brief: architecture and implementation risk.
   - Executive Brief: business decision memo.
   - Hackathon Judge Brief: pitch, sponsor story, demo flow.
8. Show **Hackathon package**.
   - Say: the product generates the materials needed to submit and explain the project.
9. Show **Final showcase command center**.
   - Say: generated reports become routed tasks and demo rescue cards.
10. Click **Download full showcase package**.

## Closing line

> Box is the memory. Apify is the eyes. AI is the translator.

## Only show live integrations if stable

Live Apify:

- Turn on `USE_REAL_APIFY=true`.
- Add `APIFY_API_TOKEN`.
- Keep `APIFY_MAX_CRAWL_DEPTH=0` and `APIFY_MAX_CRAWL_PAGES=3`.

Live Box:

- Turn on `USE_REAL_BOX=true`.
- Add `BOX_DEVELOPER_TOKEN`.
- Keep sample demo ready as fallback.

## Rescue answers

**Box already has AI. Why is this different?**

Box AI understands content already inside Box. RoleBrief AI brings external web evidence into the Box project memory first, then translates the combined evidence for different audiences.

**Is this just summarization?**

No. The same evidence becomes different decision artifacts: architecture for engineers, scope for PMs, strategic memo for executives, provenance review for legal, and pitch material for judges.

**Why Apify?**

Because teams need current external context: sponsor docs, product pages, competitor pages, rules, and API docs. Apify is the web evidence collection layer.

**Why Box?**

Because the outputs should not disappear in a chat. They become a structured, auditable project memory that teams can review, share, and govern.
