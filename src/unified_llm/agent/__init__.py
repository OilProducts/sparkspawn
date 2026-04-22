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
from .local_environment import LocalExecutionEnvironment
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
    "check_context_usage",
    "execute_tool_call",
    "execute_tool_calls",
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
    "UserTurn",
    "truncate_lines",
    "truncate_output",
    "truncate_tool_output",
]
