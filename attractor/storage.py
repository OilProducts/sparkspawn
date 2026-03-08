from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import tomllib
from typing import Any


def normalize_project_path(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    return str(Path(trimmed).expanduser().resolve(strict=False))


def _iso_now() -> str:
    from time import gmtime, strftime

    return strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


_UNSET = object()


def build_project_id(project_path: str) -> str:
    normalized_path = normalize_project_path(project_path)
    if not normalized_path:
        raise ValueError("Project path is required.")
    slug = _slugify(Path(normalized_path).name)
    digest = hashlib.sha1(normalized_path.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


@dataclass(frozen=True)
class ProjectPaths:
    project_id: str
    project_path: str
    display_name: str
    root: Path
    project_file: Path
    conversations_dir: Path
    workflow_dir: Path
    proposals_dir: Path
    execution_cards_dir: Path
    runs_dir: Path


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    project_path: str
    display_name: str
    created_at: str
    last_opened_at: str
    last_accessed_at: str | None
    is_favorite: bool
    active_conversation_id: str | None


def ensure_project_paths(home_dir: Path, project_path: str) -> ProjectPaths:
    normalized_project_path = normalize_project_path(project_path)
    if not normalized_project_path:
        raise ValueError("Project path is required.")

    project_id = build_project_id(normalized_project_path)
    display_name = Path(normalized_project_path).name or normalized_project_path
    project_root = home_dir / "projects" / project_id
    project_file = project_root / "project.toml"
    conversations_dir = project_root / "conversations"
    workflow_dir = project_root / "workflow"
    proposals_dir = project_root / "proposals"
    execution_cards_dir = project_root / "execution-cards"
    runs_dir = project_root / "runs"

    for directory in (
        project_root,
        conversations_dir,
        workflow_dir,
        proposals_dir,
        execution_cards_dir,
        runs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    payload = _read_project_record(project_file)
    created_at = str(payload.get("created_at", "") or "")
    if not created_at:
        created_at = _iso_now()

    _write_project_record(
        project_file,
        {
            "project_id": project_id,
            "project_path": normalized_project_path,
            "display_name": display_name,
            "created_at": created_at,
            "last_opened_at": _iso_now(),
            "last_accessed_at": _read_optional_string(payload, "last_accessed_at"),
            "is_favorite": _read_optional_bool(payload, "is_favorite", default=False),
            "active_conversation_id": _read_optional_string(payload, "active_conversation_id"),
        },
    )

    return ProjectPaths(
        project_id=project_id,
        project_path=normalized_project_path,
        display_name=display_name,
        root=project_root,
        project_file=project_file,
        conversations_dir=conversations_dir,
        workflow_dir=workflow_dir,
        proposals_dir=proposals_dir,
        execution_cards_dir=execution_cards_dir,
        runs_dir=runs_dir,
    )


def read_project_paths_by_id(home_dir: Path, project_id: str) -> ProjectPaths | None:
    root = home_dir / "projects" / project_id
    project_file = root / "project.toml"
    if not project_file.exists():
        return None
    payload = _read_project_record(project_file)
    project_path = normalize_project_path(str(payload.get("project_path", "")))
    if not project_path:
        return None
    display_name = str(payload.get("display_name", "") or Path(project_path).name or project_path)
    return ProjectPaths(
        project_id=project_id,
        project_path=project_path,
        display_name=display_name,
        root=root,
        project_file=project_file,
        conversations_dir=root / "conversations",
        workflow_dir=root / "workflow",
        proposals_dir=root / "proposals",
        execution_cards_dir=root / "execution-cards",
        runs_dir=root / "runs",
    )


def read_project_record(home_dir: Path, project_path: str) -> ProjectRecord | None:
    project_paths = ensure_project_paths(home_dir, project_path)
    return read_project_record_by_id(home_dir, project_paths.project_id)


def read_project_record_by_id(home_dir: Path, project_id: str) -> ProjectRecord | None:
    project_paths = read_project_paths_by_id(home_dir, project_id)
    if project_paths is None:
        return None
    return _build_project_record(project_paths)


def list_project_records(home_dir: Path) -> list[ProjectRecord]:
    projects_root = home_dir / "projects"
    if not projects_root.exists():
        return []
    records: list[ProjectRecord] = []
    for project_root in sorted(projects_root.iterdir()):
        if not project_root.is_dir():
            continue
        record = read_project_record_by_id(home_dir, project_root.name)
        if record is not None:
            records.append(record)
    return records


def update_project_record(
    home_dir: Path,
    project_path: str,
    *,
    display_name: str | None = None,
    last_accessed_at: str | None | object = _UNSET,
    is_favorite: bool | object = _UNSET,
    active_conversation_id: str | None | object = _UNSET,
) -> ProjectRecord:
    project_paths = ensure_project_paths(home_dir, project_path)
    payload = _read_project_record(project_paths.project_file)
    next_payload: dict[str, Any] = {
        "project_id": project_paths.project_id,
        "project_path": project_paths.project_path,
        "display_name": display_name or str(payload.get("display_name", "") or project_paths.display_name),
        "created_at": str(payload.get("created_at", "") or _iso_now()),
        "last_opened_at": str(payload.get("last_opened_at", "") or _iso_now()),
        "last_accessed_at": _read_optional_string(payload, "last_accessed_at"),
        "is_favorite": _read_optional_bool(payload, "is_favorite", default=False),
        "active_conversation_id": _read_optional_string(payload, "active_conversation_id"),
    }
    if last_accessed_at is not _UNSET:
        next_payload["last_accessed_at"] = _normalize_optional_string(last_accessed_at)
    if is_favorite is not _UNSET:
        next_payload["is_favorite"] = bool(is_favorite)
    if active_conversation_id is not _UNSET:
        next_payload["active_conversation_id"] = _normalize_optional_string(active_conversation_id)
    _write_project_record(project_paths.project_file, next_payload)
    return _build_project_record(project_paths)


def _read_project_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _normalize_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _read_optional_string(payload: dict[str, object], key: str) -> str | None:
    return _normalize_optional_string(payload.get(key))


def _read_optional_bool(payload: dict[str, object], key: str, *, default: bool) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    return default


def _build_project_record(project_paths: ProjectPaths) -> ProjectRecord:
    payload = _read_project_record(project_paths.project_file)
    return ProjectRecord(
        project_id=project_paths.project_id,
        project_path=project_paths.project_path,
        display_name=str(payload.get("display_name", "") or project_paths.display_name),
        created_at=str(payload.get("created_at", "") or ""),
        last_opened_at=str(payload.get("last_opened_at", "") or ""),
        last_accessed_at=_read_optional_string(payload, "last_accessed_at"),
        is_favorite=_read_optional_bool(payload, "is_favorite", default=False),
        active_conversation_id=_read_optional_string(payload, "active_conversation_id"),
    )


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
    return f"\"{escaped}\""


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _write_project_record(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"project_id = {_toml_string(payload['project_id'])}",
        f"project_path = {_toml_string(payload['project_path'])}",
        f"display_name = {_toml_string(payload['display_name'])}",
        f"created_at = {_toml_string(payload['created_at'])}",
        f"last_opened_at = {_toml_string(payload['last_opened_at'])}",
    ]
    if payload.get("last_accessed_at"):
        lines.append(f"last_accessed_at = {_toml_string(str(payload['last_accessed_at']))}")
    lines.append(f"is_favorite = {_toml_bool(bool(payload.get('is_favorite', False)))}")
    if payload.get("active_conversation_id"):
        lines.append(f"active_conversation_id = {_toml_string(str(payload['active_conversation_id']))}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
