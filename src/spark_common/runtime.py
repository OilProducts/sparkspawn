from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path


RUNTIME_REPO_ROOT = Path(__file__).resolve().parents[2]


def normalize_project_path(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    return str(Path(trimmed).expanduser().resolve(strict=False))


def build_project_id(project_path: str) -> str:
    normalized_path = normalize_project_path(project_path)
    if not normalized_path:
        raise ValueError("Project path is required.")
    slug = _slugify(Path(normalized_path).name)
    digest = hashlib.sha1(normalized_path.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def resolve_runtime_workspace_path(value: str) -> str:
    normalized = normalize_project_path(value)
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
        runtime_root = Path(tempfile.gettempdir()) / "spark-codex-runtime"
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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"
