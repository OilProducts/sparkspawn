from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from ..types import ContentKind, ContentPart, FinishReason, ToolCallData, ToolResultData, Usage
from .environment import ExecutionEnvironment
from .profiles.base import ProviderProfile
from .tools import RegisteredTool, ToolDefinition, ToolRegistry


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _coerce_uuid(value: UUID | str | None) -> UUID | str | None:
    if not isinstance(value, str):
        return value
    try:
        return UUID(value)
    except ValueError:
        return value


def _normalize_turn_content(content: str | Iterable[ContentPart]) -> str | list[ContentPart]:
    if isinstance(content, str):
        return content
    if isinstance(content, Iterable) and not isinstance(
        content,
        (bytes, bytearray, memoryview),
    ):
        parts = list(content)
        for part in parts:
            if not isinstance(part, ContentPart):
                raise TypeError("content must contain only ContentPart instances")
        return parts
    raise TypeError("content must be text or an iterable of ContentPart")


def _content_parts(content: str | Iterable[ContentPart]) -> list[ContentPart]:
    if isinstance(content, str):
        return [ContentPart(kind=ContentKind.TEXT, text=content)]
    return list(content)


def _content_text(content: str | Iterable[ContentPart]) -> str:
    parts = _content_parts(content)
    return "".join(
        part.text or ""
        for part in parts
        if part.kind == ContentKind.TEXT
    )


@dataclass
class SessionConfig:
    max_turns: int = 0
    max_tool_rounds_per_input: int = 0
    default_command_timeout_ms: int = 10000
    max_command_timeout_ms: int = 600000
    reasoning_effort: str | None = None
    tool_output_limits: dict[str, int] = field(default_factory=dict)
    line_limits: dict[str, int] = field(default_factory=dict)
    enable_loop_detection: bool = True
    loop_detection_window: int = 10
    max_subagent_depth: int = 1

    def __post_init__(self) -> None:
        self.tool_output_limits = dict(self.tool_output_limits)
        self.line_limits = dict(self.line_limits)

    @property
    def tool_output_char_limits(self) -> dict[str, int]:
        return self.tool_output_limits

    @tool_output_char_limits.setter
    def tool_output_char_limits(self, value: Mapping[str, int]) -> None:
        self.tool_output_limits = dict(value)

    @property
    def tool_line_limits(self) -> dict[str, int]:
        return self.line_limits

    @tool_line_limits.setter
    def tool_line_limits(self, value: Mapping[str, int]) -> None:
        self.line_limits = dict(value)


class SessionState(StrEnum):
    IDLE = "idle"
    PROCESSING = "processing"
    AWAITING_INPUT = "awaiting_input"
    CLOSED = "closed"


class _TurnContentMixin:
    content: str | list[ContentPart]

    @property
    def content_parts(self) -> list[ContentPart]:
        return _content_parts(self.content)

    @property
    def text(self) -> str:
        return _content_text(self.content)


@dataclass
class UserTurn(_TurnContentMixin):
    content: str | list[ContentPart]
    timestamp: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.content = _normalize_turn_content(self.content)


@dataclass
class SystemTurn(_TurnContentMixin):
    content: str | list[ContentPart]
    timestamp: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.content = _normalize_turn_content(self.content)


@dataclass
class SteeringTurn(_TurnContentMixin):
    content: str | list[ContentPart]
    timestamp: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.content = _normalize_turn_content(self.content)


@dataclass
class AssistantTurn(_TurnContentMixin):
    content: str | list[ContentPart]
    tool_calls: list[ToolCallData] = field(default_factory=list)
    reasoning: str | None = None
    usage: Usage | None = None
    response_id: str | None = None
    finish_reason: FinishReason | str | None = None
    raw: Any | None = None
    timestamp: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.content = _normalize_turn_content(self.content)
        self.tool_calls = list(self.tool_calls)
        if self.finish_reason is not None and not isinstance(self.finish_reason, FinishReason):
            self.finish_reason = FinishReason(self.finish_reason)
        if self.reasoning is not None and not isinstance(self.reasoning, str):
            raise TypeError("reasoning must be a string or None")
        if self.response_id is not None and not isinstance(self.response_id, str):
            raise TypeError("response_id must be a string or None")


@dataclass
class ToolResultsTurn:
    result_list: list[ToolResultData] = field(default_factory=list)
    timestamp: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.result_list = list(self.result_list)

    @property
    def results(self) -> list[ToolResultData]:
        return self.result_list

    @results.setter
    def results(self, value: Iterable[ToolResultData]) -> None:
        self.result_list = list(value)


class SubAgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class SubAgentHandle:
    id: UUID | str
    status: SubAgentStatus = SubAgentStatus.PENDING
    session_id: UUID | str | None = None
    provider_profile: ProviderProfile | None = None
    working_directory: Path | str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utcnow)
    result: SubAgentResult | None = None

    def __post_init__(self) -> None:
        self.id = _coerce_uuid(self.id)
        self.session_id = _coerce_uuid(self.session_id)
        if self.working_directory is not None and not isinstance(self.working_directory, Path):
            self.working_directory = Path(self.working_directory)
        self.metadata = dict(self.metadata)

    @property
    def profile(self) -> ProviderProfile | None:
        return self.provider_profile

    @profile.setter
    def profile(self, value: ProviderProfile | None) -> None:
        self.provider_profile = value


@dataclass
class SubAgentResult:
    handle_id: UUID | str
    status: SubAgentStatus = SubAgentStatus.COMPLETED
    session_id: UUID | str | None = None
    turns: list[Any] = field(default_factory=list)
    response_id: str | None = None
    summary: str | None = None
    error: BaseException | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self.handle_id = _coerce_uuid(self.handle_id)
        self.session_id = _coerce_uuid(self.session_id)
        self.turns = list(self.turns)
        self.metadata = dict(self.metadata)


class AgentError(Exception):
    pass


class SessionStateError(AgentError):
    pass


class SessionClosedError(SessionStateError):
    pass


class SessionAbortedError(SessionStateError):
    pass


class SubAgentError(AgentError):
    pass


class SubAgentLimitError(SubAgentError):
    pass


__all__ = [
    "AgentError",
    "AssistantTurn",
    "ExecutionEnvironment",
    "ProviderProfile",
    "RegisteredTool",
    "SessionAbortedError",
    "SessionClosedError",
    "SessionConfig",
    "SessionState",
    "SessionStateError",
    "SteeringTurn",
    "SubAgentError",
    "SubAgentHandle",
    "SubAgentLimitError",
    "SubAgentResult",
    "SubAgentStatus",
    "SystemTurn",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResultsTurn",
    "UserTurn",
]
