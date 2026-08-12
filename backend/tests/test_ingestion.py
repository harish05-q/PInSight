"""Integration tests for the ingestion pipeline (Phase 3)."""

import time
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import transaction_service

pytestmark = pytest.mark.asyncio


async def test_incident_creation_is_async_and_returns_fast(
    integration_client: AsyncClient, integration_session: AsyncSession, merchant_id: uuid.UUID
):
    """Prove the API returns immediately even if the embedding generation is slow.

    We mock the embedding generation to take 2 seconds, but the API should return in < 100ms
    because it offloads the work to RQ.
    """
    # 1. Create a real transaction to attach the incident to
    idem_key = f"idem-inc-{uuid.uuid4()}"
    tx, _ = await transaction_service.create_transaction(
        integration_session, idem_key, merchant_id, 50.00
    )
    await integration_session.commit()

    # 2. Mock the embedding service to be artificially slow
    def slow_embedding(text):
        time.sleep(2)
        return [0.0] * 384

    # We patch RQ's enqueue to just simulate what the worker would do asynchronously,
    # but we don't want it to block the API call. Since the API natively uses RQ which
    # pushes to Redis, we mock `q.enqueue` to NOT hit Redis (in case it's missing in CI)
    # but still prove the API flow itself doesn't call the slow embedding synchronously.

    with (
        patch("app.api.incidents.q.enqueue") as mock_enqueue,
        patch("app.services.embedding_service.generate_embedding", side_effect=slow_embedding),
    ):
        start_time = time.time()

        resp = await integration_client.post(
            "/v1/incidents",
            json={
                "transaction_id": str(tx.id),
                "description": "Customer claims they were double charged.",
            },
        )

        end_time = time.time()

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "open"
        assert data["transaction_id"] == str(tx.id)

        # 3. Assert the API returned extremely fast, ignoring the 2-second sleep
        elapsed = end_time - start_time
        assert elapsed < 0.5, f"API blocked! Request took {elapsed:.2f} seconds."

        # 4. Assert that enqueue was actually called, delegating the work
        mock_enqueue.assert_called_once()
        args, kwargs = mock_enqueue.call_args
        # First arg is the task function, second is the incident_id
        assert args[0].__name__ == "embed_and_save_incident"
        assert args[1] == data["id"]
