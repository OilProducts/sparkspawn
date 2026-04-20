from __future__ import annotations

import json
from pathlib import Path

from attractor.dsl import parse_dot


FLOW_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "spark"
    / "flows"
    / "software-development"
    / "implement-change-request.dot"
)


def _graph():
    return parse_dot(FLOW_PATH.read_text(encoding="utf-8"))


def _json_array_attr(node_id: str, attr_name: str) -> set[str]:
    graph = _graph()
    node = graph.nodes[node_id]
    attr = node.attrs.get(attr_name)
    assert attr is not None, f"missing {attr_name} for {node_id}"
    parsed = json.loads(str(attr.value))
    assert isinstance(parsed, list)
    return {str(item) for item in parsed}


def _launch_input_keys() -> set[str]:
    graph = _graph()
    attr = graph.graph_attrs.get("spark.launch_inputs")
    assert attr is not None, "missing spark.launch_inputs"
    parsed = json.loads(str(attr.value))
    assert isinstance(parsed, list)
    return {str(item["key"]) for item in parsed if isinstance(item, dict) and "key" in item}


def test_change_request_flow_declares_change_request_launch_inputs() -> None:
    keys = _launch_input_keys()

    assert {
        "context.request.change_request_path",
        "context.request.change_request_id",
        "context.request.target_paths",
        "context.request.acceptance_criteria",
        "context.request.validation_command",
    } <= keys
    assert "context.request.plan_path" not in keys


def test_prepare_change_runtime_preserves_runtime_context_contract() -> None:
    reads_context = _json_array_attr("prepare_change_runtime", "spark.reads_context")
    writes_context = _json_array_attr("prepare_change_runtime", "spark.writes_context")

    assert {
        "context.request.change_request_path",
        "context.request.change_request_id",
        "context.request.target_paths",
        "context.request.acceptance_criteria",
        "context.request.validation_command",
    } <= reads_context
    assert {
        "context.change_request.id",
        "context.change_request.runtime_dir",
        "context.change_request.request_path",
        "context.change_request.result_path",
        "context.change_request.state_path",
    } <= writes_context


def test_implement_evaluate_and_record_result_read_change_request_runtime_context() -> None:
    expected_reads = {
        "context.change_request.id",
        "context.change_request.runtime_dir",
        "context.change_request.request_path",
        "context.change_request.state_path",
    }

    assert expected_reads <= _json_array_attr("implement", "spark.reads_context")
    assert expected_reads | {"context.change_request.result_path"} <= _json_array_attr(
        "evaluate",
        "spark.reads_context",
    )
    assert expected_reads | {"context.change_request.result_path"} <= _json_array_attr(
        "record_result",
        "spark.reads_context",
    )
