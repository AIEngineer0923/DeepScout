"""Centralized retry policy for provider/search/fetch calls."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from deepscout_research.exceptions import RunCancelledError


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.4
    max_delay_s: float = 8.0
    jitter: bool = True


DEFAULT_RETRY_POLICY = RetryPolicy()

NON_RETRYABLE_STATUS = {400, 401, 403, 404, 422}


class NonRetryableError(Exception):
    """Validation, security, or cancellation failures must not be retried."""


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RunCancelledError | NonRetryableError):
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in NON_RETRYABLE_STATUS:
            return False
        return status == 429 or status >= 500
    return isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.ConnectError,
            ConnectionError,
            TimeoutError,
        ),
    )


def run_with_retry[T](
    operation: Callable[[], T],
    *,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    cancelled: Callable[[], bool] | None = None,
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        if cancelled is not None and cancelled():
            raise RunCancelledError("cancelled before retry attempt")
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if not is_retryable(exc) or attempt >= policy.max_attempts:
                raise
            delay = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
            if policy.jitter:
                delay = delay * (0.5 + random.random())
            if on_retry is not None:
                on_retry(attempt, exc)
            time.sleep(delay)
    assert last_error is not None
    raise last_error
