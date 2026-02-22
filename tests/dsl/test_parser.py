import unittest

from attractor.dsl import DotParseError, parse_dot
from attractor.dsl.models import DotValueType, Duration


class TestDotParser(unittest.TestCase):
    def test_parse_basic_graph_with_typed_attrs_and_chained_edges(self):
        dot = """
        // graph comment
        digraph Demo {
            graph [goal="Ship", default_max_retry=5]
            node [shape=box, timeout=900s]
            edge [weight=2]

            start [shape=Mdiamond, label="Start"]
            plan [prompt="Plan for $goal"]
            done [shape=Msquare]

            start -> plan -> done [label="next"]
        }
        """
        graph = parse_dot(dot)

        self.assertEqual(graph.graph_id, "Demo")
        self.assertIn("goal", graph.graph_attrs)
        self.assertEqual(graph.graph_attrs["goal"].value, "Ship")
        self.assertEqual(graph.graph_attrs["default_max_retry"].value, 5)

        self.assertEqual(len(graph.edges), 2)
        self.assertEqual(graph.edges[0].source, "start")
        self.assertEqual(graph.edges[0].target, "plan")
        self.assertEqual(graph.edges[0].attrs["weight"].value, 2)
        self.assertEqual(graph.edges[0].attrs["label"].value, "next")

        plan_timeout = graph.nodes["plan"].attrs["timeout"]
        self.assertEqual(plan_timeout.value_type, DotValueType.DURATION)
        self.assertIsInstance(plan_timeout.value, Duration)
        self.assertEqual(plan_timeout.value.raw, "900s")

    def test_parse_subgraph_scope_defaults(self):
        dot = """
        digraph Scoped {
            start [shape=Mdiamond]
            done [shape=Msquare]

            subgraph cluster_loop {
                node [thread_id="loop-a", timeout=15m]
                plan [prompt="p"]
            }

            start -> plan -> done
        }
        """
        graph = parse_dot(dot)
        plan = graph.nodes["plan"]
        self.assertEqual(plan.attrs["thread_id"].value, "loop-a")
        self.assertEqual(plan.attrs["timeout"].value.raw, "15m")

    def test_reject_undirected_edges(self):
        dot = """
        digraph Bad {
            a -- b
        }
        """
        with self.assertRaises(DotParseError):
            parse_dot(dot)

    def test_reject_invalid_node_id(self):
        dot = """
        digraph Bad {
            bad-id [prompt="x"]
        }
        """
        with self.assertRaises(DotParseError):
            parse_dot(dot)

    def test_requires_commas_between_attributes(self):
        dot = """
        digraph Bad {
            a [shape=box timeout=900s]
        }
        """
        with self.assertRaises(DotParseError):
            parse_dot(dot)


if __name__ == "__main__":
    unittest.main()
