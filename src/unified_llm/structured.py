from __future__ import annotations

import copy
import json
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, replace
from typing import Any

from jsonschema.exceptions import SchemaError, ValidationError
from jsonschema.validators import validator_for

from .errors import NoObjectGeneratedError
from .generation import (
    GenerateResult,
    StreamResult,
    _best_effort_close_awaitable,
    generate,
    stream,
)
from .types import Response, ResponseFormat, StreamEventType

logger = logging.getLogger(__name__)

_MISSING = object()


@dataclass(slots=True)
class _PartialParseResult:
    value: Any
    complete: bool


@dataclass(slots=True)
class _StructuredOutputPlan:
    schema: dict[str, Any]
    validator: Any
    response_format: ResponseFormat
    provider_options: dict[str, Any]


def _coerce_schema(schema: Mapping[str, Any] | None) -> dict[str, Any]:
    if schema is None:
        raise TypeError("schema must be provided")
    if not isinstance(schema, Mapping):
        raise TypeError("schema must be a mapping")

    normalized_schema = copy.deepcopy(dict(schema))
    validator_cls = validator_for(normalized_schema)
    try:
        validator_cls.check_schema(normalized_schema)
    except SchemaError as exc:
        logger.debug("Invalid JSON schema provided", exc_info=True)
        raise ValueError(f"schema must be a valid JSON Schema: {exc.message}") from exc
    return normalized_schema


def _deep_merge_mappings(
    base: Mapping[str, Any] | None,
    additions: Mapping[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(base or {}))
    for key, value in additions.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge_mappings(existing, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _structured_provider_options(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "openai": {
            "response_format": {
                "type": "json_schema",
                "json_schema": schema,
                "strict": True,
            },
            "structured_output": {
                "provider": "openai",
                "strategy": "json_schema",
                "schema": schema,
                "strict": True,
            },
        },
        "gemini": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "structured_output": {
                "provider": "gemini",
                "strategy": "responseSchema",
                "schema": schema,
                "responseMimeType": "application/json",
            },
        },
        "anthropic": {
            "structured_output": {
                "provider": "anthropic",
                "strategy": "schema-instruction",
                "fallback": "forced-tool",
                "schema": schema,
            },
            "system_instruction": (
                "Return only valid JSON that matches the provided schema."
            ),
        },
    }


def _build_structured_output_plan(
    schema: Mapping[str, Any],
    *,
    provider_options: Mapping[str, Any] | None = None,
) -> _StructuredOutputPlan:
    normalized_schema = _coerce_schema(schema)
    validator_cls = validator_for(normalized_schema)
    validator = validator_cls(normalized_schema)
    response_format = ResponseFormat(
        type="json_schema",
        json_schema=normalized_schema,
        strict=True,
    )
    structured_provider_options = _structured_provider_options(normalized_schema)
    merged_provider_options = _deep_merge_mappings(
        provider_options,
        structured_provider_options,
    )

    return _StructuredOutputPlan(
        schema=normalized_schema,
        validator=validator,
        response_format=response_format,
        provider_options=merged_provider_options,
    )


def _parse_complete_object(
    text: str,
    *,
    validator: Any,
    schema: Mapping[str, Any],
    response: Response | None = None,
) -> Any:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.debug("Failed to parse structured output as JSON", exc_info=True)
        raise NoObjectGeneratedError(
            "failed to parse structured output as JSON",
            cause=exc,
            raw_text=text,
            response=response,
            schema=dict(schema),
        ) from exc

    try:
        validator.validate(value)
    except ValidationError as exc:
        logger.debug("Structured output failed JSON Schema validation", exc_info=True)
        raise NoObjectGeneratedError(
            "structured output did not match the provided JSON Schema",
            cause=exc,
            raw_text=text,
            response=response,
            schema=dict(schema),
            parsed=value,
        ) from exc

    return value


class _PartialJsonParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.pos = 0

    def parse(self) -> _PartialParseResult | None:
        self._skip_ws()
        value, complete, present = self._parse_value()
        if not present:
            return None
        return _PartialParseResult(value=value, complete=complete)

    def _skip_ws(self) -> None:
        while self.pos < self.length and self.text[self.pos].isspace():
            self.pos += 1

    def _parse_value(self) -> tuple[Any, bool, bool]:
        self._skip_ws()
        if self.pos >= self.length:
            return None, False, False

        char = self.text[self.pos]
        if char == "{":
            return self._parse_object()
        if char == "[":
            return self._parse_array()
        if char == '"':
            return self._parse_string()
        if char in "-0123456789":
            return self._parse_number()
        if self.text.startswith("true", self.pos):
            return self._parse_literal("true", True)
        if self.text.startswith("false", self.pos):
            return self._parse_literal("false", False)
        if self.text.startswith("null", self.pos):
            return self._parse_literal("null", None)
        return None, False, False

    def _parse_literal(self, literal: str, value: Any) -> tuple[Any, bool, bool]:
        end = self.pos + len(literal)
        if end > self.length:
            return None, False, False
        if self.text[self.pos:end] != literal:
            return None, False, False
        if end < self.length and self.text[end].isalnum():
            return None, False, False
        self.pos = end
        return value, True, True

    def _parse_string(self) -> tuple[Any, bool, bool]:
        start = self.pos
        self.pos += 1

        while self.pos < self.length:
            char = self.text[self.pos]
            if char == '"':
                self.pos += 1
                token = self.text[start:self.pos]
                try:
                    return json.loads(token), True, True
                except json.JSONDecodeError:
                    return None, False, False
            if char == "\\":
                self.pos += 1
                if self.pos >= self.length:
                    return None, False, False
                if self.text[self.pos] == "u":
                    if self.pos + 4 >= self.length:
                        return None, False, False
                    hex_digits = self.text[self.pos + 1 : self.pos + 5]
                    if any(ch not in "0123456789abcdefABCDEF" for ch in hex_digits):
                        return None, False, False
                    self.pos += 5
                    continue
                self.pos += 1
                continue
            self.pos += 1

        return None, False, False

    def _parse_number(self) -> tuple[Any, bool, bool]:
        start = self.pos
        pos = self.pos

        if self.text[pos] == "-":
            pos += 1
            if pos >= self.length:
                return None, False, False

        if pos >= self.length:
            return None, False, False

        if self.text[pos] == "0":
            pos += 1
        elif self.text[pos].isdigit():
            pos += 1
            while pos < self.length and self.text[pos].isdigit():
                pos += 1
        else:
            return None, False, False

        if pos < self.length and self.text[pos] == ".":
            pos += 1
            if pos >= self.length or not self.text[pos].isdigit():
                return None, False, False
            while pos < self.length and self.text[pos].isdigit():
                pos += 1

        if pos < self.length and self.text[pos] in "eE":
            exponent = pos + 1
            if exponent < self.length and self.text[exponent] in "+-":
                exponent += 1
            if exponent >= self.length or not self.text[exponent].isdigit():
                return None, False, False
            exponent += 1
            while exponent < self.length and self.text[exponent].isdigit():
                exponent += 1
            pos = exponent

        token = self.text[start:pos]
        if pos < self.length and self.text[pos] in "0123456789eE+-.":
            return None, False, False

        try:
            value = json.loads(token)
        except json.JSONDecodeError:
            return None, False, False

        self.pos = pos
        return value, True, True

    def _parse_array(self) -> tuple[Any, bool, bool]:
        self.pos += 1
        items: list[Any] = []
        has_content = False
        self._skip_ws()

        if self.pos >= self.length:
            return items, False, False
        if self.text[self.pos] == "]":
            self.pos += 1
            return items, True, True

        while True:
            self._skip_ws()
            if self.pos >= self.length:
                return items, False, has_content

            value, _complete, present = self._parse_value()
            if not present:
                return items, False, has_content

            items.append(value)
            has_content = True
            self._skip_ws()
            if self.pos >= self.length:
                return items, False, has_content

            char = self.text[self.pos]
            if char == ",":
                self.pos += 1
                self._skip_ws()
                if self.pos >= self.length:
                    return items, False, has_content
                continue
            if char == "]":
                self.pos += 1
                return items, True, True
            return items, False, has_content

    def _parse_object(self) -> tuple[Any, bool, bool]:
        self.pos += 1
        items: dict[str, Any] = {}
        has_content = False
        self._skip_ws()

        if self.pos >= self.length:
            return items, False, False
        if self.text[self.pos] == "}":
            self.pos += 1
            return items, True, True

        while True:
            self._skip_ws()
            if self.pos >= self.length:
                return items, False, has_content
            if self.text[self.pos] != '"':
                return items, False, has_content

            key, complete, present = self._parse_string()
            if not present or not complete:
                return items, False, has_content

            self._skip_ws()
            if self.pos >= self.length or self.text[self.pos] != ":":
                return items, False, has_content
            self.pos += 1
            self._skip_ws()
            if self.pos >= self.length:
                return items, False, has_content

            value, _complete, present = self._parse_value()
            if not present:
                return items, False, has_content

            items[key] = value
            has_content = True
            self._skip_ws()
            if self.pos >= self.length:
                return items, False, has_content

            char = self.text[self.pos]
            if char == ",":
                self.pos += 1
                self._skip_ws()
                if self.pos >= self.length:
                    return items, False, has_content
                continue
            if char == "}":
                self.pos += 1
                return items, True, True
            return items, False, has_content


def _parse_partial_json(text: str) -> _PartialParseResult | None:
    parser = _PartialJsonParser(text)
    return parser.parse()


class _StructuredObjectIterator(AsyncIterator[Any]):
    def __init__(self, stream: _StructuredStreamResult) -> None:
        self._stream = stream

    def __aiter__(self) -> _StructuredObjectIterator:
        return self

    def __del__(self) -> None:
        _best_effort_close_awaitable(self._stream.close())

    async def __anext__(self) -> Any:
        return await self._stream.__anext__()

    async def aclose(self) -> None:
        await self._stream.close()

    async def close(self) -> None:
        await self.aclose()


class _StructuredStreamResult(StreamResult):
    def __init__(
        self,
        stream_result: StreamResult,
        *,
        schema: Mapping[str, Any],
        validator: Any,
    ) -> None:
        super().__init__()
        self._stream = stream_result
        self._schema = schema
        self._validator = validator
        self._closed = False
        self._finished = False
        self._terminal_error: BaseException | None = None
        self._final_response: Response | None = None
        self._final_object: Any = _MISSING
        self._last_partial_object: Any = _MISSING

    def __aiter__(self) -> AsyncIterator[Any]:
        return _StructuredObjectIterator(self)

    @property
    def text_stream(self) -> AsyncIterator[str] | _StructuredStreamResult:
        return self._stream.text_stream

    @property
    def partial_response(self) -> Response:
        return self._stream.partial_response

    @property
    def partial_object(self) -> Any:
        if self._final_object is not _MISSING:
            return self._final_object
        if self._last_partial_object is not _MISSING:
            return self._last_partial_object
        return None

    async def __anext__(self) -> Any:
        if self._terminal_error is not None:
            raise self._terminal_error
        if self._closed or self._finished:
            raise StopAsyncIteration

        while True:
            try:
                event = await self._stream.__anext__()
            except StopAsyncIteration:
                self._finished = True
                raw_response = await self._stream.response()
                self._final_response = raw_response
                try:
                    final_object = _parse_complete_object(
                        raw_response.text,
                        validator=self._validator,
                        schema=self._schema,
                        response=raw_response,
                    )
                except NoObjectGeneratedError as error:
                    self._terminal_error = error
                    await self.close()
                    raise

                self._final_object = final_object
                self._closed = True
                if (
                    self._last_partial_object is _MISSING
                    or final_object != self._last_partial_object
                ):
                    self._last_partial_object = final_object
                    return final_object
                raise StopAsyncIteration
            except Exception as error:
                self._terminal_error = error
                self._finished = True
                await self.close()
                raise

            if event.type not in (
                StreamEventType.TEXT_DELTA,
                StreamEventType.FINISH,
                StreamEventType.ERROR,
            ):
                continue

            partial = _parse_partial_json(self._stream.partial_response.text)
            if partial is None or partial.value is _MISSING:
                continue
            if (
                not partial.complete
                and isinstance(partial.value, (dict, list))
                and not partial.value
            ):
                continue
            if partial.value == self._last_partial_object:
                continue

            self._last_partial_object = partial.value
            return partial.value

    async def response(self) -> Response:
        if self._terminal_error is not None:
            raise self._terminal_error
        if self._final_response is not None and self._final_object is not _MISSING:
            return self._final_response

        raw_response = await self._stream.response()
        self._final_response = raw_response
        if self._terminal_error is not None:
            raise self._terminal_error

        try:
            self._final_object = _parse_complete_object(
                raw_response.text,
                validator=self._validator,
                schema=self._schema,
                response=raw_response,
            )
        except NoObjectGeneratedError as error:
            self._terminal_error = error
            self._finished = True
            self._closed = True
            raise

        self._finished = True
        self._closed = True
        return raw_response

    async def object(self) -> Any:
        if self._terminal_error is not None:
            raise self._terminal_error
        if self._final_object is not _MISSING:
            return self._final_object

        await self.response()
        if self._terminal_error is not None:
            raise self._terminal_error
        return self._final_object

    async def close(self) -> None:
        self._closed = True
        self._finished = True
        await self._stream.close()

    async def aclose(self) -> None:
        await self.close()


async def generate_object(
    model: str | None = None,
    *,
    prompt: str | None = None,
    messages: Any = None,
    system: str | None = None,
    tools: Any = None,
    tool_choice: Any = None,
    max_tool_rounds: int = 1,
    stop_when: Any = None,
    schema: Mapping[str, Any] | None = None,
    temperature: Any = None,
    top_p: Any = None,
    max_tokens: Any = None,
    stop_sequences: Any = None,
    reasoning_effort: Any = None,
    provider: str | None = None,
    provider_options: Mapping[str, Any] | None = None,
    max_retries: int = 2,
    timeout: Any = None,
    abort_signal: Any = None,
    repair_tool_call: Any = None,
    client: Any = None,
) -> GenerateResult:
    plan = _build_structured_output_plan(schema, provider_options=provider_options)
    result = await generate(
        model,
        prompt=prompt,
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tool_rounds=max_tool_rounds,
        stop_when=stop_when,
        response_format=plan.response_format,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stop_sequences=stop_sequences,
        reasoning_effort=reasoning_effort,
        provider=provider,
        provider_options=plan.provider_options,
        max_retries=max_retries,
        timeout=timeout,
        abort_signal=abort_signal,
        repair_tool_call=repair_tool_call,
        client=client,
    )
    output = _parse_complete_object(
        result.response.text,
        validator=plan.validator,
        schema=plan.schema,
        response=result.response,
    )
    return replace(result, output=output)


def stream_object(
    model: str | None = None,
    *,
    prompt: str | None = None,
    messages: Any = None,
    system: str | None = None,
    tools: Any = None,
    tool_choice: Any = None,
    max_tool_rounds: int = 1,
    stop_when: Any = None,
    schema: Mapping[str, Any] | None = None,
    temperature: Any = None,
    top_p: Any = None,
    max_tokens: Any = None,
    stop_sequences: Any = None,
    reasoning_effort: Any = None,
    provider: str | None = None,
    provider_options: Mapping[str, Any] | None = None,
    max_retries: int = 2,
    timeout: Any = None,
    abort_signal: Any = None,
    repair_tool_call: Any = None,
    client: Any = None,
) -> StreamResult:
    plan = _build_structured_output_plan(schema, provider_options=provider_options)
    raw_stream = stream(
        model,
        prompt=prompt,
        messages=messages,
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        max_tool_rounds=max_tool_rounds,
        stop_when=stop_when,
        response_format=plan.response_format,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stop_sequences=stop_sequences,
        reasoning_effort=reasoning_effort,
        provider=provider,
        provider_options=plan.provider_options,
        max_retries=max_retries,
        timeout=timeout,
        abort_signal=abort_signal,
        repair_tool_call=repair_tool_call,
        client=client,
    )
    return _StructuredStreamResult(
        raw_stream,
        schema=plan.schema,
        validator=plan.validator,
    )


__all__ = ["generate_object", "stream_object"]
