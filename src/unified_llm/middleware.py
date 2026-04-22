from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, TypeAlias

from .errors import SDKError
from .types import Request, Response, StreamEvent

logger = logging.getLogger(__name__)

CompleteNext: TypeAlias = Callable[[Request], Awaitable[Response]]
CompleteMiddleware: TypeAlias = Callable[
    [Request, CompleteNext],
    Response | Awaitable[Response],
]
StreamNext: TypeAlias = Callable[[Request], AsyncIterator[StreamEvent]]
StreamMiddleware: TypeAlias = Callable[
    [Request, StreamNext],
    AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]],
]
Middleware: TypeAlias = CompleteMiddleware | StreamMiddleware


def _callable_name(value: Any) -> str:
    name = getattr(value, "__name__", None)
    if isinstance(name, str) and name:
        return name

    qualname = getattr(value, "__qualname__", None)
    if isinstance(qualname, str) and qualname:
        return qualname

    return value.__class__.__name__


def _ensure_response_awaitable(
    value: Response | Awaitable[Response],
) -> Awaitable[Response]:
    if inspect.isawaitable(value):
        return value

    async def _completed() -> Response:
        return value

    return _completed()


class _DeferredAsyncIterator(AsyncIterator[StreamEvent]):
    def __init__(self, source: Awaitable[AsyncIterator[StreamEvent]]) -> None:
        self._source = source
        self._iterator: AsyncIterator[StreamEvent] | None = None

    def __aiter__(self) -> _DeferredAsyncIterator:
        return self

    async def __anext__(self) -> StreamEvent:
        if self._iterator is None:
            self._iterator = await self._source
        return await self._iterator.__anext__()

    async def aclose(self) -> None:
        iterator = self._iterator
        if iterator is None:
            return

        close = getattr(iterator, "aclose", None)
        if close is None:
            close = getattr(iterator, "close", None)
        if close is None:
            return

        result = close()
        if inspect.isawaitable(result):
            await result

    async def close(self) -> None:
        await self.aclose()


class _StreamMiddlewareIterator(AsyncIterator[StreamEvent]):
    def __init__(
        self,
        source: Callable[
            [Request],
            AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]],
        ],
        request: Request,
    ) -> None:
        self._source = source
        self._request = request
        self._iterator: AsyncIterator[StreamEvent] | None = None
        self._resolved = False

    def __aiter__(self) -> _StreamMiddlewareIterator:
        return self

    async def __anext__(self) -> StreamEvent:
        if not self._resolved:
            self._resolved = True
            try:
                iterator = self._source(self._request)
                if inspect.isawaitable(iterator):
                    iterator = await iterator
                self._iterator = iterator
            except SDKError:
                raise
            except Exception:
                logger.exception("Unexpected error executing stream middleware chain")
                raise

        assert self._iterator is not None

        try:
            return await self._iterator.__anext__()
        except StopAsyncIteration:
            raise
        except SDKError:
            raise
        except Exception:
            logger.exception("Unexpected error iterating stream middleware chain")
            raise

    async def aclose(self) -> None:
        iterator = self._iterator
        if iterator is None:
            return

        close = getattr(iterator, "aclose", None)
        if close is None:
            close = getattr(iterator, "close", None)
        if close is None:
            return

        result = close()
        if inspect.isawaitable(result):
            await result

    async def close(self) -> None:
        await self.aclose()


def build_complete_middleware_chain(
    terminal: CompleteNext,
    middleware: Sequence[CompleteMiddleware] | None = None,
) -> CompleteNext:
    chain = tuple(middleware or ())

    def invoke(index: int, request: Request) -> Response | Awaitable[Response]:
        if index >= len(chain):
            return terminal(request)

        current = chain[index]

        def next_call(next_request: Request, index: int = index + 1) -> Awaitable[Response]:
            return _ensure_response_awaitable(invoke(index, next_request))

        return current(request, next_call)

    async def call(request: Request) -> Response:
        try:
            response = invoke(0, request)
            if inspect.isawaitable(response):
                response = await response
            return response
        except SDKError:
            raise
        except Exception:
            logger.exception("Unexpected error executing complete middleware chain")
            raise

    return call


def build_stream_middleware_chain(
    terminal: StreamNext,
    middleware: Sequence[StreamMiddleware] | None = None,
) -> Callable[
    [Request],
    AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]],
]:
    chain = tuple(middleware or ())

    def invoke(
        index: int,
        request: Request,
    ) -> AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]]:
        if index >= len(chain):
            return terminal(request)

        current = chain[index]

        def next_call(next_request: Request, index: int = index + 1) -> AsyncIterator[StreamEvent]:
            return _ensure_stream_iterator(invoke(index, next_request))

        return current(request, next_call)

    return lambda request: invoke(0, request)


def complete_with_middleware(
    terminal: CompleteNext,
    request: Request,
    middleware: Sequence[CompleteMiddleware] | None = None,
) -> Awaitable[Response]:
    return build_complete_middleware_chain(terminal, middleware)(request)


def stream_with_middleware(
    terminal: StreamNext,
    request: Request,
    middleware: Sequence[StreamMiddleware] | None = None,
) -> AsyncIterator[StreamEvent]:
    return _StreamMiddlewareIterator(
        build_stream_middleware_chain(terminal, middleware),
        request,
    )


def _ensure_stream_iterator(
    value: AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]],
) -> AsyncIterator[StreamEvent]:
    if inspect.isawaitable(value):
        return _DeferredAsyncIterator(value)
    return value


__all__ = [
    "CompleteMiddleware",
    "CompleteNext",
    "Middleware",
    "StreamMiddleware",
    "StreamNext",
    "build_complete_middleware_chain",
    "build_stream_middleware_chain",
    "complete_with_middleware",
    "stream_with_middleware",
]
