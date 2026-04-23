from __future__ import annotations

import inspect
import logging

import pytest

import unified_llm
from unified_llm.errors import NoObjectGeneratedError


def _text_delta(text: str) -> unified_llm.StreamEvent:
    return unified_llm.StreamEvent(
        type=unified_llm.StreamEventType.TEXT_DELTA,
        delta=text,
    )


def _provider_event(raw: object) -> unified_llm.StreamEvent:
    return unified_llm.StreamEvent(
        type=unified_llm.StreamEventType.PROVIDER_EVENT,
        raw=raw,
    )


class _SequencedStream:
    def __init__(
        self,
        events: list[object],
        *,
        close_error: BaseException | None = None,
    ) -> None:
        self._events = iter(events)
        self.close_error = close_error
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
        if self.close_error is not None:
            raise self.close_error


class _SequencedCompleteAdapter:
    def __init__(self, name: str, behaviors: list[object]) -> None:
        self.name = name
        self._behaviors = list(behaviors)
        self.complete_requests: list[unified_llm.Request] = []

    async def complete(self, request: unified_llm.Request) -> unified_llm.Response:
        self.complete_requests.append(request)
        if not self._behaviors:
            raise AssertionError(f"{self.name} received more requests than expected")

        behavior = self._behaviors.pop(0)
        if callable(behavior):
            behavior = behavior(request)
        if isinstance(behavior, BaseException):
            raise behavior
        if inspect.isawaitable(behavior):
            behavior = await behavior
        return behavior


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


def _text_response(
    *,
    provider: str,
    request: unified_llm.Request,
    text: str,
) -> unified_llm.Response:
    return unified_llm.Response(
        provider=provider,
        model=request.model,
        message=unified_llm.Message.assistant(text),
        finish_reason=unified_llm.FinishReason(
            reason=unified_llm.FinishReason.STOP,
        ),
        usage=unified_llm.Usage(),
    )


def _structured_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_generate_object_builds_provider_strategy_metadata_and_returns_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _structured_schema()
    adapter = _SequencedCompleteAdapter(
        "openai",
        [
            lambda request: _text_response(
                provider="openai",
                request=request,
                text='{"name":"Alice","age":30}',
            )
        ],
    )
    client = unified_llm.Client(providers={"openai": adapter}, default_provider="openai")

    result = await unified_llm.generate_object(
        model="gpt-5.2",
        prompt="extract the object",
        schema=schema,
        provider="openai",
        provider_options={"openai": {"reasoning": {"effort": "high"}}},
        client=client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert isinstance(result, unified_llm.GenerateResult)
    assert result.output == {"name": "Alice", "age": 30}
    assert result.response.text == '{"name":"Alice","age":30}'
    assert len(adapter.complete_requests) == 1

    request = adapter.complete_requests[0]
    assert request.provider == "openai"
    assert request.response_format == unified_llm.ResponseFormat(
        type="json_schema",
        json_schema=schema,
        strict=True,
    )
    assert request.provider_options["openai"]["reasoning"] == {"effort": "high"}
    assert request.provider_options["openai"]["response_format"] == {
        "type": "json_schema",
        "json_schema": schema,
        "strict": True,
    }
    assert request.provider_options["openai"]["structured_output"]["strategy"] == "json_schema"
    assert request.provider_options["gemini"]["responseMimeType"] == "application/json"
    assert request.provider_options["gemini"]["responseSchema"] == schema
    assert request.provider_options["gemini"]["structured_output"]["strategy"] == "responseSchema"
    assert request.provider_options["anthropic"]["structured_output"]["strategy"] == (
        "schema-instruction"
    )
    assert request.provider_options["anthropic"]["structured_output"]["fallback"] == "forced-tool"
    assert request.provider_options["anthropic"]["system_instruction"] == (
        "Return only valid JSON that matches the provided schema."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected_log"),
    [
        ('{"name":"Alice","age":30', "parse"),
        ('{"name":"Alice","age":"30"}', "validation"),
    ],
)
async def test_generate_object_raises_no_object_generated_error_without_retry(
    text: str,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _structured_schema()
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _text_response(
                provider="fake",
                request=request,
                text=text,
            )
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    with caplog.at_level(logging.DEBUG, logger="unified_llm.structured"):
        with pytest.raises(NoObjectGeneratedError):
            await unified_llm.generate_object(
                model="gpt-5.2",
                prompt="extract the object",
                schema=schema,
                provider="fake",
                client=client,
                max_retries=2,
            )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert len(adapter.complete_requests) == 1
    assert any(expected_log in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_stream_object_yields_partial_objects_and_returns_final_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _structured_schema()
    adapter = _SequencedStreamAdapter(
        "gemini",
        [
            [
                _text_delta('{"name":"Alice",'),
                _provider_event({"kind": "noise"}),
                _text_delta('"age":30}'),
            ]
        ],
    )
    client = unified_llm.Client(providers={"gemini": adapter}, default_provider="gemini")

    stream = unified_llm.stream_object(
        model="gpt-5.2",
        prompt="extract the object",
        schema=schema,
        provider="gemini",
        provider_options={"gemini": {"temperature": 0.1}},
        client=client,
    )

    assert isinstance(stream, unified_llm.StreamResult)

    partials = [partial async for partial in stream]
    response = await stream.response()
    final_object = await stream.object()

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert partials == [
        {"name": "Alice"},
        {"name": "Alice", "age": 30},
    ]
    assert response.text == '{"name":"Alice","age":30}'
    assert final_object == {"name": "Alice", "age": 30}
    assert stream.partial_object == {"name": "Alice", "age": 30}
    assert stream.partial_response.text == '{"name":"Alice","age":30}'
    assert len(adapter.stream_requests) == 1

    request = adapter.stream_requests[0]
    assert request.response_format == unified_llm.ResponseFormat(
        type="json_schema",
        json_schema=schema,
        strict=True,
    )
    assert request.provider_options["gemini"]["temperature"] == 0.1
    assert request.provider_options["gemini"]["responseMimeType"] == "application/json"
    assert request.provider_options["gemini"]["responseSchema"] == schema

    await stream.close()
    assert adapter.opened_streams[0].closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected_log"),
    [
        ('{"name":"Alice","age":30', "parse"),
        ('{"name":"Alice","age":"30"}', "validation"),
    ],
)
async def test_stream_object_raises_no_object_generated_error_without_retry(
    text: str,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schema = _structured_schema()
    adapter = _SequencedStreamAdapter(
        "fake",
        [
            [
                _text_delta(text),
            ]
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    stream = unified_llm.stream_object(
        model="gpt-5.2",
        prompt="extract the object",
        schema=schema,
        provider="fake",
        client=client,
        max_retries=2,
    )

    with caplog.at_level(logging.DEBUG, logger="unified_llm.structured"):
        with pytest.raises(NoObjectGeneratedError):
            await stream.object()

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert len(adapter.stream_requests) == 1
    assert adapter.opened_streams[0].closed is True
    assert any(expected_log in record.message for record in caplog.records)
