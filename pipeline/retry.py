"""Retry helper with exponential backoff and fail-fast auth handling."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


class RetryableError(RuntimeError):
    """Raised for transient network/rate-limit failures safe to retry."""


class NonRetryableError(RuntimeError):
    """Raised for auth, permission, or malformed input errors (fail fast)."""


def classify_http_status(status_code: int, message: str) -> RuntimeError:
    """Map an HTTP status code to RetryableError or NonRetryableError."""
    if status_code in RETRYABLE_STATUS_CODES:
        return RetryableError(f"Transient HTTP {status_code}: {message}")
    return NonRetryableError(f"Non-retryable HTTP {status_code}: {message}")


def run_with_retry(
    operation: Callable[[], T],
    max_attempts: int = 3,
    base_delay_sec: float = 1.5,
    max_delay_sec: float = 16.0,
    jitter_ratio: float = 0.2,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Execute `operation` with exponential backoff on transient failures."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except NonRetryableError:
            raise
        except (RetryableError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            delay = min(base_delay_sec * (2 ** (attempt - 1)), max_delay_sec)
            jitter = delay * jitter_ratio * random.uniform(0.0, 1.0)
            sleep_fn(delay + jitter)

    assert last_error is not None
    raise last_error
