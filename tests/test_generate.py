from __future__ import annotations

import asyncio
import importlib
import inspect
import logging

import pytest

import unified_llm
import unified_llm.defaults as defaults_mod
from unified_llm.errors import AbortError, RequestTimeoutError

retry_mod = importlib.import_module("unified_llm.retry")


def _tool_call(
    call_id: str,
    name: str,
    arguments: dict[str, object],
) -> unified_llm.ToolCall:
    return unified_llm.ToolCall(id=call_id, name=name, arguments=arguments)


def _tool_call_message(*tool_calls: unified_llm.ToolCall) -> unified_llm.Message:
    return unified_llm.Message.assistant(
        [
            unified_llm.ContentPart(
                kind=unified_llm.ContentKind.TOOL_CALL,
                tool_call=tool_call,
            )
            for tool_call in tool_calls
        ]
    )


def _tool_call_response(
    *,
    provider: str,
    request: unified_llm.Request,
    tool_calls: list[unified_llm.ToolCall],
    usage: unified_llm.Usage | None = None,
    warnings: list[unified_llm.Warning] | None = None,
) -> unified_llm.Response:
    return unified_llm.Response(
        provider=provider,
        model=request.model,
        message=_tool_call_message(*tool_calls),
        finish_reason=unified_llm.FinishReason(
            reason=unified_llm.FinishReason.TOOL_CALLS,
        ),
        usage=usage or unified_llm.Usage(),
        warnings=warnings or [],
    )


def _text_response(
    *,
    provider: str,
    request: unified_llm.Request,
    text: str,
    usage: unified_llm.Usage | None = None,
) -> unified_llm.Response:
    return unified_llm.Response(
        provider=provider,
        model=request.model,
        message=unified_llm.Message.assistant(text),
        finish_reason=unified_llm.FinishReason(
            reason=unified_llm.FinishReason.STOP,
        ),
        usage=usage or unified_llm.Usage(),
    )


class _SequencedCompleteAdapter:
    def __init__(
        self,
        name: str,
        behaviors: list[object],
    ) -> None:
        self.name = name
        self.complete_requests: list[unified_llm.Request] = []
        self._behaviors = list(behaviors)

    async def complete(self, request: unified_llm.Request) -> unified_llm.Response:
        self.complete_requests.append(request)
        if not self._behaviors:
            raise AssertionError(f"{self.name} received more requests than expected")

        behavior = self._behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior

        if callable(behavior):
            result = behavior(request)
            if inspect.isawaitable(result):
                result = await result
            return result

        return behavior


class _HangingCompleteAdapter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.complete_requests: list[unified_llm.Request] = []
        self.started = asyncio.Event()

    async def complete(self, request: unified_llm.Request) -> unified_llm.Response:
        self.complete_requests.append(request)
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_generate_standardizes_prompt_and_prepends_system_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="final answer",
                usage=unified_llm.Usage(
                    input_tokens=1,
                    output_tokens=2,
                    total_tokens=3,
                ),
            )
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    result = await unified_llm.generate(
        model="gpt-5.2",
        prompt="hello",
        system="system prompt",
        client=client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert isinstance(result, unified_llm.GenerateResult)
    assert result.text == "final answer"
    assert result.reasoning is None
    assert result.tool_calls == []
    assert result.tool_results == []
    assert result.output is None
    assert result.usage.total_tokens == 3
    assert result.total_usage.total_tokens == 3
    assert len(result.steps) == 1
    assert len(adapter.complete_requests) == 1
    request = adapter.complete_requests[0]
    assert request.provider == "fake"
    assert request.tool_choice is None
    assert [message.role for message in request.messages] == [
        unified_llm.Role.SYSTEM,
        unified_llm.Role.USER,
    ]
    assert request.messages[0].text == "system prompt"
    assert request.messages[1].text == "hello"


@pytest.mark.asyncio
async def test_generate_rejects_prompt_and_messages_together_and_requires_one_of_them(
) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        await unified_llm.generate(
            model="gpt-5.2",
            prompt="hello",
            messages=[unified_llm.Message.user("hi")],
        )

    with pytest.raises(ValueError, match="either prompt or messages"):
        await unified_llm.generate(model="gpt-5.2")


@pytest.mark.asyncio
async def test_generate_uses_default_and_explicit_clients(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    default_adapter = _SequencedCompleteAdapter(
        "default",
        [lambda request: _text_response(provider="default", request=request, text="default")],
    )
    explicit_adapter = _SequencedCompleteAdapter(
        "explicit",
        [lambda request: _text_response(provider="explicit", request=request, text="explicit")],
    )
    default_client = unified_llm.Client(
        providers={"fake": default_adapter},
        default_provider="fake",
    )
    explicit_client = unified_llm.Client(
        providers={"fake": explicit_adapter},
        default_provider="fake",
    )
    monkeypatch.setattr(defaults_mod, "_default_client", default_client)

    default_result = await unified_llm.generate(model="gpt-5.2", prompt="hello")
    explicit_result = await unified_llm.generate(
        model="gpt-5.2",
        prompt="world",
        client=explicit_client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert default_result.text == "default"
    assert explicit_result.text == "explicit"
    assert len(default_adapter.complete_requests) == 1
    assert len(explicit_adapter.complete_requests) == 1
    assert default_adapter.complete_requests[0].messages[0].text == "hello"
    assert explicit_adapter.complete_requests[0].messages[0].text == "world"


@pytest.mark.asyncio
async def test_generate_defaults_omitted_model_from_provider_and_client_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    explicit_adapter = _SequencedCompleteAdapter(
        "openai",
        [lambda request: _text_response(provider="openai", request=request, text="explicit")],
    )
    explicit_client = unified_llm.Client(
        providers={"openai": explicit_adapter},
        default_provider=None,
    )
    default_adapter = _SequencedCompleteAdapter(
        "anthropic",
        [lambda request: _text_response(provider="anthropic", request=request, text="default")],
    )
    default_client = unified_llm.Client(
        providers={"anthropic": default_adapter},
        default_provider="anthropic",
    )
    pass_through_adapter = _SequencedCompleteAdapter(
        "openai",
        [lambda request: _text_response(provider="openai", request=request, text="custom")],
    )
    pass_through_client = unified_llm.Client(
        providers={"openai": pass_through_adapter},
        default_provider="openai",
    )

    explicit_result = await unified_llm.generate(
        prompt="hello",
        provider="openai",
        client=explicit_client,
    )
    default_result = await unified_llm.generate(
        prompt="hello",
        client=default_client,
    )
    pass_through_result = await unified_llm.generate(
        model="custom-model",
        prompt="hello",
        provider="openai",
        client=pass_through_client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert explicit_result.text == "explicit"
    assert default_result.text == "default"
    assert pass_through_result.text == "custom"
    assert explicit_adapter.complete_requests[0].model == "gpt-5.2"
    assert explicit_adapter.complete_requests[0].provider == "openai"
    assert default_adapter.complete_requests[0].model == "claude-opus-4-6"
    assert default_adapter.complete_requests[0].provider == "anthropic"
    assert pass_through_adapter.complete_requests[0].model == "custom-model"


@pytest.mark.asyncio
async def test_generate_omitted_model_requires_resolvable_provider_and_latest_catalog_model(
) -> None:
    unresolved_adapter = _SequencedCompleteAdapter("openai", [])
    unresolved_client = unified_llm.Client(
        providers={"openai": unresolved_adapter},
        default_provider=None,
    )
    missing_adapter = _SequencedCompleteAdapter("fake", [])
    missing_client = unified_llm.Client(
        providers={"fake": missing_adapter},
        default_provider="fake",
    )

    with pytest.raises(unified_llm.ConfigurationError, match="No provider configured"):
        await unified_llm.generate(prompt="hello", client=unresolved_client)

    with pytest.raises(
        unified_llm.ConfigurationError,
        match="No latest model configured for provider 'fake'",
    ):
        await unified_llm.generate(prompt="hello", client=missing_client)

    assert unresolved_adapter.complete_requests == []
    assert missing_adapter.complete_requests == []


@pytest.mark.asyncio
async def test_generate_tool_loop_concurrency_and_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    weather_started = asyncio.Event()
    time_started = asyncio.Event()
    release_tools = asyncio.Event()
    completion_order: list[str] = []

    async def weather_tool(city: str) -> dict[str, str]:
        weather_started.set()
        await release_tools.wait()
        await asyncio.sleep(0.05)
        completion_order.append("weather")
        return {"tool": "weather", "city": city}

    async def time_tool(city: str) -> dict[str, str]:
        time_started.set()
        await release_tools.wait()
        completion_order.append("time")
        return {"tool": "time", "city": city}

    weather = unified_llm.Tool.active(
        name="weather",
        description="Lookup weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=weather_tool,
    )
    time = unified_llm.Tool.active(
        name="time",
        description="Lookup time",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=time_tool,
    )
    first_usage = unified_llm.Usage(
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
    )
    second_usage = unified_llm.Usage(
        input_tokens=4,
        output_tokens=5,
        total_tokens=9,
    )
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[
                    _tool_call("call_weather", "weather", {"city": "Paris"}),
                    _tool_call("call_time", "time", {"city": "Paris"}),
                ],
                usage=first_usage,
                warnings=[unified_llm.Warning(message="step one warning")],
            ),
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="all done",
                usage=second_usage,
            ),
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    task = asyncio.create_task(
        unified_llm.generate(
            model="gpt-5.2",
            prompt="what should I do?",
            tools=[weather, time],
            client=client,
        )
    )

    await asyncio.wait_for(
        asyncio.gather(weather_started.wait(), time_started.wait()),
        timeout=0.5,
    )
    release_tools.set()
    result = await task

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert isinstance(result, unified_llm.GenerateResult)
    assert result.text == "all done"
    assert result.reasoning is None
    assert result.output is None
    assert result.usage == second_usage
    assert result.total_usage == unified_llm.Usage(
        input_tokens=5,
        output_tokens=7,
        total_tokens=12,
    )
    assert len(result.steps) == 2
    assert result.steps[0].warnings == [unified_llm.Warning(message="step one warning")]
    assert [tool_call.name for tool_call in result.steps[0].tool_calls] == [
        "weather",
        "time",
    ]
    assert [tool_result.is_error for tool_result in result.steps[0].tool_results] == [
        False,
        False,
    ]
    assert [tool_result.content["tool"] for tool_result in result.steps[0].tool_results] == [
        "weather",
        "time",
    ]
    assert completion_order == ["time", "weather"]
    assert adapter.complete_requests[0].tool_choice is not None
    assert adapter.complete_requests[0].tool_choice.is_auto is True
    assert [message.role for message in adapter.complete_requests[1].messages] == [
        unified_llm.Role.USER,
        unified_llm.Role.ASSISTANT,
        unified_llm.Role.TOOL,
        unified_llm.Role.TOOL,
    ]
    assert [message.tool_call_id for message in adapter.complete_requests[1].messages[2:]] == [
        "call_weather",
        "call_time",
    ]


@pytest.mark.asyncio
async def test_generate_respects_max_tool_rounds_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool_calls_executed = 0

    async def lookup(city: str) -> dict[str, str]:
        nonlocal tool_calls_executed
        tool_calls_executed += 1
        return {"city": city}

    tool = unified_llm.Tool.active(
        name="lookup",
        description="Lookup something",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=lookup,
    )
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[_tool_call("call_lookup", "lookup", {"city": "Paris"})],
                usage=unified_llm.Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    result = await unified_llm.generate(
        model="gpt-5.2",
        prompt="use the lookup tool",
        tools=[tool],
        max_tool_rounds=0,
        client=client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.steps[0].tool_results == []
    assert [tool_call.name for tool_call in result.steps[0].tool_calls] == ["lookup"]
    assert tool_calls_executed == 0
    assert len(adapter.complete_requests) == 1
    assert adapter.complete_requests[0].tool_choice is not None
    assert adapter.complete_requests[0].tool_choice.is_auto is True


@pytest.mark.asyncio
async def test_generate_returns_passive_tool_calls_without_auto_execution(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = unified_llm.Tool.passive(
        name="fetch_weather",
        description="Fetch weather information for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    first_usage = unified_llm.Usage(
        input_tokens=3,
        output_tokens=4,
        total_tokens=7,
    )
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[_tool_call("call_fetch", "fetch_weather", {"city": "Paris"})],
                usage=first_usage,
            ),
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    result = await unified_llm.generate(
        model="gpt-5.2",
        prompt="look up the weather",
        tools=[tool],
        client=client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert isinstance(result, unified_llm.GenerateResult)
    assert result.text == ""
    assert result.tool_calls[0].name == "fetch_weather"
    assert result.tool_results == []
    assert result.steps[0].tool_results == []
    assert result.usage == first_usage
    assert result.total_usage == first_usage
    assert len(result.steps) == 1
    assert len(adapter.complete_requests) == 1
    assert adapter.complete_requests[0].tool_choice is not None
    assert adapter.complete_requests[0].tool_choice.is_auto is True
    assert [message.role for message in adapter.complete_requests[0].messages] == [
        unified_llm.Role.USER,
    ]


@pytest.mark.asyncio
async def test_generate_converts_tool_execution_errors(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def boom_handler() -> dict[str, str]:
        raise RuntimeError("boom")

    validating_tool = unified_llm.Tool.active(
        name="validate_tool",
        description="Validate arguments",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=lambda city: {"city": city},
    )
    boom_tool = unified_llm.Tool.active(
        name="boom_tool",
        description="Boom handler",
        parameters={
            "type": "object",
            "properties": {},
        },
        execute_handler=boom_handler,
    )
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[
                    _tool_call("call_missing", "missing_tool", {}),
                    _tool_call("call_validate", "validate_tool", {}),
                    _tool_call("call_boom", "boom_tool", {}),
                ],
                usage=unified_llm.Usage(input_tokens=2, output_tokens=3, total_tokens=5),
            ),
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="recovered",
                usage=unified_llm.Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            ),
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await unified_llm.generate(
            model="gpt-5.2",
            prompt="handle tool errors",
            tools=[validating_tool, boom_tool],
            client=client,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.steps[0].tool_results[0].is_error is True
    assert result.steps[0].tool_results[1].is_error is True
    assert result.steps[0].tool_results[2].is_error is True
    assert "Unknown tool 'missing_tool'" in str(result.steps[0].tool_results[0].content)
    assert "Invalid arguments" in str(result.steps[0].tool_results[1].content)
    assert result.steps[0].tool_results[2].content == "boom"
    assert [message.role for message in adapter.complete_requests[1].messages] == [
        unified_llm.Role.USER,
        unified_llm.Role.ASSISTANT,
        unified_llm.Role.TOOL,
        unified_llm.Role.TOOL,
        unified_llm.Role.TOOL,
    ]
    assert [message.tool_call_id for message in adapter.complete_requests[1].messages[2:]] == [
        "call_missing",
        "call_validate",
        "call_boom",
    ]
    assert any("Unknown tool missing_tool" in record.message for record in caplog.records)
    assert any(
        "Invalid arguments for tool validate_tool" in record.message
        for record in caplog.records
    )
    assert any(
        "Unexpected error executing tool boom_tool" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_generate_repairs_invalid_tool_arguments_and_preserves_ordering(
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
    ) -> str:
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
        return '{"city": "Paris"}'

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
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[
                    _tool_call("call_weather", "weather", "{not json"),
                    _tool_call("call_time", "time", {"city": "Paris"}),
                ],
                usage=unified_llm.Usage(
                    input_tokens=1,
                    output_tokens=2,
                    total_tokens=3,
                ),
            ),
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="all done",
                usage=unified_llm.Usage(
                    input_tokens=4,
                    output_tokens=5,
                    total_tokens=9,
                ),
            ),
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    task = asyncio.create_task(
        unified_llm.generate(
            model="gpt-5.2",
            prompt="what should I do?",
            tools=[weather_tool, time_tool],
            client=client,
            abort_signal=controller.signal,
            repair_tool_call=repair_tool_call,
        )
    )

    await asyncio.wait_for(
        asyncio.gather(repair_started.wait(), normal_started.wait()),
        timeout=0.5,
    )
    release_normal.set()
    await asyncio.wait_for(time_finished.wait(), timeout=0.5)
    assert completion_order == ["time"]
    release_repair.set()
    result = await task

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.text == "all done"
    assert result.steps[0].tool_results[0].is_error is False
    assert result.steps[0].tool_results[1].is_error is False
    assert [tool_result.content["tool"] for tool_result in result.steps[0].tool_results] == [
        "weather",
        "time",
    ]
    assert completion_order == ["time", "weather"]
    assert len(adapter.complete_requests) == 2
    assert [message.role for message in adapter.complete_requests[1].messages] == [
        unified_llm.Role.USER,
        unified_llm.Role.ASSISTANT,
        unified_llm.Role.TOOL,
        unified_llm.Role.TOOL,
    ]
    assert [message.tool_call_id for message in adapter.complete_requests[1].messages[2:]] == [
        "call_weather",
        "call_time",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repair_result", "expected_log"),
    [
        (None, "Repair hook for tool weather returned no usable repair"),
        ({"city": 7}, "Invalid repaired arguments for tool weather"),
        (RuntimeError("repair boom"), "Unexpected error repairing tool weather"),
    ],
)
async def test_generate_logs_repair_failures_without_stdout(
    repair_result: object,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller = unified_llm.AbortController()

    async def weather(city: str) -> dict[str, str]:
        return {"tool": "weather", "city": city}

    async def repair_tool_call(
        *,
        tool_call: unified_llm.ToolCall,
        tool: unified_llm.Tool,
        error: object,
        messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> object:
        assert tool_call.name == "weather"
        assert tool.name == "weather"
        assert tool_call_id == "call_weather"
        assert [message.role for message in messages] == [unified_llm.Role.USER]
        assert abort_signal is controller.signal
        if isinstance(repair_result, BaseException):
            raise repair_result
        return repair_result

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
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[_tool_call("call_weather", "weather", '{"city": 7}')],
                usage=unified_llm.Usage(
                    input_tokens=1,
                    output_tokens=1,
                    total_tokens=2,
                ),
            ),
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="finished",
                usage=unified_llm.Usage(
                    input_tokens=2,
                    output_tokens=3,
                    total_tokens=5,
                ),
            ),
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await unified_llm.generate(
            model="gpt-5.2",
            prompt="what should I do?",
            tools=[weather_tool],
            client=client,
            abort_signal=controller.signal,
            repair_tool_call=repair_tool_call,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.text == "finished"
    assert result.steps[0].tool_results[0].is_error is True
    assert "Invalid arguments for tool 'weather'" in str(result.steps[0].tool_results[0].content)
    assert any(
        record.name == "unified_llm.tools" and expected_log in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_generate_retries_individual_llm_calls_without_repeating_completed_tool_rounds(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sleep_calls: list[float] = []
    tool_calls_executed = 0

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(retry_mod.random, "uniform", lambda a, b: 1.0)
    monkeypatch.setattr(retry_mod.asyncio, "sleep", fake_sleep)

    async def weather(city: str) -> dict[str, str]:
        nonlocal tool_calls_executed
        tool_calls_executed += 1
        return {"city": city}

    tool = unified_llm.Tool.active(
        name="weather",
        description="Lookup weather",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=weather,
    )
    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _tool_call_response(
                provider="fake",
                request=request,
                tool_calls=[_tool_call("call_weather", "weather", {"city": "Paris"})],
                usage=unified_llm.Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            ),
            unified_llm.RateLimitError("retry later", provider="fake"),
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="finished",
                usage=unified_llm.Usage(input_tokens=2, output_tokens=3, total_tokens=5),
            ),
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    result = await unified_llm.generate(
        model="gpt-5.2",
        prompt="what is the weather?",
        tools=[tool],
        max_retries=1,
        client=client,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.text == "finished"
    assert len(result.steps) == 2
    assert result.steps[0].tool_results[0].is_error is False
    assert result.steps[1].tool_results == []
    assert tool_calls_executed == 1
    assert len(adapter.complete_requests) == 3
    assert sleep_calls == [1.0]


@pytest.mark.asyncio
async def test_generate_with_abort_signal_completes_without_threadpool_usage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_in_executor_calls = 0
    original_run_in_executor = asyncio.BaseEventLoop.run_in_executor

    def counting_run_in_executor(self, executor, func, *args):
        nonlocal run_in_executor_calls
        run_in_executor_calls += 1
        return original_run_in_executor(self, executor, func, *args)

    monkeypatch.setattr(asyncio.BaseEventLoop, "run_in_executor", counting_run_in_executor)

    adapter = _SequencedCompleteAdapter(
        "fake",
        [
            lambda request: _text_response(
                provider="fake",
                request=request,
                text="final answer",
                usage=unified_llm.Usage(
                    input_tokens=2,
                    output_tokens=3,
                    total_tokens=5,
                ),
            )
        ],
    )
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")
    controller = unified_llm.AbortController()

    result = await unified_llm.generate(
        model="gpt-5.2",
        prompt="hello",
        client=client,
        abort_signal=controller.signal,
    )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.text == "final answer"
    assert run_in_executor_calls == 0
    assert len(controller.signal._waiters) == 0


@pytest.mark.asyncio
async def test_generate_raises_abort_error_when_abort_signal_is_triggered(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_in_executor_calls = 0
    original_run_in_executor = asyncio.BaseEventLoop.run_in_executor

    def counting_run_in_executor(self, executor, func, *args):
        nonlocal run_in_executor_calls
        run_in_executor_calls += 1
        return original_run_in_executor(self, executor, func, *args)

    monkeypatch.setattr(asyncio.BaseEventLoop, "run_in_executor", counting_run_in_executor)

    adapter = _HangingCompleteAdapter("fake")
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")
    controller = unified_llm.AbortController()

    task = asyncio.create_task(
        unified_llm.generate(
            model="gpt-5.2",
            prompt="hello",
            client=client,
            abort_signal=controller.signal,
            max_retries=0,
        )
    )

    try:
        await asyncio.wait_for(adapter.started.wait(), timeout=0.5)
        controller.abort("stop now")

        with pytest.raises(AbortError):
            await asyncio.wait_for(task, timeout=0.5)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert len(adapter.complete_requests) == 1
    assert run_in_executor_calls == 0
    assert len(controller.signal._waiters) == 0


@pytest.mark.parametrize(
    "timeout",
    [
        unified_llm.TimeoutConfig(total=0.0),
        unified_llm.TimeoutConfig(per_step=0.0),
    ],
)
@pytest.mark.asyncio
async def test_generate_raises_request_timeout_error_for_total_and_per_step_timeouts(
    timeout: unified_llm.TimeoutConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adapter = _HangingCompleteAdapter("fake")
    client = unified_llm.Client(providers={"fake": adapter}, default_provider="fake")

    with pytest.raises(RequestTimeoutError):
        await unified_llm.generate(
            model="gpt-5.2",
            prompt="hello",
            client=client,
            timeout=timeout,
            max_retries=0,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
