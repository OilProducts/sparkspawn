from attractor.dsl import parse_dot
from attractor.engine.context import Context
from attractor.engine.executor import PipelineExecutor
from attractor.engine.outcome import Outcome, OutcomeStatus


def _runner(node_id: str, prompt: str, context: Context) -> Outcome:
    return Outcome(status=OutcomeStatus.SUCCESS)


def test_retry_policy_object_uses_max_attempts_from_node_max_retries():
    graph = parse_dot(
        """
        digraph G {
            start [shape=Mdiamond]
            task [shape=box, max_retries=2]
            done [shape=Msquare]
            start -> task
            task -> done
        }
        """
    )

    executor = PipelineExecutor(graph, _runner)

    policy = executor._retry_policy_for_node("task")

    assert policy.max_attempts == 3
    assert policy.backoff.initial_delay_ms == 200
    assert policy.backoff.backoff_factor == 2.0
    assert policy.backoff.max_delay_ms == 60000
    assert policy.backoff.jitter is True


def test_retry_policy_should_retry_for_retry_and_retryable_fail():
    graph = parse_dot(
        """
        digraph G {
            start [shape=Mdiamond]
            task [shape=box, max_retries=1]
            done [shape=Msquare]
            start -> task
            task -> done
        }
        """
    )

    executor = PipelineExecutor(graph, _runner)

    policy = executor._retry_policy_for_node("task")

    assert policy.should_retry(Outcome(status=OutcomeStatus.RETRY)) is True
    assert policy.should_retry(Outcome(status=OutcomeStatus.FAIL, retryable=True)) is True
    assert policy.should_retry(Outcome(status=OutcomeStatus.FAIL, retryable=False)) is False
    assert policy.should_retry(Outcome(status=OutcomeStatus.SUCCESS)) is False
