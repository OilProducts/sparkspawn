from pathlib import Path
import tempfile

from attractor.dsl import parse_dot
from attractor.engine.context import Context
from attractor.engine.outcome import OutcomeStatus
from attractor.handlers import HandlerRunner, build_default_registry

from tests.handlers._support.fakes import (
    _StubBackend,
    _FanInRankingBackend,
    _StageLoggingBackend,
)

class TestFanInHandler:
    def test_fan_in_uses_backend_ranking_when_prompt_present(self):
        graph = parse_dot(
            """
            digraph G {
                fan_in [shape=tripleoctagon, prompt="Rank the branch results"]
            }
            """
        )
        backend = _FanInRankingBackend('{"best_id":"branch_b"}')
        registry = build_default_registry(codergen_backend=backend)
        runner = HandlerRunner(graph, registry)
        context = Context(
            values={
                "parallel.results": [
                    {"id": "branch_a", "status": "success"},
                    {"id": "branch_b", "status": "success"},
                ]
            }
        )

        outcome = runner("fan_in", "Rank the branch results", context)

        assert outcome.status == OutcomeStatus.SUCCESS
        assert outcome.context_updates["parallel.fan_in.best_id"] == "branch_b"
        assert outcome.context_updates["parallel.fan_in.best_outcome"] == "success"
        assert len(backend.calls) == 1
        assert "Rank the branch results" in backend.calls[0]["prompt"]

    def test_fan_in_uses_heuristic_score_fallback_without_prompt(self):
        graph = parse_dot(
            """
            digraph G {
                fan_in [shape=tripleoctagon]
            }
            """
        )
        registry = build_default_registry(codergen_backend=_StubBackend())
        runner = HandlerRunner(graph, registry)
        context = Context(
            values={
                "parallel.results": [
                    {"id": "branch_a", "status": "success", "score": 0.2},
                    {"id": "branch_b", "status": "success", "score": 0.9},
                    {"id": "branch_c", "status": "partial_success", "score": 1.0},
                ]
            }
        )

        outcome = runner("fan_in", "", context)

        assert outcome.status == OutcomeStatus.SUCCESS
        assert outcome.context_updates["parallel.fan_in.best_id"] == "branch_b"
        assert outcome.context_updates["parallel.fan_in.best_outcome"] == "success"

    def test_fan_in_normalizes_parallel_pipeline_status_payloads(self):
        graph = parse_dot(
            """
            digraph G {
                fan_in [shape=tripleoctagon]
            }
            """
        )
        registry = build_default_registry(codergen_backend=_StubBackend())
        runner = HandlerRunner(graph, registry)
        context = Context(
            values={
                "parallel.results": [
                    {"id": "branch_a", "status": "completed", "outcome": "success", "score": 0.2},
                    {"id": "branch_b", "status": "completed", "outcome": "partial_success", "score": 1.0},
                    {"id": "branch_c", "status": "failed", "outcome": "", "score": 9.0},
                ]
            }
        )

        outcome = runner("fan_in", "", context)

        assert outcome.status == OutcomeStatus.SUCCESS
        assert outcome.context_updates["parallel.fan_in.best_id"] == "branch_a"
        assert outcome.context_updates["parallel.fan_in.best_outcome"] == "success"

    def test_fan_in_binds_stage_raw_rpc_logging_for_supporting_backends(self):
        graph = parse_dot(
            """
            digraph G {
                fan_in [shape=tripleoctagon, prompt="Rank the branch results"]
            }
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            logs_root = Path(tmp) / "logs"
            backend = _StageLoggingBackend('{"best_id":"branch_b"}')
            registry = build_default_registry(codergen_backend=backend)
            runner = HandlerRunner(graph, registry, logs_root=logs_root)
            context = Context(
                values={
                    "parallel.results": [
                        {"id": "branch_a", "status": "success"},
                        {"id": "branch_b", "status": "success"},
                    ]
                }
            )

            outcome = runner("fan_in", "Rank the branch results", context)

            assert outcome.status == OutcomeStatus.SUCCESS
            assert backend.run_bound is True
            assert backend.bind_calls == [("fan_in", logs_root)]
