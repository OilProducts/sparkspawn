from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Dict, Tuple, Type, TypeVar

from .context import ReadWriteLock


T = TypeVar("T")


@dataclass(frozen=True)
class ArtifactInfo:
    id: str
    name: str
    size_bytes: int
    stored_at: datetime
    is_file_backed: bool


class ArtifactStore:
    def __init__(self) -> None:
        self._artifacts: Dict[str, Tuple[ArtifactInfo, Any]] = {}
        self._lock = ReadWriteLock()

    def store(self, artifact_id: str, name: str, data: Any) -> ArtifactInfo:
        info = ArtifactInfo(
            id=artifact_id,
            name=name,
            size_bytes=_byte_size(data),
            stored_at=datetime.now(timezone.utc),
            is_file_backed=False,
        )
        with self._lock.write_lock():
            self._artifacts[artifact_id] = (info, data)
        return info

    def retrieve(self, artifact_id: str, expected_type: Type[T] | None = None) -> T | Any:
        with self._lock.read_lock():
            artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise KeyError(f"Artifact not found: {artifact_id}")

        _, data = artifact
        if expected_type is not None and not isinstance(data, expected_type):
            raise TypeError(
                f"Artifact '{artifact_id}' expected type {expected_type.__name__}, "
                f"received {type(data).__name__}"
            )
        return data


def _byte_size(data: Any) -> int:
    try:
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError):
        payload = repr(data).encode("utf-8")
    return len(payload)
