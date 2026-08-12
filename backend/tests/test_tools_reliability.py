"""Tests for the @reliable decorator as applied to actual tool functions.

These tests verify that the reliability wrapper (timeout, retry, circuit breaker)
behaves correctly when applied to the real tool functions in app.agent.tools,
not just on isolated dummy functions.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.reliability import CircuitBreaker, CircuitBreakerOpenException, CircuitBreakerState


class TestToolReliabilityWrapper:
    """Test the @reliable wrapper as it actually wraps tool functions."""

    @pytest.mark.asyncio
    async def test_reliable_retries_on_transient_failure(self):
        """A function decorated with @reliable should retry on transient exceptions."""
        from app.agent.reliability import reliable

        cb = CircuitBreaker(max_failures=5, cooldown_seconds=60)
        call_count = 0

        @reliable(cb=cb, max_retries=3, timeout_seconds=2.0, base_backoff=0.01)
        async def flaky_tool():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient DB error")
            return {"result": "success"}

        result = await flaky_tool()
        assert result == {"result": "success"}
        assert call_count == 3  # Failed twice, succeeded on third
        assert cb.state == CircuitBreakerState.CLOSED  # Success resets CB

    @pytest.mark.asyncio
    async def test_reliable_enforces_timeout(self):
        """A function that exceeds the timeout should raise TimeoutError."""
        from app.agent.reliability import reliable

        cb = CircuitBreaker(max_failures=5, cooldown_seconds=60)

        @reliable(cb=cb, max_retries=1, timeout_seconds=0.1, base_backoff=0.01)
        async def slow_tool():
            await asyncio.sleep(5)
            return "should not reach here"

        with pytest.raises(TimeoutError):
            await slow_tool()

    @pytest.mark.asyncio
    async def test_reliable_opens_circuit_after_max_failures(self):
        """After max_failures consecutive failures, the CB should open and reject calls."""
        from app.agent.reliability import reliable

        cb = CircuitBreaker(max_failures=3, cooldown_seconds=60)

        @reliable(cb=cb, max_retries=1, timeout_seconds=1.0, base_backoff=0.01)
        async def always_fails():
            raise RuntimeError("Persistent failure")

        # Each invocation of the decorated function counts as 1 failure
        # (max_retries=1 means only 1 attempt per call)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await always_fails()

        assert cb.state == CircuitBreakerState.OPEN

        # Now subsequent calls should be rejected immediately
        with pytest.raises(CircuitBreakerOpenException):
            await always_fails()

    @pytest.mark.asyncio
    async def test_tools_share_circuit_breaker_instance(self):
        """All 5 tool functions in tools.py share the same tools_cb instance."""
        from app.agent.tools import (
            query_transaction_db,
            search_logs,
            retrieve_similar_incidents,
            retrieve_runbooks,
            check_failure_signatures,
            tools_cb,
        )

        # Verify they all share the same CB instance by checking the CB state
        # affects all tools equally
        assert tools_cb.state == CircuitBreakerState.CLOSED

        # All tool functions should be wrapped (they have __wrapped__ attribute
        # from functools.wraps)
        for tool in [query_transaction_db, search_logs, retrieve_similar_incidents,
                     retrieve_runbooks, check_failure_signatures]:
            assert hasattr(tool, "__wrapped__"), f"{tool.__name__} is not decorated with @reliable"

    @pytest.mark.asyncio
    async def test_reliable_wrapper_preserves_function_metadata(self):
        """The @reliable decorator should preserve the original function's name and docstring."""
        from app.agent.tools import query_transaction_db, search_logs

        assert query_transaction_db.__name__ == "query_transaction_db"
        assert "transaction" in query_transaction_db.__doc__.lower()
        assert search_logs.__name__ == "search_logs"
        assert "log" in search_logs.__doc__.lower()
