from __future__ import annotations

import inspect
import logging
import os
import threading
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from ..errors import ConfigurationError, NetworkError, RequestTimeoutError
from ..provider_utils.errors import provider_error_from_response
from ..provider_utils.gemini import (
    build_gemini_generate_content_request,
    build_gemini_generate_content_url,
    build_gemini_stream_generate_content_url,
    normalize_gemini_base_url,
    normalize_gemini_response,
    normalize_gemini_stream_events,
)
from ..provider_utils.normalization import normalize_raw_payload
from ..types import Response, StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


def _env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value


def _provider_error_from_httpx_error(
    error: httpx.HTTPError,
    *,
    provider: str,
) -> Exception:
    if isinstance(error, httpx.TimeoutException):
        message = str(error).strip() or f"{provider} request timed out"
        return RequestTimeoutError(message, provider=provider, cause=error)

    if isinstance(error, httpx.HTTPStatusError):
        response = getattr(error, "response", None)
        if response is not None:
            raw = normalize_raw_payload(response.text)
            return provider_error_from_response(
                response,
                provider=provider,
                raw=raw,
                cause=error,
            )

    message = str(error).strip() or f"{provider} network error"
    return NetworkError(message, provider=provider, cause=error)


class GeminiAdapter:
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        default_headers: Mapping[str, Any] | None = None,
        client: httpx.AsyncClient | Any | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        owns_client: bool = False,
    ) -> None:
        if client is not None and transport is not None:
            raise ValueError("client and transport are mutually exclusive")

        resolved_api_key = api_key if api_key is not None else _env_value("GEMINI_API_KEY")
        if resolved_api_key is None:
            resolved_api_key = _env_value("GOOGLE_API_KEY")
        resolved_base_url = base_url if base_url is not None else _env_value("GEMINI_BASE_URL")

        self.api_key = resolved_api_key
        self.base_url = normalize_gemini_base_url(resolved_base_url)
        self.timeout = timeout
        self.default_headers = dict(default_headers or {})
        self._tool_call_name_by_id: dict[str, str] = {}
        self._tool_call_name_lock = threading.RLock()
        self.config = {
            "api_key": self.api_key,
            "base_url": self.base_url,
        }
        self._client = client
        self._owns_client = owns_client or client is None
        self._client_closed = False

        if self._client is None:
            client_kwargs: dict[str, Any] = {}
            if transport is not None:
                client_kwargs["transport"] = transport
            if self.timeout is not None:
                client_kwargs["timeout"] = self.timeout
            self._client = httpx.AsyncClient(**client_kwargs)

    def _tool_name_for_id(self, tool_call_id: str) -> str | None:
        with self._tool_call_name_lock:
            return self._tool_call_name_by_id.get(tool_call_id)

    def _remember_tool_call_name(self, tool_call_id: str | None, name: str | None) -> None:
        if tool_call_id is None or name is None:
            return

        with self._tool_call_name_lock:
            existing_name = self._tool_call_name_by_id.get(tool_call_id)
            if existing_name is None:
                self._tool_call_name_by_id[tool_call_id] = name
                return
            if existing_name != name:
                logger.debug(
                    "Ignoring conflicting Gemini tool_call name for %s: %r != %r",
                    tool_call_id,
                    existing_name,
                    name,
                )

    def _remember_response_tool_calls(self, response: Response | None) -> None:
        if response is None:
            return

        for tool_call in response.tool_calls:
            self._remember_tool_call_name(
                getattr(tool_call, "id", None),
                getattr(tool_call, "name", None),
            )

    def _remember_stream_event_tool_calls(self, event: StreamEvent) -> None:
        self._remember_response_tool_calls(event.response)
        if event.tool_call is not None:
            self._remember_tool_call_name(
                getattr(event.tool_call, "id", None),
                getattr(event.tool_call, "name", None),
            )

    def _client_or_error(self) -> httpx.AsyncClient | Any:
        if self._client_closed or self._client is None:
            raise ConfigurationError("Gemini HTTP client is not available")
        return self._client

    def _request_kwargs(self, request: Any) -> dict[str, Any]:
        body = build_gemini_generate_content_request(
            request,
            tool_name_lookup=self._tool_name_for_id,
        )
        kwargs: dict[str, Any] = {
            "headers": httpx.Headers(self.default_headers),
            "json": body,
            "params": {"key": self.api_key},
        }
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout
        return kwargs

    async def complete(self, request: Any) -> Response:
        if not hasattr(request, "messages"):
            raise TypeError("request must be a Request")

        client = self._client_or_error()
        if self.api_key is None:
            raise ConfigurationError("Gemini API key is required")

        url = build_gemini_generate_content_url(self.base_url, request.model)
        try:
            response = await client.post(url, **self._request_kwargs(request))
        except httpx.HTTPError as exc:
            raise _provider_error_from_httpx_error(exc, provider=self.name) from exc

        if response.status_code >= 400:
            await response.aread()
            raise provider_error_from_response(
                response,
                provider=self.name,
                raw=normalize_raw_payload(response.text),
            )

        payload = normalize_raw_payload(response.text)
        normalized = normalize_gemini_response(
            payload,
            provider=self.name,
            headers=response.headers,
            raw=payload,
        )
        self._remember_response_tool_calls(normalized)
        return normalized

    def stream(self, request: Any) -> AsyncIterator[StreamEvent]:
        async def _stream() -> AsyncIterator[StreamEvent]:
            if not hasattr(request, "messages"):
                raise TypeError("request must be a Request")

            client = self._client_or_error()
            if self.api_key is None:
                raise ConfigurationError("Gemini API key is required")

            url = build_gemini_stream_generate_content_url(self.base_url, request.model)
            stream_kwargs = self._request_kwargs(request)
            stream_kwargs["params"] = {"key": self.api_key, "alt": "sse"}

            try:
                async with client.stream("POST", url, **stream_kwargs) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise provider_error_from_response(
                            response,
                            provider=self.name,
                            raw=normalize_raw_payload(response.text),
                        )

                    async for event in normalize_gemini_stream_events(
                        response,
                        provider=self.name,
                    ):
                        self._remember_stream_event_tool_calls(event)
                        yield event
                        if event.type in (
                            StreamEventType.FINISH,
                            StreamEventType.ERROR,
                        ):
                            return
            except httpx.HTTPError as exc:
                raise _provider_error_from_httpx_error(exc, provider=self.name) from exc

        return _stream()

    def supports_tool_choice(self, mode: str) -> bool:
        return mode.casefold() in {"auto", "none", "required", "named"}

    async def close(self) -> None:
        if self._client_closed or not self._owns_client:
            return None

        client = self._client
        if client is None:
            self._client_closed = True
            return None

        close = getattr(client, "aclose", None)
        if close is None or not callable(close):
            self._client_closed = True
            return None

        try:
            result = close()
            if inspect.isawaitable(result):
                await result
            self._client_closed = True
        except Exception:
            logger.exception("Unexpected error closing Gemini HTTP client")


__all__ = ["GeminiAdapter"]
