"""Public re-export surface for the unified_llm.agent package."""

from __future__ import annotations

from .context import check_context_usage
from .environment import (
    DirEntry,
    EnvironmentInheritancePolicy,
    ExecResult,
    ExecutionEnvironment,
    GrepOptions,
)
from .events import EventKind, SessionEvent
from .history import history_to_messages, turn_to_messages
from .local_environment import LocalExecutionEnvironment
from .loop_detection import LOOP_DETECTION_WARNING, ToolCallSignature, detect_loop
from .session import Session
from .tool_execution import execute_tool_call, execute_tool_calls
from .truncation import (
    DEFAULT_LINE_LIMITS,
    DEFAULT_TOOL_LIMITS,
    DEFAULT_TOOL_LINE_LIMITS,
    DEFAULT_TOOL_OUTPUT_LIMITS,
    DEFAULT_TRUNCATION_MODES,
    truncate_lines,
    truncate_output,
    truncate_tool_output,
)
from .types import (
    AgentError,
    AssistantTurn,
    ProviderProfile,
    RegisteredTool,
    SessionAbortedError,
    SessionClosedError,
    SessionConfig,
    SessionState,
    SessionStateError,
    SteeringTurn,
    SubAgentError,
    SubAgentHandle,
    SubAgentLimitError,
    SubAgentResult,
    SubAgentStatus,
    SystemTurn,
    ToolDefinition,
    ToolRegistry,
    ToolResultsTurn,
    UserTurn,
)

__all__ = [
    "AgentError",
    "AssistantTurn",
    "DirEntry",
    "EventKind",
    "EnvironmentInheritancePolicy",
    "ExecResult",
    "ExecutionEnvironment",
    "GrepOptions",
    "DEFAULT_LINE_LIMITS",
    "DEFAULT_TOOL_LIMITS",
    "DEFAULT_TOOL_LINE_LIMITS",
    "DEFAULT_TOOL_OUTPUT_LIMITS",
    "DEFAULT_TRUNCATION_MODES",
    "LOOP_DETECTION_WARNING",
    "check_context_usage",
    "execute_tool_call",
    "execute_tool_calls",
    "detect_loop",
    "history_to_messages",
    "LocalExecutionEnvironment",
    "ProviderProfile",
    "RegisteredTool",
    "Session",
    "SessionAbortedError",
    "SessionClosedError",
    "SessionConfig",
    "SessionEvent",
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
    "ToolCallSignature",
    "turn_to_messages",
    "UserTurn",
    "truncate_lines",
    "truncate_output",
    "truncate_tool_output",
]
