from attractor.engine.context import Context
from attractor.transforms import RuntimePreambleTransform


class TestRuntimePreambleTransform:
    def test_builds_non_full_preamble_for_handoff(self):
        context = Context(
            values={
                "graph.goal": "Ship docs",
                "internal.run_id": "run-123",
                "context.release": "v1",
                "context.tests_passed": True,
                "_attractor.node_outcomes": {"start": "success"},
            }
        )
        transform = RuntimePreambleTransform()

        preamble = transform.apply("compact", context, ["start"])

        assert "carryover:compact" in preamble
        assert "goal=Ship docs" in preamble
        assert "run_id=run-123" in preamble
        assert "completed=start:success" in preamble
        assert "- context.release=v1" in preamble
        assert "- context.tests_passed=true" in preamble

    def test_returns_empty_preamble_for_full_fidelity(self):
        context = Context(values={"graph.goal": "Ship docs", "internal.run_id": "run-123"})
        transform = RuntimePreambleTransform()

        assert transform.apply("full", context, ["start"]) == ""
