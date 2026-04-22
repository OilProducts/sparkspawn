from __future__ import annotations

import asyncio

import pytest

import unified_llm


def _tool_call(
    call_id: str,
    name: str,
    arguments: str | dict[str, object],
    raw_arguments: str | None = None,
) -> unified_llm.ToolCall:
    if raw_arguments is None and isinstance(arguments, str):
        raw_arguments = arguments
    return unified_llm.ToolCall(
        id=call_id,
        name=name,
        arguments=arguments,
        raw_arguments=raw_arguments,
    )


class _SequencedStream:
    def __init__(self, events: list[object]) -> None:
        self._events = iter(events)
        self.closed = False

    def __aiter__(self) -> _SequencedStream:
        return self

    async def __anext__(self) -> unified_llm.StreamEvent:
        try:
            item = next(self._events)
        except StopIteration:
            raise StopAsyncIteration from None

        if isinstance(item, BaseException):
            raise item
        return item

    async def aclose(self) -> None:
        self.closed = True


class _SequencedStreamAdapter:
    def __init__(self, name: str, behaviors: list[object]) -> None:
        self.name = name
        self._behaviors = list(behaviors)
        self.stream_requests: list[unified_llm.Request] = []
        self.opened_streams: list[_SequencedStream] = []

    def stream(self, request: unified_llm.Request) -> _SequencedStream:
        self.stream_requests.append(request)
        if not self._behaviors:
            raise AssertionError(f"{self.name} received more stream requests than expected")

        behavior = self._behaviors.pop(0)
        if callable(behavior):
            behavior = behavior(request)
        if isinstance(behavior, BaseException):
            raise behavior
        if isinstance(behavior, _SequencedStream):
            self.opened_streams.append(behavior)
            return behavior

        stream = _SequencedStream(list(behavior))
        self.opened_streams.append(stream)
        return stream


def _text_delta(text: str) -> unified_llm.StreamEvent:
    return unified_llm.StreamEvent(
        type=unified_llm.StreamEventType.TEXT_DELTA,
        delta=text,
    )


def _tool_call_event(
    event_type: unified_llm.StreamEventType,
    call_id: str,
    name: str,
    arguments: str | dict[str, object],
) -> unified_llm.StreamEvent:
    return unified_llm.StreamEvent(
        type=event_type,
        tool_call=_tool_call(call_id, name, arguments),
    )


@pytest.mark.asyncio
async def test_stream_continues_multi_step_tool_loop_and_emits_step_finish(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def weather(city: str) -> dict[str, str]:
        return {"tool": "weather", "city": city}

    async def time(city: str) -> dict[str, str]:
        return {"tool": "time", "city": city}

    weather_tool = unified_llm.Tool.active(
        name="weather",
        description="Lookup weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=weather,
    )
    time_tool = unified_llm.Tool.active(
        name="time",
        description="Lookup time",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=time,
    )
    adapter = _SequencedStreamAdapter(
        "fake",
        [
            [
                _text_delta("Need tools"),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_START,
                    "call_weather",
                    "weather",
                    '{"city": "Par',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_DELTA,
                    "call_weather",
                    "weather",
                    'is"}',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_END,
                    "call_weather",
                    "weather",
                    '{"city": "Paris"}',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_START,
                    "call_time",
                    "time",
                    '{"city": "Par',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_DELTA,
                    "call_time",
                    "time",
                    'is"}',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_END,
                    "call_time",
                    "time",
                    '{"city": "Paris"}',
                ),
                unified_llm.StreamEvent(
                    type=unified_llm.StreamEventType.FINISH,
                    finish_reason=unified_llm.FinishReason(
                        reason=unified_llm.FinishReason.TOOL_CALLS,
                    ),
                    usage=unified_llm.Usage(),
                    response=unified_llm.Response(
                        model="gpt-5.2",
                        provider="fake",
                    ),
                ),
            ],
            [
                _text_delta("final answer"),
            ],
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")
    stream = unified_llm.stream(
        model="gpt-5.2",
        prompt="what should I do?",
        tools=[weather_tool, time_tool],
        client=client,
    )

    events = [event async for event in stream]
    response = await stream.response()
    await stream.close()

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
        "step_finish",
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[7].response.text == "Need tools"
    assert events[8].response.text == "Need tools"
    assert events[8].finish_reason.reason == "tool_calls"
    assert adapter.stream_requests[0].tool_choice is not None
    assert adapter.stream_requests[0].tool_choice.is_auto is True
    assert [message.role for message in adapter.stream_requests[1].messages] == [
        unified_llm.Role.USER,
        unified_llm.Role.ASSISTANT,
        unified_llm.Role.TOOL,
        unified_llm.Role.TOOL,
    ]
    assert adapter.stream_requests[1].messages[2].tool_call_id == "call_weather"
    assert adapter.stream_requests[1].messages[3].tool_call_id == "call_time"
    assert response.text == "final answer"
    assert stream.partial_response.text == "final answer"
    assert adapter.opened_streams[0].closed is True
    assert adapter.opened_streams[1].closed is True


@pytest.mark.asyncio
async def test_stream_does_not_retry_after_tool_loop_partial_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def weather(city: str) -> dict[str, str]:
        return {"tool": "weather", "city": city}

    weather_tool = unified_llm.Tool.active(
        name="weather",
        description="Lookup weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=weather,
    )
    adapter = _SequencedStreamAdapter(
        "fake",
        [
            [
                _text_delta("Need tools"),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_START,
                    "call_weather",
                    "weather",
                    '{"city": "Par',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_DELTA,
                    "call_weather",
                    "weather",
                    'is"}',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_END,
                    "call_weather",
                    "weather",
                    '{"city": "Paris"}',
                ),
                unified_llm.StreamEvent(
                    type=unified_llm.StreamEventType.FINISH,
                    finish_reason=unified_llm.FinishReason(
                        reason=unified_llm.FinishReason.TOOL_CALLS,
                    ),
                    usage=unified_llm.Usage(),
                    response=unified_llm.Response(
                        model="gpt-5.2",
                        provider="fake",
                    ),
                ),
            ],
            [unified_llm.RateLimitError("retry later", provider="fake")],
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")
    stream = unified_llm.stream(
        model="gpt-5.2",
        prompt="what should I do?",
        tools=[weather_tool],
        client=client,
        max_retries=1,
    )

    events = [event async for event in stream]
    response = await stream.response()
    await stream.close()

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
        "step_finish",
        unified_llm.StreamEventType.ERROR,
    ]
    assert events[-1].response is not None
    assert events[-1].response.text == "Need tools"
    assert events[-1].response.finish_reason.reason == "error"
    assert response.text == "Need tools"
    assert response.finish_reason.reason == "error"
    assert stream.partial_response.text == "Need tools"
    assert stream.partial_response.finish_reason.reason == "error"
    assert len(adapter.stream_requests) == 2
    assert adapter.opened_streams[0].closed is True


@pytest.mark.asyncio
async def test_stream_repairs_invalid_tool_arguments_and_preserves_ordering(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repair_started = asyncio.Event()
    release_repair = asyncio.Event()
    normal_started = asyncio.Event()
    release_normal = asyncio.Event()
    time_finished = asyncio.Event()
    completion_order: list[str] = []
    controller = unified_llm.AbortController()

    async def weather(city: str) -> dict[str, str]:
        completion_order.append("weather")
        return {"tool": "weather", "city": city}

    async def time(city: str) -> dict[str, str]:
        normal_started.set()
        await release_normal.wait()
        completion_order.append("time")
        time_finished.set()
        return {"tool": "time", "city": city}

    async def repair_tool_call(
        *,
        tool_call: unified_llm.ToolCall,
        tool_definition: unified_llm.Tool,
        validation_error_context: object,
        current_messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> dict[str, str]:
        repair_started.set()
        assert tool_call.name == "weather"
        assert tool_definition.name == "weather"
        assert tool_call_id == "call_weather"
        assert [message.role for message in current_messages] == [
            unified_llm.Role.USER,
        ]
        assert abort_signal is controller.signal
        assert "JSON" in str(validation_error_context).upper()
        await release_repair.wait()
        return {"city": "Paris"}

    weather_tool = unified_llm.Tool.active(
        name="weather",
        description="Lookup weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=weather,
    )
    time_tool = unified_llm.Tool.active(
        name="time",
        description="Lookup time",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=time,
    )
    adapter = _SequencedStreamAdapter(
        "fake",
        [
            [
                _text_delta("Need tools"),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_START,
                    "call_weather",
                    "weather",
                    "{not json",
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_DELTA,
                    "call_weather",
                    "weather",
                    "{not json",
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_END,
                    "call_weather",
                    "weather",
                    "{not json",
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_START,
                    "call_time",
                    "time",
                    '{"city": "Par',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_DELTA,
                    "call_time",
                    "time",
                    'is"}',
                ),
                _tool_call_event(
                    unified_llm.StreamEventType.TOOL_CALL_END,
                    "call_time",
                    "time",
                    '{"city": "Paris"}',
                ),
                unified_llm.StreamEvent(
                    type=unified_llm.StreamEventType.FINISH,
                    finish_reason=unified_llm.FinishReason(
                        reason=unified_llm.FinishReason.TOOL_CALLS,
                    ),
                    usage=unified_llm.Usage(),
                    response=unified_llm.Response(
                        model="gpt-5.2",
                        provider="fake",
                    ),
                ),
            ],
            [
                _text_delta("all done"),
                unified_llm.StreamEvent(
                    type=unified_llm.StreamEventType.FINISH,
                    finish_reason=unified_llm.FinishReason(
                        reason=unified_llm.FinishReason.STOP,
                    ),
                    usage=unified_llm.Usage(),
                    response=unified_llm.Response(
                        model="gpt-5.2",
                        provider="fake",
                    ),
                ),
            ],
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")
    stream = unified_llm.stream(
        model="gpt-5.2",
        prompt="what should I do?",
        tools=[weather_tool, time_tool],
        client=client,
        abort_signal=controller.signal,
        repair_tool_call=repair_tool_call,
    )

    events: list[unified_llm.StreamEvent] = []
    while True:
        event = await stream.__anext__()
        events.append(event)
        if event.type == unified_llm.StreamEventType.FINISH:
            break

    step_finish_task = asyncio.create_task(stream.__anext__())
    await asyncio.wait_for(
        asyncio.gather(repair_started.wait(), normal_started.wait()),
        timeout=0.5,
    )
    release_normal.set()
    await asyncio.wait_for(time_finished.wait(), timeout=0.5)
    assert completion_order == ["time"]
    release_repair.set()

    events.append(await step_finish_task)

    try:
        while True:
            events.append(await stream.__anext__())
    except StopAsyncIteration:
        pass

    response = await stream.response()
    await stream.close()

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert [event.type for event in events] == [
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.TOOL_CALL_START,
        unified_llm.StreamEventType.TOOL_CALL_DELTA,
        unified_llm.StreamEventType.TOOL_CALL_END,
        unified_llm.StreamEventType.FINISH,
        "step_finish",
        unified_llm.StreamEventType.TEXT_DELTA,
        unified_llm.StreamEventType.FINISH,
    ]
    assert events[7].response.text == "Need tools"
    assert events[8].response.text == "Need tools"
    assert events[8].finish_reason.reason == "tool_calls"
    assert response.text == "all done"
    assert stream.partial_response.text == "all done"
    assert completion_order == ["time", "weather"]
    assert len(adapter.stream_requests) == 2
    assert [message.role for message in adapter.stream_requests[1].messages] == [
        unified_llm.Role.USER,
        unified_llm.Role.ASSISTANT,
        unified_llm.Role.TOOL,
        unified_llm.Role.TOOL,
    ]
    assert [message.tool_call_id for message in adapter.stream_requests[1].messages[2:]] == [
        "call_weather",
        "call_time",
    ]
