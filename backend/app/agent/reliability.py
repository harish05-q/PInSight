import asyncio
import enum
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import structlog

log = structlog.get_logger()


class CircuitBreakerState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenException(Exception):
    pass


class CircuitBreaker:
    def __init__(self, max_failures: int = 5, cooldown_seconds: float = 60.0):
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        self.last_failure_time: float = 0.0

    def record_failure(self):
        self.last_failure_time = time.time()
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failed during probe -> immediately back to OPEN
            self.state = CircuitBreakerState.OPEN
            log.warning("Circuit breaker re-opened on half-open probe failure")
        else:
            self.failure_count += 1
            if self.failure_count >= self.max_failures:
                self.state = CircuitBreakerState.OPEN
                log.warning("Circuit breaker tripped to OPEN", max_failures=self.max_failures)

    def record_success(self):
        if self.state == CircuitBreakerState.HALF_OPEN:
            log.info("Circuit breaker probe succeeded, transitioning to CLOSED")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0

    def can_execute(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time >= self.cooldown_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow 1 execution to probe
        return True


# Global circuit breaker instances per dependency could be managed here.
# For simplicity, we'll allow passing a CB instance to the decorator, or default to a singleton.
default_cb = CircuitBreaker()

T = TypeVar("T")


def reliable(
    cb: CircuitBreaker = default_cb,
    max_retries: int = 3,
    timeout_seconds: float = 10.0,
    base_backoff: float = 1.0,
) -> Callable:
    """Decorator to wrap an async function with Timeout, Retry, and Circuit Breaker."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not cb.can_execute():
                raise CircuitBreakerOpenException("Circuit breaker is OPEN")

            last_exception = None
            for attempt in range(max_retries):
                # Only the first attempt in HALF_OPEN is allowed, if that fails, CB goes OPEN
                # and subsequent retries within this loop should immediately abort?
                # Actually, if we are in HALF_OPEN and fail, the CB records failure and goes OPEN.
                # If the CB is OPEN, we should abort retries immediately.
                if attempt > 0 and not cb.can_execute():
                    raise CircuitBreakerOpenException("Circuit breaker tripped during retries")

                try:
                    # Enforce timeout
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
                    cb.record_success()
                    return result
                except TimeoutError as e:
                    last_exception = e
                    log.warning(
                        "Timeout in reliable wrapper",
                        func=func.__name__,
                        attempt=attempt + 1,
                        timeout=timeout_seconds,
                    )
                    cb.record_failure()
                except Exception as e:
                    last_exception = e
                    log.warning(
                        "Exception in reliable wrapper",
                        func=func.__name__,
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    cb.record_failure()

                # Exponential backoff
                if attempt < max_retries - 1 and cb.state != CircuitBreakerState.OPEN:
                    sleep_time = base_backoff * (2**attempt)
                    await asyncio.sleep(sleep_time)

            if last_exception:
                raise last_exception

        return wrapper

    return decorator
