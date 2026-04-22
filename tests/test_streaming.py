from __future__ import annotations

import unified_llm
from unified_llm.streaming import StreamAccumulator


def _tool_call(arguments: str | dict[str, object], raw_arguments: str | None = None):
    if raw_arguments is None and isinstance(arguments, str):
        raw_arguments = arguments
    if raw_arguments is None:
        raw_arguments = "{}"
    return unified_llm.ToolCall(
        id="call_123",
        name="lookup_weather",
        arguments=arguments,
        raw_arguments=raw_arguments,
        type="function",
    )


def test_stream_accumulator_builds_response_from_text_reasoning_tool_calls_and_finish_metadata(
) -> None:
    accumulator = StreamAccumulator(
        response=unified_llm.Response(
            id="resp_1",
            model="gpt-5.2",
            provider="openai",
        )
    )

    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TEXT_START,
            text_id="text-1",
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TEXT_DELTA,
            delta="Hello ",
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TEXT_DELTA,
            delta="world",
        )
    )
    accumulator.add(unified_llm.StreamEvent(type=unified_llm.StreamEventType.TEXT_END))
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.REASONING_START,
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.REASONING_DELTA,
            reasoning_delta="thinking",
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(type=unified_llm.StreamEventType.REASONING_END)
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TOOL_CALL_START,
            tool_call=_tool_call('{"location": "Par'),
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TOOL_CALL_DELTA,
            tool_call=_tool_call('is"}'),
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TOOL_CALL_END,
            tool_call=_tool_call('{"location": "Paris"}'),
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.PROVIDER_EVENT,
            raw={"provider": "delta"},
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type="step_finish",
            raw={"step": "complete"},
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.FINISH,
            finish_reason=unified_llm.FinishReason(
                reason=unified_llm.FinishReason.STOP,
                raw="end_turn",
            ),
            usage=unified_llm.Usage(
                input_tokens=1,
                output_tokens=2,
                total_tokens=3,
            ),
            response=unified_llm.Response(
                id="resp_1",
                model="gpt-5.2",
                provider="openai",
                raw={"finish": True},
            ),
        )
    )

    response = accumulator.response

    assert response.id == "resp_1"
    assert response.model == "gpt-5.2"
    assert response.provider == "openai"
    assert response.text == "Hello world"
    assert response.reasoning == "thinking"
    assert response.finish_reason.reason == "stop"
    assert response.finish_reason.raw == "end_turn"
    assert response.usage.total_tokens == 3
    assert response.raw == {"finish": True}
    assert response.tool_calls[0].id == "call_123"
    assert response.tool_calls[0].arguments == {"location": "Paris"}
    assert response.tool_calls[0].raw_arguments == '{"location": "Paris"}'
    assert accumulator.text == "Hello world"
    assert accumulator.reasoning == "thinking"
    assert [
        event.delta
        for event in accumulator.events
        if event.type == unified_llm.StreamEventType.TEXT_DELTA
    ] == ["Hello ", "world"]
    assert accumulator.raw_events == [
        {"provider": "delta"},
        {"step": "complete"},
    ]

    finish_event = accumulator.finish_event
    assert finish_event is not None
    assert finish_event.type == unified_llm.StreamEventType.FINISH
    assert finish_event.finish_reason.reason == "stop"
    assert finish_event.usage.total_tokens == 3
    assert finish_event.response.raw == {"finish": True}
    assert finish_event.response.text == "Hello world"


def test_stream_accumulator_records_error_state_without_losing_partial_response() -> None:
    accumulator = StreamAccumulator()
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.TEXT_DELTA,
            delta="partial",
        )
    )
    accumulator.add(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.ERROR,
            error=unified_llm.SDKError("boom"),
            raw={"error": "boom"},
        )
    )

    assert accumulator.error is not None
    assert accumulator.error.message == "boom"
    assert accumulator.finish_reason.reason == "error"
    assert accumulator.response.text == "partial"
    assert accumulator.finish_event is not None
    assert accumulator.finish_event.type == unified_llm.StreamEventType.ERROR
    assert accumulator.finish_event.response.text == "partial"
