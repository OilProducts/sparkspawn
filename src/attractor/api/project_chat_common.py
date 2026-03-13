from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from attractor.api.project_chat_models import ConversationTurn
from attractor.storage import normalize_project_path


LOGGER = logging.getLogger(__name__)
RUNTIME_REPO_ROOT = Path(__file__).resolve().parents[2]


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def truncate_text(value: str, limit: int) -> str:
    trimmed = value.strip()
    if len(trimmed) <= limit:
        return trimmed
    return trimmed[: max(0, limit - 1)].rstrip() + "…"


def normalize_project_path_value(value: str) -> str:
    return normalize_project_path(value)


def as_non_empty_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        raise ValueError("Expected non-empty JSON response from Codex.")
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    if not candidate.lstrip().startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Expected top-level JSON object from Codex.")
    return parsed


def parse_chat_response_payload(raw: str) -> tuple[str, Optional[dict[str, Any]]]:
    text = raw.strip()
    if not text:
        return "", None
    try:
        parsed = extract_json_object(text)
    except Exception:
        return text, None
    assistant_message = as_non_empty_string(parsed.get("assistant_message"))
    if assistant_message:
        return assistant_message, parsed if isinstance(parsed, dict) else None
    fallback_text = text if not text.startswith("{") else ""
    return fallback_text, parsed if isinstance(parsed, dict) else None


def derive_conversation_title(turns: list[ConversationTurn]) -> str:
    for turn in turns:
        if turn.role != "user":
            continue
        title = as_non_empty_string(turn.content)
        if title:
            return truncate_text(title, 64)
    return "New thread"


def build_conversation_preview(turns: list[ConversationTurn]) -> Optional[str]:
    for turn in reversed(turns):
        if turn.kind != "message":
            continue
        preview = as_non_empty_string(turn.content)
        if preview:
            return truncate_text(preview, 96)
    return None


def is_project_chat_debug_enabled() -> bool:
    value = str(os.environ.get("SPARKSPAWN_DEBUG_PROJECT_CHAT", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def summarize_turns_for_debug(turns: list[ConversationTurn]) -> list[dict[str, Any]]:
    return [
        {
            "id": turn.id,
            "role": turn.role,
            "kind": turn.kind,
            "artifact_id": turn.artifact_id,
            "content": turn.content[:160],
        }
        for turn in turns
    ]


def log_project_chat_debug(message: str, **fields: Any) -> None:
    if not is_project_chat_debug_enabled():
        return
    if fields:
        LOGGER.info("[project-chat] %s | %s", message, json.dumps(fields, sort_keys=True, default=str))
        return
    LOGGER.info("[project-chat] %s", message)


def resolve_runtime_workspace_path(value: str) -> str:
    normalized = normalize_project_path_value(value)
    if not normalized:
        return ""

    requested_path = Path(normalized)
    if requested_path.exists():
        return str(requested_path)

    runtime_roots: list[Path] = []
    host_root_override = os.environ.get("ATTRACTOR_HOST_REPO_ROOT", "").strip()
    runtime_root_override = os.environ.get("ATTRACTOR_RUNTIME_REPO_ROOT", "").strip()
    host_root = Path(host_root_override).expanduser().resolve(strict=False) if host_root_override else None
    if runtime_root_override:
        runtime_roots.append(Path(runtime_root_override).expanduser().resolve(strict=False))
    runtime_roots.append(RUNTIME_REPO_ROOT)

    requested_parts = requested_path.parts
    for runtime_root in runtime_roots:
        if not runtime_root.exists():
            continue
        if host_root is not None:
            try:
                relative_to_host_root = requested_path.relative_to(host_root)
            except ValueError:
                relative_to_host_root = None
            if relative_to_host_root is not None:
                candidate = runtime_root / relative_to_host_root
                if candidate.exists():
                    return str(candidate.resolve(strict=False))
            host_root_matching_indexes = [index for index, part in enumerate(requested_parts) if part == host_root.name]
            for index in reversed(host_root_matching_indexes):
                candidate = runtime_root.joinpath(*requested_parts[index + 1 :])
                if candidate.exists():
                    return str(candidate.resolve(strict=False))
        matching_indexes = [index for index, part in enumerate(requested_parts) if part == runtime_root.name]
        for index in reversed(matching_indexes):
            candidate = runtime_root.joinpath(*requested_parts[index + 1 :])
            if candidate.exists():
                return str(candidate.resolve(strict=False))

    return str(requested_path)


def build_codex_runtime_environment() -> dict[str, str]:
    env = os.environ.copy()
    original_home = Path(env.get("HOME", str(Path.home()))).expanduser()
    original_codex_home = Path(env.get("CODEX_HOME", str(original_home / ".codex"))).expanduser()
    configured_runtime_root = Path(env.get("ATTRACTOR_CODEX_RUNTIME_ROOT", "/codex-runtime")).expanduser()
    runtime_root = configured_runtime_root
    try:
        runtime_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        runtime_root = Path(tempfile.gettempdir()) / "sparkspawn-codex-runtime"
    codex_home = Path(env.get("CODEX_HOME", str(runtime_root / ".codex"))).expanduser()
    xdg_config_home = Path(env.get("XDG_CONFIG_HOME", str(runtime_root / ".config"))).expanduser()
    xdg_data_home = Path(env.get("XDG_DATA_HOME", str(runtime_root / ".local/share"))).expanduser()
    for directory in (runtime_root, codex_home, xdg_config_home, xdg_data_home):
        directory.mkdir(parents=True, exist_ok=True)

    explicit_seed_dir = Path(env.get("ATTRACTOR_CODEX_SEED_DIR", "/codex-seed")).expanduser()
    seed_candidates: list[Path] = []
    for candidate in (explicit_seed_dir, original_codex_home):
        normalized_candidate = candidate.expanduser()
        if normalized_candidate == codex_home:
            continue
        if normalized_candidate in seed_candidates:
            continue
        seed_candidates.append(normalized_candidate)
    for file_name in ("auth.json", "config.toml"):
        source = next((candidate / file_name for candidate in seed_candidates if (candidate / file_name).exists()), None)
        if source is None:
            continue
        destination = codex_home / file_name
        if destination.exists():
            try:
                if source.read_bytes() == destination.read_bytes():
                    continue
            except OSError:
                pass
        shutil.copy2(source, destination)

    env.update(
        {
            "HOME": str(runtime_root),
            "CODEX_HOME": str(codex_home),
            "XDG_CONFIG_HOME": str(xdg_config_home),
            "XDG_DATA_HOME": str(xdg_data_home),
        }
    )
    return env
