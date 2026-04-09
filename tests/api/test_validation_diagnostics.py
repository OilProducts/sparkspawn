from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import attractor.api.server as server
from attractor.dsl import parse_dot
from attractor.dsl.models import Diagnostic, DiagnosticSeverity, DotAttribute, DotValueType
from tests.api._support import (
    SIMPLE_FLOW as FLOW,
    close_task_immediately as _close_task_immediately,
)


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


def test_preview_preserves_warning_and_info_diagnostics(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server,
        "_prepare_graph_for_server",
        lambda graph: (graph, _warning_info_diagnostics()),
    )

    response = attractor_api_client.post("/preview", json={"flow_content": FLOW})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["errors"] == []
    assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "info"]
    assert payload["diagnostics"][0]["node_id"] == "start"


def test_preview_default_payload_omits_child_previews(
    attractor_api_client: TestClient,
    tmp_path: Path,
) -> None:
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    server.configure_runtime_paths(flows_dir=flows_dir)
    (flows_dir / "child.dot").write_text(
        """
        digraph ChildFlow {
            start [shape=Mdiamond]
            done [shape=Msquare]
            start -> done
        }
        """,
        encoding="utf-8",
    )

    response = attractor_api_client.post(
        "/preview",
        json={
            "flow_content": """
            digraph ParentFlow {
                graph [stack.child_dotfile="child.dot"]
                manager [shape=house, type="stack.manager_loop"]
            }
            """,
            "flow_name": "parent.dot",
        },
    )

    assert response.status_code == 200
    graph_payload = response.json()["graph"]
    assert "child_previews" not in graph_payload


def test_preview_expand_children_resolves_relative_child_flows_from_parent_flow_path(
    attractor_api_client: TestClient,
    tmp_path: Path,
) -> None:
    flows_dir = tmp_path / "flows"
    parent_dir = flows_dir / "programs"
    parent_dir.mkdir(parents=True, exist_ok=True)
    server.configure_runtime_paths(flows_dir=flows_dir)
    (parent_dir / "child-worker.dot").write_text(
        """
        digraph ChildWorker {
            start [shape=Mdiamond]
            implement [shape=box, label="Implement"]
            done [shape=Msquare]
            start -> implement -> done
        }
        """,
        encoding="utf-8",
    )

    response = attractor_api_client.post(
        "/preview",
        json={
            "flow_content": """
            digraph ParentFlow {
                graph [stack.child_dotfile="child-worker.dot"]
                manager [shape=house, type="stack.manager_loop", label="Manager"]
            }
            """,
            "flow_name": "programs/parent.dot",
            "expand_children": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    child_previews = payload["graph"]["child_previews"]
    assert set(child_previews.keys()) == {"manager"}
    manager_preview = child_previews["manager"]
    assert manager_preview["flow_name"] == "child-worker.dot"
    assert manager_preview["read_only"] is True
    assert manager_preview["provenance"] == "derived_child_preview"
    assert manager_preview["graph"]["nodes"][1]["id"] == "implement"


def test_preview_expand_children_omits_unresolvable_child_flow_without_breaking_parent_preview(
    attractor_api_client: TestClient,
    tmp_path: Path,
) -> None:
    flows_dir = tmp_path / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    server.configure_runtime_paths(flows_dir=flows_dir)

    response = attractor_api_client.post(
        "/preview",
        json={
            "flow_content": """
            digraph ParentFlow {
                graph [stack.child_dotfile="missing-child.dot"]
                start [shape=Mdiamond]
                manager [shape=house, type="stack.manager_loop"]
                done [shape=Msquare]
                start -> manager -> done
            }
            """,
            "flow_name": "parent.dot",
            "expand_children": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["graph"]["nodes"], list)
    assert "child_previews" not in payload["graph"]


def test_preview_validation_error_payload_shape(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server,
        "_prepare_graph_for_server",
        lambda graph: (graph, _warning_error_diagnostics()),
    )

    response = attractor_api_client.post("/preview", json={"flow_content": FLOW})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validation_error"
    assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "error"]
    warning_diag, error_diag = payload["diagnostics"]

    assert warning_diag["rule"] == "type_known"
    assert warning_diag["rule_id"] == "type_known"
    assert warning_diag["message"] == "unrecognized type"
    assert warning_diag["node"] == "start"
    assert warning_diag["node_id"] == "start"

    assert error_diag["rule"] == "edge_target_exists"
    assert error_diag["rule_id"] == "edge_target_exists"
    assert error_diag["message"] == "edge target does not exist"
    assert error_diag["edge"] == ["start", "missing"]
    assert error_diag["fix"] == "define node 'missing' or update edge"
    assert error_diag["node"] is None
    assert "node_id" in error_diag
    assert error_diag["node_id"] is None

    assert len(payload["errors"]) == 1
    assert payload["errors"][0] == error_diag


def test_start_pipeline_preserves_warning_and_info_diagnostics(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    monkeypatch.setattr(
        server,
        "_prepare_graph_for_server",
        lambda graph: (graph, _warning_info_diagnostics()),
    )

    response = attractor_api_client.post(
        "/pipelines",
        json={
            "flow_content": FLOW,
            "working_directory": str(tmp_path / "work"),
            "backend": "codex-app-server",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    try:
        assert payload["status"] == "started"
        assert payload["errors"] == []
        assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "info"]
    finally:
        if payload.get("pipeline_id"):
            server._pop_active_run(str(payload["pipeline_id"]))


def test_start_pipeline_validation_error_payload_shape(
    attractor_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server.configure_runtime_paths(runs_dir=tmp_path / "runs")
    monkeypatch.setattr(server.asyncio, "create_task", _close_task_immediately)
    monkeypatch.setattr(
        server,
        "_prepare_graph_for_server",
        lambda graph: (graph, _warning_error_diagnostics()),
    )

    response = attractor_api_client.post(
        "/pipelines",
        json={
            "flow_content": FLOW,
            "working_directory": str(tmp_path / "work"),
            "backend": "codex-app-server",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validation_error"
    assert [diag["severity"] for diag in payload["diagnostics"]] == ["warning", "error"]
    assert len(payload["errors"]) == 1

    warning_diag, error_diag = payload["diagnostics"]
    assert warning_diag["rule"] == "type_known"
    assert warning_diag["message"] == "unrecognized type"
    assert warning_diag["node"] == "start"
    assert warning_diag["node_id"] == "start"
    assert error_diag["rule"] == "edge_target_exists"
    assert error_diag["message"] == "edge target does not exist"
    assert error_diag["edge"] == ["start", "missing"]
    assert "node_id" in error_diag
    assert error_diag["node_id"] is None
    assert payload["errors"][0] == error_diag


def test_server_graph_prep_runs_stylesheet_transform_before_validation() -> None:
    flow = """
    digraph G {
        graph [model_stylesheet=".fast { llm_model: fast-model; }"]
        start [shape=Mdiamond]
        plan [shape=box, class="fast"]
        done [shape=Msquare]
        start -> plan -> done
    }
    """
    graph, diagnostics = server._prepare_graph_for_server(parse_dot(flow))

    assert [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR] == []
    assert graph.nodes["plan"].attrs["llm_model"].value == "fast-model"


def test_preview_applies_registered_custom_transform(attractor_api_client: TestClient) -> None:
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
        response = attractor_api_client.post("/preview", json={"flow_content": flow})
        assert response.status_code == 200
        payload = response.json()
        nodes_by_id = {str(node["id"]): node for node in payload["graph"]["nodes"]}
        assert nodes_by_id["task"]["prompt"] == "Build [custom]"
    finally:
        server.clear_registered_transforms()


def test_preview_applies_multiple_custom_transforms_in_registration_order(attractor_api_client: TestClient) -> None:
    class _AppendFirstTransform:
        def apply(self, graph):
            prompt_attr = graph.nodes["task"].attrs["prompt"]
            prompt_attr.value = f"{prompt_attr.value} [first]"
            return graph

    class _AppendSecondTransform:
        def apply(self, graph):
            prompt_attr = graph.nodes["task"].attrs["prompt"]
            prompt_attr.value = f"{prompt_attr.value} [second]"
            return graph

    flow = """
    digraph G {
        graph [goal="Ship Docs"]
        start [shape=Mdiamond]
        task [shape=box, prompt="Build $goal"]
        done [shape=Msquare]
        start -> task -> done
    }
    """

    server.clear_registered_transforms()
    try:
        server.register_transform(_AppendFirstTransform())
        server.register_transform(_AppendSecondTransform())
        response = attractor_api_client.post("/preview", json={"flow_content": flow})
        assert response.status_code == 200
        payload = response.json()
        nodes_by_id = {str(node["id"]): node for node in payload["graph"]["nodes"]}

        assert nodes_by_id["task"]["prompt"] == "Build Ship Docs [first] [second]"
    finally:
        server.clear_registered_transforms()


def test_preview_runs_custom_transforms_after_builtin_transforms(attractor_api_client: TestClient) -> None:
    class _BuiltInOrderingProbeTransform:
        def apply(self, graph):
            prompt_attr = graph.nodes["task"].attrs["prompt"]
            if "$goal" in str(prompt_attr.value):
                prompt_attr.value = f"{prompt_attr.value} [before-builtins]"
            else:
                prompt_attr.value = f"{prompt_attr.value} [after-builtins]"
            return graph

    flow = """
    digraph G {
        graph [goal="Ship Docs"]
        start [shape=Mdiamond]
        task [shape=box, prompt="Build $goal"]
        done [shape=Msquare]
        start -> task -> done
    }
    """

    server.clear_registered_transforms()
    try:
        server.register_transform(_BuiltInOrderingProbeTransform())
        response = attractor_api_client.post("/preview", json={"flow_content": flow})
        assert response.status_code == 200
        payload = response.json()
        nodes_by_id = {str(node["id"]): node for node in payload["graph"]["nodes"]}

        assert nodes_by_id["task"]["prompt"] == "Build Ship Docs [after-builtins]"
    finally:
        server.clear_registered_transforms()


def test_server_graph_prep_custom_transform_conflict_uses_later_registration_precedence() -> None:
    class _SetFirstModelTransform:
        def apply(self, graph):
            graph.nodes["task"].attrs["llm_model"] = DotAttribute(
                key="llm_model",
                value="first-model",
                value_type=DotValueType.STRING,
                line=0,
            )
            return graph

    class _SetSecondModelTransform:
        def apply(self, graph):
            graph.nodes["task"].attrs["llm_model"] = DotAttribute(
                key="llm_model",
                value="second-model",
                value_type=DotValueType.STRING,
                line=0,
            )
            return graph

    flow = """
    digraph G {
        graph [model_stylesheet="* { llm_model: base-model; }"]
        start [shape=Mdiamond]
        task [shape=box, prompt="Build"]
        done [shape=Msquare]
        start -> task -> done
    }
    """

    server.clear_registered_transforms()
    try:
        server.register_transform(_SetFirstModelTransform())
        server.register_transform(_SetSecondModelTransform())
        graph, diagnostics = server._prepare_graph_for_server(parse_dot(flow))
        assert [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR] == []
        assert graph.nodes["task"].attrs["llm_model"].value == "second-model"
    finally:
        server.clear_registered_transforms()


def test_preview_custom_transform_conflict_precedence_is_deterministic_across_runs(
    attractor_api_client: TestClient,
) -> None:
    class _StatefulFirstTransform:
        def __init__(self):
            self.count = 0

        def apply(self, graph):
            self.count += 1
            graph.nodes["task"].attrs["llm_model"] = DotAttribute(
                key="llm_model",
                value=f"first-{self.count}",
                value_type=DotValueType.STRING,
                line=0,
            )
            return graph

    class _StatefulSecondTransform:
        def __init__(self):
            self.count = 0

        def apply(self, graph):
            self.count += 1
            graph.nodes["task"].attrs["llm_model"] = DotAttribute(
                key="llm_model",
                value=f"second-{self.count}",
                value_type=DotValueType.STRING,
                line=0,
            )
            return graph

    flow = """
    digraph G {
        start [shape=Mdiamond]
        task [shape=box, prompt="Build"]
        done [shape=Msquare]
        start -> task -> done
    }
    """

    first = _StatefulFirstTransform()
    second = _StatefulSecondTransform()
    server.clear_registered_transforms()
    try:
        server.register_transform(first)
        server.register_transform(second)

        first_response = attractor_api_client.post("/preview", json={"flow_content": flow})
        second_response = attractor_api_client.post("/preview", json={"flow_content": flow})
        assert first_response.status_code == 200
        assert second_response.status_code == 200
        first_payload = first_response.json()
        second_payload = second_response.json()
        first_nodes = {str(node["id"]): node for node in first_payload["graph"]["nodes"]}
        second_nodes = {str(node["id"]): node for node in second_payload["graph"]["nodes"]}

        assert first_nodes["task"]["llm_model"] == "second-1"
        assert second_nodes["task"]["llm_model"] == "second-1"
    finally:
        server.clear_registered_transforms()


def test_build_transform_pipeline_uses_stable_custom_transform_snapshot(
) -> None:
    class _FirstTransform:
        def apply(self, graph):
            return graph

    class _LateTransform:
        def apply(self, graph):
            return graph

    first = _FirstTransform()
    late = _LateTransform()

    server.clear_registered_transforms()
    try:
        server.register_transform(first)
        pipeline = server._build_transform_pipeline()
        server.register_transform(late)
        custom_transforms = [t for t in pipeline.transforms if t in (first, late)]

        assert custom_transforms == [first]
    finally:
        server.clear_registered_transforms()
