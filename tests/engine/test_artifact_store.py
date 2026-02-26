from __future__ import annotations

from datetime import datetime, timezone

import pytest

from attractor.engine.artifacts import ArtifactInfo, ArtifactStore


def test_store_registers_artifact_with_metadata() -> None:
    store = ArtifactStore()

    info = store.store("artifact-1", "plan-output", {"status": "ok"})

    assert isinstance(info, ArtifactInfo)
    assert info.id == "artifact-1"
    assert info.name == "plan-output"
    assert info.size_bytes > 0
    assert isinstance(info.stored_at, datetime)
    assert info.stored_at.tzinfo == timezone.utc
    assert info.is_file_backed is False


def test_retrieve_supports_optional_type_assertion() -> None:
    store = ArtifactStore()
    payload = {"result": "ready"}
    store.store("artifact-2", "review-output", payload)

    typed_value = store.retrieve("artifact-2", expected_type=dict)
    assert typed_value == payload

    with pytest.raises(TypeError):
        store.retrieve("artifact-2", expected_type=list)
