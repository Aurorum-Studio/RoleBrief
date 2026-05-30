"""Box client boundary for RoleBrief AI.

This module provides a real Box upload path while preserving the local mirror. The local mirror is always written first; if live Box is enabled,
the same folder tree is then synced to Box.

The live path uses Box's REST APIs with a developer token because that is the
fastest hackathon setup. For production, replace the developer-token auth with
OAuth 2.0 or JWT/server-to-server auth.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import mimetypes
import os
import re

import requests


BOX_API_BASE = "https://api.box.com/2.0"
BOX_UPLOAD_BASE = "https://upload.box.com/api/2.0"


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "project"


class LocalBoxMemory:
    """Local filesystem mirror of the intended Box project-memory layout."""

    def __init__(self, root: Path):
        self.root = root

    def create_project_folder(self, project_name: str) -> Path:
        folder = self.root / f"{slugify(project_name)}-box-memory"
        (folder / "sources").mkdir(parents=True, exist_ok=True)
        (folder / "role_briefs").mkdir(parents=True, exist_ok=True)
        (folder / "metadata").mkdir(parents=True, exist_ok=True)
        return folder

    def write_markdown(self, folder: Path, relative_path: str, content: str) -> Path:
        path = folder / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, folder: Path, relative_path: str, data: dict) -> Path:
        path = folder / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path


@dataclass
class BoxSyncStatus:
    mode: str
    ok: bool
    message: str
    root_folder_id: str | None = None
    root_folder_name: str | None = None
    root_folder_url: str | None = None
    uploaded_files: int = 0
    created_folders: int = 0
    parent_folder_id: str | None = None
    fallback_used: bool = False
    warnings: list[str] | None = None
    uploaded_items: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = data.get("warnings") or []
        data["uploaded_items"] = data.get("uploaded_items") or []
        return data


class BoxRestUploader:
    """Tiny REST wrapper for creating folders and uploading small files to Box.

    This intentionally avoids a heavyweight SDK so the hackathon code stays easy
    to inspect. It uses direct upload, which is appropriate for generated
    Markdown/JSON artifacts. Large binary uploads should use Box chunked uploads.
    """

    def __init__(
        self,
        token: str | None = None,
        parent_folder_id: str | None = None,
        create_shared_link: bool | None = None,
        timeout_seconds: int | None = None,
        use_live: bool | None = None,
    ) -> None:
        self.token = token or os.getenv("BOX_DEVELOPER_TOKEN", "").strip()
        self.parent_folder_id = parent_folder_id or os.getenv("BOX_PARENT_FOLDER_ID", "0").strip() or "0"
        if create_shared_link is None:
            create_shared_link = os.getenv("BOX_CREATE_SHARED_LINK", "true").lower() in {"1", "true", "yes", "on"}
        self.create_shared_link = create_shared_link
        self.timeout_seconds = timeout_seconds or int(os.getenv("BOX_TIMEOUT_SECONDS", "90"))
        self.use_live = should_use_live_box(use_live)
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def sync_directory(self, local_project_folder: Path, project_name: str, run_id: str) -> BoxSyncStatus:
        if not self.use_live:
            return BoxSyncStatus(
                mode="local_only",
                ok=True,
                message="Live Box upload is disabled. The app wrote the Box-style project memory locally.",
                parent_folder_id=self.parent_folder_id,
                fallback_used=True,
                warnings=["Set USE_REAL_BOX=true and BOX_DEVELOPER_TOKEN in .env to upload these artifacts to Box."],
            )

        if not self.token:
            return BoxSyncStatus(
                mode="local_mirror",
                ok=False,
                message="USE_REAL_BOX=true, but BOX_DEVELOPER_TOKEN is missing. The local Box mirror was kept.",
                parent_folder_id=self.parent_folder_id,
                fallback_used=True,
                warnings=["Create a Box app developer token or use OAuth/JWT, then set BOX_DEVELOPER_TOKEN in .env."],
            )

        if not local_project_folder.exists():
            return BoxSyncStatus(
                mode="local_mirror",
                ok=False,
                message="The local project memory folder does not exist, so nothing was uploaded to Box.",
                parent_folder_id=self.parent_folder_id,
                fallback_used=True,
                warnings=[str(local_project_folder)],
            )

        folder_name = f"{slugify(project_name)}-{run_id}-rolebrief-ai"
        try:
            root = self.create_folder(folder_name, self.parent_folder_id)
            root_id = root["id"]
            created_folders = 1
            folder_map: dict[str, str] = {".": root_id}

            # Create subfolders first so file uploads are deterministic.
            for relative_dir in sorted({p.parent.relative_to(local_project_folder).as_posix() for p in local_project_folder.rglob("*") if p.is_file()}):
                if relative_dir in {"", "."}:
                    continue
                current_parent = root_id
                current_key = ""
                for part in relative_dir.split("/"):
                    current_key = f"{current_key}/{part}".strip("/")
                    if current_key not in folder_map:
                        folder = self.create_folder(part, current_parent)
                        folder_map[current_key] = folder["id"]
                        created_folders += 1
                    current_parent = folder_map[current_key]

            uploaded_items: list[dict[str, Any]] = []
            uploaded_files = 0
            for path in sorted(local_project_folder.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(local_project_folder).as_posix()
                parent_key = path.parent.relative_to(local_project_folder).as_posix()
                parent_id = folder_map.get(parent_key if parent_key != "." else ".", root_id)
                file_info = self.upload_file(path, parent_id)
                uploaded_files += 1
                uploaded_items.append(
                    {
                        "name": path.name,
                        "relative_path": rel,
                        "id": file_info.get("id"),
                        "url": (file_info.get("shared_link") or {}).get("url") or box_file_url(file_info.get("id")),
                    }
                )

            folder_url = box_folder_url(root_id)
            if self.create_shared_link:
                linked = self.create_folder_shared_link(root_id)
                folder_url = ((linked.get("shared_link") or {}).get("url")) or folder_url

            return BoxSyncStatus(
                mode="box_live",
                ok=True,
                message="Generated sources, role briefs, and metadata were uploaded to a real Box folder.",
                root_folder_id=root_id,
                root_folder_name=folder_name,
                root_folder_url=folder_url,
                uploaded_files=uploaded_files,
                created_folders=created_folders,
                parent_folder_id=self.parent_folder_id,
                fallback_used=False,
                uploaded_items=uploaded_items,
            )
        except Exception as exc:
            return BoxSyncStatus(
                mode="local_mirror",
                ok=False,
                message=f"Live Box upload did not complete, so the local Box mirror was kept: {exc}",
                parent_folder_id=self.parent_folder_id,
                fallback_used=True,
                warnings=["Check token scope, parent folder access, app authorization, and Box admin settings."],
            )

    def create_folder(self, name: str, parent_id: str) -> dict[str, Any]:
        response = self.session.post(
            f"{BOX_API_BASE}/folders",
            json={"name": name, "parent": {"id": parent_id}},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def upload_file(self, path: Path, parent_id: str) -> dict[str, Any]:
        attributes = {"name": path.name, "parent": {"id": parent_id}}
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as file_obj:
            response = self.session.post(
                f"{BOX_UPLOAD_BASE}/files/content",
                files={
                    # Box requires the attributes part to come before the file part.
                    "attributes": (None, json.dumps(attributes), "application/json"),
                    "file": (path.name, file_obj, mime_type),
                },
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        data = response.json()
        entries = data.get("entries") or []
        if not entries:
            raise RuntimeError(f"Box upload returned no file entry for {path.name}")
        return entries[0]

    def create_folder_shared_link(self, folder_id: str) -> dict[str, Any]:
        response = self.session.put(
            f"{BOX_API_BASE}/folders/{folder_id}",
            json={"shared_link": {"access": os.getenv("BOX_SHARED_LINK_ACCESS", "open")}},
            headers={"Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


@dataclass
class BoxReadStatus:
    mode: str
    ok: bool
    message: str
    folder_id: str | None = None
    scanned_items: int = 0
    downloaded_files: int = 0
    normalized_sources: int = 0
    fallback_used: bool = False
    warnings: list[str] | None = None
    imported_items: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["warnings"] = data.get("warnings") or []
        data["imported_items"] = data.get("imported_items") or []
        return data


class BoxContentReader:
    """Read existing Box folder contents into RoleBrief evidence sources.

    This is the missing counterpart to BoxRestUploader. The uploader turns a run
    into a Box project memory; the reader turns an existing Box folder into
    source evidence that Gemini can reason over.
    """

    def __init__(
        self,
        token: str | None = None,
        folder_id: str | None = None,
        recursive: bool | None = None,
        max_files: int | None = None,
        max_bytes: int | None = None,
        timeout_seconds: int | None = None,
        use_live: bool | None = None,
    ) -> None:
        self.token = token or os.getenv("BOX_DEVELOPER_TOKEN", "").strip()
        self.folder_id = folder_id or os.getenv("BOX_SOURCE_FOLDER_ID", "").strip()
        self.recursive = recursive if recursive is not None else os.getenv("BOX_READ_RECURSIVE", "false").lower() in {"1", "true", "yes", "on"}
        self.max_files = max_files if max_files is not None else int(os.getenv("BOX_READ_MAX_FILES", "8") or "8")
        self.max_bytes = max_bytes if max_bytes is not None else int(os.getenv("BOX_READ_MAX_BYTES", "120000") or "120000")
        self.timeout_seconds = timeout_seconds or int(os.getenv("BOX_TIMEOUT_SECONDS", "90") or "90")
        self.allowed_extensions = parse_extension_list(os.getenv("BOX_READ_ALLOWED_EXTENSIONS", ".md,.txt,.json,.csv,.py,.js,.ts,.html,.css,.yml,.yaml,.xml"))
        self.use_live = should_read_live_box(use_live)
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def collect_sources(self, project_goal: str = "") -> tuple[list[dict[str, Any]], BoxReadStatus]:
        if not self.use_live:
            return [], BoxReadStatus(
                mode="disabled",
                ok=True,
                message="Box source import is disabled. The app will use URL evidence, notes, and sample data only.",
                folder_id=self.folder_id or None,
                fallback_used=True,
                warnings=["Set USE_BOX_READ=true and BOX_SOURCE_FOLDER_ID in .env to import existing Box files as evidence."],
            )

        if not self.token:
            return [], BoxReadStatus(
                mode="missing_token",
                ok=False,
                message="USE_BOX_READ=true, but BOX_DEVELOPER_TOKEN is missing. No Box files were imported.",
                folder_id=self.folder_id or None,
                fallback_used=True,
                warnings=["Set BOX_DEVELOPER_TOKEN with read access to the source folder."],
            )

        if not self.folder_id:
            return [], BoxReadStatus(
                mode="missing_folder",
                ok=False,
                message="USE_BOX_READ=true, but BOX_SOURCE_FOLDER_ID is missing. No Box files were imported.",
                fallback_used=True,
                warnings=["Copy a Box folder ID from the Box web URL and set BOX_SOURCE_FOLDER_ID."],
            )

        try:
            items = self._walk_folder(self.folder_id)
            sources: list[dict[str, Any]] = []
            imported_items: list[dict[str, Any]] = []
            warnings: list[str] = []
            for item in items:
                if len(sources) >= self.max_files:
                    break
                if item.get("type") != "file":
                    continue
                name = item.get("name", "untitled")
                if not is_allowed_text_file(name, self.allowed_extensions):
                    continue
                text = self.download_file_text(item["id"], name)
                if not text:
                    warnings.append(f"Skipped empty or unreadable Box file: {name}")
                    continue
                source_id = f"B{len(sources) + 1}"
                source = {
                    "id": source_id,
                    "title": name,
                    "url": box_file_url(item.get("id")) or f"box://file/{item.get('id')}",
                    "source_type": "box_file",
                    "summary": summarize_box_text(text),
                    "key_points": extract_box_key_points(text),
                    "excerpt": text[:2200],
                    "collector": "box_read",
                    "box_file_id": item.get("id"),
                    "box_file_name": name,
                    "box_parent_folder_id": item.get("parent", {}).get("id") if isinstance(item.get("parent"), dict) else self.folder_id,
                }
                sources.append(source)
                imported_items.append({
                    "id": item.get("id"),
                    "name": name,
                    "source_id": source_id,
                    "url": source["url"],
                    "size": item.get("size"),
                })

            return sources, BoxReadStatus(
                mode="box_read_live",
                ok=True,
                message="Existing Box folder files were imported as evidence sources.",
                folder_id=self.folder_id,
                scanned_items=len(items),
                downloaded_files=len(imported_items),
                normalized_sources=len(sources),
                fallback_used=False,
                warnings=warnings,
                imported_items=imported_items,
            )
        except Exception as exc:
            return [], BoxReadStatus(
                mode="read_failed",
                ok=False,
                message=f"Box source import failed: {exc}",
                folder_id=self.folder_id,
                fallback_used=True,
                warnings=["Check token scopes, folder permissions, folder ID, and file types."],
            )

    def _walk_folder(self, folder_id: str) -> list[dict[str, Any]]:
        queue = [folder_id]
        collected: list[dict[str, Any]] = []
        while queue and len(collected) < max(self.max_files * 4, self.max_files):
            current = queue.pop(0)
            items = self.list_folder_items(current)
            for item in items:
                collected.append(item)
                if self.recursive and item.get("type") == "folder":
                    queue.append(item["id"])
                if len(collected) >= max(self.max_files * 4, self.max_files):
                    break
            if not self.recursive:
                break
        return collected

    def list_folder_items(self, folder_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        marker: str | None = None
        fields = "id,type,name,size,parent,modified_at"
        while True:
            params: dict[str, Any] = {"usemarker": "true", "limit": min(100, max(1, self.max_files * 2)), "fields": fields}
            if marker:
                params["marker"] = marker
            response = self.session.get(
                f"{BOX_API_BASE}/folders/{folder_id}/items",
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            entries = payload.get("entries") or []
            items.extend(entries)
            marker = payload.get("next_marker")
            if not marker or len(items) >= max(self.max_files * 4, self.max_files):
                break
        return items

    def download_file_text(self, file_id: str, name: str) -> str:
        headers = {"Range": f"bytes=0-{max(0, self.max_bytes - 1)}"}
        response = self.session.get(
            f"{BOX_API_BASE}/files/{file_id}/content",
            headers=headers,
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        response.raise_for_status()
        raw = response.content[: self.max_bytes]
        return decode_text_bytes(raw, name)


def should_read_live_box(form_value: bool | None = None) -> bool:
    if form_value is not None:
        return bool(form_value)
    return os.getenv("USE_BOX_READ", "false").lower() in {"1", "true", "yes", "on"}


def parse_extension_list(raw: str) -> set[str]:
    values = set()
    for item in (raw or "").split(','):
        item = item.strip().lower()
        if not item:
            continue
        if not item.startswith('.'):
            item = '.' + item
        values.add(item)
    return values or {".md", ".txt", ".json", ".csv"}


def is_allowed_text_file(name: str, allowed_extensions: set[str]) -> bool:
    lower = (name or "").lower()
    return any(lower.endswith(ext) for ext in allowed_extensions)


def decode_text_bytes(raw: bytes, name: str) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding, errors="replace").strip()
        except Exception:
            continue
    return ""


def summarize_box_text(text: str, limit: int = 650) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    boundary = text.rfind(". ", 0, limit)
    if boundary < 180:
        boundary = limit
    return text[:boundary].strip() + "…"


def extract_box_key_points(text: str, max_points: int = 5) -> list[str]:
    lines = []
    for line in (text or "").splitlines():
        cleaned = line.strip(" #-*\t")
        if 25 <= len(cleaned) <= 180:
            lines.append(cleaned)
        if len(lines) >= max_points:
            return lines
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text or "").strip())
    for sentence in sentences:
        if 35 <= len(sentence) <= 180:
            lines.append(sentence)
        if len(lines) >= max_points:
            break
    return lines or ["Imported from an existing Box file as project evidence."]


def should_use_live_box(form_value: bool | None = None) -> bool:
    if form_value is not None:
        return bool(form_value)
    return os.getenv("USE_REAL_BOX", "false").lower() in {"1", "true", "yes", "on"}


def box_folder_url(folder_id: str | None) -> str | None:
    return f"https://app.box.com/folder/{folder_id}" if folder_id else None


def box_file_url(file_id: str | None) -> str | None:
    return f"https://app.box.com/file/{file_id}" if file_id else None
