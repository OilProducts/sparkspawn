from __future__ import annotations

from pathlib import Path

from attractor.dsl import parse_dot


FLOW_PATH = Path(__file__).resolve().parents[2] / "src" / "spark" / "flows" / "implement-from-plan.dot"


def _prompt(node_id: str) -> str:
    graph = parse_dot(FLOW_PATH.read_text(encoding="utf-8"))
    node = graph.nodes[node_id]
    prompt_attr = node.attrs.get("prompt")
    assert prompt_attr is not None, f"missing prompt for {node_id}"
    return str(prompt_attr.value)


def _attr(node_id: str, attr_name: str) -> str:
    graph = parse_dot(FLOW_PATH.read_text(encoding="utf-8"))
    node = graph.nodes[node_id]
    attr = node.attrs.get(attr_name)
    assert attr is not None, f"missing {attr_name} for {node_id}"
    return str(attr.value)


def test_prepare_plan_workspace_uses_project_local_planflows_workspace() -> None:
    prompt = _prompt("prepare_plan_workspace")

    assert "Create .spark/planflows/" in prompt
    assert "choose a fresh workspace directory for this run" in prompt
    assert "<workspace_dir>/plan-source.md" in prompt
    assert "<workspace_dir>/state.json" in prompt
    assert ".spark/" in prompt


def test_prepare_plan_workspace_writes_planflow_context_paths() -> None:
    writes_context = _attr("prepare_plan_workspace", "spark.writes_context")

    assert "context.planflow.workspace_dir" in writes_context
    assert "context.planflow.plan_source_path" in writes_context
    assert "context.planflow.state_path" in writes_context


def test_implement_and_evaluate_read_planflow_context_paths() -> None:
    for node_id in ("implement", "evaluate"):
        prompt = _prompt(node_id)
        reads_context = _attr(node_id, "spark.reads_context")

        assert "context.planflow.workspace_dir" in prompt
        assert "context.planflow.plan_source_path" in prompt
        assert "context.planflow.state_path" in prompt
        assert "context.planflow.workspace_dir" in reads_context
        assert "context.planflow.plan_source_path" in reads_context
        assert "context.planflow.state_path" in reads_context
