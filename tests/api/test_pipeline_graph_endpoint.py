from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

import attractor.api.server as server


def test_get_pipeline_graph_returns_svg_for_known_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_id = "run-graph"
    runs_root = tmp_path / "runs"
    monkeypatch.setattr(server, "RUNS_ROOT", runs_root)

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

    svg_path = runs_root / run_id / "artifacts" / "graphviz" / "pipeline.svg"
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text("<svg/>", encoding="utf-8")

    response = asyncio.run(server.get_pipeline_graph(run_id))

    assert isinstance(response, FileResponse)
    assert Path(response.path) == svg_path


def test_get_pipeline_graph_returns_404_for_unknown_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.get_pipeline_graph("missing-run"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Unknown pipeline"


def test_get_pipeline_graph_returns_404_when_svg_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_id = "run-no-svg"
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

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.get_pipeline_graph(run_id))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Graph visualization unavailable"
