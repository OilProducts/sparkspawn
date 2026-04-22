from __future__ import annotations

import asyncio
import logging

import pytest

import unified_llm
import unified_llm.agent as agent


async def _next_event(stream) -> agent.SessionEvent:
    return await asyncio.wait_for(anext(stream), timeout=1)


@pytest.mark.asyncio
async def test_execute_tool_call_truncates_model_result_but_keeps_full_event_output(
    tmp_path,
) -> None:
    output = "0123456789ABCDEFGHIJ"
    expected_environment = agent.LocalExecutionEnvironment(working_dir=tmp_path)
    tool_definition = agent.ToolDefinition(
        name="shell",
        description="Echo output",
        parameters={"type": "object"},
    )

    def executor(arguments: dict[str, object], execution_environment: object) -> str:
        assert arguments == {}
        assert execution_environment is expected_environment
        return output

    registry = agent.ToolRegistry(
        {
            "shell": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=expected_environment,
        config=agent.SessionConfig(tool_output_limits={"shell": 10}),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    result = await agent.execute_tool_call(
        session,
        unified_llm.ToolCallData(id="call-1", name="shell", arguments="{}"),
    )

    assert result.tool_call_id == "call-1"
    assert result.is_error is False
    assert result.content == agent.truncate_output(output, 10, "head_tail")

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START
    assert tool_start_event.data == {"tool_call_id": "call-1", "tool_name": "shell"}

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-1",
        "tool_name": "shell",
        "output": output,
    }


@pytest.mark.asyncio
async def test_execute_tool_call_returns_recoverable_error_for_unknown_tools(
    tmp_path,
) -> None:
    session = agent.Session(
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    result = await agent.execute_tool_call(
        session,
        unified_llm.ToolCallData(id="call-2", name="missing", arguments="{}"),
    )

    assert result.tool_call_id == "call-2"
    assert result.is_error is True
    assert result.content == "Unknown tool: missing"

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-2",
        "tool_name": "missing",
        "error": "Unknown tool: missing",
    }


@pytest.mark.asyncio
async def test_execute_tool_call_rejects_invalid_json_arguments(tmp_path) -> None:
    called = False
    tool_definition = agent.ToolDefinition(
        name="shell",
        description="Echo output",
        parameters={"type": "object"},
    )

    def executor(arguments: dict[str, object], execution_environment: object) -> str:
        nonlocal called
        called = True
        return "unexpected"

    registry = agent.ToolRegistry(
        {
            "shell": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    result = await agent.execute_tool_call(
        session,
        unified_llm.ToolCallData(id="call-json", name="shell", arguments="{not json"),
    )

    assert called is False
    assert result.tool_call_id == "call-json"
    assert result.is_error is True
    assert result.content.startswith("Invalid arguments for tool: shell")

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data["error"].startswith("Invalid arguments for tool: shell")


@pytest.mark.asyncio
async def test_execute_tool_call_rejects_schema_validation_failures(tmp_path) -> None:
    called = False
    tool_definition = agent.ToolDefinition(
        name="lookup",
        description="Lookup value",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )

    def executor(arguments: dict[str, object], execution_environment: object) -> str:
        nonlocal called
        called = True
        return "unexpected"

    registry = agent.ToolRegistry(
        {
            "lookup": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    result = await agent.execute_tool_call(
        session,
        unified_llm.ToolCallData(id="call-schema", name="lookup", arguments="{}"),
    )

    assert called is False
    assert result.tool_call_id == "call-schema"
    assert result.is_error is True
    assert result.content.startswith("Invalid arguments for tool: lookup")

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data["error"].startswith("Invalid arguments for tool: lookup")


@pytest.mark.asyncio
async def test_execute_tool_call_preserves_sdk_tool_result_objects(tmp_path) -> None:
    expected_environment = agent.LocalExecutionEnvironment(working_dir=tmp_path)
    tool_definition = agent.ToolDefinition(
        name="structured",
        description="Return a structured result",
        parameters={"type": "object"},
    )
    tool_result = unified_llm.ToolResult(
        tool_call_id="call-structured",
        content={"answer": 42},
        is_error=False,
    )

    def executor(arguments: dict[str, object], execution_environment: object):
        assert arguments == {}
        assert execution_environment is expected_environment
        return tool_result

    registry = agent.ToolRegistry(
        {
            "structured": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=expected_environment,
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    result = await agent.execute_tool_call(
        session,
        unified_llm.ToolCallData(id="call-structured", name="structured", arguments="{}"),
    )

    assert result.tool_call_id == "call-structured"
    assert result.is_error is False
    assert result.content == {"answer": 42}

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-structured",
        "tool_name": "structured",
        "output": tool_result,
    }


@pytest.mark.asyncio
async def test_execute_tool_call_preserves_successful_exec_result_output(
    tmp_path,
) -> None:
    expected_environment = agent.LocalExecutionEnvironment(working_dir=tmp_path)
    tool_definition = agent.ToolDefinition(
        name="shell",
        description="Run a command",
        parameters={"type": "object"},
    )
    exec_result = agent.ExecResult(
        stdout="stdout",
        stderr="stderr",
        exit_code=0,
        timed_out=False,
        duration_ms=15,
    )

    def executor(arguments: dict[str, object], execution_environment: object):
        assert arguments == {}
        assert execution_environment is expected_environment
        return exec_result

    registry = agent.ToolRegistry(
        {
            "shell": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=expected_environment,
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    result = await agent.execute_tool_call(
        session,
        unified_llm.ToolCallData(id="call-exec-success", name="shell", arguments="{}"),
    )

    assert result.tool_call_id == "call-exec-success"
    assert result.is_error is False
    assert result.content == "stdout\nstderr"

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-exec-success",
        "tool_name": "shell",
        "output": exec_result,
    }


@pytest.mark.asyncio
async def test_execute_tool_call_converts_failed_exec_result_into_recoverable_error(
    tmp_path,
    caplog,
) -> None:
    expected_environment = agent.LocalExecutionEnvironment(working_dir=tmp_path)
    tool_definition = agent.ToolDefinition(
        name="shell",
        description="Run a command",
        parameters={"type": "object"},
    )
    exec_result = agent.ExecResult(
        stdout="partial",
        stderr="boom",
        exit_code=7,
        timed_out=False,
        duration_ms=12,
    )

    def executor(arguments: dict[str, object], execution_environment: object):
        assert arguments == {}
        assert execution_environment is expected_environment
        return exec_result

    registry = agent.ToolRegistry(
        {
            "shell": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=expected_environment,
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    with caplog.at_level(logging.WARNING):
        result = await agent.execute_tool_call(
            session,
            unified_llm.ToolCallData(id="call-exec-failure", name="shell", arguments="{}"),
        )

    assert result.tool_call_id == "call-exec-failure"
    assert result.is_error is True
    assert result.content == "partial\nboom\n[exit_code=7, timed_out=False, duration_ms=12]"
    assert any(
        record.levelno == logging.WARNING
        and "failed ExecResult" in record.message
        and "shell" in record.message
        for record in caplog.records
    )

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-exec-failure",
        "tool_name": "shell",
        "error": {
            "stdout": "partial",
            "stderr": "boom",
            "exit_code": 7,
            "timed_out": False,
            "duration_ms": 12,
        },
    }


@pytest.mark.asyncio
async def test_execute_tool_call_converts_timed_out_exec_result_into_recoverable_error(
    tmp_path,
    caplog,
) -> None:
    expected_environment = agent.LocalExecutionEnvironment(working_dir=tmp_path)
    tool_definition = agent.ToolDefinition(
        name="shell",
        description="Run a command",
        parameters={"type": "object"},
    )
    exec_result = agent.ExecResult(
        stdout="start",
        stderr="Command timed out after 50 ms",
        exit_code=124,
        timed_out=True,
        duration_ms=53,
    )

    def executor(arguments: dict[str, object], execution_environment: object):
        assert arguments == {}
        assert execution_environment is expected_environment
        return exec_result

    registry = agent.ToolRegistry(
        {
            "shell": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=expected_environment,
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    with caplog.at_level(logging.WARNING):
        result = await agent.execute_tool_call(
            session,
            unified_llm.ToolCallData(id="call-exec-timeout", name="shell", arguments="{}"),
        )

    assert result.tool_call_id == "call-exec-timeout"
    assert result.is_error is True
    assert result.content == (
        "start\nCommand timed out after 50 ms\n"
        "[exit_code=124, timed_out=True, duration_ms=53]"
    )
    assert any(
        record.levelno == logging.WARNING
        and "failed ExecResult" in record.message
        and "shell" in record.message
        for record in caplog.records
    )

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-exec-timeout",
        "tool_name": "shell",
        "error": {
            "stdout": "start",
            "stderr": "Command timed out after 50 ms",
            "exit_code": 124,
            "timed_out": True,
            "duration_ms": 53,
        },
    }


@pytest.mark.asyncio
async def test_execute_tool_call_converts_executor_exceptions_into_recoverable_errors(
    tmp_path,
    caplog,
) -> None:
    tool_definition = agent.ToolDefinition(
        name="shell",
        description="Echo output",
        parameters={"type": "object"},
    )

    def executor(arguments: dict[str, object], execution_environment: object) -> str:
        raise PermissionError("denied")

    registry = agent.ToolRegistry(
        {
            "shell": agent.RegisteredTool(
                definition=tool_definition,
                executor=executor,
            )
        }
    )
    profile = agent.ProviderProfile(
        id="fake-provider",
        model="fake-model",
        tool_registry=registry,
    )
    session = agent.Session(
        profile=profile,
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    with caplog.at_level(logging.ERROR):
        result = await agent.execute_tool_call(
            session,
            unified_llm.ToolCallData(id="call-exc", name="shell", arguments="{}"),
        )

    assert result.tool_call_id == "call-exc"
    assert result.is_error is True
    assert result.content == "Tool error (shell): denied"
    assert any(
        record.levelno >= logging.ERROR and "Tool execution failed for shell" in record.message
        for record in caplog.records
    )

    tool_start_event = await _next_event(stream)
    assert tool_start_event.kind == agent.EventKind.TOOL_CALL_START

    tool_end_event = await _next_event(stream)
    assert tool_end_event.kind == agent.EventKind.TOOL_CALL_END
    assert tool_end_event.data == {
        "tool_call_id": "call-exc",
        "tool_name": "shell",
        "error": "Tool error (shell): denied",
    }


@pytest.mark.asyncio
async def test_execute_tool_calls_preserves_order_when_parallel_execution_is_supported(
    tmp_path,
) -> None:
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_first = asyncio.Event()
    release_second = asyncio.Event()

    async def first_executor(
        arguments: dict[str, object],
        execution_environment: object,
    ) -> str:
        assert arguments == {}
        first_started.set()
        await release_first.wait()
        return "first"

    async def second_executor(
        arguments: dict[str, object],
        execution_environment: object,
    ) -> str:
        assert arguments == {}
        second_started.set()
        await release_second.wait()
        return "second"

    first_definition = agent.ToolDefinition(
        name="first",
        description="First executor",
        parameters={"type": "object"},
    )
    second_definition = agent.ToolDefinition(
        name="second",
        description="Second executor",
        parameters={"type": "object"},
    )
    registry = agent.ToolRegistry(
        {
            "first": agent.RegisteredTool(
                definition=first_definition,
                executor=first_executor,
            ),
            "second": agent.RegisteredTool(
                definition=second_definition,
                executor=second_executor,
            ),
        }
    )

    class ParallelProfile:
        def __init__(self, tool_registry: agent.ToolRegistry) -> None:
            self.id = "parallel-provider"
            self.model = "parallel-model"
            self.tool_registry = tool_registry
            self.supports_parallel_tool_calls = True

    session = agent.Session(
        profile=ParallelProfile(registry),
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START

    task = asyncio.create_task(
        agent.execute_tool_calls(
            session,
            [
                unified_llm.ToolCallData(id="call-first", name="first", arguments="{}"),
                unified_llm.ToolCallData(id="call-second", name="second", arguments="{}"),
            ],
        )
    )

    await asyncio.wait_for(first_started.wait(), timeout=1)
    await asyncio.wait_for(second_started.wait(), timeout=1)
    release_second.set()
    await asyncio.sleep(0)
    release_first.set()

    results = await asyncio.wait_for(task, timeout=1)

    assert [result.tool_call_id for result in results] == ["call-first", "call-second"]
    assert [result.content for result in results] == ["first", "second"]
