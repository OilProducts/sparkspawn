from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, replace
from time import monotonic
from typing import Any, TypeVar

from .errors import AbortError, RequestTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_timeout_value(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if not _is_number(value):
        raise TypeError(f"{field_name} must be a number or None")
    coerced = float(value)
    if coerced < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return coerced


def _timeout_error(scope: str, timeout: float | None) -> RequestTimeoutError:
    if timeout is None:
        message = f"{scope} timed out"
    else:
        message = f"{scope} timed out after {timeout} seconds"
    return RequestTimeoutError(message, timeout=timeout, scope=scope)


def _abort_error(scope: str, reason: Any | None) -> AbortError:
    message = f"{scope} aborted"
    if reason is not None and isinstance(reason, str) and reason:
        message = reason
    return AbortError(message, reason=reason, scope=scope)


@dataclass(slots=True)
class TimeoutConfig:
    total: float | None = None
    per_step: float | None = None
    stream_read: float | None = None

    def __post_init__(self) -> None:
        self.total = _coerce_timeout_value(self.total, "total")
        self.per_step = _coerce_timeout_value(self.per_step, "per_step")
        self.stream_read = _coerce_timeout_value(self.stream_read, "stream_read")

    def with_stream_read(self, stream_read: float | None) -> TimeoutConfig:
        return replace(self, stream_read=_coerce_timeout_value(stream_read, "stream_read"))


@dataclass(slots=True)
class AdapterTimeout:
    connect: float = 10.0
    request: float = 120.0
    stream_read: float = 30.0

    def __post_init__(self) -> None:
        self.connect = _coerce_timeout_value(self.connect, "connect")
        self.request = _coerce_timeout_value(self.request, "request")
        self.stream_read = _coerce_timeout_value(self.stream_read, "stream_read")
        if self.connect is None or self.request is None or self.stream_read is None:
            raise TypeError("adapter timeout values must be numbers")


class AbortSignal:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason: Any | None = None
        self._waiters: set[asyncio.Future[None]] = set()
        self._waiters_lock = threading.Lock()

    def _register_waiter(self) -> asyncio.Future[None]:
        loop = asyncio.get_running_loop()
        waiter = loop.create_future()
        with self._waiters_lock:
            if self._event.is_set():
                waiter.set_result(None)
                return waiter
            self._waiters.add(waiter)
        return waiter

    def _release_waiter(self, waiter: asyncio.Future[None]) -> None:
        with self._waiters_lock:
            self._waiters.discard(waiter)

    @property
    def aborted(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> Any | None:
        return self._reason

    async def wait(self) -> None:
        waiter = self._register_waiter()
        try:
            await waiter
        finally:
            self._release_waiter(waiter)
        return None

    def throw_if_aborted(self) -> None:
        if self.aborted:
            raise _abort_error("operation", self.reason)

    def _abort(self, reason: Any | None = None) -> None:
        if self._event.is_set():
            return
        self._reason = reason
        self._event.set()
        with self._waiters_lock:
            waiters = tuple(self._waiters)
            self._waiters.clear()
        for waiter in waiters:
            if waiter.done():
                continue
            try:
                loop = waiter.get_loop()
                loop.call_soon_threadsafe(_resolve_abort_waiter, waiter)
            except RuntimeError:
                # The loop was already closed; there is no waiter to wake.
                continue


def _resolve_abort_waiter(waiter: asyncio.Future[None]) -> None:
    if not waiter.done():
        waiter.set_result(None)


class AbortController:
    def __init__(self) -> None:
        self._signal = AbortSignal()

    @property
    def signal(self) -> AbortSignal:
        return self._signal

    def abort(self, reason: Any | None = None) -> None:
        self._signal._abort(reason)


def check_abort(abort_signal: AbortSignal | None) -> None:
    if abort_signal is None:
        return
    abort_signal.throw_if_aborted()


def coerce_timeout_config(
    timeout: float | TimeoutConfig | None,
    *,
    stream_read: float | None = None,
) -> TimeoutConfig | None:
    if timeout is None:
        if stream_read is None:
            return None
        return TimeoutConfig(stream_read=stream_read)
    if isinstance(timeout, TimeoutConfig):
        if stream_read is None:
            return timeout
        return replace(timeout, stream_read=_coerce_timeout_value(stream_read, "stream_read"))
    if _is_number(timeout):
        return TimeoutConfig(total=float(timeout), stream_read=stream_read)
    raise TypeError("timeout must be a float, TimeoutConfig, or None")


def deadline_after(
    timeout: float | None,
    *,
    clock: Callable[[], float] = monotonic,
) -> float | None:
    if timeout is None:
        return None
    return clock() + timeout


def remaining_timeout(
    deadline: float | None,
    *,
    clock: Callable[[], float] = monotonic,
) -> float | None:
    if deadline is None:
        return None
    remaining = deadline - clock()
    return remaining if remaining > 0 else 0.0


async def await_with_timeout(
    awaitable: Awaitable[T],
    timeout: float | None,
    *,
    scope: str = "operation",
    abort_signal: AbortSignal | None = None,
) -> T:
    if timeout is not None and timeout < 0:
        raise ValueError("timeout must be non-negative or None")

    if abort_signal is not None:
        abort_signal.throw_if_aborted()

    if abort_signal is None:
        try:
            if timeout is None:
                return await awaitable
            return await asyncio.wait_for(awaitable, timeout)
        except TimeoutError as exc:
            logger.debug("%s timed out after %.3fs", scope, timeout)
            raise _timeout_error(scope, timeout) from exc

    task = asyncio.ensure_future(awaitable)
    abort_waiter = abort_signal._register_waiter()
    try:
        done, _ = await asyncio.wait(
            {task, abort_waiter},
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if task in done:
            return await task

        if abort_waiter in done:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            logger.debug("%s aborted", scope)
            raise _abort_error(scope, abort_signal.reason)

        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        logger.debug("%s timed out after %.3fs", scope, timeout)
        raise _timeout_error(scope, timeout)
    finally:
        abort_waiter.cancel()
        abort_signal._release_waiter(abort_waiter)


async def anext_with_timeout(
    iterator: Any,
    timeout: float | None,
    *,
    scope: str = "stream_read",
    abort_signal: AbortSignal | None = None,
) -> Any:
    return await await_with_timeout(
        iterator.__anext__(),
        timeout,
        scope=scope,
        abort_signal=abort_signal,
    )


__all__ = [
    "AbortController",
    "AbortSignal",
    "AdapterTimeout",
    "TimeoutConfig",
    "anext_with_timeout",
    "await_with_timeout",
    "check_abort",
    "coerce_timeout_config",
    "deadline_after",
    "remaining_timeout",
]
