"""Minimal smoke tests for Batch 3.

Run:
    python smoke_test.py

The tests avoid live Apify and live Box calls so they stay deterministic.
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ["USE_REAL_APIFY"] = "false"
os.environ["USE_REAL_BOX"] = "false"
os.environ["BOX_DEVELOPER_TOKEN"] = ""

from app import app, collect_sources  # noqa: E402
from apify_client import MockApifyClient, normalize_apify_items  # noqa: E402
from box_client import BoxRestUploader, LocalBoxMemory  # noqa: E402
from demo_data import SAMPLE_PROJECT  # noqa: E402
from report_generator import generate_role_briefs  # noqa: E402


def test_generator():
    result = generate_role_briefs(SAMPLE_PROJECT, SAMPLE_PROJECT["sources"], SAMPLE_PROJECT["roles"])
    assert "engineer" in result["briefs"]
    assert "judge" in result["briefs"]
    assert result["sponsor_fit"]["total_score"] >= 80
    assert len(result["sources"]) >= 3


def test_mock_apify_client():
    sources = MockApifyClient().collect_sources(["https://example.com/docs"], "demo goal")
    assert len(sources) == 1
    assert sources[0]["source_type"] == "mock_external_url"
    assert sources[0]["collector"] == "mock"


def test_apify_item_normalizer():
    items = [
        {
            "url": "https://example.com/product",
            "title": "Example Product",
            "markdown": "# Example Product\nThis page explains a product for project teams. It has APIs, use cases, and security notes.",
        }
    ]
    sources = normalize_apify_items(items, ["https://example.com/product"])
    assert len(sources) == 1
    assert sources[0]["source_type"] == "apify_external_web"
    assert sources[0]["id"] == "A1"


def test_collect_sources_mock_path():
    project = {
        "external_urls": ["https://example.com/docs"],
        "project_goal": "Test goal",
        "internal_notes": "Internal note for smoke test.",
        "use_live_apify": False,
    }
    sources, status = collect_sources(project)
    assert status["mode"] == "mock"
    assert status["normalized_sources"] == 2
    assert any(s["source_type"] == "internal_notes" for s in sources)


def test_local_box_memory():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        box = LocalBoxMemory(root)
        folder = box.create_project_folder("Smoke Test Project")
        box.write_markdown(folder, "sources/source.md", "# Source")
        box.write_json(folder, "metadata/test.json", {"ok": True})
        assert (folder / "sources/source.md").exists()
        assert (folder / "metadata/test.json").exists()


def test_box_disabled_status():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        local = root / "project-box-memory"
        (local / "metadata").mkdir(parents=True)
        (local / "metadata/manifest.json").write_text('{"ok": true}', encoding="utf-8")
        status = BoxRestUploader(use_live=False).sync_directory(local, "Smoke Project", "abc123").to_dict()
        assert status["mode"] == "local_only"
        assert status["fallback_used"] is True


def test_box_missing_token_status():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        local = root / "project-box-memory"
        (local / "metadata").mkdir(parents=True)
        (local / "metadata/manifest.json").write_text('{"ok": true}', encoding="utf-8")
        status = BoxRestUploader(token="", use_live=True).sync_directory(local, "Smoke Project", "abc123").to_dict()
        assert status["mode"] == "local_fallback"
        assert status["ok"] is False
        assert "BOX_DEVELOPER_TOKEN" in status["message"]


def test_flask_demo_route():
    app.testing = True
    client = app.test_client()
    response = client.get("/demo", follow_redirects=True)
    assert response.status_code == 200
    assert b"Role-specific briefs" in response.data
    assert b"Project memory layout" in response.data
    assert b"Evidence collection status" in response.data
    assert b"Box sync status" in response.data


if __name__ == "__main__":
    test_generator()
    test_mock_apify_client()
    test_apify_item_normalizer()
    test_collect_sources_mock_path()
    test_local_box_memory()
    test_box_disabled_status()
    test_box_missing_token_status()
    test_flask_demo_route()
    print("Smoke tests passed.")
