# Release Notes — Final Hackathon Release

## Final polish changes

- Renamed the packaged project to `rolebrief_ai_final`.
- Removed cached Python files and generated output runs from the release zip.
- Updated README to remove stale batch-specific paths.
- Added `FINAL_DEMO_GUIDE.md` for judging.
- Added `SUBMISSION_CHEATSHEET.md` for Devpost/Luma-style submissions.
- Added `final_check.py` for final release validation.
- Added `run_demo.sh` and `run_demo.ps1` helper scripts.
- Updated UI copy from batch language to final showcase language.

## What is intentionally not included

- Full authentication system.
- Persistent database.
- Multi-user permission model.
- Heavy RAG infrastructure.
- Background scheduled monitoring.

Those are production roadmap items. This release is optimized for a hackathon: stable demo, clear sponsor story, and strong judge-facing packaging.

## Final recommended mode

Use deterministic sample mode first. Show live Apify or Box only after verifying tokens locally.
