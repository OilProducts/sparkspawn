from __future__ import annotations

import inspect
import logging
import os
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from ..errors import ConfigurationError
from ..provider_utils.anthropic import (
    _provider_error_from_httpx_error,
    build_anthropic_messages_request,
    build_anthropic_messages_url,
    normalize_anthropic_base_url,
    normalize_anthropic_response,
    normalize_anthropic_stream_events,
)
from ..provider_utils.errors import provider_error_from_response
from ..provider_utils.http import provider_options_for
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


class AnthropicAdapter:
    name = "anthropic"

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

        resolved_api_key = api_key if api_key is not None else _env_value("ANTHROPIC_API_KEY")
        resolved_base_url = base_url if base_url is not None else _env_value("ANTHROPIC_BASE_URL")

        self.api_key = resolved_api_key
        self.base_url = normalize_anthropic_base_url(resolved_base_url)
        self.timeout = timeout
        self.default_headers = dict(default_headers or {})
        self.config = {
            "api_key": self.api_key,
        }
        if base_url is not None or _env_value("ANTHROPIC_BASE_URL") is not None:
            self.config["base_url"] = self.base_url
        self._messages_url = build_anthropic_messages_url(self.base_url)
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

    def _request_kwargs(
        self,
        request: Any,
        *,
        stream: bool = False,
    ) -> dict[str, Any]:
        provider_options = provider_options_for(request, self.name)
        body, header_overrides = build_anthropic_messages_request(
            request,
            provider_options=provider_options,
            stream=stream,
        )

        if self.api_key is None:
            raise ConfigurationError("Anthropic API key is required")

        headers = httpx.Headers(self.default_headers)
        headers.update(header_overrides)
        headers["x-api-key"] = self.api_key

        kwargs: dict[str, Any] = {
            "headers": headers,
            "json": body,
        }
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout
        return kwargs

    async def complete(self, request: Any) -> Response:
        if not hasattr(request, "messages"):
            raise TypeError("request must be a Request")

        client = self._client
        if client is None:
            raise ConfigurationError("Anthropic HTTP client is not available")

        try:
            response = await client.post(self._messages_url, **self._request_kwargs(request))
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
        return normalize_anthropic_response(
            payload,
            provider=self.name,
            headers=response.headers,
            raw=payload,
        )

    def stream(self, request: Any) -> AsyncIterator[StreamEvent]:
        async def _stream() -> AsyncIterator[StreamEvent]:
            if not hasattr(request, "messages"):
                raise TypeError("request must be a Request")

            client = self._client
            if client is None:
                raise ConfigurationError("Anthropic HTTP client is not available")

            try:
                async with client.stream(
                    "POST",
                    self._messages_url,
                    **self._request_kwargs(request, stream=True),
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise provider_error_from_response(
                            response,
                            provider=self.name,
                            raw=normalize_raw_payload(response.text),
                        )

                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type.casefold():
                        payload = normalize_raw_payload(await response.aread())
                        normalized = normalize_anthropic_response(
                            payload,
                            provider=self.name,
                            headers=response.headers,
                            raw=payload,
                        )
                        yield StreamEvent(
                            type=StreamEventType.STREAM_START,
                            response=normalized,
                            raw=payload,
                        )
                        yield StreamEvent(
                            type=StreamEventType.FINISH,
                            finish_reason=normalized.finish_reason,
                            usage=normalized.usage,
                            response=normalized,
                            raw=payload,
                        )
                        return

                    async for event in normalize_anthropic_stream_events(
                        response,
                        provider=self.name,
                    ):
                        yield event
                        if event.type in (StreamEventType.FINISH, StreamEventType.ERROR):
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
            logger.exception("Unexpected error closing Anthropic HTTP client")


__all__ = ["AnthropicAdapter"]
