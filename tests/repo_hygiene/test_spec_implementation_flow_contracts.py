from __future__ import annotations

from pathlib import Path

from attractor.dsl import parse_dot


def test_spec_implementation_milestone_worker_routes_validation_through_assessment() -> None:
    dot_path = (
        Path(__file__).resolve().parents[2]
        / "starter-flows"
        / "spec-implementation"
        / "implement-milestone.dot"
    )
    graph = parse_dot(dot_path.read_text(encoding="utf-8"))

    assert "assess_validation" in graph.nodes

    validate_node = graph.nodes["validate_repo"]
    artifact_paths = str(validate_node.attrs["tool.artifacts.paths"].value)
    assert ".specflow/validation-plan.json" in artifact_paths
    assert ".specflow/validation-result.json" not in artifact_paths

    edge_targets = {
        (
            edge.source,
            edge.target,
            str(edge.attrs.get("label").value) if edge.attrs.get("label") is not None else "",
        )
        for edge in graph.edges
    }
    assert ("validate_repo", "assess_validation", "Assess Pass") in edge_targets
    assert ("validate_repo", "assess_validation", "Assess Fail") in edge_targets
    assert ("assess_validation", "review_current", "") in edge_targets
