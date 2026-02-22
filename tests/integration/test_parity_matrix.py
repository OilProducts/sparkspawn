import unittest

from attractor.dsl import DiagnosticSeverity, parse_dot, validate_graph
from attractor.engine import Context, PipelineExecutor
from attractor.engine.outcome import Outcome, OutcomeStatus
from attractor.handlers import HandlerRunner, build_default_registry
from attractor.handlers.registry import HandlerRegistry
from attractor.interviewer import Answer, QueueInterviewer
from attractor.transforms import GoalVariableTransform, ModelStylesheetTransform, TransformPipeline


class _Backend:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def run(self, node_id, prompt, context):
        self.calls.append((node_id, prompt))
        value = self.plan.get(node_id, True)
        if isinstance(value, list):
            idx = sum(1 for n, _ in self.calls if n == node_id) - 1
            idx = min(idx, len(value) - 1)
            return bool(value[idx])
        return bool(value)


class _FlakyHandler:
    def __init__(self):
        self.calls = 0

    def run(self, runtime):
        self.calls += 1
        if self.calls <= 2:
            return Outcome(status=OutcomeStatus.RETRY, failure_reason="temporary")
        return Outcome(status=OutcomeStatus.SUCCESS)


class _ContextWriterHandler:
    def run(self, runtime):
        return Outcome(status=OutcomeStatus.SUCCESS, context_updates={"artifact_path": "/tmp/out"})


class _ContextReaderHandler:
    def run(self, runtime):
        seen = runtime.context.get("artifact_path", "")
        if seen == "/tmp/out":
            return Outcome(status=OutcomeStatus.SUCCESS)
        return Outcome(status=OutcomeStatus.FAIL, failure_reason="missing context")


class TestParityMatrixSubset(unittest.TestCase):
    def test_parse_simple_linear_pipeline(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            A [shape=box]
            B [shape=box]
            done [shape=Msquare]
            start -> A -> B -> done
        }
        """
        graph = parse_dot(dot)
        self.assertEqual(4, len(graph.nodes))
        self.assertEqual(3, len(graph.edges))

    def test_validate_missing_start(self):
        dot = """
        digraph G {
            A [shape=box]
            done [shape=Msquare]
            A -> done
        }
        """
        diagnostics = validate_graph(parse_dot(dot))
        error_rules = {d.rule_id for d in diagnostics if d.severity == DiagnosticSeverity.ERROR}
        self.assertIn("start_node", error_rules)

    def test_execute_linear_pipeline_end_to_end(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            plan [shape=box, prompt="plan"]
            implement [shape=box, prompt="impl"]
            done [shape=Msquare]
            start -> plan -> implement -> done
        }
        """
        graph = parse_dot(dot)
        backend = _Backend({"start": True, "plan": True, "implement": True})
        registry = build_default_registry(codergen_backend=backend)
        result = PipelineExecutor(graph, HandlerRunner(graph, registry)).run(Context())
        self.assertEqual("success", result.status)
        self.assertEqual(["start", "plan", "implement"], result.completed_nodes)

    def test_execute_conditional_branching_success_fail_paths(self):
        dot = """
        digraph G {
            graph [default_max_retry=0]
            start [shape=Mdiamond]
            gate [shape=box]
            fix [shape=box]
            done [shape=Msquare]
            start -> gate
            gate -> done [condition="outcome=success"]
            gate -> fix [condition="outcome=fail"]
            fix -> done
        }
        """
        graph = parse_dot(dot)
        backend = _Backend({"start": True, "gate": False, "fix": True})
        registry = build_default_registry(codergen_backend=backend)
        result = PipelineExecutor(graph, HandlerRunner(graph, registry)).run(Context())
        self.assertEqual("success", result.status)
        self.assertIn("fix", result.completed_nodes)

    def test_retry_on_failure_max_retries(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            flaky [shape=box, type="flaky", max_retries=2]
            done [shape=Msquare]
            start -> flaky
            flaky -> done
        }
        """
        graph = parse_dot(dot)
        registry = HandlerRegistry()
        registry.handlers = build_default_registry(codergen_backend=_Backend({})).handlers.copy()
        flaky = _FlakyHandler()
        registry.register("flaky", flaky)

        result = PipelineExecutor(graph, HandlerRunner(graph, registry)).run(Context())
        self.assertEqual("success", result.status)
        self.assertEqual(3, flaky.calls)

    def test_wait_human_routes_on_selection(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            gate [shape=hexagon]
            ship [shape=box]
            fix [shape=box]
            done [shape=Msquare]
            start -> gate
            gate -> ship [label="Approve"]
            gate -> fix [label="Fix"]
            ship -> done
            fix -> done
        }
        """
        graph = parse_dot(dot)
        interviewer = QueueInterviewer([Answer(selected_values=["Fix"])])
        registry = build_default_registry(codergen_backend=_Backend({"start": True, "fix": True}), interviewer=interviewer)
        result = PipelineExecutor(graph, HandlerRunner(graph, registry)).run(Context())
        self.assertEqual("success", result.status)
        self.assertIn("fix", result.completed_nodes)

    def test_context_updates_visible_next_node(self):
        dot = """
        digraph G {
            start [shape=Mdiamond]
            writer [shape=box, type="ctx.write"]
            reader [shape=box, type="ctx.read"]
            done [shape=Msquare]
            start -> writer -> reader -> done
        }
        """
        graph = parse_dot(dot)
        registry = HandlerRegistry()
        registry.handlers = build_default_registry(codergen_backend=_Backend({})).handlers.copy()
        registry.register("ctx.write", _ContextWriterHandler())
        registry.register("ctx.read", _ContextReaderHandler())

        result = PipelineExecutor(graph, HandlerRunner(graph, registry)).run(Context())
        self.assertEqual("success", result.status)

    def test_stylesheet_and_goal_variable_transforms(self):
        graph = parse_dot(
            """
            digraph G {
                graph [goal="hello", model_stylesheet="box { model = gpt-5; }"]
                start [shape=Mdiamond]
                task [shape=box, prompt="Do $goal"]
                done [shape=Msquare]
                start -> task -> done
            }
            """
        )

        pipeline = TransformPipeline()
        pipeline.register(GoalVariableTransform())
        pipeline.register(ModelStylesheetTransform())
        graph = pipeline.apply(graph)

        self.assertEqual("Do hello", graph.nodes["task"].attrs["prompt"].value)
        self.assertEqual("gpt-5", graph.nodes["task"].attrs["llm_model"].value)

    def test_pipeline_with_10_nodes(self):
        parts = ["digraph G {"]
        parts.append("start [shape=Mdiamond]")
        for i in range(1, 11):
            parts.append(f"n{i} [shape=box]")
        parts.append("done [shape=Msquare]")
        parts.append("start -> n1")
        for i in range(1, 10):
            parts.append(f"n{i} -> n{i+1}")
        parts.append("n10 -> done")
        parts.append("}")
        dot = "\n".join(parts)

        graph = parse_dot(dot)
        registry = build_default_registry(codergen_backend=_Backend({}))
        result = PipelineExecutor(graph, HandlerRunner(graph, registry)).run(Context())
        self.assertEqual("success", result.status)
        self.assertEqual(11, len(result.completed_nodes))


if __name__ == "__main__":
    unittest.main()
