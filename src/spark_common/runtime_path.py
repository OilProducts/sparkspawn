from __future__ import annotations

import os
from pathlib import Path

from spark_common.project_identity import normalize_project_path


RUNTIME_REPO_ROOT = Path(__file__).resolve().parents[2]


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
