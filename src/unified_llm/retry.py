from __future__ import annotations

import asyncio
import inspect
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from .errors import SDKError

logger = logging.getLogger(__name__)

T = TypeVar("T")
RetryPredicate = Callable[[BaseException], bool]
RetryCallback = Callable[[BaseException, int, float], Any]
Sleeper = Callable[[float], Awaitable[None] | None]
RandomSource = random.Random | Callable[[float, float], float] | None


def _is_int_like(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _coerce_positive_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    coerced = float(value)
    if coerced < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return coerced


def _coerce_optional_retry_after(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        coerced = float(value)
        return coerced if coerced >= 0 else None
    if isinstance(value, str):
        try:
            coerced = float(value.strip())
        except ValueError:
            logger.debug("Unexpected retry_after string value: %r", value)
            return None
        return coerced if coerced >= 0 else None
    logger.debug("Unexpected retry_after value type: %s", type(value).__name__)
    return None


def _random_multiplier(random_source: RandomSource) -> float:
    if random_source is None:
        return random.uniform(0.5, 1.5)

    uniform = getattr(random_source, "uniform", None)
    if callable(uniform):
        return float(uniform(0.5, 1.5))

    if callable(random_source):
        return float(random_source(0.5, 1.5))

    raise TypeError("random_source must provide uniform() or be callable")


def is_retryable_error(error: BaseException) -> bool:
    retryable = getattr(error, "retryable", None)
    if retryable is not None:
        return bool(retryable)
    return not isinstance(error, SDKError)


def calculate_retry_delay(
    policy: RetryPolicy,
    attempt: int,
    *,
    error: BaseException | None = None,
    random_source: RandomSource = None,
) -> float | None:
    return policy.calculate_delay(
        attempt,
        error=error,
        random_source=random_source,
    )


@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 2
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    on_retry: RetryCallback | None = None

    def __post_init__(self) -> None:
        if not _is_int_like(self.max_retries):
            raise TypeError("max_retries must be an integer")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")

        self.base_delay = _coerce_positive_number(self.base_delay, "base_delay")
        self.max_delay = _coerce_positive_number(self.max_delay, "max_delay")
        self.backoff_multiplier = _coerce_positive_number(
            self.backoff_multiplier,
            "backoff_multiplier",
        )
        if self.backoff_multiplier == 0:
            raise ValueError("backoff_multiplier must be greater than 0")
        if not isinstance(self.jitter, bool):
            raise TypeError("jitter must be a boolean")
        if self.on_retry is not None and not callable(self.on_retry):
            raise TypeError("on_retry must be callable or None")

    def is_retryable_error(self, error: BaseException) -> bool:
        return is_retryable_error(error)

    def calculate_delay(
        self,
        attempt: int,
        *,
        error: BaseException | None = None,
        random_source: RandomSource = None,
    ) -> float | None:
        if not _is_int_like(attempt):
            raise TypeError("attempt must be an integer")
        if attempt < 0:
            raise ValueError("attempt must be non-negative")

        retry_after = _coerce_optional_retry_after(getattr(error, "retry_after", None))
        if retry_after is not None:
            if retry_after > self.max_delay:
                logger.debug(
                    "Retry-After %.3fs exceeds max_delay %.3fs; not retrying",
                    retry_after,
                    self.max_delay,
                )
                return None
            return retry_after

        delay = min(
            self.base_delay * (self.backoff_multiplier**attempt),
            self.max_delay,
        )
        if self.jitter:
            delay *= _random_multiplier(random_source)
        return float(delay)

    async def retry(
        self,
        operation: Callable[[], Awaitable[T] | T] | Awaitable[T] | T,
        *,
        should_retry: RetryPredicate | None = None,
        sleeper: Sleeper | None = None,
        random_source: RandomSource = None,
    ) -> T:
        return await retry(
            operation,
            policy=self,
            should_retry=should_retry,
            sleeper=sleeper,
            random_source=random_source,
        )


async def retry(
    operation: Callable[[], Awaitable[T] | T] | Awaitable[T] | T,
    *,
    policy: RetryPolicy | None = None,
    should_retry: RetryPredicate | None = None,
    sleeper: Sleeper | None = None,
    random_source: RandomSource = None,
) -> T:
    resolved_policy = policy or RetryPolicy()
    retry_predicate = should_retry or resolved_policy.is_retryable_error
    sleep = sleeper or asyncio.sleep

    attempt = 0
    while True:
        try:
            value = operation() if callable(operation) else operation
            if inspect.isawaitable(value):
                return await value
            return value
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not retry_predicate(error):
                logger.debug(
                    "Not retrying non-retryable error %s",
                    error.__class__.__name__,
                )
                raise

            if attempt >= resolved_policy.max_retries:
                logger.debug(
                    "Retry budget exhausted after %d attempts",
                    resolved_policy.max_retries,
                )
                raise

            delay = resolved_policy.calculate_delay(
                attempt,
                error=error,
                random_source=random_source,
            )
            if delay is None:
                raise

            if resolved_policy.on_retry is not None:
                callback_result = resolved_policy.on_retry(error, attempt, delay)
                if inspect.isawaitable(callback_result):
                    await callback_result

            logger.debug(
                "Retrying %s after %.3fs (attempt %d of %d)",
                error.__class__.__name__,
                delay,
                attempt + 1,
                resolved_policy.max_retries,
            )

            sleep_result = sleep(delay)
            if inspect.isawaitable(sleep_result):
                await sleep_result
            attempt += 1


__all__ = [
    "RetryPolicy",
    "calculate_retry_delay",
    "is_retryable_error",
    "retry",
]
