from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server
from attractor.engine import Checkpoint, save_checkpoint


def test_get_pipeline_checkpoint_returns_404_for_unknown_pipeline(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")

    response = api_client.get("/pipelines/missing-run/checkpoint")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown pipeline"


def test_get_pipeline_checkpoint_returns_current_state_for_known_pipeline(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_id = "run-with-checkpoint"
    runs_root = tmp_path / "runs"
    run_root = runs_root / run_id
    run_root.mkdir(parents=True)
    monkeypatch.setattr(server, "RUNS_ROOT", runs_root)

    checkpoint = Checkpoint(
        timestamp="2026-01-01T00:00:00Z",
        current_node="implement",
        completed_nodes=["start", "plan"],
        context={"graph.goal": "Ship feature", "outcome": "success"},
        retry_counts={"implement": 1},
        logs=["started", "implemented"],
    )
    save_checkpoint(run_root / "state.json", checkpoint)

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

    response = api_client.get(f"/pipelines/{run_id}/checkpoint")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "pipeline_id": run_id,
        "checkpoint": checkpoint.to_dict(),
    }
