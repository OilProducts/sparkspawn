from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SSEEvent:
    type: str
    data: str | None = None
    id: str | None = None
    retry: int | None = None
    comment: str | None = None
    raw: str = ""
    data_lines: tuple[str, ...] = ()

    @property
    def event(self) -> str:
        return self.type


def _decode_chunk(chunk: bytes | bytearray, *, field_name: str) -> str:
    try:
        return bytes(chunk).decode("utf-8")
    except UnicodeDecodeError:
        logger.debug("Unable to decode %s as UTF-8", field_name, exc_info=True)
        return bytes(chunk).decode("utf-8", errors="replace")


def _normalize_line_source(source: Any) -> Iterator[str]:
    if source is None:
        raise TypeError("source must be a string, bytes, or iterable of strings/bytes")

    if isinstance(source, (bytes, bytearray)):
        yield from _decode_chunk(source, field_name="SSE payload").splitlines()
        return

    if isinstance(source, str):
        yield from source.splitlines()
        return

    try:
        iterator = iter(source)
    except TypeError as error:
        raise TypeError(
            "source must be a string, bytes, or iterable of strings/bytes"
        ) from error

    for chunk in iterator:
        if chunk is None:
            continue
        if isinstance(chunk, (bytes, bytearray)):
            chunk = _decode_chunk(chunk, field_name="SSE chunk")
        elif not isinstance(chunk, str):
            logger.debug("Unexpected SSE chunk type: %s", type(chunk).__name__)
            raise TypeError("SSE chunks must be strings or bytes")

        if chunk == "":
            yield ""
            continue

        yield from chunk.splitlines()


def _strip_sse_value(value: str) -> str:
    return value[1:] if value.startswith(" ") else value


def _parse_retry(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        logger.debug("Unable to parse SSE retry value %r", value, exc_info=True)
        return None


def iter_sse_events(source: Any) -> Iterator[SSEEvent]:
    event_type: str | None = None
    event_seen = False
    data_lines: list[str] = []
    comments: list[str] = []
    event_id: str | None = None
    id_seen = False
    retry: int | None = None
    retry_seen = False
    raw_lines: list[str] = []

    def emit_event() -> SSEEvent | None:
        if not (event_seen or data_lines or comments or id_seen or retry_seen):
            return None

        return SSEEvent(
            type=event_type if event_seen else "message",
            data="\n".join(data_lines) if data_lines else None,
            id=event_id,
            retry=retry if retry_seen else None,
            comment="\n".join(comments) if comments else None,
            raw="\n".join(raw_lines),
            data_lines=tuple(data_lines),
        )

    def reset_state() -> None:
        nonlocal event_type, event_seen, data_lines, comments, event_id
        nonlocal id_seen, retry, retry_seen, raw_lines
        event_type = None
        event_seen = False
        data_lines = []
        comments = []
        event_id = None
        id_seen = False
        retry = None
        retry_seen = False
        raw_lines = []

    for line in _normalize_line_source(source):
        if line.endswith("\r"):
            line = line[:-1]

        if line == "":
            event = emit_event()
            if event is not None:
                yield event
            reset_state()
            continue

        raw_lines.append(line)

        if line.startswith(":"):
            comments.append(_strip_sse_value(line[1:]))
            continue

        field_name, separator, value = line.partition(":")
        if separator:
            value = _strip_sse_value(value)
        else:
            value = ""
        field_name = field_name.strip()

        if field_name == "event":
            event_type = value
            event_seen = True
        elif field_name == "data":
            data_lines.append(value)
        elif field_name == "id":
            event_id = value
            id_seen = True
        elif field_name == "retry":
            parsed_retry = _parse_retry(value)
            if parsed_retry is not None:
                retry = parsed_retry
                retry_seen = True

    event = emit_event()
    if event is not None:
        yield event


def parse_sse_events(source: Any) -> Iterator[SSEEvent]:
    return iter_sse_events(source)


parse_sse = parse_sse_events


__all__ = [
    "SSEEvent",
    "iter_sse_events",
    "parse_sse",
    "parse_sse_events",
]
