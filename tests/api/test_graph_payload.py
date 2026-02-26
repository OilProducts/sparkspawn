from __future__ import annotations

from attractor.api import server
from attractor.dsl import parse_dot


def test_graph_payload_defaults_label_to_empty_string() -> None:
    graph = parse_dot(
        """
        digraph G {
            start [shape=Mdiamond]
            done [shape=Msquare]
            start -> done
        }
        """
    )

    payload = server._graph_payload(graph)

    assert payload["graph_attrs"]["label"] == ""


def test_graph_payload_keeps_explicit_graph_label() -> None:
    graph = parse_dot(
        """
        digraph G {
            graph [label="Build Flow"]
            start [shape=Mdiamond]
            done [shape=Msquare]
            start -> done
        }
        """
    )

    payload = server._graph_payload(graph)

    assert payload["graph_attrs"]["label"] == "Build Flow"
