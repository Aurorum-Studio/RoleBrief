"""Final release checks for RoleBrief AI.

Run:
    python final_check.py

This script avoids live Apify and Box calls. It verifies that the packaged
release is clean, the sample demo route works, and the generated run contains
all judge-facing artifact groups.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def cleanup_transients() -> None:
    """Make final_check idempotent after previous local runs."""
    for cache_dir in ROOT.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir, ignore_errors=True)
    for pyc in ROOT.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    output_root = ROOT / "output_runs"
    output_root.mkdir(exist_ok=True)
    for child in output_root.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    (output_root / ".gitkeep").touch()


def fail(message: str) -> None:
    raise SystemExit(f"Final check failed: {message}")


def require_file(path: str) -> None:
    if not (ROOT / path).exists():
        fail(f"missing required file: {path}")


def run_smoke_test() -> None:
    env = os.environ.copy()
    env["USE_REAL_APIFY"] = "false"
    env["USE_REAL_BOX"] = "false"
    env["USE_BOX_READ"] = "false"
    env["USE_REAL_LLM"] = "false"
    env["BOX_DEVELOPER_TOKEN"] = ""
    env["GEMINI_API_KEY"] = ""
    completed = subprocess.run(
        [sys.executable, "smoke_test.py"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr)
        fail("smoke_test.py failed")
    if "Smoke tests passed." not in completed.stdout:
        fail("smoke test did not print expected success message")


def check_clean_release() -> None:
    forbidden_dirs = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    for path in ROOT.rglob("*"):
        if path.is_dir() and path.name in forbidden_dirs:
            fail(f"forbidden cache directory found: {path.relative_to(ROOT)}")
        if path.suffix == ".pyc":
            fail(f"compiled Python file found: {path.relative_to(ROOT)}")
    generated_runs = [p for p in (ROOT / "output_runs").iterdir() if p.name != ".gitkeep"]
    if generated_runs:
        fail("output_runs should be empty in the release package")


def check_demo_output() -> None:
    os.environ["USE_REAL_APIFY"] = "false"
    os.environ["USE_REAL_BOX"] = "false"
    os.environ["USE_BOX_READ"] = "false"
    os.environ["USE_REAL_LLM"] = "false"
    os.environ["BOX_DEVELOPER_TOKEN"] = ""
    os.environ["GEMINI_API_KEY"] = ""

    from app import app  # imported after env setup

    app.testing = True
    client = app.test_client()
    response = client.get("/demo", follow_redirects=True)
    if response.status_code != 200:
        fail(f"/demo returned HTTP {response.status_code}")
    body = response.data.decode("utf-8", errors="replace")
    required_phrases = [
        "Role-specific briefs",
        "Project memory layout",
        "Evidence collection status",
        "Box sync status",
        "Box source import status",
        "Gemini AI generation status",
        "Hackathon package",
        "Final showcase command center",
        "Download full showcase package",
    ]
    for phrase in required_phrases:
        if phrase not in body:
            fail(f"demo page missing phrase: {phrase}")

    runs = sorted((ROOT / "output_runs").glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not runs:
        fail("demo did not create result.json")
    result = json.loads(runs[0].read_text(encoding="utf-8"))
    for key in ["briefs", "hackathon_package", "showcase_features", "box_sync_status", "box_read_status", "evidence_map", "llm_generation"]:
        if key not in result:
            fail(f"result.json missing key: {key}")
    outputs = result.get("manifest", {}).get("outputs", {})
    for group in ["sources", "role_briefs", "submission_package", "task_inbox", "metadata"]:
        if group not in outputs:
            fail(f"manifest outputs missing group: {group}")


def main() -> None:
    cleanup_transients()
    required = [
        "README.md",
        "FINAL_DEMO_GUIDE.md",
        "SUBMISSION_CHEATSHEET.md",
        "RELEASE_NOTES.md",
        "app.py",
        "apify_client.py",
        "box_client.py",
        "report_generator.py",
        "hackathon_packager.py",
        "showcase_features.py",
        "llm_client.py",
        "smoke_test.py",
        ".env.example",
        "requirements.txt",
        "templates/index.html",
        "templates/result.html",
        "static/style.css",
    ]
    for path in required:
        require_file(path)
    check_clean_release()
    run_smoke_test()
    check_demo_output()
    print("Final release checks passed.")


if __name__ == "__main__":
    main()
