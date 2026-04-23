from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import unified_llm
import unified_llm.agent as agent


async def _next_event(stream) -> agent.SessionEvent:
    return await asyncio.wait_for(anext(stream), timeout=1)


@dataclass(frozen=True)
class ProviderCase:
    name: str
    model: str
    factory: Callable[..., agent.ProviderProfile]
    write_file_path_key: str
    expected_tool_names: tuple[str, ...]
    expected_provider_options: dict[str, Any]


PROVIDER_CASES = (
    ProviderCase(
        name="openai",
        model="gpt-5.2",
        factory=agent.create_openai_profile,
        write_file_path_key="path",
        expected_tool_names=(
            "read_file",
            "apply_patch",
            "write_file",
            "shell",
            "grep",
            "glob",
            "spawn_agent",
            "send_input",
            "wait",
            "close_agent",
        ),
        expected_provider_options={
            "reasoning": {"effort": "medium"},
        },
    ),
    ProviderCase(
        name="anthropic",
        model="claude-sonnet-4-5",
        factory=agent.create_anthropic_profile,
        write_file_path_key="file_path",
        expected_tool_names=(
            "read_file",
            "write_file",
            "edit_file",
            "shell",
            "grep",
            "glob",
            "spawn_agent",
            "send_input",
            "wait",
            "close_agent",
        ),
        expected_provider_options={},
    ),
    ProviderCase(
        name="gemini",
        model="gemini-3.1-pro-preview",
        factory=agent.create_gemini_profile,
        write_file_path_key="file_path",
        expected_tool_names=(
            "read_file",
            "read_many_files",
            "write_file",
            "edit_file",
            "shell",
            "grep",
            "glob",
            "list_dir",
            "spawn_agent",
            "send_input",
            "wait",
            "close_agent",
        ),
        expected_provider_options={},
    ),
)

USER_INPUT = "Create hello.txt and confirm it was written."
FIRST_ASSISTANT_TEXT = "Writing hello.txt."
SECOND_ASSISTANT_TEXT = "Created hello.txt."
FILE_NAME = "hello.txt"
FILE_CONTENT = "alpha\nbeta\n"
TOOL_CALL_ID = "call-1"
RESP_1_ID = "resp-1"
RESP_2_ID = "resp-2"
REASONING_EFFORT = "medium"


class _CompleteClient:
    def __init__(self, responses: list[unified_llm.Response]) -> None:
        self.requests: list[unified_llm.Request] = []
        self._responses = list(responses)

    async def complete(self, request: unified_llm.Request) -> unified_llm.Response:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("unexpected complete call")
        return self._responses.pop(0)

    def stream(self, request: unified_llm.Request):
        raise AssertionError("complete-mode sessions must not call stream()")


class _StreamingClient:
    def __init__(self, stream_groups: list[list[unified_llm.StreamEvent]]) -> None:
        self.requests: list[unified_llm.Request] = []
        self._stream_groups = [list(group) for group in stream_groups]

    def stream(self, request: unified_llm.Request):
        self.requests.append(request)
        if not self._stream_groups:
            raise AssertionError("unexpected stream call")
        events = self._stream_groups.pop(0)

        async def _events():
            for event in events:
                yield event

        return _events()

    async def complete(self, request: unified_llm.Request) -> unified_llm.Response:
        raise AssertionError("stream-mode sessions must not call complete()")


def _tool_call_arguments(provider_case: ProviderCase) -> dict[str, str]:
    return {
        provider_case.write_file_path_key: FILE_NAME,
        "content": FILE_CONTENT,
    }


def _write_file_tool_call(provider_case: ProviderCase) -> unified_llm.ToolCallData:
    return unified_llm.ToolCallData(
        id=TOOL_CALL_ID,
        name="write_file",
        arguments=_tool_call_arguments(provider_case),
    )


def _tool_call_response(
    *,
    response_id: str,
    provider_case: ProviderCase,
    text: str,
    tool_call: unified_llm.ToolCallData | None = None,
    finish_reason: unified_llm.FinishReason = unified_llm.FinishReason.STOP,
) -> unified_llm.Response:
    message_content: list[unified_llm.ContentPart] = []
    if text:
        message_content.append(
            unified_llm.ContentPart(kind=unified_llm.ContentKind.TEXT, text=text)
        )
    if tool_call is not None:
        message_content.append(
            unified_llm.ContentPart(
                kind=unified_llm.ContentKind.TOOL_CALL,
                tool_call=tool_call,
            )
        )
    return unified_llm.Response(
        id=response_id,
        model=provider_case.model,
        provider=provider_case.name,
        message=unified_llm.Message.assistant(message_content),
        finish_reason=finish_reason,
    )


def _stream_turn(
    *,
    response_id: str,
    provider_case: ProviderCase,
    text: str,
    tool_call: unified_llm.ToolCallData | None = None,
    finish_reason: unified_llm.FinishReason = unified_llm.FinishReason.STOP,
) -> list[unified_llm.StreamEvent]:
    events: list[unified_llm.StreamEvent] = [
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.STREAM_START,
            response=unified_llm.Response(
                id=response_id,
                model=provider_case.model,
                provider=provider_case.name,
            ),
        )
    ]
    if text:
        events.append(
            unified_llm.StreamEvent(
                type=unified_llm.StreamEventType.TEXT_START,
                delta=text,
            )
        )
        events.append(
            unified_llm.StreamEvent(
                type=unified_llm.StreamEventType.TEXT_END,
            )
        )
    if tool_call is not None:
        events.append(
            unified_llm.StreamEvent(
                type=unified_llm.StreamEventType.TOOL_CALL_START,
                tool_call=tool_call,
            )
        )
        events.append(
            unified_llm.StreamEvent(
                type=unified_llm.StreamEventType.TOOL_CALL_END,
                tool_call=tool_call,
            )
        )
    events.append(
        unified_llm.StreamEvent(
            type=unified_llm.StreamEventType.FINISH,
            finish_reason=finish_reason,
            response=unified_llm.Response(
                id=response_id,
                model=provider_case.model,
                provider=provider_case.name,
            ),
        )
    )
    return events


def _request_tool_names(request: unified_llm.Request) -> list[str]:
    return [tool.name for tool in request.tools or []]


def _assert_provider_request_shape(
    request: unified_llm.Request,
    *,
    provider_case: ProviderCase,
) -> None:
    assert request.provider == provider_case.name
    assert request.model == provider_case.model
    assert request.reasoning_effort == REASONING_EFFORT
    assert request.provider_options == {
        provider_case.name: provider_case.expected_provider_options
    }
    assert _request_tool_names(request) == list(provider_case.expected_tool_names)
    assert request.tool_choice is not None
    assert request.tool_choice.mode == "auto"
    assert request.tool_choice.tool_name is None

    write_tool = next(tool for tool in request.tools or [] if tool.name == "write_file")
    assert write_tool.parameters["properties"][provider_case.write_file_path_key][
        "type"
    ] == "string"
    assert write_tool.parameters["properties"]["content"]["type"] == "string"
    assert write_tool.parameters["required"] == [
        provider_case.write_file_path_key,
        "content",
    ]


def _assert_assistant_tool_call_message(
    message: unified_llm.Message,
    *,
    text: str,
    provider_case: ProviderCase,
) -> None:
    assert message.role == unified_llm.Role.ASSISTANT
    assert message.text == text
    assert [part.kind for part in message.content] == [
        unified_llm.ContentKind.TEXT,
        unified_llm.ContentKind.TOOL_CALL,
    ]
    tool_call = message.content[1].tool_call
    assert tool_call is not None
    assert tool_call.id == TOOL_CALL_ID
    assert tool_call.name == "write_file"
    assert tool_call.type == "function"
    assert tool_call.arguments == _tool_call_arguments(provider_case)


def _assert_request_turns(
    request: unified_llm.Request,
    *,
    provider_case: ProviderCase,
    expected_user_message: str,
    assistant_text: str | None = None,
) -> None:
    assert request.messages[0].role == unified_llm.Role.SYSTEM
    assert request.messages[1] == unified_llm.Message.user(expected_user_message)

    if assistant_text is None:
        assert len(request.messages) == 2
        return

    assert len(request.messages) == 4
    _assert_assistant_tool_call_message(
        request.messages[2],
        text=assistant_text,
        provider_case=provider_case,
    )
    assert request.messages[3] == unified_llm.Message.tool_result(
        tool_call_id=TOOL_CALL_ID,
        content={
            "path": FILE_NAME,
            "bytes_written": len(FILE_CONTENT),
        },
        is_error=False,
    )


def _assert_events(
    events: list[agent.SessionEvent],
) -> None:
    expected_kinds = [
        agent.EventKind.SESSION_START,
        agent.EventKind.USER_INPUT,
        agent.EventKind.ASSISTANT_TEXT_START,
        agent.EventKind.ASSISTANT_TEXT_DELTA,
        agent.EventKind.ASSISTANT_TEXT_END,
        agent.EventKind.TOOL_CALL_START,
        agent.EventKind.TOOL_CALL_END,
        agent.EventKind.ASSISTANT_TEXT_START,
        agent.EventKind.ASSISTANT_TEXT_DELTA,
        agent.EventKind.ASSISTANT_TEXT_END,
        agent.EventKind.PROCESSING_END,
    ]
    assert [event.kind for event in events] == expected_kinds
    assert events[0].data == {"state": "idle"}
    assert events[1].data == {"content": USER_INPUT}
    assert events[2].data == {"response_id": RESP_1_ID}
    assert events[3].data == {"response_id": RESP_1_ID, "delta": FIRST_ASSISTANT_TEXT}
    assert events[4].data == {"text": FIRST_ASSISTANT_TEXT, "reasoning": None}
    assert events[5].data == {
        "tool_call_id": TOOL_CALL_ID,
        "tool_name": "write_file",
    }
    assert isinstance(events[6].data["output"], unified_llm.ToolResult)
    assert events[6].data["output"].is_error is False
    assert events[6].data["output"].content == {
        "path": FILE_NAME,
        "bytes_written": len(FILE_CONTENT),
    }
    assert events[7].data == {"response_id": RESP_2_ID}
    assert events[8].data == {"response_id": RESP_2_ID, "delta": SECOND_ASSISTANT_TEXT}
    assert events[9].data == {"text": SECOND_ASSISTANT_TEXT, "reasoning": None}
    assert events[10].data == {"state": "idle"}


def _assert_session_history(session: agent.Session) -> None:
    assert [type(turn).__name__ for turn in session.history] == [
        "UserTurn",
        "AssistantTurn",
        "ToolResultsTurn",
        "AssistantTurn",
    ]
    assert session.history[0].text == USER_INPUT
    assert session.history[1].text == FIRST_ASSISTANT_TEXT
    assert session.history[1].tool_calls[0].name == "write_file"
    assert session.history[1].tool_calls[0].arguments in (
        {
            "path": FILE_NAME,
            "content": FILE_CONTENT,
        },
        {
            "file_path": FILE_NAME,
            "content": FILE_CONTENT,
        },
    )
    assert session.history[1].finish_reason.reason == "tool_calls"
    assert session.history[2].result_list[0] == unified_llm.ToolResultData(
        tool_call_id=TOOL_CALL_ID,
        content={
            "path": FILE_NAME,
            "bytes_written": len(FILE_CONTENT),
        },
        is_error=False,
    )
    assert session.history[3].text == SECOND_ASSISTANT_TEXT
    assert session.history[3].finish_reason.reason == "stop"


@pytest.mark.parametrize(
    "provider_case",
    PROVIDER_CASES,
    ids=[case.name for case in PROVIDER_CASES],
)
@pytest.mark.parametrize("client_mode", ["complete", "stream"], ids=["complete", "stream"])
@pytest.mark.asyncio
async def test_cross_provider_parity_harness(
    tmp_path: Path,
    provider_case: ProviderCase,
    client_mode: str,
) -> None:
    profile = provider_case.factory(
        model=provider_case.model,
        supports_streaming=client_mode == "stream",
    )
    session = agent.Session(
        profile=profile,
        execution_env=agent.LocalExecutionEnvironment(working_dir=tmp_path),
        llm_client=(
            _CompleteClient(
                [
                    _tool_call_response(
                        response_id=RESP_1_ID,
                        provider_case=provider_case,
                        text=FIRST_ASSISTANT_TEXT,
                        tool_call=_write_file_tool_call(provider_case),
                        finish_reason=unified_llm.FinishReason.TOOL_CALLS,
                    ),
                    _tool_call_response(
                        response_id=RESP_2_ID,
                        provider_case=provider_case,
                        text=SECOND_ASSISTANT_TEXT,
                        finish_reason=unified_llm.FinishReason.STOP,
                    ),
                ]
            )
            if client_mode == "complete"
            else _StreamingClient(
                [
                    _stream_turn(
                        response_id=RESP_1_ID,
                        provider_case=provider_case,
                        text=FIRST_ASSISTANT_TEXT,
                        tool_call=_write_file_tool_call(provider_case),
                        finish_reason=unified_llm.FinishReason.TOOL_CALLS,
                    ),
                    _stream_turn(
                        response_id=RESP_2_ID,
                        provider_case=provider_case,
                        text=SECOND_ASSISTANT_TEXT,
                        finish_reason=unified_llm.FinishReason.STOP,
                    ),
                ]
            )
        ),
        config=agent.SessionConfig(reasoning_effort=REASONING_EFFORT),
    )
    stream = session.events()

    start_event = await _next_event(stream)
    assert start_event.kind == agent.EventKind.SESSION_START
    assert start_event.data == {"state": "idle"}

    await session.process_input(USER_INPUT)

    events: list[agent.SessionEvent] = [start_event]
    while True:
        event = await _next_event(stream)
        events.append(event)
        if event.kind == agent.EventKind.PROCESSING_END:
            break

    if client_mode == "complete":
        client = session.client
        assert isinstance(client, _CompleteClient)
    else:
        client = session.client
        assert isinstance(client, _StreamingClient)

    assert session.state == agent.SessionState.IDLE
    assert session.execution_environment.read_file(FILE_NAME) == FILE_CONTENT
    assert len(client.requests) == 2

    _assert_provider_request_shape(client.requests[0], provider_case=provider_case)
    _assert_provider_request_shape(client.requests[1], provider_case=provider_case)

    _assert_request_turns(
        client.requests[0],
        provider_case=provider_case,
        expected_user_message=USER_INPUT,
    )
    _assert_request_turns(
        client.requests[1],
        provider_case=provider_case,
        expected_user_message=USER_INPUT,
        assistant_text=FIRST_ASSISTANT_TEXT,
    )

    _assert_events(events)
    _assert_session_history(session)
