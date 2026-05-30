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
                mode="local_fallback",
                ok=False,
                message="USE_REAL_BOX=true, but BOX_DEVELOPER_TOKEN is missing. The local Box mirror was kept as fallback.",
                parent_folder_id=self.parent_folder_id,
                fallback_used=True,
                warnings=["Create a Box app developer token or use OAuth/JWT, then set BOX_DEVELOPER_TOKEN in .env."],
            )

        if not local_project_folder.exists():
            return BoxSyncStatus(
                mode="local_fallback",
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
                        "url": file_info.get("shared_link", {}).get("url") or box_file_url(file_info.get("id")),
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
                mode="local_fallback",
                ok=False,
                message=f"Live Box upload failed, so the local Box mirror was kept as fallback: {exc}",
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


def should_use_live_box(form_value: bool | None = None) -> bool:
    if form_value is not None:
        return bool(form_value)
    return os.getenv("USE_REAL_BOX", "false").lower() in {"1", "true", "yes", "on"}


def box_folder_url(folder_id: str | None) -> str | None:
    return f"https://app.box.com/folder/{folder_id}" if folder_id else None


def box_file_url(file_id: str | None) -> str | None:
    return f"https://app.box.com/file/{file_id}" if file_id else None
