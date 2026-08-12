"""Tests for the agent orchestrator."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.orchestrator import investigate_incident, validate_citations

pytestmark = pytest.mark.asyncio


def test_validate_citations_success():
    final_answer = {
        "evidence": [
            {"claim": "X", "source_tool": "search_logs"},
            {"claim": "Y", "source_tool": "query_transaction_db"},
        ]
    }
    trace = [{"tool_name": "search_logs"}, {"tool_name": "query_transaction_db"}]
    assert validate_citations(final_answer, trace) is True


def test_validate_citations_failure():
    final_answer = {"evidence": [{"claim": "Z", "source_tool": "hallucinated_tool"}]}
    trace = [{"tool_name": "search_logs"}]
    assert validate_citations(final_answer, trace) is False


async def test_max_steps_fallback_exhaustion():
    """Test that max steps exhaustion triggers the low-confidence fallback."""
    # We mock the LLM Client to always return a tool call, never a final answer

    mock_session = AsyncMock()
    mock_incident = AsyncMock()
    mock_incident.description = "Test incident"
    mock_incident.transaction_id = uuid.uuid4()
    mock_session.get.return_value = mock_incident

    with (
        patch("app.agent.orchestrator.LLMClient") as MockClient,
        patch("app.agent.orchestrator.agent_tools") as mock_tools,
    ):
        instance = MockClient.return_value

        # Simulate LLM always calling search_logs
        instance.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "search_logs",
                                    "arguments": '{"transaction_id": "test", "query": "test"}',
                                },
                            }
                        ]
                    }
                }
            ]
        }

        # Mock the tool itself to return simple string
        mock_tools.search_logs = AsyncMock(return_value=["mocked log"])

        final_answer, trace, hall_count = await investigate_incident(
            mock_session, str(uuid.uuid4())
        )

        # Assert fallback was triggered
        assert final_answer["degraded"] is True
        assert final_answer["confidence"] == 0.0
        assert "aborted" in final_answer["root_cause"].lower()

        # Assert trace has 10 steps (MAX_STEPS)
        assert len(trace) == 10
        assert trace[0]["tool_name"] == "search_logs"
