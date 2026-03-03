from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server
from attractor.engine import Checkpoint, save_checkpoint


def _write_checkpoint(run_root: Path, current_node: str, completed_nodes: list[str]) -> None:
    save_checkpoint(
        run_root / "state.json",
        Checkpoint(
            current_node=current_node,
            completed_nodes=completed_nodes,
            context={},
            retry_counts={},
        ),
    )


def test_get_pipeline_returns_progress_for_active_run(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-active"
    runs_root = tmp_path / "runs"
    run_root = runs_root / run_id
    run_root.mkdir(parents=True)
    monkeypatch.setattr(server, "RUNS_ROOT", runs_root)

    _write_checkpoint(run_root, current_node="plan", completed_nodes=["start"])
    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="Flow",
            status="running",
            result=None,
            working_directory=str(tmp_path / "work"),
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
        )
    )

    with server.ACTIVE_RUNS_LOCK:
        server.ACTIVE_RUNS[run_id] = server.ActiveRun(
            run_id=run_id,
            flow_name="Flow",
            working_directory=str(tmp_path / "work"),
            model="test-model",
            status="running",
            completed_nodes=["start"],
        )

    try:
        response = api_client.get(f"/pipelines/{run_id}")
    finally:
        server._pop_active_run(run_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline_id"] == run_id
    assert payload["status"] == "running"
    assert payload["completed_nodes"] == ["start"]
    assert payload["progress"] == {
        "current_node": "plan",
        "completed_count": 1,
    }


def test_get_pipeline_uses_checkpoint_progress_for_persisted_run(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-finished"
    runs_root = tmp_path / "runs"
    run_root = runs_root / run_id
    run_root.mkdir(parents=True)
    monkeypatch.setattr(server, "RUNS_ROOT", runs_root)

    _write_checkpoint(run_root, current_node="done", completed_nodes=["start", "plan"])
    server._write_run_meta(
        server.RunRecord(
            run_id=run_id,
            flow_name="Flow",
            status="success",
            result="success",
            working_directory=str(tmp_path / "work"),
            model="test-model",
            started_at="2026-01-01T00:00:00Z",
            ended_at="2026-01-01T00:01:00Z",
        )
    )

    response = api_client.get(f"/pipelines/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline_id"] == run_id
    assert payload["status"] == "success"
    assert payload["completed_nodes"] == ["start", "plan"]
    assert payload["progress"] == {
        "current_node": "done",
        "completed_count": 2,
    }
