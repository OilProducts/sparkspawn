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


def test_spec_implementation_parent_flow_commits_after_milestone_acceptance() -> None:
    dot_path = (
        Path(__file__).resolve().parents[2]
        / "starter-flows"
        / "spec-implementation"
        / "implement-spec.dot"
    )
    graph = parse_dot(dot_path.read_text(encoding="utf-8"))

    assert "commit_milestone" in graph.nodes

    commit_node = graph.nodes["commit_milestone"]
    assert str(commit_node.attrs["shape"].value) == "parallelogram"
    assert "git commit -m" in str(commit_node.attrs["tool.command"].value)

    audit_prompt = str(graph.nodes["audit_milestone"].attrs["prompt"].value)
    assert "keep the current milestone metadata available" in audit_prompt

    edge_targets = {
        (
            edge.source,
            edge.target,
            str(edge.attrs.get("label").value) if edge.attrs.get("label") is not None else "",
        )
        for edge in graph.edges
    }
    assert ("audit_milestone", "commit_milestone", "Commit") in edge_targets
    assert ("commit_milestone", "next_milestone", "Continue") in edge_targets
    assert ("commit_milestone", "blocked_exit", "Commit Failed") in edge_targets
