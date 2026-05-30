"""Optional Gemini enhancement layer for RoleBrief AI.

The app is still fully demoable without external AI keys. When enabled, Gemini
rewrites the deterministic role-brief draft into a richer, evidence-grounded
brief. If the SDK, API key, or model call fails, the caller keeps the local draft.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
import re
import textwrap
from typing import Any


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def should_use_live_llm(value: bool | None = None) -> bool:
    """Return whether the live LLM enhancement path should be attempted."""
    if value is not None:
        return bool(value)
    return _env_bool("USE_REAL_LLM", "false")


@dataclass
class LLMRunState:
    enabled: bool
    provider: str = "disabled"
    model: str | None = None
    api_key_present: bool = False
    enhanced_roles: list[str] = field(default_factory=list)
    fallback_roles: list[str] = field(default_factory=list)
    role_statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "api_key_present": self.api_key_present,
            "enhanced_roles": self.enhanced_roles,
            "fallback_roles": self.fallback_roles,
            "role_statuses": self.role_statuses,
            "warnings": self.warnings,
            "generated_at": self.generated_at,
        }


class RoleBriefEnhancer:
    """Base interface for role-brief enhancement."""

    def __init__(self, enabled: bool = False, provider: str = "disabled", model: str | None = None, api_key_present: bool = False):
        self.state = LLMRunState(enabled=enabled, provider=provider, model=model, api_key_present=api_key_present)

    def enhance(
        self,
        *,
        role: str,
        role_label: str,
        role_profile: dict[str, Any],
        project: dict[str, Any],
        sources: list[dict[str, Any]],
        evidence_map: dict[str, Any],
        draft_markdown: str,
    ) -> tuple[str, dict[str, Any]]:
        status = {
            "ok": False,
            "enhanced": False,
            "provider": self.state.provider,
            "model": self.state.model,
            "message": "Live LLM enhancement is disabled; using deterministic local brief.",
        }
        self.state.role_statuses[role] = status
        return draft_markdown, status


class GeminiEnhancer(RoleBriefEnhancer):
    """Gemini-powered role-brief enhancer with safe fallback behavior."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.35") or "0.35")
        self.max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2600") or "2600")
        self.max_sources = int(os.getenv("LLM_MAX_SOURCES", "8") or "8")
        self.max_source_chars = int(os.getenv("LLM_MAX_SOURCE_CHARS", "900") or "900")
        super().__init__(enabled=True, provider="gemini", model=self.model, api_key_present=bool(self.api_key))
        if not self.api_key:
            self.state.warnings.append("USE_REAL_LLM is enabled but GEMINI_API_KEY is missing; local fallback will be used.")

    def enhance(
        self,
        *,
        role: str,
        role_label: str,
        role_profile: dict[str, Any],
        project: dict[str, Any],
        sources: list[dict[str, Any]],
        evidence_map: dict[str, Any],
        draft_markdown: str,
    ) -> tuple[str, dict[str, Any]]:
        if not self.api_key:
            return self._fallback(role, "Missing GEMINI_API_KEY; using deterministic local brief.", draft_markdown)

        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on local environment
            return self._fallback(role, f"google-genai is not installed or import failed: {exc}", draft_markdown)

        prompt = self._build_prompt(
            role=role,
            role_label=role_label,
            role_profile=role_profile,
            project=project,
            sources=sources,
            evidence_map=evidence_map,
            draft_markdown=draft_markdown,
        )

        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
            if not self._looks_usable(text):
                print(f"DEBUG: Gemini response was too short: {repr(text)}")
                return self._fallback(role, "Gemini returned an empty or too-short response; using deterministic local brief.", draft_markdown)
            status = {
                "ok": True,
                "enhanced": True,
                "provider": "gemini",
                "model": self.model,
                "message": "Role brief enhanced with Gemini from the local draft and evidence map.",
                "input_sources": min(len(sources), self.max_sources),
                "output_chars": len(text),
            }
            self.state.enhanced_roles.append(role)
            self.state.role_statuses[role] = status
            return text, status
        except Exception as exc:  # pragma: no cover - requires live API call
            return self._fallback(role, f"Gemini call failed: {exc}", draft_markdown)

    def _fallback(self, role: str, message: str, draft_markdown: str) -> tuple[str, dict[str, Any]]:
        status = {
            "ok": False,
            "enhanced": False,
            "provider": "gemini",
            "model": self.model,
            "message": message,
        }
        self.state.fallback_roles.append(role)
        self.state.role_statuses[role] = status
        if message not in self.state.warnings:
            self.state.warnings.append(message)
        return draft_markdown, status

    def _build_prompt(
        self,
        *,
        role: str,
        role_label: str,
        role_profile: dict[str, Any],
        project: dict[str, Any],
        sources: list[dict[str, Any]],
        evidence_map: dict[str, Any],
        draft_markdown: str,
    ) -> str:
        source_block = self._source_block(sources)
        project_block = textwrap.dedent(
            f"""\
            Project name: {project.get('project_name', 'Untitled Project')}
            Tagline: {project.get('tagline', 'One project. Many audiences.')}
            Goal: {project.get('project_goal', 'No project goal provided.')}
            Internal notes: {project.get('internal_notes', 'No internal notes provided.')[:1200]}
            """
        ).strip()
        missing = evidence_map.get("missing_evidence", []) or ["No major evidence gaps were detected."]
        red_flags = evidence_map.get("red_flags", []) or ["No red flags detected in the local evidence map."]
        return textwrap.dedent(
            f"""\
            You are RoleBrief AI's live Gemini enhancement layer.

            Task:
            Rewrite the deterministic draft into a sharper, more useful {role_label}.
            You must optimize for this audience, not for a generic summary.

            Role profile:
            - Role key: {role}
            - Primary question: {role_profile.get('primary_question')}
            - Deliverable: {role_profile.get('deliverable')}
            - Cares about: {', '.join(role_profile.get('cares_about', []))}
            - Avoid: {role_profile.get('avoid')}

            Project:
            {project_block}

            Evidence sources:
            {source_block}

            Evidence health:
            - Missing evidence: {'; '.join(missing)}
            - Red flags: {'; '.join(red_flags)}

            Deterministic draft to improve:
            {draft_markdown[:6500]}

            Output rules:
            - Return Markdown only.
            - Use only the evidence above and the deterministic draft. Do not invent URLs, prices, laws, API capabilities, or sponsor requirements.
            - Cite source IDs exactly like [S1], [A1], [N4] when making source-backed claims.
            - If evidence is missing, say what evidence is missing instead of guessing.
            - Keep the report concise enough for a hackathon judge or teammate to scan quickly.
            - Make this role clearly different from the other roles.
            - Preserve these headings exactly:
              # {role_label}: {project.get('project_name', 'Untitled Project')}
              ## What this role needs to know
              ## Evidence-backed insights
              ## Decisions or actions
              ## Risks and missing evidence
              ## Source references
            """
        ).strip()

    def _source_block(self, sources: list[dict[str, Any]]) -> str:
        rows = []
        for source in sources[: self.max_sources]:
            points = "; ".join((source.get("key_points") or [])[:4])
            excerpt = (source.get("excerpt") or "")[: self.max_source_chars]
            rows.append(
                textwrap.dedent(
                    f"""\
                    [{source.get('id', 'S?')}] {source.get('title', 'Untitled source')}
                    URL: {source.get('url', 'N/A')}
                    Type: {source.get('source_type', 'unknown')}
                    Summary: {source.get('summary', 'No summary provided.')}
                    Key points: {points or 'No key points provided.'}
                    Excerpt: {excerpt or 'No excerpt provided.'}
                    """
                ).strip()
            )
        if not rows:
            return "No evidence sources were provided."
        if len(sources) > self.max_sources:
            rows.append(f"... {len(sources) - self.max_sources} additional sources omitted from the LLM prompt for safety.")
        return "\n\n".join(rows)

    @staticmethod
    def _looks_usable(text: str) -> bool:
        if len(text) < 400:
            return False
        # Require at least a couple of section headings so we know we got a
        # structured brief and not a stray sentence or an error string.
        if text.count("##") < 2:
            return False
        # Confirm the response is actually about the brief's content. The model
        # output can be truncated by max_output_tokens before it reaches the
        # final "## Source references" heading, so don't depend on that section
        # existing. Instead accept any evidence reference, e.g. a citation like
        # [S1]/[A2]/[N3] or the word "source" in any case.
        if re.search(r"\[[A-Za-z]+\d+\]", text):
            return True
        return "source" in text.lower()


def create_llm_enhancer(use_live: bool | None = None) -> RoleBriefEnhancer:
    """Create the configured role-brief enhancer."""
    enabled = should_use_live_llm(use_live)
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower() or "gemini"
    if not enabled:
        return RoleBriefEnhancer(enabled=False)
    if provider == "gemini":
        return GeminiEnhancer()
    enhancer = RoleBriefEnhancer(enabled=True, provider=provider, model=None, api_key_present=False)
    enhancer.state.warnings.append(f"Unsupported LLM_PROVIDER={provider!r}; local fallback will be used.")
    return enhancer
