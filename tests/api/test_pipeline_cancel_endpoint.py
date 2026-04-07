from __future__ import annotations

from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server
from tests.api._support import (
    close_task_immediately as _close_task_immediately,
    start_pipeline as _start_pipeline,
    wait_for_pipeline_completion as _wait_for_pipeline_completion,
    wait_for_pipeline_terminal_status as _wait_for_pipeline_terminal_status,
)


def test_cancel_pipeline_returns_404_for_unknown_pipeline(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")

    response = attractor_api_client.post("/pipelines/missing-run/cancel")
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown pipeline"


def test_cancel_pipeline_requests_cancel_for_active_run(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    start_payload = _start_pipeline(attractor_api_client, tmp_path / "work")
    run_id = str(start_payload["pipeline_id"])

    response = attractor_api_client.post(f"/pipelines/{run_id}/cancel")
    assert response.status_code == 200
    payload = response.json()

    status_response = attractor_api_client.get(f"/pipelines/{run_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()

    runs_response = attractor_api_client.get("/runs")
    assert runs_response.status_code == 200
    run_rows = runs_response.json()["runs"]
    row = next((entry for entry in run_rows if entry["run_id"] == run_id), None)
    assert row is not None
    assert row["status"] == "cancel_requested"

    assert payload == {"status": "cancel_requested", "pipeline_id": run_id}
    assert status_payload["status"] == "cancel_requested"
    assert status_payload["last_error"] == "cancel_requested_by_user"
    assert server.RUNTIME.status == "cancel_requested"
    assert server.RUNTIME.last_error == "cancel_requested_by_user"

    history = server.EVENT_HUB.history(run_id)
    assert any(
        event.get("type") == "runtime"
        and event.get("status") == "cancel_requested"
        and event.get("outcome") is None
        and event.get("outcome_reason_code") is None
        and event.get("outcome_reason_message") is None
        and event.get("run_id") == run_id
        and isinstance(event.get("sequence"), int)
        and isinstance(event.get("emitted_at"), str)
        for event in history
    )
    assert any(
        event.get("type") == "log"
        and event.get("msg") == "[System] Cancel requested. Stopping after current node."
        and event.get("run_id") == run_id
        and isinstance(event.get("sequence"), int)
        and isinstance(event.get("emitted_at"), str)
        for event in history
    )


def test_cancel_pipeline_ignores_non_running_known_pipeline(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    start_payload = _start_pipeline(attractor_api_client, tmp_path / "work")
    run_id = str(start_payload["pipeline_id"])
    final_status = _wait_for_pipeline_terminal_status(attractor_api_client, run_id)
    assert final_status == "completed"

    response = attractor_api_client.post(f"/pipelines/{run_id}/cancel")
    assert response.status_code == 200
    payload = response.json()

    assert payload == {"status": "ignored", "pipeline_id": run_id}


def test_cancel_pipeline_stops_nested_manager_loop_child_execution(
    attractor_api_client: TestClient,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")

    child_dot_path = tmp_path / "child.dot"
    child_dot_path.write_text(
        """
        digraph Child {
            start [shape=Mdiamond]
            first [shape=parallelogram, tool.command="sleep 0.5"]
            second [shape=parallelogram, tool.command="sleep 0.5"]
            done [shape=Msquare]

            start -> first -> second -> done
        }
        """,
        encoding="utf-8",
    )

    start_payload = _start_pipeline(
        attractor_api_client,
        tmp_path / "work",
        flow_content=f"""
        digraph Parent {{
            graph [stack.child_dotfile="{child_dot_path}"]
            start [shape=Mdiamond]
            manager [shape=house, manager.poll_interval=0ms, manager.max_cycles=1, manager.actions=""]
            done [shape=Msquare]

            start -> manager -> done
        }}
        """,
    )
    run_id = str(start_payload["pipeline_id"])

    for _ in range(200):
        events = server._read_persisted_run_events(run_id)
        if any(
            event.get("type") == "StageStarted"
            and event.get("source_scope") == "child"
            and event.get("node_id") == "first"
            for event in events
        ):
            break
        time.sleep(0.01)
    else:
        raise AssertionError("timed out waiting for child stage start before cancel")

    cancel_response = attractor_api_client.post(f"/pipelines/{run_id}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json() == {"status": "cancel_requested", "pipeline_id": run_id}

    final_payload = _wait_for_pipeline_completion(attractor_api_client, run_id, attempts=800)

    assert final_payload["status"] == "canceled"

    events = server._read_persisted_run_events(run_id)
    child_started_nodes = [
        str(event.get("node_id"))
        for event in events
        if event.get("type") == "StageStarted" and event.get("source_scope") == "child"
    ]
    assert "first" in child_started_nodes
    assert "second" not in child_started_nodes
    assert any(
        event.get("type") == "runtime" and event.get("status") == "canceled"
        for event in events
    )
