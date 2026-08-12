import time

import pytest

from app.agent.reliability import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitBreakerState,
    reliable,
)

pytestmark = pytest.mark.asyncio


async def test_circuit_breaker_open_state():
    """Test the circuit breaker trips to OPEN after max failures."""
    cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)

    call_count = 0

    @reliable(cb=cb, max_retries=1, timeout_seconds=1.0)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        raise ValueError("Simulated failure")

    for _ in range(3):
        with pytest.raises(ValueError):
            await failing_func()

    assert cb.state == CircuitBreakerState.OPEN
    assert call_count == 3

    # Next call should raise CircuitBreakerOpenException without invoking the func
    with pytest.raises(CircuitBreakerOpenException):
        await failing_func()

    assert call_count == 3


async def test_circuit_breaker_half_open_to_closed():
    """Test transition from HALF_OPEN to CLOSED on success."""
    cb = CircuitBreaker(max_failures=1, cooldown_seconds=0.1)

    fail_next = True

    @reliable(cb=cb, max_retries=1, timeout_seconds=1.0)
    async def flaky_func():
        if fail_next:
            raise ValueError("Fail")
        return "Success"

    # Trip it
    with pytest.raises(ValueError):
        await flaky_func()

    assert cb.state == CircuitBreakerState.OPEN

    # Wait for cooldown
    time.sleep(0.2)

    # It should transition to HALF_OPEN, execute, succeed, and close
    fail_next = False
    res = await flaky_func()

    assert res == "Success"
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.failure_count == 0


async def test_circuit_breaker_half_open_to_open():
    """Test transition from HALF_OPEN back to OPEN on failure."""
    cb = CircuitBreaker(max_failures=1, cooldown_seconds=0.1)

    @reliable(cb=cb, max_retries=1, timeout_seconds=1.0)
    async def failing_func():
        raise ValueError("Fail")

    # Trip it
    with pytest.raises(ValueError):
        await failing_func()

    assert cb.state == CircuitBreakerState.OPEN

    # Wait for cooldown
    time.sleep(0.2)

    # Assert can_execute sets it to HALF_OPEN
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # It should transition back to OPEN immediately after one failure
    with pytest.raises(ValueError):
        await failing_func()

    assert cb.state == CircuitBreakerState.OPEN
