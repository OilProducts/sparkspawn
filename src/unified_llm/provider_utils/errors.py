from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..errors import (
    ProviderError,
    classify_provider_error_message,
    error_from_grpc_code,
    error_from_status_code,
)
from .http import parse_retry_after


def normalize_provider_error(
    status_code: int | str | None,
    message: str | None = None,
    *,
    provider: str | None = None,
    error_code: str | None = None,
    retry_after: float | None = None,
    headers: Mapping[str, Any] | Any | None = None,
    raw: Any = None,
    cause: BaseException | None = None,
) -> ProviderError:
    if retry_after is None:
        retry_after = parse_retry_after(headers)
    return error_from_status_code(
        status_code,
        message=message,
        provider=provider,
        error_code=error_code,
        retry_after=retry_after,
        raw=raw,
        cause=cause,
    )


provider_error_from_status_code = normalize_provider_error


def provider_error_from_response(
    response: Any,
    *,
    provider: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    raw: Any = None,
    cause: BaseException | None = None,
) -> ProviderError:
    status_code = getattr(response, "status_code", None)
    headers = getattr(response, "headers", None)
    if raw is None:
        raw = getattr(response, "text", None)
    return normalize_provider_error(
        status_code,
        message=message,
        provider=provider,
        error_code=error_code,
        headers=headers,
        raw=raw,
        cause=cause,
    )


__all__ = [
    "classify_provider_error_message",
    "error_from_grpc_code",
    "error_from_status_code",
    "normalize_provider_error",
    "provider_error_from_response",
    "provider_error_from_status_code",
]
