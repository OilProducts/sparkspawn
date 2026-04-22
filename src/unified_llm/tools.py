from __future__ import annotations

import inspect
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from jsonschema.exceptions import SchemaError, ValidationError
from jsonschema.validators import validator_for

logger = logging.getLogger(__name__)

_TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_TOOL_CHOICE_MODES = {"auto", "none", "required", "named"}


def _validate_optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    return value


def _validate_tool_name(value: Any, field_name: str = "name") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if len(value) > 64:
        raise ValueError(f"{field_name} must be 64 characters or fewer")
    if not _TOOL_NAME_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must start with an ASCII letter and contain only "
            "ASCII letters, numbers, and underscores"
        )
    return value


def _resolve_callable(*handlers: Any) -> Callable[..., Any] | None:
    resolved: Callable[..., Any] | None = None
    for handler in handlers:
        if handler is None:
            continue
        if not callable(handler):
            raise TypeError("execute handler must be callable or None")
        if resolved is None:
            resolved = handler
            continue
        if resolved is not handler:
            raise ValueError("only one execute handler may be provided")
    return resolved


def _schema_root_is_object(schema: Mapping[str, Any]) -> bool:
    return schema.get("type") == "object"


def _normalize_tool_parameters(
    parameters: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if parameters is None:
        return None
    if not isinstance(parameters, Mapping):
        raise TypeError("parameters must be a mapping or None")

    schema = dict(parameters)
    if not _schema_root_is_object(schema):
        raise ValueError("parameters root type must be object")

    validator_cls = validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"parameters must be a valid JSON Schema: {exc.message}") from exc
    return schema


def _normalize_message_tool_result_content(value: Any) -> str | dict[str, Any] | list[Any]:
    if isinstance(value, (str, dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _parse_tool_call_arguments(tool_call: ToolCall) -> Any:
    if not isinstance(tool_call.arguments, str):
        return tool_call.arguments

    raw_arguments = (
        tool_call.raw_arguments
        if isinstance(tool_call.raw_arguments, str)
        else tool_call.arguments
    )
    try:
        return json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise _ToolInvocationError("failed to parse tool call arguments as JSON") from exc


def _coerce_tool_call_arguments(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _context_kwargs(
    *,
    messages: Any | None,
    abort_signal: Any | None,
    tool_call_id: str | None,
    extra_context: Mapping[str, Any],
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for name, value in (
        ("messages", messages),
        ("abort_signal", abort_signal),
        ("tool_call_id", tool_call_id),
    ):
        if value is not None:
            context[name] = value
    for name, value in extra_context.items():
        if value is not None:
            context[name] = value
    return context


class _ToolInvocationError(Exception):
    pass


def _prepare_repair_tool_call_kwargs(
    repair_tool_call: Callable[..., Any],
    *,
    tool_call: ToolCall,
    tool: Tool,
    error: _ToolInvocationError,
    messages: Any | None,
    abort_signal: Any | None,
    tool_call_id: str | None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    try:
        signature = inspect.signature(repair_tool_call)
    except (TypeError, ValueError):
        return (
            (tool_call, tool, error, messages, abort_signal, tool_call_id),
            {},
        )

    accepted_names = {
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
    }
    accepts_var_keyword = any(
        parameter.kind == parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    candidate_kwargs = {
        "tool_call": tool_call,
        "failing_tool_call": tool_call,
        "tool": tool,
        "tool_definition": tool,
        "error": error,
        "validation_error": error,
        "validation_error_context": error,
        "messages": messages,
        "current_messages": messages,
        "abort_signal": abort_signal,
        "tool_call_id": tool_call_id,
    }

    call_kwargs: dict[str, Any] = {}
    for name, value in candidate_kwargs.items():
        if value is None:
            continue
        if accepts_var_keyword or name in accepted_names:
            call_kwargs[name] = value

    return (), call_kwargs


def _repaired_tool_call(
    original_call: ToolCall,
    repair_result: Any,
) -> ToolCall | None:
    if repair_result is None:
        return None

    if isinstance(repair_result, ToolCall):
        repaired_arguments = repair_result.arguments
        repaired_raw_arguments = repair_result.raw_arguments
    else:
        repaired_arguments = repair_result
        repaired_raw_arguments = None

    return replace(
        original_call,
        arguments=repaired_arguments,
        raw_arguments=repaired_raw_arguments,
    )


@dataclass(eq=True)
class ToolChoice:
    mode: str = field(init=False)
    tool_name: str | None = field(init=False, default=None)

    def __init__(
        self,
        mode: str,
        tool_name: str | None = None,
        *,
        tool: str | None = None,
    ) -> None:
        if tool is not None:
            if tool_name is not None and tool_name != tool:
                raise ValueError("tool and tool_name must match when both are provided")
            tool_name = tool

        if not isinstance(mode, str):
            raise TypeError("mode must be a string")

        normalized_mode = mode.casefold()
        if normalized_mode not in _TOOL_CHOICE_MODES:
            raise ValueError("mode must be one of auto, none, required, or named")

        normalized_tool_name = _validate_optional_str(tool_name, "tool_name")
        if normalized_mode == "named":
            if normalized_tool_name is None:
                raise ValueError("named tool choice requires tool_name")
            normalized_tool_name = _validate_tool_name(normalized_tool_name, "tool_name")
        elif normalized_tool_name is not None:
            raise ValueError("tool_name is only valid for named tool choice")

        self.mode = normalized_mode
        self.tool_name = normalized_tool_name

    @property
    def is_auto(self) -> bool:
        return self.mode == "auto"

    @property
    def is_none(self) -> bool:
        return self.mode == "none"

    @property
    def is_required(self) -> bool:
        return self.mode == "required"

    @property
    def is_named(self) -> bool:
        return self.mode == "named"

    @property
    def tool(self) -> str | None:
        return self.tool_name

    @classmethod
    def auto(cls) -> ToolChoice:
        return cls("auto")

    @classmethod
    def none(cls) -> ToolChoice:
        return cls("none")

    @classmethod
    def required(cls) -> ToolChoice:
        return cls("required")

    @classmethod
    def named(cls, tool_name: str) -> ToolChoice:
        return cls("named", tool_name=tool_name)

    @classmethod
    def for_tool(cls, tool_name: str) -> ToolChoice:
        return cls.named(tool_name)


@dataclass(eq=True)
class ToolCall:
    id: str
    name: str
    arguments: Any
    raw_arguments: str | None = None
    type: str = "function"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("id must be a string")
        self.name = _validate_tool_name(self.name)
        if self.raw_arguments is not None and not isinstance(self.raw_arguments, str):
            raise TypeError("raw_arguments must be a string or None")
        if not isinstance(self.type, str):
            raise TypeError("type must be a string")

        if isinstance(self.arguments, str):
            if self.raw_arguments is None:
                self.raw_arguments = self.arguments
            self.arguments = _coerce_tool_call_arguments(self.arguments)

    @property
    def parsed_arguments(self) -> Any:
        return self.arguments

    @property
    def raw_arguments_text(self) -> str | None:
        return self.raw_arguments


@dataclass(eq=True)
class ToolResult:
    tool_call_id: str
    content: Any
    is_error: bool

    def __post_init__(self) -> None:
        if not isinstance(self.tool_call_id, str):
            raise TypeError("tool_call_id must be a string")
        if not isinstance(self.is_error, bool):
            raise TypeError("is_error must be a boolean")

    @classmethod
    def success(cls, tool_call_id: str, content: Any) -> ToolResult:
        return cls(tool_call_id=tool_call_id, content=content, is_error=False)

    @classmethod
    def failure(cls, tool_call_id: str, content: Any) -> ToolResult:
        return cls(tool_call_id=tool_call_id, content=content, is_error=True)

    @classmethod
    def error(cls, tool_call_id: str, content: Any) -> ToolResult:
        return cls.failure(tool_call_id, content)

    @classmethod
    def from_value(
        cls,
        tool_call_id: str,
        content: Any,
        *,
        is_error: bool = False,
    ) -> ToolResult:
        return cls(tool_call_id=tool_call_id, content=content, is_error=is_error)

    @classmethod
    def from_exception(
        cls,
        tool_call_id: str,
        error: BaseException,
    ) -> ToolResult:
        message = str(error) or error.__class__.__name__
        return cls.failure(tool_call_id, message)

    def to_message(self, *, name: str | None = None):
        from .types import Message

        return Message.tool_result(
            tool_call_id=self.tool_call_id,
            content=_normalize_message_tool_result_content(self.content),
            is_error=self.is_error,
            name=name,
        )

    def as_message(self, *, name: str | None = None):
        return self.to_message(name=name)


@dataclass(eq=True)
class Tool:
    name: str = field(init=False)
    description: str | None = field(init=False, default=None)
    parameters: dict[str, Any] | None = field(init=False, default=None)
    execute_handler: Callable[..., Any] | None = field(
        init=False,
        default=None,
        repr=False,
    )

    def __init__(
        self,
        name: str,
        description: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        execute_handler: Callable[..., Any] | None = None,
        *,
        handler: Callable[..., Any] | None = None,
        execute: Callable[..., Any] | None = None,
    ) -> None:
        self.name = _validate_tool_name(name)
        self.description = _validate_optional_str(description, "description")
        self.parameters = _normalize_tool_parameters(parameters)
        self.execute_handler = _resolve_callable(execute_handler, handler, execute)

    @property
    def is_active(self) -> bool:
        return self.execute_handler is not None

    @property
    def is_passive(self) -> bool:
        return self.execute_handler is None

    @property
    def handler(self) -> Callable[..., Any] | None:
        return self.execute_handler

    @classmethod
    def active(
        cls,
        name: str,
        description: str | None = None,
        parameters: Mapping[str, Any] | None = None,
        execute_handler: Callable[..., Any] | None = None,
        *,
        handler: Callable[..., Any] | None = None,
        execute: Callable[..., Any] | None = None,
    ) -> Tool:
        resolved_handler = _resolve_callable(execute_handler, handler, execute)
        if resolved_handler is None:
            raise TypeError("Tool.active() requires a callable execute handler")
        return cls(
            name=name,
            description=description,
            parameters=parameters,
            execute_handler=resolved_handler,
        )

    @classmethod
    def passive(
        cls,
        name: str,
        description: str | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> Tool:
        return cls(name=name, description=description, parameters=parameters)

    @classmethod
    def from_callable(
        cls,
        execute_handler: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> Tool:
        inferred_name = name
        if inferred_name is None:
            inferred_name = getattr(execute_handler, "__name__", None) or "tool"
            if not _TOOL_NAME_PATTERN.fullmatch(inferred_name) or len(inferred_name) > 64:
                inferred_name = "tool"
        inferred_description = description or inspect.getdoc(execute_handler)
        return cls(
            name=inferred_name,
            description=inferred_description,
            parameters=parameters,
            execute_handler=execute_handler,
        )

    async def execute(
        self,
        tool_call: ToolCall | Any,
        *,
        messages: Any | None = None,
        abort_signal: Any | None = None,
        tool_call_id: str | None = None,
        repair_tool_call: Callable[..., Any] | None = None,
        **context: Any,
    ) -> ToolResult:
        if isinstance(tool_call, ToolCall):
            resolved_call = tool_call
            if tool_call_id is not None and tool_call_id != tool_call.id:
                resolved_call = replace(tool_call, id=tool_call_id)
        else:
            if tool_call_id is None:
                raise TypeError(
                    "tool_call_id must be provided when executing without a ToolCall"
                )
            resolved_call = ToolCall(
                id=tool_call_id,
                name=self.name,
                arguments=tool_call,
            )

        return await execute_tool_call(
            self,
            resolved_call,
            messages=messages,
            abort_signal=abort_signal,
            tool_call_id=resolved_call.id,
            repair_tool_call=repair_tool_call,
            **context,
        )

    async def run(
        self,
        tool_call: ToolCall | Any,
        *,
        messages: Any | None = None,
        abort_signal: Any | None = None,
        tool_call_id: str | None = None,
        repair_tool_call: Callable[..., Any] | None = None,
        **context: Any,
    ) -> ToolResult:
        return await self.execute(
            tool_call,
            messages=messages,
            abort_signal=abort_signal,
            tool_call_id=tool_call_id,
            repair_tool_call=repair_tool_call,
            **context,
        )

    async def invoke(
        self,
        tool_call: ToolCall | Any,
        *,
        messages: Any | None = None,
        abort_signal: Any | None = None,
        tool_call_id: str | None = None,
        repair_tool_call: Callable[..., Any] | None = None,
        **context: Any,
    ) -> ToolResult:
        return await self.execute(
            tool_call,
            messages=messages,
            abort_signal=abort_signal,
            tool_call_id=tool_call_id,
            repair_tool_call=repair_tool_call,
            **context,
        )


def _prepare_handler_call(
    handler: Callable[..., Any],
    arguments: Any,
    *,
    messages: Any | None,
    abort_signal: Any | None,
    tool_call_id: str | None,
    context: Mapping[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):
        if isinstance(arguments, Mapping):
            return (), dict(arguments)
        if arguments is None:
            return (), {}
        return (arguments,), {}

    accepted_names = {
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
    }
    accepts_var_keyword = any(
        parameter.kind == parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    context_kwargs = _context_kwargs(
        messages=messages,
        abort_signal=abort_signal,
        tool_call_id=tool_call_id,
        extra_context=context,
    )

    def prepare_call_kwargs(call_kwargs: Mapping[str, Any]) -> dict[str, Any]:
        prepared = dict(call_kwargs)
        for name, value in context_kwargs.items():
            if name in prepared:
                continue
            if accepts_var_keyword or name in accepted_names:
                prepared[name] = value
        return prepared

    if isinstance(arguments, Mapping):
        mapping_arguments = dict(arguments)
        keyword_call_kwargs = prepare_call_kwargs(mapping_arguments)
        try:
            signature.bind(**keyword_call_kwargs)
        except TypeError as keyword_error:
            dict_call_kwargs = prepare_call_kwargs({})
            try:
                signature.bind(mapping_arguments, **dict_call_kwargs)
            except TypeError:
                raise _ToolInvocationError(str(keyword_error)) from keyword_error
            return (mapping_arguments,), dict_call_kwargs
        return (), keyword_call_kwargs

    if arguments is None:
        call_args: tuple[Any, ...] = ()
        call_kwargs = prepare_call_kwargs({})
    else:
        call_args = (arguments,)
        call_kwargs = prepare_call_kwargs({})

    try:
        signature.bind(*call_args, **call_kwargs)
    except TypeError as exc:
        raise _ToolInvocationError(str(exc)) from exc

    return call_args, call_kwargs


def _validate_tool_arguments(tool: Tool, arguments: Any) -> None:
    if tool.parameters is None:
        return

    validator_cls = validator_for(tool.parameters)
    try:
        validator_cls(tool.parameters).validate(arguments)
    except ValidationError as exc:
        raise _ToolInvocationError(exc.message) from exc


async def execute_tool_call(
    tool: Tool | None,
    tool_call: ToolCall,
    *,
    messages: Any | None = None,
    abort_signal: Any | None = None,
    tool_call_id: str | None = None,
    repair_tool_call: Callable[..., Any] | None = None,
    **context: Any,
) -> ToolResult:
    if not isinstance(tool_call, ToolCall):
        raise TypeError("tool_call must be a ToolCall")

    resolved_call_id = tool_call_id if tool_call_id is not None else tool_call.id

    if tool is None:
        logger.warning("Unknown tool %s", tool_call.name)
        return ToolResult.failure(
            resolved_call_id,
            f"Unknown tool '{tool_call.name}'",
        )

    if not tool.is_active or tool.execute_handler is None:
        logger.warning("Tool %s has no execute handler", tool.name)
        return ToolResult.failure(
            resolved_call_id,
            f"Tool '{tool.name}' has no execute handler",
        )

    def _failure_result(error: _ToolInvocationError) -> ToolResult:
        return ToolResult.failure(
            resolved_call_id,
            f"Invalid arguments for tool '{tool.name}': {error}",
        )

    def _prepare_call(call: ToolCall) -> tuple[tuple[Any, ...], dict[str, Any]]:
        arguments = _parse_tool_call_arguments(call)
        _validate_tool_arguments(tool, arguments)
        return _prepare_handler_call(
            tool.execute_handler,
            arguments,
            messages=messages,
            abort_signal=abort_signal,
            tool_call_id=resolved_call_id,
            context=context,
        )

    try:
        call_args, call_kwargs = _prepare_call(tool_call)
    except _ToolInvocationError as exc:
        logger.debug("Invalid arguments for tool %s: %s", tool.name, exc)
        if repair_tool_call is None:
            return _failure_result(exc)

        try:
            repair_call_args, repair_call_kwargs = _prepare_repair_tool_call_kwargs(
                repair_tool_call,
                tool_call=tool_call,
                tool=tool,
                error=exc,
                messages=messages,
                abort_signal=abort_signal,
                tool_call_id=resolved_call_id,
            )
            repair_result = repair_tool_call(*repair_call_args, **repair_call_kwargs)
            if inspect.isawaitable(repair_result):
                repair_result = await repair_result
            repaired_call = _repaired_tool_call(tool_call, repair_result)
        except Exception:
            logger.exception("Unexpected error repairing tool %s", tool.name)
            return _failure_result(exc)

        if repaired_call is None:
            logger.debug("Repair hook for tool %s returned no usable repair", tool.name)
            return _failure_result(exc)

        try:
            call_args, call_kwargs = _prepare_call(repaired_call)
        except _ToolInvocationError as repaired_exc:
            logger.debug(
                "Invalid repaired arguments for tool %s: %s",
                tool.name,
                repaired_exc,
            )
            return _failure_result(repaired_exc)

    try:
        result = tool.execute_handler(*call_args, **call_kwargs)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        logger.exception("Unexpected error executing tool %s", tool.name)
        return ToolResult.failure(
            resolved_call_id,
            str(exc) or exc.__class__.__name__,
        )

    if isinstance(result, ToolResult):
        if result.tool_call_id != resolved_call_id:
            return replace(result, tool_call_id=resolved_call_id)
        return result

    return ToolResult.success(resolved_call_id, result)


async def execute_tool(
    tool: Tool | None,
    tool_call: ToolCall,
    *,
    messages: Any | None = None,
    abort_signal: Any | None = None,
    tool_call_id: str | None = None,
    repair_tool_call: Callable[..., Any] | None = None,
    **context: Any,
) -> ToolResult:
    return await execute_tool_call(
        tool,
        tool_call,
        messages=messages,
        abort_signal=abort_signal,
        tool_call_id=tool_call_id,
        repair_tool_call=repair_tool_call,
        **context,
    )


__all__ = [
    "Tool",
    "ToolCall",
    "ToolChoice",
    "ToolResult",
    "execute_tool",
    "execute_tool_call",
]
