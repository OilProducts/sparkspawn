from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

import unified_llm
import unified_llm.middleware as middleware_mod


class _FakeStream:
    def __init__(self, events: list[unified_llm.StreamEvent]) -> None:
        self._events = iter(events)

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> unified_llm.StreamEvent:
        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeAdapter:
    def __init__(self, name: str = "fake") -> None:
        self.name = name
        self.complete_requests: list[unified_llm.Request] = []
        self.stream_requests: list[unified_llm.Request] = []

    async def complete(self, request: unified_llm.Request) -> unified_llm.Response:
        self.complete_requests.append(request)
        return unified_llm.Response(
            provider=self.name,
            model=request.model,
            message=unified_llm.Message.assistant(f"{self.name}:{request.provider}"),
        )

    def stream(self, request: unified_llm.Request) -> _FakeStream:
        self.stream_requests.append(request)
        return _FakeStream(
            [
                unified_llm.StreamEvent(
                    type=unified_llm.StreamEventType.TEXT_DELTA,
                    delta="first",
                ),
                unified_llm.StreamEvent(
                    type=unified_llm.StreamEventType.TEXT_DELTA,
                    delta="second",
                ),
            ]
        )


def _request() -> unified_llm.Request:
    return unified_llm.Request(
        model="gpt-5.2",
        messages=[unified_llm.Message.user("hello")],
    )


@pytest.mark.asyncio
async def test_client_complete_middleware_onion_order_and_response_replacement() -> None:
    adapter = _FakeAdapter()
    call_order: list[str] = []

    async def outer(
        request: unified_llm.Request,
        next_call: middleware_mod.CompleteNext,
    ) -> unified_llm.Response:
        call_order.append("outer:request")
        response = await next_call(request)
        call_order.append("outer:response")
        return response

    async def inner(
        request: unified_llm.Request,
        next_call: middleware_mod.CompleteNext,
    ) -> unified_llm.Response:
        call_order.append("inner:request")
        response = await next_call(request)
        call_order.append("inner:response")
        return replace(
            response,
            provider="replacement",
            message=unified_llm.Message.assistant("replacement"),
        )

    client = unified_llm.Client(
        providers={"fake": adapter},
        default_provider="fake",
        complete_middleware=[outer, inner],
    )

    response = await client.complete(_request())

    assert call_order == [
        "outer:request",
        "inner:request",
        "inner:response",
        "outer:response",
    ]
    assert response.provider == "replacement"
    assert response.text == "replacement"
    assert adapter.complete_requests[0].provider == "fake"


@pytest.mark.asyncio
async def test_client_stream_middleware_onion_order_and_event_transforms() -> None:
    adapter = _FakeAdapter()
    call_order: list[str] = []

    async def outer(
        request: unified_llm.Request,
        next_call: middleware_mod.StreamNext,
    ) -> AsyncIterator[unified_llm.StreamEvent]:
        call_order.append("outer:request")
        async for event in next_call(request):
            call_order.append(f"outer:event:{event.delta}")
            yield replace(event, delta=f"{event.delta}|outer")
        call_order.append("outer:response")

    async def inner(
        request: unified_llm.Request,
        next_call: middleware_mod.StreamNext,
    ) -> AsyncIterator[unified_llm.StreamEvent]:
        call_order.append("inner:request")
        async for event in next_call(request):
            call_order.append(f"inner:event:{event.delta}")
            yield replace(event, delta=f"{event.delta}|inner")
        call_order.append("inner:response")

    client = unified_llm.Client(
        providers={"fake": adapter},
        default_provider="fake",
        stream_middleware=[outer, inner],
    )

    events = [event async for event in client.stream(_request())]

    assert call_order == [
        "outer:request",
        "inner:request",
        "inner:event:first",
        "outer:event:first|inner",
        "inner:event:second",
        "outer:event:second|inner",
        "inner:response",
        "outer:response",
    ]
    assert [event.delta for event in events] == [
        "first|inner|outer",
        "second|inner|outer",
    ]
    assert adapter.stream_requests[0].provider == "fake"


@pytest.mark.asyncio
async def test_client_complete_logs_unexpected_middleware_failures_before_reraising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = _FakeAdapter()

    async def boom(
        request: unified_llm.Request,
        next_call: middleware_mod.CompleteNext,
    ) -> unified_llm.Response:
        raise RuntimeError("boom")

    client = unified_llm.Client(
        providers={"fake": adapter},
        default_provider="fake",
        complete_middleware=[boom],
    )

    with caplog.at_level(logging.ERROR, logger="unified_llm.middleware"):
        with pytest.raises(RuntimeError, match="boom"):
            await client.complete(_request())

    assert any(
        record.name == "unified_llm.middleware"
        and "Unexpected error executing complete middleware chain" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_client_stream_logs_unexpected_middleware_failures_before_reraising(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = _FakeAdapter()

    async def boom(
        request: unified_llm.Request,
        next_call: middleware_mod.StreamNext,
    ) -> AsyncIterator[unified_llm.StreamEvent]:
        raise RuntimeError("boom")

    client = unified_llm.Client(
        providers={"fake": adapter},
        default_provider="fake",
        stream_middleware=[boom],
    )

    with caplog.at_level(logging.ERROR, logger="unified_llm.middleware"):
        with pytest.raises(RuntimeError, match="boom"):
            [event async for event in client.stream(_request())]

    assert any(
        record.name == "unified_llm.middleware"
        and "Unexpected error executing stream middleware chain" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_client_complete_propagates_sdk_errors_without_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = _FakeAdapter()

    async def fail(
        request: unified_llm.Request,
        next_call: middleware_mod.CompleteNext,
    ) -> unified_llm.Response:
        raise unified_llm.ConfigurationError("bad config")

    client = unified_llm.Client(
        providers={"fake": adapter},
        default_provider="fake",
        complete_middleware=[fail],
    )

    with caplog.at_level(logging.ERROR, logger="unified_llm.middleware"):
        with pytest.raises(unified_llm.ConfigurationError, match="bad config"):
            await client.complete(_request())

    assert not caplog.records


@pytest.mark.asyncio
async def test_client_stream_propagates_sdk_errors_without_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = _FakeAdapter()

    async def fail(
        request: unified_llm.Request,
        next_call: middleware_mod.StreamNext,
    ) -> AsyncIterator[unified_llm.StreamEvent]:
        raise unified_llm.ConfigurationError("bad config")

    client = unified_llm.Client(
        providers={"fake": adapter},
        default_provider="fake",
        stream_middleware=[fail],
    )

    with caplog.at_level(logging.ERROR, logger="unified_llm.middleware"):
        with pytest.raises(unified_llm.ConfigurationError, match="bad config"):
            [event async for event in client.stream(_request())]

    assert not caplog.records
