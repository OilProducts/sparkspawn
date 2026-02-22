import unittest

from attractor.dsl import parse_dot, validate_graph
from attractor.dsl.models import DiagnosticSeverity


class TestDotValidator(unittest.TestCase):
    def _errors(self, diagnostics):
        return [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR]

    def test_start_exit_and_reachability_rules(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            done [shape=Msquare]
            orphan [shape=box]
            start -> done
        }
        """
        graph = parse_dot(dot)
        diagnostics = validate_graph(graph)

        rule_ids = {d.rule_id for d in diagnostics}
        self.assertIn("reachability", rule_ids)

    def test_edge_target_exists_and_start_incoming_exit_outgoing(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            done [shape=Msquare]
            helper [shape=box]

            helper -> start
            done -> helper
            start -> missing
        }
        """
        graph = parse_dot(dot)
        diagnostics = validate_graph(graph)
        rule_ids = [d.rule_id for d in diagnostics]

        self.assertIn("edge_target_exists", rule_ids)
        self.assertIn("start_no_incoming", rule_ids)
        self.assertIn("exit_no_outgoing", rule_ids)

    def test_condition_and_stylesheet_syntax(self):
        dot = """
        digraph G {
            graph [model_stylesheet="box model = x }"]
            start [shape=Mdiamond]
            done [shape=Msquare]
            a [shape=box]

            start -> a [condition="unknown=1"]
            a -> done
        }
        """
        graph = parse_dot(dot)
        diagnostics = validate_graph(graph)
        rule_ids = {d.rule_id for d in diagnostics}

        self.assertIn("condition_syntax", rule_ids)
        self.assertIn("stylesheet_syntax", rule_ids)

    def test_retry_target_and_fidelity_warnings(self):
        dot = """
        digraph G {
            graph [default_fidelity="invalid"]
            start [shape=Mdiamond]
            a [shape=box, retry_target="missing", fidelity="bad"]
            done [shape=Msquare]
            start -> a [fidelity="wrong"]
            a -> done
        }
        """
        graph = parse_dot(dot)
        diagnostics = validate_graph(graph)

        warning_rules = {d.rule_id for d in diagnostics if d.severity == DiagnosticSeverity.WARNING}
        self.assertIn("retry_target_exists", warning_rules)
        self.assertIn("fidelity_valid", warning_rules)

    def test_valid_minimal_graph(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            task [shape=box, prompt="do"]
            done [shape=Msquare]
            start -> task
            task -> done [condition="outcome=success"]
        }
        """
        graph = parse_dot(dot)
        diagnostics = validate_graph(graph)
        self.assertEqual([], self._errors(diagnostics))


if __name__ == "__main__":
    unittest.main()
