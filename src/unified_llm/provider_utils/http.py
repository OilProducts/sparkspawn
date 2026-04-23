from __future__ import annotations

import copy
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from ..types import RateLimitInfo, Request

logger = logging.getLogger(__name__)


def _provider_options_source(
    request_or_options: Request | Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if request_or_options is None:
        return None
    if isinstance(request_or_options, Mapping):
        return request_or_options

    provider_options = getattr(request_or_options, "provider_options", None)
    if provider_options is None:
        return None
    if not isinstance(provider_options, Mapping):
        logger.debug(
            "Unexpected request provider_options type: %s",
            type(provider_options).__name__,
        )
        raise TypeError("provider_options must be a mapping or None")
    return provider_options


def extract_provider_options(
    request_or_options: Request | Mapping[str, Any] | None,
    selected_provider: str | None = None,
    *,
    provider: str | None = None,
) -> dict[str, Any]:
    provider_name = selected_provider if selected_provider is not None else provider
    if provider_name is None:
        raise TypeError("selected_provider must be provided")
    if not isinstance(provider_name, str):
        raise TypeError("selected_provider must be a string")

    source = _provider_options_source(request_or_options)
    if source is None:
        return {}

    selected_options = source.get(provider_name)
    if selected_options is None:
        return {}
    if not isinstance(selected_options, Mapping):
        logger.debug(
            "Unexpected provider options type for %s: %s",
            provider_name,
            type(selected_options).__name__,
        )
        raise TypeError("selected provider options must be a mapping or None")

    try:
        return copy.deepcopy(dict(selected_options))
    except Exception:
        logger.exception(
            "Unexpected failure isolating provider options for %s",
            provider_name,
        )
        raise


provider_options_for = extract_provider_options


def _coerce_header_value(headers: Any, header_name: str) -> Any | None:
    if headers is None:
        return None
    if isinstance(headers, Mapping):
        for key, value in headers.items():
            if str(key).casefold() == header_name.casefold():
                return value
        return None

    getter = getattr(headers, "get", None)
    if callable(getter):
        try:
            value = getter(header_name)
        except Exception:
            logger.debug(
                "Unexpected header lookup failure for %s",
                header_name,
                exc_info=True,
            )
            return None
        if value is not None:
            return value

    attrs = getattr(headers, "headers", None)
    if attrs is not None and attrs is not headers:
        return _coerce_header_value(attrs, header_name)

    return None


def _coerce_retry_after_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    if isinstance(value, (bytes, bytearray)):
        try:
            value = bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Unable to decode Retry-After header as UTF-8", exc_info=True)
            value = bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError, IndexError):
                logger.debug(
                    "Unable to parse Retry-After header value %r",
                    value,
                    exc_info=True,
                )
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            delay = (parsed - datetime.now(UTC)).total_seconds()
            return delay if delay >= 0 else 0.0
    logger.debug(
        "Unexpected Retry-After header type: %s",
        type(value).__name__,
    )
    return None


def parse_retry_after(headers_or_value: Any) -> float | None:
    if isinstance(headers_or_value, Mapping) or hasattr(headers_or_value, "get"):
        value = _coerce_header_value(headers_or_value, "retry-after")
        if value is None:
            value = _coerce_header_value(headers_or_value, "Retry-After")
        if value is None:
            return None
        return _coerce_retry_after_seconds(value)
    return _coerce_retry_after_seconds(headers_or_value)


retry_after_from_headers = parse_retry_after


def _coerce_int_header(headers: Any, *header_names: str) -> int | None:
    for header_name in header_names:
        value = _coerce_header_value(headers, header_name)
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            continue
        if isinstance(value, (bytes, bytearray)):
            try:
                value = bytes(value).decode("utf-8")
            except UnicodeDecodeError:
                logger.debug("Unable to decode rate-limit header as UTF-8", exc_info=True)
                value = bytes(value).decode("utf-8", errors="replace")
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            try:
                return int(text)
            except ValueError:
                try:
                    number = float(text)
                except ValueError:
                    logger.debug(
                        "Unable to parse integer rate-limit header %s=%r",
                        header_name,
                        value,
                        exc_info=True,
                    )
                    continue
                if number.is_integer():
                    return int(number)
        logger.debug(
            "Unexpected rate-limit header type for %s: %s",
            header_name,
            type(value).__name__,
        )
    return None


def _coerce_reset_value(headers: Any, *header_names: str) -> Any | None:
    for header_name in header_names:
        value = _coerce_header_value(headers, header_name)
        if value is None:
            continue
        if isinstance(value, (bytes, bytearray)):
            try:
                return bytes(value).decode("utf-8").strip()
            except UnicodeDecodeError:
                logger.debug(
                    "Unable to decode rate-limit reset header as UTF-8",
                    exc_info=True,
                )
                return bytes(value).decode("utf-8", errors="replace").strip()
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return value
    return None


def normalize_rate_limit(headers: Any | None) -> RateLimitInfo | None:
    if headers is None:
        return None

    rate_limit = RateLimitInfo(
        requests_remaining=_coerce_int_header(
            headers,
            "x-ratelimit-remaining-requests",
            "anthropic-ratelimit-requests-remaining",
        ),
        requests_limit=_coerce_int_header(
            headers,
            "x-ratelimit-limit-requests",
            "anthropic-ratelimit-requests-limit",
        ),
        tokens_remaining=_coerce_int_header(
            headers,
            "x-ratelimit-remaining-tokens",
            "anthropic-ratelimit-tokens-remaining",
        ),
        tokens_limit=_coerce_int_header(
            headers,
            "x-ratelimit-limit-tokens",
            "anthropic-ratelimit-tokens-limit",
        ),
        reset_at=_coerce_reset_value(
            headers,
            "x-ratelimit-reset",
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
            "ratelimit-reset",
            "anthropic-ratelimit-requests-reset",
            "anthropic-ratelimit-tokens-reset",
        ),
    )

    if (
        rate_limit.requests_remaining is None
        and rate_limit.requests_limit is None
        and rate_limit.tokens_remaining is None
        and rate_limit.tokens_limit is None
        and rate_limit.reset_at is None
    ):
        return None
    return rate_limit


normalize_rate_limit_headers = normalize_rate_limit


__all__ = [
    "extract_provider_options",
    "normalize_rate_limit",
    "normalize_rate_limit_headers",
    "parse_retry_after",
    "provider_options_for",
    "retry_after_from_headers",
]
