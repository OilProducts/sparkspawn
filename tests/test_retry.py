from __future__ import annotations

import asyncio

import pytest

import unified_llm
from unified_llm import (
    AbortController,
    AbortSignal,
    AdapterTimeout,
    RetryPolicy,
    TimeoutConfig,
)
from unified_llm.errors import AbortError, ConfigurationError, RateLimitError, RequestTimeoutError
from unified_llm.retry import calculate_retry_delay, is_retryable_error
from unified_llm.retry import retry as retry_operation
from unified_llm.timeouts import (
    anext_with_timeout,
    await_with_timeout,
    check_abort,
    coerce_timeout_config,
)


def test_retry_policy_defaults_and_backoff_are_publicly_visible() -> None:
    policy = RetryPolicy()

    assert policy.max_retries == 2
    assert policy.base_delay == 1.0
    assert policy.max_delay == 60.0
    assert policy.backoff_multiplier == 2.0
    assert policy.jitter is True
    assert policy.on_retry is None
    assert calculate_retry_delay(policy, 0, random_source=lambda a, b: 1.0) == pytest.approx(1.0)
    assert calculate_retry_delay(policy, 1, random_source=lambda a, b: 1.0) == pytest.approx(2.0)
    assert calculate_retry_delay(policy, 10, random_source=lambda a, b: 1.0) == pytest.approx(60.0)
    assert calculate_retry_delay(policy, 0, random_source=lambda a, b: a) == pytest.approx(0.5)
    assert calculate_retry_delay(policy, 0, random_source=lambda a, b: b) == pytest.approx(1.5)


def test_retry_eligibility_tracks_public_error_metadata() -> None:
    assert is_retryable_error(RateLimitError("rate limited", provider="openai")) is True
    assert is_retryable_error(unified_llm.ServerError("boom", provider="openai")) is True
    assert is_retryable_error(unified_llm.NetworkError("network")) is True
    assert is_retryable_error(unified_llm.StreamError("stream")) is True
    assert is_retryable_error(ConfigurationError("bad config")) is False
    assert is_retryable_error(RequestTimeoutError("slow")) is False


@pytest.mark.asyncio
async def test_retry_retries_retryable_errors_and_calls_callbacks_before_sleep() -> None:
    calls = 0
    sleep_durations: list[float] = []
    callback_events: list[tuple[str, int, float]] = []

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RateLimitError("rate limited", provider="openai")
        return "ok"

    async def sleeper(delay: float) -> None:
        sleep_durations.append(delay)

    def on_retry(error: BaseException, attempt: int, delay: float) -> None:
        callback_events.append((type(error).__name__, attempt, delay))

    policy = RetryPolicy(max_retries=2, jitter=False, on_retry=on_retry)

    result = await retry_operation(operation, policy=policy, sleeper=sleeper)

    assert result == "ok"
    assert calls == 3
    assert sleep_durations == [1.0, 2.0]
    assert callback_events == [
        ("RateLimitError", 0, 1.0),
        ("RateLimitError", 1, 2.0),
    ]


@pytest.mark.asyncio
async def test_retry_handles_retry_after_cutoff_and_preserves_error_metadata() -> None:
    policy = RetryPolicy(jitter=False)
    retry_after = RateLimitError(
        "retry later",
        provider="openai",
        retry_after=61.0,
    )
    short_retry_after = RateLimitError(
        "retry later",
        provider="openai",
        retry_after=12.5,
    )

    assert policy.calculate_delay(0, error=short_retry_after) == pytest.approx(12.5)
    assert policy.calculate_delay(0, error=retry_after) is None

    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise retry_after

    with pytest.raises(RateLimitError) as excinfo:
        await retry_operation(operation, policy=policy, sleeper=lambda delay: None)

    assert calls == 1
    assert excinfo.value.retry_after == 61.0


@pytest.mark.asyncio
async def test_retry_zero_budget_and_custom_timeout_retry_predicate_are_opt_in() -> None:
    zero_budget_calls = 0

    async def zero_budget_operation() -> str:
        nonlocal zero_budget_calls
        zero_budget_calls += 1
        raise RateLimitError("rate limited", provider="openai")

    with pytest.raises(RateLimitError):
        await retry_operation(
            zero_budget_operation,
            policy=RetryPolicy(max_retries=0, jitter=False),
            sleeper=lambda delay: None,
        )

    assert zero_budget_calls == 1

    timeout_calls = 0

    async def timeout_operation() -> str:
        nonlocal timeout_calls
        timeout_calls += 1
        if timeout_calls == 1:
            raise RequestTimeoutError("timed out", timeout=0.1, scope="step")
        return "ok"

    with pytest.raises(RequestTimeoutError):
        await retry_operation(
            timeout_operation,
            policy=RetryPolicy(max_retries=1, jitter=False),
            sleeper=lambda delay: None,
        )

    timeout_calls = 0

    result = await retry_operation(
        timeout_operation,
        policy=RetryPolicy(max_retries=1, jitter=False),
        should_retry=lambda error: isinstance(error, RequestTimeoutError),
        sleeper=lambda delay: None,
    )

    assert result == "ok"
    assert timeout_calls == 2


@pytest.mark.asyncio
async def test_timeout_helpers_support_generation_and_stream_read_scopes() -> None:
    timeout = TimeoutConfig(total=30, per_step=5, stream_read=2)
    coerced = coerce_timeout_config(timeout)
    overridden = coerce_timeout_config(10, stream_read=1.5)

    assert timeout.total == 30.0
    assert timeout.per_step == 5.0
    assert timeout.stream_read == 2.0
    assert coerced is timeout
    assert overridden == TimeoutConfig(total=10.0, per_step=None, stream_read=1.5)
    assert AdapterTimeout() == AdapterTimeout(connect=10.0, request=120.0, stream_read=30.0)

    controller = AbortController()
    signal = controller.signal
    assert isinstance(signal, AbortSignal)
    assert not signal.aborted
    controller.abort("stop now")
    assert signal.aborted
    assert signal.reason == "stop now"

    with pytest.raises(AbortError):
        check_abort(signal)

    await asyncio.wait_for(signal.wait(), timeout=0.1)

    async def never_finishing() -> None:
        await asyncio.Event().wait()

    with pytest.raises(RequestTimeoutError) as excinfo:
        await await_with_timeout(never_finishing(), 0.0, scope="generation")

    assert excinfo.value.timeout == 0.0
    assert excinfo.value.scope == "generation"

    class _SlowIterator:
        def __aiter__(self) -> _SlowIterator:
            return self

        async def __anext__(self) -> str:
            await asyncio.Event().wait()
            raise StopAsyncIteration

    with pytest.raises(RequestTimeoutError) as stream_excinfo:
        await anext_with_timeout(_SlowIterator(), 0.0)

    assert stream_excinfo.value.timeout == 0.0
    assert stream_excinfo.value.scope == "stream_read"


@pytest.mark.asyncio
async def test_await_with_timeout_releases_abort_waiters_without_threadpool_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_in_executor_calls = 0
    original_run_in_executor = asyncio.BaseEventLoop.run_in_executor

    def counting_run_in_executor(self, executor, func, *args):
        nonlocal run_in_executor_calls
        run_in_executor_calls += 1
        return original_run_in_executor(self, executor, func, *args)

    monkeypatch.setattr(asyncio.BaseEventLoop, "run_in_executor", counting_run_in_executor)

    controller = AbortController()
    signal = controller.signal

    async def completed() -> str:
        return "ok"

    async def hanging() -> None:
        await asyncio.Event().wait()

    for _ in range(3):
        result = await await_with_timeout(
            completed(),
            1.0,
            scope="generation",
            abort_signal=signal,
        )
        assert result == "ok"
        assert len(signal._waiters) == 0

    with pytest.raises(RequestTimeoutError) as timeout_excinfo:
        await await_with_timeout(
            hanging(),
            0.0,
            scope="generation",
            abort_signal=signal,
        )

    assert timeout_excinfo.value.timeout == 0.0
    assert timeout_excinfo.value.scope == "generation"
    assert run_in_executor_calls == 0
    assert len(signal._waiters) == 0


def test_root_package_exposes_retry_and_timeout_primitives() -> None:
    assert unified_llm.RetryPolicy is RetryPolicy
    assert unified_llm.TimeoutConfig is TimeoutConfig
    assert unified_llm.AbortController is AbortController
    assert unified_llm.AbortSignal is AbortSignal
