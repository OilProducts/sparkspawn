from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

import attractor.api.server as server


def test_list_pipeline_questions_returns_404_for_unknown_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.list_pipeline_questions("missing-run"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Unknown pipeline"


def test_list_pipeline_questions_returns_only_pending_questions_for_requested_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_id = "run-with-questions"
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")

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

    broker = server.HumanGateBroker()
    with broker._lock:
        broker._pending["q-1"] = {
            "event": server.threading.Event(),
            "answer": None,
            "run_id": run_id,
            "node_id": "gate",
            "flow_name": "Flow",
            "prompt": "Approve plan?",
            "options": [{"label": "Approve", "value": "approve"}],
        }
        broker._pending["q-2"] = {
            "event": server.threading.Event(),
            "answer": None,
            "run_id": "other-run",
            "node_id": "gate",
            "flow_name": "Flow",
            "prompt": "Ignore me",
            "options": [{"label": "Nope", "value": "nope"}],
        }
    monkeypatch.setattr(server, "HUMAN_BROKER", broker)

    payload = asyncio.run(server.list_pipeline_questions(run_id))

    assert payload == {
        "questions": [
            {
                "question_id": "q-1",
                "run_id": run_id,
                "node_id": "gate",
                "flow_name": "Flow",
                "prompt": "Approve plan?",
                "options": [{"label": "Approve", "value": "approve"}],
            }
        ]
    }
