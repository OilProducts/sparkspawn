from __future__ import annotations

import hashlib
from pathlib import Path
import re


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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"
