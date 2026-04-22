from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import replace
from enum import StrEnum
from typing import Any

from ..types import FinishReason, Usage, Warning

logger = logging.getLogger(__name__)

_CANONICAL_FINISH_REASONS = {"stop", "length", "tool_calls", "content_filter", "error", "other"}
_FINISH_REASON_ALIASES = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "safety": "content_filter",
    "recitation": "content_filter",
}


def _coerce_text(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (bytes, bytearray)):
        try:
            text = bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug(
                "Unable to decode %s as UTF-8",
                field_name,
                exc_info=True,
            )
            text = bytes(value).decode("utf-8", errors="replace")
        text = text.strip()
        return text or None
    logger.debug(
        "Unexpected %s type: %s",
        field_name,
        type(value).__name__,
    )
    return None


def _lookup_case_insensitive(mapping: Mapping[str, Any], name: str) -> Any | None:
    if name in mapping:
        return mapping[name]
    normalized_name = name.casefold()
    for key, value in mapping.items():
        if str(key).casefold() == normalized_name:
            return value
    return None


def _lookup_value(source: Any, *names: str) -> Any | None:
    if source is None:
        return None
    if isinstance(source, Mapping):
        for name in names:
            value = _lookup_case_insensitive(source, name)
            if value is not None:
                return value
        return None
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _lookup_path(source: Any, *path: str) -> Any | None:
    current = source
    for name in path:
        current = _lookup_value(current, name)
        if current is None:
            return None
    return current


def _coerce_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, (bytes, bytearray)):
        try:
            value = bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Unable to decode %s as UTF-8", field_name, exc_info=True)
            value = bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            try:
                number = float(text)
            except ValueError:
                logger.debug(
                    "Unable to coerce %s to an integer: %r",
                    field_name,
                    value,
                    exc_info=True,
                )
                return None
            if number.is_integer():
                return int(number)
    logger.debug(
        "Unexpected %s type: %s",
        field_name,
        type(value).__name__,
    )
    return None


def normalize_raw_payload(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, (bytes, bytearray)):
        try:
            text = bytes(payload).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Unable to decode raw payload as UTF-8", exc_info=True)
            text = bytes(payload).decode("utf-8", errors="replace")
        return normalize_raw_payload(text)
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return text
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                logger.debug("Failed to parse raw payload as JSON", exc_info=True)
                return text
        return text
    return payload


normalize_response_payload = normalize_raw_payload


def _finish_reason_text(value: Any) -> tuple[str, str | None]:
    if isinstance(value, FinishReason):
        text = _coerce_text(value.reason, field_name="finish_reason")
        if text is None:
            raise TypeError("finish_reason must be a FinishReason or string")
        normalized = _normalize_finish_reason_text(text)
        if value.raw is not None and normalized == text.casefold():
            return normalized, value.raw
        if normalized in _CANONICAL_FINISH_REASONS:
            return normalized, value.raw if value.raw is not None else text
        return normalized, value.raw if value.raw is not None else text
    if isinstance(value, StrEnum):
        value = value.value
    text = _coerce_text(value, field_name="finish_reason")
    if text is None:
        raise TypeError("finish_reason must be a FinishReason or string")
    normalized = _normalize_finish_reason_text(text)
    if normalized in _CANONICAL_FINISH_REASONS:
        return normalized, text
    return normalized, text


def _normalize_finish_reason_text(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in _CANONICAL_FINISH_REASONS:
        return normalized
    return _FINISH_REASON_ALIASES.get(normalized, "other")


def normalize_finish_reason(
    value: Any,
    *,
    provider: str | None = None,
) -> FinishReason:
    if value is None:
        return FinishReason(reason="other")
    if isinstance(value, Mapping):
        extracted = _lookup_value(
            value,
            "finish_reason",
            "finishReason",
            "stop_reason",
            "stopReason",
            "reason",
        )
        if extracted is None:
            logger.debug(
                "Unable to find finish reason in provider payload for %s",
                provider or "unknown provider",
            )
            return FinishReason(reason="other", raw=None)
        reason, raw = _finish_reason_text(extracted)
        return FinishReason(reason=reason, raw=raw)

    reason, raw = _finish_reason_text(value)
    return FinishReason(reason=reason, raw=raw)


def _usage_sources(value: Any) -> list[Any]:
    sources: list[Any] = []
    if value is None:
        return sources
    if isinstance(value, (str, bytes, bytearray)):
        return sources
    if isinstance(value, Mapping):
        sources.append(value)
        for key in ("usage", "usageMetadata", "usage_metadata"):
            nested = _lookup_value(value, key)
            if nested is not None and nested not in sources:
                sources.append(nested)
        return sources

    candidate_attrs = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "promptTokenCount",
        "candidatesTokenCount",
        "thoughtsTokenCount",
        "cachedContentTokenCount",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "usage",
        "usageMetadata",
        "usage_metadata",
        "output_tokens_details",
        "input_tokens_details",
        "outputTokensDetails",
    )
    if not any(hasattr(value, attr) for attr in candidate_attrs):
        return sources

    sources.append(value)
    if not isinstance(value, Mapping):
        for attr in ("usage", "usageMetadata", "usage_metadata"):
            nested = getattr(value, attr, None)
            if nested is not None and nested not in sources:
                sources.append(nested)
    return sources


def _first_usage_value(sources: list[Any], *paths: tuple[str, ...]) -> Any | None:
    for source in sources:
        for path in paths:
            value = _lookup_path(source, *path)
            if value is not None:
                return value
    return None


def normalize_usage(
    value: Any,
    *,
    provider: str | None = None,
    raw: Any | None = None,
) -> Usage:
    if isinstance(value, Usage):
        if raw is None or value.raw is raw:
            return value
        return replace(value, raw=raw)

    if value is None:
        return Usage(raw=raw)

    sources = _usage_sources(value)
    if not sources:
        raise TypeError("usage must be a Usage, mapping, or provider usage object")

    input_tokens = _coerce_int(
        _first_usage_value(
            sources,
            ("input_tokens",),
            ("prompt_tokens",),
            ("promptTokenCount",),
        ),
        field_name="input_tokens",
    )
    output_tokens = _coerce_int(
        _first_usage_value(
            sources,
            ("output_tokens",),
            ("completion_tokens",),
            ("candidatesTokenCount",),
        ),
        field_name="output_tokens",
    )
    total_tokens = _coerce_int(
        _first_usage_value(
            sources,
            ("total_tokens",),
            ("totalTokenCount",),
        ),
        field_name="total_tokens",
    )
    reasoning_tokens = _coerce_int(
        _first_usage_value(
            sources,
            ("output_tokens_details", "reasoning_tokens"),
            ("output_tokens_details", "reasoningTokens"),
            ("outputTokensDetails", "reasoningTokens"),
            ("reasoning_tokens",),
            ("thoughtsTokenCount",),
        ),
        field_name="reasoning_tokens",
    )
    cache_read_tokens = _coerce_int(
        _first_usage_value(
            sources,
            ("input_tokens_details", "cached_tokens"),
            ("input_tokens_details", "cachedTokens"),
            ("inputTokensDetails", "cachedTokens"),
            ("cache_read_input_tokens",),
            ("cachedContentTokenCount",),
        ),
        field_name="cache_read_tokens",
    )
    cache_write_tokens = _coerce_int(
        _first_usage_value(
            sources,
            ("cache_creation_input_tokens",),
            ("cache_write_tokens",),
            ("cacheWriteTokens",),
        ),
        field_name="cache_write_tokens",
    )

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return Usage(
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        total_tokens=total_tokens or 0,
        reasoning_tokens=reasoning_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        raw=raw if raw is not None else value,
    )


def normalize_warnings(value: Any) -> list[Warning]:
    if value is None:
        return []
    if isinstance(value, Warning):
        return [value]
    if isinstance(value, Mapping) or isinstance(value, (str, bytes, bytearray)):
        items: Iterable[Any] = [value]
    elif isinstance(value, Iterable):
        items = value
    else:
        raise TypeError("warnings must be a warning, mapping, or iterable")

    warnings: list[Warning] = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, Warning):
            warnings.append(item)
            continue
        if isinstance(item, Mapping):
            message = _coerce_text(
                _lookup_value(
                    item,
                    "message",
                    "text",
                    "detail",
                    "description",
                    "warning",
                ),
                field_name="warning.message",
            )
            code = _coerce_text(
                _lookup_value(item, "code", "type", "warning_code"),
                field_name="warning.code",
            )
            if message is None:
                logger.debug("Skipping warning without a message: %r", item)
                continue
            warnings.append(Warning(message=message, code=code))
            continue
        message = _coerce_text(item, field_name="warning")
        if message is None:
            logger.debug("Skipping warning value that could not be normalized: %r", item)
            continue
        warnings.append(Warning(message=message))
    return warnings


normalize_warning_payload = normalize_warnings


__all__ = [
    "normalize_finish_reason",
    "normalize_raw_payload",
    "normalize_response_payload",
    "normalize_usage",
    "normalize_warning_payload",
    "normalize_warnings",
]
