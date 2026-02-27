from pathlib import Path

from attractor.dsl import parse_dot


def test_spec_smoke_pipeline_fixture_matches_structure() -> None:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "integration_smoke_pipeline.dot"
    assert fixture_path.exists(), f"Missing smoke pipeline fixture: {fixture_path}"

    graph = parse_dot(fixture_path.read_text(encoding="utf-8"))

    goal_attr = graph.graph_attrs.get("goal")
    assert goal_attr is not None
    assert goal_attr.value == "Create a hello world Python script"
    assert set(graph.nodes.keys()) == {"start", "plan", "implement", "review", "done"}
    assert len(graph.edges) == 6

    actual_edges = {
        (
            edge.source,
            edge.target,
            str(edge.attrs["condition"].value) if "condition" in edge.attrs else None,
            str(edge.attrs["label"].value) if "label" in edge.attrs else None,
        )
        for edge in graph.edges
    }
    assert actual_edges == {
        ("start", "plan", None, None),
        ("plan", "implement", None, None),
        ("implement", "review", "outcome=success", None),
        ("implement", "plan", "outcome=fail", "Retry"),
        ("review", "done", "outcome=success", None),
        ("review", "implement", "outcome=fail", "Fix"),
    }
