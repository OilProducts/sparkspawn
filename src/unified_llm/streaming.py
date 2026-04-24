from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import AsyncIterator, Iterable
from dataclasses import replace
from typing import Any

from .errors import SDKError
from .tools import ToolCall
from .types import (
    ContentKind,
    ContentPart,
    FinishReason,
    Response,
    Role,
    StreamEvent,
    StreamEventType,
    ThinkingData,
    Usage,
    _PlaceholderRecord,
)

logger = logging.getLogger(__name__)


def _tool_call_data(tool_call: ToolCall | None) -> dict[str, Any]:
    if tool_call is None:
        return {}
    return dict(getattr(tool_call, "__dict__", {}))


def _best_effort_close_awaitable(awaitable: Any) -> None:
    if not inspect.isawaitable(awaitable):
        return

    if inspect.iscoroutine(awaitable):
        coroutine = awaitable
        try:
            coroutine.send(None)
        except StopIteration:
            return
        except Exception:
            logger.exception("Unexpected error closing stream iterator")
            coroutine.close()
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coroutine.close()
            return

        loop.create_task(coroutine)
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _await_close() -> None:
        await awaitable

    loop.create_task(_await_close())


def _serialize_tool_call_arguments(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Unable to decode tool-call arguments as UTF-8", exc_info=True)
            return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, dict):
        try:
            return json.dumps(value, separators=(",", ":"), sort_keys=True)
        except Exception:
            logger.exception("Unexpected failure serializing tool-call arguments")
            raise
    return str(value)


def _merge_tool_call_state(
    current: dict[str, Any] | None,
    incoming: ToolCall | None,
    *,
    final: bool = False,
) -> dict[str, Any] | None:
    if incoming is None:
        return current

    incoming_data = _tool_call_data(incoming)
    if current is None:
        current = {}

    state = dict(current)
    for field_name in ("id", "name", "type"):
        value = incoming_data.get(field_name)
        if value is not None:
            state[field_name] = value

    arguments = incoming_data.get("arguments")
    raw_arguments = incoming_data.get("raw_arguments")
    current_arguments = state.get("arguments")
    current_raw_arguments = state.get("raw_arguments")

    if arguments is not None:
        if isinstance(arguments, dict):
            if isinstance(current_arguments, dict) and not final:
                merged_arguments = dict(current_arguments)
                merged_arguments.update(arguments)
                state["arguments"] = merged_arguments
            else:
                state["arguments"] = dict(arguments)
            if isinstance(raw_arguments, str):
                state["raw_arguments"] = raw_arguments
            elif isinstance(current_raw_arguments, str):
                state["raw_arguments"] = current_raw_arguments
            else:
                serialized = _serialize_tool_call_arguments(arguments)
                if serialized is not None:
                    state["raw_arguments"] = serialized
        elif isinstance(arguments, str):
            fragment = raw_arguments if isinstance(raw_arguments, str) else arguments
            if isinstance(current_arguments, dict):
                serialized = _serialize_tool_call_arguments(current_arguments) or ""
                previous = (
                    current_raw_arguments
                    if isinstance(current_raw_arguments, str)
                    else serialized
                )
            else:
                previous = current_raw_arguments if isinstance(current_raw_arguments, str) else ""
                if not previous and isinstance(current_arguments, str):
                    previous = current_arguments

            if final and previous and (fragment == previous or fragment.startswith(previous)):
                merged = fragment
            else:
                merged = previous + fragment

            state["arguments"] = merged
            state["raw_arguments"] = merged
        else:
            serialized = _serialize_tool_call_arguments(arguments)
            if serialized is not None:
                state["arguments"] = serialized
                if isinstance(raw_arguments, str):
                    state["raw_arguments"] = raw_arguments
                elif isinstance(current_raw_arguments, str):
                    state["raw_arguments"] = current_raw_arguments
                else:
                    state["raw_arguments"] = serialized
    elif isinstance(raw_arguments, str):
        if isinstance(current_arguments, dict):
            serialized = _serialize_tool_call_arguments(current_arguments) or ""
            state["arguments"] = serialized
            state["raw_arguments"] = (
                (current_raw_arguments if isinstance(current_raw_arguments, str) else serialized)
                + raw_arguments
            )
        else:
            previous = current_arguments if isinstance(current_arguments, str) else ""
            state["arguments"] = previous + raw_arguments
            state["raw_arguments"] = (
                (current_raw_arguments if isinstance(current_raw_arguments, str) else "")
                + raw_arguments
            )

    return state


def _build_tool_call(state: dict[str, Any] | None) -> ToolCall | None:
    if not state:
        return None
    return ToolCall(**state)


class StreamAccumulator:
    def __init__(self, response: Response | None = None, **response_fields: Any) -> None:
        if response is None:
            self._template_response = Response(**response_fields) if response_fields else Response()
        elif response_fields:
            self._template_response = replace(response, **response_fields)
        else:
            self._template_response = response

        self._events: list[StreamEvent] = []
        self._content_parts: list[ContentPart] = []
        self._active_text: list[str] | None = None
        self._active_reasoning: list[str] | None = None
        self._active_tool_call: dict[str, Any] | None = None
        self._raw_payloads: list[Any] = []
        self._terminal_event: StreamEvent | None = None
        self._finish_reason: FinishReason | None = None
        self._usage: Usage | None = None
        self._error: SDKError | None = None

    @classmethod
    def from_events(
        cls,
        events: Iterable[StreamEvent],
        response: Response | None = None,
        **response_fields: Any,
    ) -> StreamAccumulator:
        accumulator = cls(response=response, **response_fields)
        accumulator.extend(events)
        return accumulator

    @property
    def events(self) -> list[StreamEvent]:
        return list(self._events)

    @property
    def raw_events(self) -> list[Any]:
        return list(self._raw_payloads)

    @property
    def error(self) -> SDKError | None:
        return self._error

    @property
    def finish_reason(self) -> FinishReason:
        if self._finish_reason is not None:
            return self._finish_reason
        return self._template_response.finish_reason

    @property
    def usage(self) -> Usage:
        if self._usage is not None:
            return self._usage
        return self._template_response.usage

    @property
    def text(self) -> str:
        return self.response.text

    @property
    def reasoning(self) -> str | None:
        return self.response.reasoning

    @property
    def tool_calls(self) -> list[ToolCall]:
        return self.response.tool_calls

    @property
    def finish_event(self) -> StreamEvent | None:
        if self._terminal_event is None:
            return None
        return replace(
            self._terminal_event,
            response=self.response,
            finish_reason=self.finish_reason,
            usage=self.usage,
        )

    @property
    def response(self) -> Response:
        try:
            return self._build_response()
        except Exception:
            logger.exception("Unexpected failure building accumulated response")
            raise

    def add(self, event: StreamEvent) -> Response:
        if not isinstance(event, StreamEvent):
            logger.debug("Unexpected stream event type: %s", type(event).__name__)
            raise TypeError("event must be a StreamEvent")

        try:
            self._events.append(event)
            if event.raw is not None:
                self._raw_payloads.append(event.raw)
            self._handle_event(event)
            return self.response
        except Exception:
            logger.exception("Unexpected failure accumulating stream event")
            raise

    def append(self, event: StreamEvent) -> Response:
        return self.add(event)

    def process(self, event: StreamEvent) -> Response:
        return self.add(event)

    def consume(self, event: StreamEvent) -> Response:
        return self.add(event)

    def extend(self, events: Iterable[StreamEvent]) -> Response:
        for event in events:
            self.add(event)
        return self.response

    def finalize(self) -> Response:
        return self.response

    def raise_for_error(self) -> None:
        if self._error is not None:
            raise self._error

    def _handle_event(self, event: StreamEvent) -> None:
        event_type = event.type

        if event_type == StreamEventType.STREAM_START:
            if event.response is not None:
                self._template_response = self._overlay_response(event.response)
            return

        if event_type == StreamEventType.TEXT_START:
            self._flush_active_blocks()
            self._active_text = []
            if event.delta is not None:
                self._active_text.append(event.delta)
            return

        if event_type == StreamEventType.TEXT_DELTA:
            if self._active_text is None:
                self._flush_active_blocks()
                self._active_text = []
            if event.delta is not None:
                self._active_text.append(event.delta)
            return

        if event_type == StreamEventType.TEXT_END:
            if self._active_text is None:
                self._flush_active_blocks()
                self._active_text = []
            if event.delta is not None:
                self._merge_final_fragment(self._active_text, event.delta)
            self._flush_text()
            return

        if event_type == StreamEventType.REASONING_START:
            self._flush_active_blocks()
            self._active_reasoning = []
            if event.reasoning_delta is not None:
                self._active_reasoning.append(event.reasoning_delta)
            return

        if event_type == StreamEventType.REASONING_DELTA:
            if self._active_reasoning is None:
                self._flush_active_blocks()
                self._active_reasoning = []
            if event.reasoning_delta is not None:
                self._active_reasoning.append(event.reasoning_delta)
            return

        if event_type == StreamEventType.REASONING_END:
            if self._active_reasoning is None:
                self._flush_active_blocks()
                self._active_reasoning = []
            if event.reasoning_delta is not None:
                self._merge_final_fragment(self._active_reasoning, event.reasoning_delta)
            self._flush_reasoning()
            return

        if event_type == StreamEventType.TOOL_CALL_START:
            self._flush_active_blocks()
            self._active_tool_call = _merge_tool_call_state(None, event.tool_call)
            return

        if event_type == StreamEventType.TOOL_CALL_DELTA:
            if self._active_tool_call is None:
                self._flush_active_blocks()
            self._active_tool_call = _merge_tool_call_state(self._active_tool_call, event.tool_call)
            return

        if event_type == StreamEventType.TOOL_CALL_END:
            if self._active_tool_call is None:
                self._flush_active_blocks()
            self._active_tool_call = _merge_tool_call_state(
                self._active_tool_call,
                event.tool_call,
                final=True,
            )
            self._flush_tool_call()
            return

        if event_type == StreamEventType.FINISH:
            self._flush_active_blocks()
            if event.response is not None:
                self._template_response = self._overlay_response(event.response)
            self._terminal_event = event
            self._finish_reason = event.finish_reason or self._template_response.finish_reason
            self._usage = event.usage or self._template_response.usage
            return

        if event_type == StreamEventType.ERROR:
            self._flush_active_blocks()
            if event.response is not None:
                self._template_response = self._overlay_response(event.response)
            self._terminal_event = event
            self._error = event.error
            self._finish_reason = event.finish_reason or FinishReason(reason=FinishReason.ERROR)
            self._usage = event.usage or self._template_response.usage
            return

    def _overlay_response(self, response: Response) -> Response:
        warnings = (
            list(response.warnings)
            if response.warnings
            else list(self._template_response.warnings)
        )
        rate_limit = (
            response.rate_limit
            if response.rate_limit is not None
            else self._template_response.rate_limit
        )
        return replace(
            self._template_response,
            id=response.id or self._template_response.id,
            model=response.model or self._template_response.model,
            provider=response.provider or self._template_response.provider,
            finish_reason=response.finish_reason or self._template_response.finish_reason,
            usage=response.usage or self._template_response.usage,
            raw=response.raw if response.raw is not None else self._template_response.raw,
            warnings=warnings,
            rate_limit=rate_limit,
        )

    def _flush_active_blocks(self) -> None:
        self._flush_text()
        self._flush_reasoning()
        self._flush_tool_call()

    def _flush_text(self) -> None:
        if self._active_text is None:
            return
        text = "".join(self._active_text)
        self._active_text = None
        if text:
            self._content_parts.append(
                ContentPart(kind=ContentKind.TEXT, text=text),
            )

    def _flush_reasoning(self) -> None:
        if self._active_reasoning is None:
            return
        reasoning_text = "".join(self._active_reasoning)
        self._active_reasoning = None
        if reasoning_text:
            self._content_parts.append(
                ContentPart(
                    kind=ContentKind.THINKING,
                    thinking=ThinkingData(text=reasoning_text),
                ),
            )

    def _flush_tool_call(self) -> None:
        if self._active_tool_call is None:
            return
        tool_call = _build_tool_call(self._active_tool_call)
        self._active_tool_call = None
        if tool_call is not None:
            self._content_parts.append(
                ContentPart(
                    kind=ContentKind.TOOL_CALL,
                    tool_call=tool_call,
                ),
            )

    def _merge_final_fragment(self, fragments: list[str], fragment: str) -> None:
        current = "".join(fragments)
        if current and (fragment == current or fragment.startswith(current)):
            fragments[:] = [fragment]
            return
        fragments.append(fragment)

    def _snapshot_content_parts(self) -> list[ContentPart]:
        parts = list(self._content_parts)

        if self._active_text is not None:
            text = "".join(self._active_text)
            if text:
                parts.append(ContentPart(kind=ContentKind.TEXT, text=text))

        if self._active_reasoning is not None:
            reasoning_text = "".join(self._active_reasoning)
            if reasoning_text:
                parts.append(
                    ContentPart(
                        kind=ContentKind.THINKING,
                        thinking=ThinkingData(text=reasoning_text),
                    ),
                )

        if self._active_tool_call is not None:
            tool_call = _build_tool_call(self._active_tool_call)
            if tool_call is not None:
                parts.append(
                    ContentPart(
                        kind=ContentKind.TOOL_CALL,
                        tool_call=tool_call,
                    ),
                )

        return parts

    def _final_response_and_parts(self) -> tuple[Response, list[ContentPart]]:
        terminal_event = self._terminal_event
        if terminal_event is not None and terminal_event.response is not None:
            terminal_response = terminal_event.response
            terminal_parts = list(terminal_response.message.content)
            if terminal_parts:
                return terminal_response, terminal_parts
            return terminal_response, self._snapshot_content_parts()

        return self._template_response, self._snapshot_content_parts()

    def _resolved_raw(self) -> Any:
        if self._template_response.raw is not None:
            return self._template_response.raw
        if not self._raw_payloads:
            return None
        if len(self._raw_payloads) == 1:
            return self._raw_payloads[0]
        return list(self._raw_payloads)

    def _build_response(self) -> Response:
        response, parts = self._final_response_and_parts()
        message = replace(
            response.message,
            role=Role.ASSISTANT,
            content=parts if parts else list(response.message.content),
        )
        return replace(
            response,
            message=message,
            finish_reason=self.finish_reason,
            usage=self.usage,
            raw=self._resolved_raw(),
        )


class StreamEventIterator(_PlaceholderRecord, AsyncIterator[StreamEvent]):
    def __init__(
        self,
        source: AsyncIterator[StreamEvent] | None = None,
        response: Response | None = None,
        **placeholder_fields: Any,
    ) -> None:
        super().__init__(source=source, **placeholder_fields)
        self._source = source
        self._iterator: AsyncIterator[StreamEvent] | None = None
        self._accumulator = StreamAccumulator(response=response)
        self._finished = False
        self._closed = False

    def __aiter__(self) -> StreamEventIterator:
        return self

    def __del__(self) -> None:
        _best_effort_close_awaitable(self.aclose())

    async def __anext__(self) -> StreamEvent:
        if self._finished:
            raise StopAsyncIteration

        if self._source is None:
            raise TypeError("StreamEventIterator requires a source")

        if self._iterator is None:
            self._iterator = self._source.__aiter__()

        try:
            event = await self._iterator.__anext__()
        except StopAsyncIteration:
            self._finished = True
            terminal_event = self._synthesized_finish_event()
            await self._finalize_source()
            if terminal_event is None:
                raise
            return terminal_event
        except SDKError:
            await self._finalize_source()
            self._finished = True
            raise
        except Exception:
            await self._finalize_source()
            self._finished = True
            raise

        if not isinstance(event, StreamEvent):
            logger.debug("Unexpected stream event type: %s", type(event).__name__)
            await self._finalize_source()
            self._finished = True
            raise TypeError("event must be a StreamEvent")

        try:
            self._accumulator.add(event)
        except Exception:
            await self._finalize_source()
            self._finished = True
            raise

        if event.type in (StreamEventType.FINISH, StreamEventType.ERROR):
            self._finished = True
            terminal_event = self._accumulator.finish_event
            if terminal_event is None:
                terminal_event = self._synthesized_finish_event()
            await self._finalize_source()
            return terminal_event

        return event

    async def close(self) -> None:
        self._finished = True
        await self._finalize_source()

    async def aclose(self) -> None:
        await self.close()

    def _synthesized_finish_event(self) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.FINISH,
            finish_reason=self._accumulator.finish_reason,
            usage=self._accumulator.usage,
            response=self._accumulator.response,
        )

    async def _finalize_source(self) -> None:
        if self._closed:
            return

        self._closed = True
        target = self._iterator if self._iterator is not None else self._source
        if target is None:
            return

        close = getattr(target, "aclose", None)
        if close is None:
            close = getattr(target, "close", None)
        if close is None:
            return

        try:
            result = close()
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("Unexpected error closing stream iterator")


__all__ = ["StreamAccumulator", "StreamEventIterator"]
