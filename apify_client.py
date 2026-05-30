"""Apify evidence collection for RoleBrief AI.

Batch 2 adds a real Apify REST integration while keeping the deterministic
mock collector from Batch 1. The rest of the app receives the same normalized
source-object contract either way:

{
    "id": "S1",
    "title": "...",
    "url": "...",
    "source_type": "apify_external_web" | "mock_external_url" | "internal_notes",
    "summary": "...",
    "key_points": ["..."],
}

Why REST instead of the Python package? This project already has a local module
named apify_client.py, which would shadow the official apify-client package.
Using the documented HTTP endpoint keeps the hackathon project simple.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import os
import re
from typing import Any
from urllib.parse import quote, urlparse

import requests


APIFY_SYNC_ENDPOINT = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
DEFAULT_ACTOR_ID = "apify/website-content-crawler"


@dataclass
class CollectorStatus:
    mode: str
    ok: bool
    message: str
    actor_id: str | None = None
    requested_urls: int = 0
    returned_items: int = 0
    normalized_sources: int = 0
    fallback_used: bool = False
    warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = data.get("warnings") or []
        return data


class MockApifyClient:
    """Local, deterministic stand-in for Apify.

    This remains important for hackathon reliability. The UI can still show a
    complete end-to-end demo when the internet, API token, or crawler actor fails.
    """

    def collect_sources(self, urls: list[str], project_goal: str) -> list[dict]:
        sources: list[dict] = []
        for index, raw_url in enumerate(urls, start=1):
            url = normalize_url(raw_url)
            if not url:
                continue
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            title = domain.replace("www.", "").split("/")[0]
            sources.append(
                {
                    "id": f"M{index}",
                    "title": f"External evidence from {title}",
                    "url": url,
                    "source_type": "mock_external_url",
                    "summary": (
                        "Demo fallback source. In live mode, Apify Website Content Crawler "
                        "fetches this URL, extracts clean AI-ready content, and returns "
                        "dataset items that RoleBrief AI normalizes into evidence."
                    ),
                    "key_points": [
                        f"Use this source to support the project goal: {project_goal[:110]}...",
                        "Batch 2 can call the real Apify API when USE_REAL_APIFY=true and APIFY_API_TOKEN is set.",
                        "The report generator treats mock and live sources through the same contract.",
                    ],
                    "extracted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "collector": "mock",
                }
            )
        return sources


class ApifyEvidenceClient:
    """Thin REST client for Apify Website Content Crawler."""

    def __init__(
        self,
        token: str | None = None,
        actor_id: str | None = None,
        max_pages: int | None = None,
        max_depth: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.token = token or os.getenv("APIFY_API_TOKEN", "").strip()
        self.actor_id = actor_id or os.getenv("APIFY_ACTOR_ID", DEFAULT_ACTOR_ID).strip() or DEFAULT_ACTOR_ID
        self.max_pages = max_pages if max_pages is not None else int(os.getenv("APIFY_MAX_CRAWL_PAGES", "3"))
        self.max_depth = max_depth if max_depth is not None else int(os.getenv("APIFY_MAX_CRAWL_DEPTH", "0"))
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else int(os.getenv("APIFY_TIMEOUT_SECONDS", "180"))

    def collect_sources(self, urls: list[str], project_goal: str) -> tuple[list[dict], CollectorStatus]:
        clean_urls = [url for url in (normalize_url(u) for u in urls) if url]
        if not clean_urls:
            return [], CollectorStatus(
                mode="apify_live",
                ok=True,
                message="No external URLs were provided.",
                actor_id=self.actor_id,
                requested_urls=0,
                returned_items=0,
                normalized_sources=0,
            )

        if not self.token:
            fallback = MockApifyClient().collect_sources(clean_urls, project_goal)
            return fallback, CollectorStatus(
                mode="mock_fallback",
                ok=False,
                message="APIFY_API_TOKEN is not set, so RoleBrief AI used deterministic mock evidence.",
                actor_id=self.actor_id,
                requested_urls=len(clean_urls),
                returned_items=0,
                normalized_sources=len(fallback),
                fallback_used=True,
                warnings=["Set USE_REAL_APIFY=true and APIFY_API_TOKEN in .env to run the real crawler."],
            )

        input_payload = self._build_actor_input(clean_urls)
        endpoint = APIFY_SYNC_ENDPOINT.format(actor_id=quote(to_apify_actor_path(self.actor_id), safe="~"))
        try:
            response = requests.post(
                endpoint,
                params={"token": self.token, "format": "json", "clean": "true"},
                json=input_payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=self.timeout_seconds + 25,
            )
            response.raise_for_status()
            items = response.json()
            if isinstance(items, dict):
                # Some actors return wrapped output. Keep the normalizer flexible.
                items = items.get("items") or items.get("data") or []
            if not isinstance(items, list):
                items = []
        except Exception as exc:  # keep demo resilient; exact exception is shown in metadata
            fallback = MockApifyClient().collect_sources(clean_urls, project_goal)
            return fallback, CollectorStatus(
                mode="mock_fallback",
                ok=False,
                message=f"Live Apify crawl failed, so fallback evidence was used: {exc}",
                actor_id=self.actor_id,
                requested_urls=len(clean_urls),
                returned_items=0,
                normalized_sources=len(fallback),
                fallback_used=True,
                warnings=["Check APIFY_API_TOKEN, actor id, internet access, actor pricing/credits, and URL accessibility."],
            )

        sources = normalize_apify_items(items, clean_urls)
        if not sources:
            fallback = MockApifyClient().collect_sources(clean_urls, project_goal)
            return fallback, CollectorStatus(
                mode="mock_fallback",
                ok=False,
                message="Apify returned no usable text items, so fallback evidence was used.",
                actor_id=self.actor_id,
                requested_urls=len(clean_urls),
                returned_items=len(items),
                normalized_sources=len(fallback),
                fallback_used=True,
                warnings=["Try lowering crawl depth, checking robots/access restrictions, or using a documentation URL."],
            )

        return sources, CollectorStatus(
            mode="apify_live",
            ok=True,
            message="Live Apify crawl completed and was normalized into evidence sources.",
            actor_id=self.actor_id,
            requested_urls=len(clean_urls),
            returned_items=len(items),
            normalized_sources=len(sources),
            fallback_used=False,
        )

    def _build_actor_input(self, urls: list[str]) -> dict[str, Any]:
        # These keys are part of the official Website Content Crawler input schema.
        # Extra actors can still be used via APIFY_ACTOR_ID as long as they accept
        # the same startUrls-style input.
        return {
            "startUrls": [{"url": url} for url in urls],
            "maxCrawlDepth": self.max_depth,
            "maxCrawlPages": self.max_pages,
            "useSitemaps": False,
            "respectRobotsTxtFile": True,
        }


def should_use_live_apify(form_value: bool | None = None) -> bool:
    if form_value is not None:
        return bool(form_value)
    return os.getenv("USE_REAL_APIFY", "false").lower() in {"1", "true", "yes", "on"}


def to_apify_actor_path(actor_id: str) -> str:
    """Apify REST paths use username~actorName for named actors."""
    return actor_id.strip().replace("/", "~")


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return ""
    return parsed.geturl()


def normalize_apify_items(items: list[dict], requested_urls: list[str]) -> list[dict]:
    sources: list[dict] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        url = first_present(item, ["url", "loadedUrl", "requestedUrl", "sourceUrl"]) or requested_urls[min(index - 1, len(requested_urls) - 1)]
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        title = (
            first_present(item, ["title", "pageTitle", "name"])
            or metadata.get("title")
            or title_from_url(url)
        )
        markdown = first_present(item, ["markdown", "text", "content", "description", "html"]) or ""
        text = clean_text(strip_html(markdown))
        if not text:
            continue
        summary = summarize_text(text)
        sources.append(
            {
                "id": f"A{len(sources) + 1}",
                "title": title,
                "url": url,
                "source_type": "apify_external_web",
                "summary": summary,
                "key_points": extract_key_points(text),
                "excerpt": text[:1400],
                "extracted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "collector": "apify",
            }
        )
    return sources


def first_present(item: dict, keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")[-1]
    if path:
        return path.replace("-", " ").replace("_", " ").title()
    return (parsed.netloc or "Untitled source").replace("www.", "")


def strip_html(text: str) -> str:
    # The crawler often returns markdown/plain text, but this makes the normalizer
    # tolerate HTML-like actor outputs too.
    return re.sub(r"<[^>]+>", " ", text or "")


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def summarize_text(text: str, limit: int = 520) -> str:
    if len(text) <= limit:
        return text
    boundary = text.rfind(". ", 0, limit)
    if boundary < 180:
        boundary = limit
    return text[:boundary].strip() + "…"


def extract_key_points(text: str, max_points: int = 4) -> list[str]:
    # Prefer concise heading-like markdown lines when available.
    points: list[str] = []
    for line in (text or "").splitlines():
        cleaned = line.strip(" #-*\t")
        if 24 <= len(cleaned) <= 150 and not cleaned.lower().startswith(("http", "image:")):
            points.append(cleaned)
        if len(points) >= max_points:
            return points

    # Fallback to sentence chunks.
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    for sentence in sentences:
        sentence = sentence.strip()
        if 35 <= len(sentence) <= 180:
            points.append(sentence)
        if len(points) >= max_points:
            break
    return points or ["Apify collected this page as external evidence for the role-specific reports."]
