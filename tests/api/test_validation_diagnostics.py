from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import attractor.api.server as server
from attractor.dsl.models import Diagnostic, DiagnosticSeverity


FLOW = """
digraph G {
    start [shape=Mdiamond]
    done [shape=Msquare]
    start -> done
}
"""


def _close_task_immediately(coro):
    coro.close()

    class _DummyTask:
        pass

    return _DummyTask()


def _warning_info_diagnostics() -> list[Diagnostic]:
    return [
        Diagnostic(
            rule_id="fidelity_valid",
            severity=DiagnosticSeverity.WARNING,
            message="fidelity should be one of supported values",
            node_id="start",
            line=2,
        ),
        Diagnostic(
            rule_id="lint_hint",
            severity=DiagnosticSeverity.INFO,
            message="consider adding explicit node labels",
            line=1,
        ),
    ]


def _warning_error_diagnostics() -> list[Diagnostic]:
    return [
        Diagnostic(
            rule_id="type_known",
            severity=DiagnosticSeverity.WARNING,
            message="unrecognized type",
            node_id="start",
            line=2,
        ),
        Diagnostic(
            rule_id="edge_target_exists",
            severity=DiagnosticSeverity.ERROR,
            message="edge target does not exist",
            edge=("start", "missing"),
            fix="define node 'missing' or update edge",
            line=4,
        ),
    ]


def test_preview_preserves_warning_and_info_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "validate_graph", lambda graph: _warning_info_diagnostics())

    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=FLOW)))

    assert payload["status"] == "ok"
    assert payload["errors"] == []
    assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "info"]
    assert payload["diagnostics"][0]["node_id"] == "start"


def test_preview_validation_error_payload_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "validate_graph", lambda graph: _warning_error_diagnostics())

    payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=FLOW)))

    assert payload["status"] == "validation_error"
    assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "error"]
    warning_diag, error_diag = payload["diagnostics"]

    assert warning_diag["rule"] == "type_known"
    assert warning_diag["rule_id"] == "type_known"
    assert warning_diag["node"] == "start"
    assert warning_diag["node_id"] == "start"

    assert error_diag["rule"] == "edge_target_exists"
    assert error_diag["rule_id"] == "edge_target_exists"
    assert error_diag["edge"] == ["start", "missing"]
    assert error_diag["fix"] == "define node 'missing' or update edge"
    assert error_diag["node"] is None

    assert len(payload["errors"]) == 1
    assert payload["errors"][0] == error_diag


def test_start_pipeline_preserves_warning_and_info_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    monkeypatch.setattr(server, "validate_graph", lambda graph: _warning_info_diagnostics())

    payload = asyncio.run(
        server._start_pipeline(
            server.PipelineStartRequest(
                flow_content=FLOW,
                working_directory=str(tmp_path / "work"),
                backend="codex",
            )
        )
    )

    try:
        assert payload["status"] == "started"
        assert payload["errors"] == []
        assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "info"]
    finally:
        if payload.get("pipeline_id"):
            server._pop_active_run(str(payload["pipeline_id"]))


def test_start_pipeline_validation_error_payload_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    monkeypatch.setattr(server, "validate_graph", lambda graph: _warning_error_diagnostics())

    payload = asyncio.run(
        server._start_pipeline(
            server.PipelineStartRequest(
                flow_content=FLOW,
                working_directory=str(tmp_path / "work"),
                backend="codex",
            )
        )
    )

    assert payload["status"] == "validation_error"
    assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "error"]
    assert len(payload["errors"]) == 1

    warning_diag, error_diag = payload["diagnostics"]
    assert warning_diag["rule"] == "type_known"
    assert warning_diag["node"] == "start"
    assert error_diag["rule"] == "edge_target_exists"
    assert error_diag["edge"] == ["start", "missing"]
    assert payload["errors"][0] == error_diag


def test_start_pipeline_runs_stylesheet_transform_before_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(server, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    captured: dict[str, str | None] = {}

    def _validate(graph):
        llm_model_attr = graph.nodes["plan"].attrs.get("llm_model")
        captured["plan_llm_model"] = None if llm_model_attr is None else str(llm_model_attr.value)
        return []

    monkeypatch.setattr(server, "validate_graph", _validate)

    flow = """
    digraph G {
        graph [model_stylesheet=".fast { llm_model: fast-model; }"]
        start [shape=Mdiamond]
        plan [shape=box, class="fast"]
        done [shape=Msquare]
        start -> plan -> done
    }
    """

    payload = asyncio.run(
        server._start_pipeline(
            server.PipelineStartRequest(
                flow_content=flow,
                working_directory=str(tmp_path / "work"),
                backend="codex",
            )
        )
    )

    try:
        assert payload["status"] == "started"
        assert captured["plan_llm_model"] == "fast-model"
    finally:
        if payload.get("pipeline_id"):
            server._pop_active_run(str(payload["pipeline_id"]))


def test_preview_applies_registered_custom_transform() -> None:
    class _CustomPromptTransform:
        def apply(self, graph):
            prompt_attr = graph.nodes["task"].attrs["prompt"]
            prompt_attr.value = f"{prompt_attr.value} [custom]"
            return graph

    flow = """
    digraph G {
        start [shape=Mdiamond]
        task [shape=box, prompt="Build"]
        done [shape=Msquare]
        start -> task -> done
    }
    """

    server.clear_registered_transforms()
    try:
        server.register_transform(_CustomPromptTransform())
        payload = asyncio.run(server.preview_pipeline(server.PreviewRequest(flow_content=flow)))
        nodes_by_id = {str(node["id"]): node for node in payload["graph"]["nodes"]}
        assert nodes_by_id["task"]["prompt"] == "Build [custom]"
    finally:
        server.clear_registered_transforms()
