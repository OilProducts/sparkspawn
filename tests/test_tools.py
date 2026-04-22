from __future__ import annotations

import logging

import pytest

import unified_llm
from unified_llm.tools import execute_tool_call


def test_tool_helpers_validate_construction_and_active_passive_state() -> None:
    def lookup_weather(city: str) -> str:
        """Lookup weather by city."""

        return city

    active = unified_llm.Tool.from_callable(
        lookup_weather,
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    passive = unified_llm.Tool.passive(
        name="fetch_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )

    assert active.name == "lookup_weather"
    assert active.description == "Lookup weather by city."
    assert active.is_active is True
    assert callable(active.execute_handler)
    assert passive.name == "fetch_weather"
    assert passive.description == "Fetch weather for a location"
    assert passive.is_passive is True
    assert passive.execute_handler is None


@pytest.mark.parametrize(
    "name",
    [
        "_tool",
        "1tool",
        "a" * 65,
    ],
)
def test_tool_rejects_invalid_names(name: str) -> None:
    with pytest.raises(ValueError):
        unified_llm.Tool.passive(name=name)


@pytest.mark.parametrize(
    "parameters",
    [
        {"type": "string"},
        {"type": ["object", "null"]},
    ],
)
def test_tool_rejects_non_object_parameter_schemas(
    parameters: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="root type must be object"):
        unified_llm.Tool.passive(
            name="lookup_weather",
            parameters=parameters,
        )


def test_tool_active_requires_a_callable_handler() -> None:
    with pytest.raises(TypeError, match="requires a callable execute handler"):
        unified_llm.Tool.active(name="lookup_weather")


def test_tool_choice_helpers_validate_modes_and_named_tools() -> None:
    auto = unified_llm.ToolChoice.auto()
    none = unified_llm.ToolChoice.none()
    required = unified_llm.ToolChoice.required()
    named = unified_llm.ToolChoice.named("lookup_weather")
    alias_named = unified_llm.ToolChoice(mode="named", tool="lookup_weather")

    assert auto.is_auto is True
    assert auto.tool_name is None
    assert none.is_none is True
    assert required.is_required is True
    assert named.is_named is True
    assert named.tool_name == "lookup_weather"
    assert named == alias_named

    with pytest.raises(ValueError, match="named tool choice requires tool_name"):
        unified_llm.ToolChoice(mode="named")

    with pytest.raises(ValueError, match="tool_name is only valid"):
        unified_llm.ToolChoice(mode="auto", tool_name="lookup_weather")

    with pytest.raises(ValueError, match="mode must be one of"):
        unified_llm.ToolChoice(mode="sometimes")


def test_tool_call_parses_json_arguments_and_preserves_raw_strings() -> None:
    parsed_call = unified_llm.ToolCall(
        id="call_123",
        name="lookup_weather",
        arguments='{"city": "Paris"}',
    )
    raw_call = unified_llm.ToolCall(
        id="call_456",
        name="lookup_weather",
        arguments="plain text",
    )
    explicit_raw_call = unified_llm.ToolCall(
        id="call_789",
        name="lookup_weather",
        arguments={"city": "Berlin"},
        raw_arguments='{"city": "Berlin"}',
    )

    assert parsed_call.arguments == {"city": "Paris"}
    assert parsed_call.raw_arguments == '{"city": "Paris"}'
    assert parsed_call.parsed_arguments == {"city": "Paris"}
    assert parsed_call.raw_arguments_text == '{"city": "Paris"}'
    assert raw_call.arguments == "plain text"
    assert raw_call.raw_arguments == "plain text"
    assert explicit_raw_call.arguments == {"city": "Berlin"}
    assert explicit_raw_call.raw_arguments == '{"city": "Berlin"}'


def test_tool_result_preserves_fields_and_round_trips_to_message() -> None:
    result = unified_llm.ToolResult(
        tool_call_id="call_123",
        content={"temperature": 72, "unit": "F"},
        is_error=False,
    )

    message = result.to_message(name="lookup_weather")

    assert result.tool_call_id == "call_123"
    assert result.content == {"temperature": 72, "unit": "F"}
    assert result.is_error is False
    assert message.role == unified_llm.Role.TOOL
    assert message.tool_call_id == "call_123"
    assert message.content[0].tool_result.content == {"temperature": 72, "unit": "F"}
    assert message.content[0].tool_result.is_error is False


@pytest.mark.asyncio
async def test_tool_execute_injects_context_without_colliding_with_tool_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def handler(
        messages: str,
        city: str,
        abort_signal: object,
        tool_call_id: str,
    ) -> dict[str, object]:
        return {
            "messages": messages,
            "city": city,
            "abort_signal": abort_signal,
            "tool_call_id": tool_call_id,
        }

    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {
                "messages": {"type": "string"},
                "city": {"type": "string"},
            },
            "required": ["messages", "city"],
        },
        execute_handler=handler,
    )
    call = unified_llm.ToolCall(
        id="call_123",
        name="lookup_weather",
        arguments='{"messages": "tool-arg", "city": "Paris"}',
    )
    abort_signal = object()

    result = await tool.execute(
        call,
        messages=["context-message"],
        abort_signal=abort_signal,
    )
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is False
    assert result.content == {
        "messages": "tool-arg",
        "city": "Paris",
        "abort_signal": abort_signal,
        "tool_call_id": "call_123",
    }


@pytest.mark.asyncio
async def test_tool_execute_can_pass_parsed_arguments_as_single_dict_when_requested(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def handler(
        payload: dict[str, object],
        *,
        messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> dict[str, object]:
        return {
            "payload": payload,
            "messages": messages,
            "abort_signal": abort_signal,
            "tool_call_id": tool_call_id,
        }

    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string"},
            },
            "required": ["city"],
        },
        execute_handler=handler,
    )
    call = unified_llm.ToolCall(
        id="call_dict",
        name="lookup_weather",
        arguments='{"city": "Paris", "unit": "celsius"}',
    )
    abort_signal = object()

    result = await tool.execute(
        call,
        messages=["context-message"],
        abort_signal=abort_signal,
    )
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is False
    assert result.content == {
        "payload": {"city": "Paris", "unit": "celsius"},
        "messages": ["context-message"],
        "abort_signal": abort_signal,
        "tool_call_id": "call_dict",
    }


@pytest.mark.asyncio
async def test_tool_execute_supports_async_handlers_and_preserves_scalar_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def handler(city: str) -> int:
        return 7

    tool = unified_llm.Tool.active(
        name="count_weather",
        description="Count weather observations",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=handler,
    )
    call = unified_llm.ToolCall(
        id="call_456",
        name="count_weather",
        arguments={"city": "Paris"},
    )

    result = await tool.execute(call)
    message = result.to_message()
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is False
    assert result.content == 7
    assert message.content[0].tool_result.content == "7"


@pytest.mark.asyncio
async def test_tool_execute_rejects_invalid_arguments_and_logs_without_stdout(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=lambda city: city,
    )
    call = unified_llm.ToolCall(
        id="call_invalid",
        name="lookup_weather",
        arguments="{not json",
    )

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await tool.execute(call)

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is True
    assert "Invalid arguments for tool 'lookup_weather'" in result.content
    assert "failed to parse tool call arguments as JSON" in result.content
    assert any(
        record.name == "unified_llm.tools"
        and "Invalid arguments for tool lookup_weather" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_tool_execute_repairs_malformed_json_arguments_before_schema_validation_or_binding(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed: dict[str, object] = {}

    async def repair_tool_call(
        *,
        tool_call: unified_llm.ToolCall,
        tool_definition: unified_llm.Tool,
        validation_error_context: object,
        current_messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> str:
        observed["tool_call"] = tool_call
        observed["tool_definition"] = tool_definition
        observed["validation_error_context"] = validation_error_context
        observed["current_messages"] = current_messages
        observed["abort_signal"] = abort_signal
        observed["tool_call_id"] = tool_call_id
        return '{"city": "Paris"}'

    async def handler(city: str) -> dict[str, str]:
        return {"city": city}

    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=handler,
    )
    call = unified_llm.ToolCall(
        id="call_123",
        name="lookup_weather",
        arguments="{not json",
    )
    abort_signal = object()

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await tool.execute(
            call,
            messages=["context-message"],
            abort_signal=abort_signal,
            repair_tool_call=repair_tool_call,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is False
    assert result.content == {"city": "Paris"}
    assert observed["tool_call"] is call
    assert observed["tool_definition"] is tool
    assert "JSON" in str(observed["validation_error_context"]).upper()
    assert observed["current_messages"] == ["context-message"]
    assert observed["abort_signal"] is abort_signal
    assert observed["tool_call_id"] == "call_123"
    assert any(
        record.name == "unified_llm.tools"
        and "Invalid arguments for tool lookup_weather" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repair_result", "expected_log"),
    [
        (None, "Repair hook for tool lookup_weather returned no usable repair"),
        (
            {"city": 7},
            "Invalid repaired arguments for tool lookup_weather",
        ),
        (RuntimeError("repair boom"), "Unexpected error repairing tool lookup_weather"),
    ],
)
async def test_tool_execute_logs_repair_failures_without_stdout(
    repair_result: object,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def repair_tool_call(
        *,
        tool_call: unified_llm.ToolCall,
        tool: unified_llm.Tool,
        error: object,
        messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> object:
        if isinstance(repair_result, BaseException):
            raise repair_result
        assert "JSON" in str(error).upper()
        return repair_result

    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=lambda city: city,
    )
    call = unified_llm.ToolCall(
        id="call_456",
        name="lookup_weather",
        arguments="{not json",
    )

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await tool.execute(
            call,
            messages=["context-message"],
            abort_signal=object(),
            repair_tool_call=repair_tool_call,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is True
    assert "Invalid arguments for tool 'lookup_weather'" in str(result.content)
    assert any(
        record.name == "unified_llm.tools" and expected_log in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_tool_execute_repairs_handler_binding_after_schema_validation(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    observed: dict[str, object] = {}

    async def repair_tool_call(
        *,
        tool_call: unified_llm.ToolCall,
        tool_definition: unified_llm.Tool,
        validation_error_context: object,
        current_messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> dict[str, str]:
        observed["tool_call"] = tool_call
        observed["tool_definition"] = tool_definition
        observed["validation_error_context"] = validation_error_context
        observed["current_messages"] = current_messages
        observed["abort_signal"] = abort_signal
        observed["tool_call_id"] = tool_call_id
        return {"city": "Paris", "country": "France"}

    async def handler(city: str, country: str) -> dict[str, str]:
        return {"city": city, "country": country}

    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=handler,
    )
    call = unified_llm.ToolCall(
        id="call_bind",
        name="lookup_weather",
        arguments='{"city": "Paris"}',
    )
    abort_signal = object()

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await tool.execute(
            call,
            messages=["context-message"],
            abort_signal=abort_signal,
            repair_tool_call=repair_tool_call,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is False
    assert result.content == {"city": "Paris", "country": "France"}
    assert observed["tool_call"] is call
    assert observed["tool_definition"] is tool
    assert "country" in str(observed["validation_error_context"])
    assert observed["current_messages"] == ["context-message"]
    assert observed["abort_signal"] is abort_signal
    assert observed["tool_call_id"] == "call_bind"
    assert any(
        record.name == "unified_llm.tools"
        and "Invalid arguments for tool lookup_weather" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("repair_result", "expected_log"),
    [
        (None, "Repair hook for tool lookup_weather returned no usable repair"),
        (
            {"city": "Paris"},
            "Invalid repaired arguments for tool lookup_weather",
        ),
        (RuntimeError("repair boom"), "Unexpected error repairing tool lookup_weather"),
    ],
)
async def test_tool_execute_logs_handler_binding_repair_failures_without_stdout(
    repair_result: object,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def repair_tool_call(
        *,
        tool_call: unified_llm.ToolCall,
        tool: unified_llm.Tool,
        error: object,
        messages: object,
        abort_signal: object,
        tool_call_id: str,
    ) -> object:
        assert tool_call.name == "lookup_weather"
        assert tool.name == "lookup_weather"
        assert tool_call_id == "call_bind"
        assert [message.role for message in messages] == [unified_llm.Role.USER]
        assert abort_signal is expected_abort_signal
        assert "country" in str(error)
        if isinstance(repair_result, BaseException):
            raise repair_result
        return repair_result

    async def handler(city: str, country: str) -> dict[str, str]:
        return {"city": city, "country": country}

    tool = unified_llm.Tool.active(
        name="lookup_weather",
        description="Fetch weather for a location",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=handler,
    )
    call = unified_llm.ToolCall(
        id="call_bind",
        name="lookup_weather",
        arguments='{"city": "Paris"}',
    )
    messages = [unified_llm.Message.user("context-message")]
    expected_abort_signal = object()

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        result = await tool.execute(
            call,
            messages=messages,
            abort_signal=expected_abort_signal,
            repair_tool_call=repair_tool_call,
        )

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert result.is_error is True
    assert "Invalid arguments for tool 'lookup_weather'" in str(result.content)
    assert any(
        record.name == "unified_llm.tools" and expected_log in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_tool_execute_converts_passive_unknown_and_handler_errors_to_failure_results(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    passive = unified_llm.Tool.passive(
        name="passive_weather",
        description="Passive weather lookup",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )

    async def failing_handler(city: str) -> str:
        raise RuntimeError("boom")

    failing = unified_llm.Tool.active(
        name="failing_weather",
        description="Failing tool",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        execute_handler=failing_handler,
    )

    passive_call = unified_llm.ToolCall(
        id="call_passive",
        name="passive_weather",
        arguments={"city": "Paris"},
    )
    unknown_call = unified_llm.ToolCall(
        id="call_unknown",
        name="missing_weather",
        arguments={"city": "Paris"},
    )
    failing_call = unified_llm.ToolCall(
        id="call_failing",
        name="failing_weather",
        arguments={"city": "Paris"},
    )

    with caplog.at_level(logging.DEBUG, logger="unified_llm.tools"):
        passive_result = await passive.execute(passive_call)
        unknown_result = await execute_tool_call(None, unknown_call)
        failing_result = await failing.execute(failing_call)

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
    assert passive_result.is_error is True
    assert "no execute handler" in passive_result.content
    assert unknown_result.is_error is True
    assert "Unknown tool 'missing_weather'" in unknown_result.content
    assert failing_result.is_error is True
    assert "boom" in failing_result.content
    assert any(
        record.name == "unified_llm.tools"
        and "Tool passive_weather has no execute handler" in record.message
        for record in caplog.records
    )
    assert any(
        record.name == "unified_llm.tools"
        and "Unknown tool missing_weather" in record.message
        for record in caplog.records
    )
    assert any(
        record.name == "unified_llm.tools"
        and "Unexpected error executing tool failing_weather" in record.message
        for record in caplog.records
    )
