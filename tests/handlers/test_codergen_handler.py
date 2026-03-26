import json
import tempfile
from pathlib import Path

from attractor.dsl import parse_dot
from attractor.engine.context import Context
from attractor.engine.outcome import Outcome, OutcomeStatus
from attractor.handlers import HandlerRunner, build_default_registry
from attractor.handlers.builtin.codergen import STATUS_ENVELOPE_PROMPT_APPENDIX

from tests.handlers._support.fakes import (
    _StubBackend,
    _ArtifactProbeBackend,
    _TextBackend,
    _OutcomeBackend,
)


class TestCodergenHandler:
    def test_codergen_handler_calls_backend(self):
        graph = parse_dot(
            """
            digraph G {
                start [shape=Mdiamond]
                task [shape=box, prompt="Plan for $goal"]
                done [shape=Msquare]
                start -> task
                task -> done
            }
            """
        )

        backend = _StubBackend(ok=True)
        registry = build_default_registry(codergen_backend=backend)
        runner = HandlerRunner(graph, registry)
        ctx = Context(values={"graph.goal": "ship"})

        outcome = runner("task", "Plan for $goal", ctx)
        assert outcome.status == OutcomeStatus.SUCCESS
        assert backend.calls[0][1] == "Plan for ship"

    def test_codergen_handler_prepends_runtime_carryover_to_rendered_prompt(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )

        backend = _StubBackend(ok=True)
        registry = build_default_registry(codergen_backend=backend)
        runner = HandlerRunner(graph, registry)
        ctx = Context(
            values={
                "graph.goal": "ship",
                "_attractor.runtime.context_carryover": "carryover:summary:high\ncontext.review.required_changes=add tests",
            }
        )

        outcome = runner("task", "Plan for $goal", ctx)

        assert outcome.status == OutcomeStatus.SUCCESS
        assert backend.calls[0][1] == (
            "Context carryover:\n\n"
            "carryover:summary:high\n"
            "context.review.required_changes=add tests\n\n"
            "Current stage task:\n\n"
            "Plan for ship"
        )

    def test_codergen_handler_expands_goal_from_graph_attr_when_context_missing(self):
        graph = parse_dot(
            """
            digraph G {
                graph [goal="Ship docs"]
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )

        backend = _StubBackend(ok=True)
        registry = build_default_registry(codergen_backend=backend)
        runner = HandlerRunner(graph, registry)

        outcome = runner("task", "Plan for $goal", Context())
        assert outcome.status == OutcomeStatus.SUCCESS
        assert backend.calls[0][1] == "Plan for Ship docs"

    def test_codergen_handler_appends_status_envelope_contract_when_configured(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal", codergen.response_contract="status_envelope"]
            }
            """
        )

        backend = _StubBackend(ok=True)
        registry = build_default_registry(codergen_backend=backend)
        runner = HandlerRunner(graph, registry)

        outcome = runner("task", "Plan for $goal", Context(values={"graph.goal": "ship"}))

        assert outcome.status == OutcomeStatus.SUCCESS
        assert backend.calls[0][1] == f"Plan for ship\n\n{STATUS_ENVELOPE_PROMPT_APPENDIX}"

    def test_codergen_handler_falls_back_to_label_when_prompt_is_empty(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, label="Label Prompt"]
            }
            """
        )

        backend = _StubBackend(ok=True)
        registry = build_default_registry(codergen_backend=backend)
        runner = HandlerRunner(graph, registry)

        outcome = runner("task", "", Context())
        assert outcome.status == OutcomeStatus.SUCCESS
        assert backend.calls[0][1] == "Label Prompt"

    def test_codergen_handler_returns_simulation_response_when_backend_absent(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )

        with tempfile.TemporaryDirectory() as tmp:
            logs_root = Path(tmp) / "logs"
            registry = build_default_registry(codergen_backend=None)
            runner = HandlerRunner(graph, registry, logs_root=logs_root)

            outcome = runner("task", "Plan for $goal", Context(values={"graph.goal": "ship"}))

            assert outcome.status == OutcomeStatus.SUCCESS
            assert outcome.notes == "Stage completed: task"
            assert outcome.context_updates == {
                "last_response": "[Simulated] Response for stage: task",
                "last_stage": "task",
            }
            response_path = logs_root / "task" / "response.md"
            assert response_path.exists()
            assert response_path.read_text(encoding="utf-8").strip() == "[Simulated] Response for stage: task"

    def test_codergen_handler_supports_backend_outcome_response(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )

        backend_outcome = Outcome(
            status=OutcomeStatus.RETRY,
            notes="please retry",
            suggested_next_ids=["fallback_stage"],
            context_updates={"work.last": "task"},
        )
        registry = build_default_registry(codergen_backend=_OutcomeBackend(backend_outcome))
        runner = HandlerRunner(graph, registry)

        outcome = runner("task", "Plan for $goal", Context(values={"graph.goal": "ship"}))

        assert outcome is backend_outcome
        assert outcome.status == OutcomeStatus.RETRY
        assert outcome.notes == "please retry"
        assert outcome.suggested_next_ids == ["fallback_stage"]
        assert outcome.context_updates == {
            "last_response": "please retry",
            "last_stage": "task",
            "work.last": "task",
        }

    def test_codergen_handler_supports_backend_text_response(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )

        with tempfile.TemporaryDirectory() as tmp:
            logs_root = Path(tmp) / "logs"
            backend = _TextBackend("backend text response")
            registry = build_default_registry(codergen_backend=backend)
            runner = HandlerRunner(graph, registry, logs_root=logs_root)

            outcome = runner("task", "Plan for $goal", Context(values={"graph.goal": "ship"}))

            assert outcome.status == OutcomeStatus.SUCCESS
            assert outcome.context_updates == {
                "last_response": "backend text response",
                "last_stage": "task",
            }
            response_path = logs_root / "task" / "response.md"
            assert response_path.exists()
            assert response_path.read_text(encoding="utf-8").strip() == "backend text response"

    def test_codergen_handler_writes_prompt_before_backend_and_response_afterward(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )

        with tempfile.TemporaryDirectory() as tmp:
            logs_root = Path(tmp) / "logs"
            backend = _ArtifactProbeBackend(logs_root)
            registry = build_default_registry(codergen_backend=backend)
            runner = HandlerRunner(graph, registry, logs_root=logs_root)
            ctx = Context(values={"graph.goal": "ship"})

            outcome = runner("task", "Plan for $goal", ctx)

            assert outcome.status == OutcomeStatus.SUCCESS
            assert backend.prompt_exists_during_call is True
            assert backend.prompt_text_during_call == "Plan for ship"
            assert backend.response_exists_during_call is False
            response_path = logs_root / "task" / "response.md"
            assert response_path.exists()
            assert response_path.read_text(encoding="utf-8").strip() == "codergen backend success"

    def test_codergen_handler_writes_status_json_from_final_outcome(self):
        graph = parse_dot(
            """
            digraph G {
                task [shape=box, prompt="Plan for $goal"]
            }
            """
        )
        backend_outcome = Outcome(
            status=OutcomeStatus.PARTIAL_SUCCESS,
            preferred_label="continue",
            suggested_next_ids=["followup"],
            context_updates={"work.last": "task"},
            notes="backend returned partial",
        )

        with tempfile.TemporaryDirectory() as tmp:
            logs_root = Path(tmp) / "logs"
            registry = build_default_registry(codergen_backend=_OutcomeBackend(backend_outcome))
            runner = HandlerRunner(graph, registry, logs_root=logs_root)

            outcome = runner("task", "Plan for $goal", Context(values={"graph.goal": "ship"}))

            assert outcome is backend_outcome
            status_path = logs_root / "task" / "status.json"
            assert status_path.exists()
            assert json.loads(status_path.read_text(encoding="utf-8")) == {
                "context_updates": {
                    "last_response": "backend returned partial",
                    "last_stage": "task",
                    "work.last": "task",
                },
                "notes": "backend returned partial",
                "outcome": "partial_success",
                "preferred_label": "continue",
                "suggested_next_ids": ["followup"],
            }
