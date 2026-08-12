from typing import Any

import httpx
import structlog

from app.agent.reliability import CircuitBreaker, reliable
from app.config import settings

log = structlog.get_logger()

# Use a dedicated circuit breaker for the LLM API
llm_cb = CircuitBreaker(max_failures=5, cooldown_seconds=60)


class LLMClient:
    """Thin wrapper around the Groq HTTP API."""

    def __init__(self):
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        # Use an explicit timeout on the client level as well
        self.client = httpx.AsyncClient(
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=15.0,
        )

    @reliable(cb=llm_cb, max_retries=3, timeout_seconds=15.0)
    async def chat_completion(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Call the Groq chat completion API with tools."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()
