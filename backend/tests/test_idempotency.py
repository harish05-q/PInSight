"""Concurrent idempotency integration tests (FR-1).

Proves: N parallel requests with the same idempotency key produce exactly ONE
transaction. The UNIQUE constraint + ON CONFLICT DO NOTHING is the enforcement
mechanism — this test verifies it holds under real concurrent load, not just
sequential calls.
"""

import asyncio
import uuid

import pytest

from tests.conftest_integration import requires_postgres

pytestmark = [pytest.mark.asyncio, requires_postgres]


async def test_concurrent_idempotency_creates_exactly_one_transaction(
    integration_client, merchant_id
):
    """Fire 20 parallel requests with the same idempotency key.
    Assert exactly ONE transaction is created — the rest return the same one."""
    N = 20
    key = f"idem-{uuid.uuid4()}"

    async def make_request():
        return await integration_client.post(
            "/v1/transactions",
            json={
                "merchant_id": str(merchant_id),
                "amount": "100.00",
                "currency": "USD",
            },
            headers={"Idempotency-Key": key},
        )

    # Fire all N requests concurrently
    responses = await asyncio.gather(*[make_request() for _ in range(N)])

    # All should succeed (either 201 Created or 200 OK for idempotent replay)
    for resp in responses:
        assert resp.status_code in (200, 201), (
            f"Unexpected status: {resp.status_code} - {resp.text}"
        )

    # Exactly one should be 201 (the one that created it)
    created_count = sum(1 for r in responses if r.status_code == 201)
    assert created_count == 1, f"Expected exactly 1 creation, got {created_count}"

    # All responses should return the same transaction ID
    tx_ids = {r.json()["id"] for r in responses}
    assert len(tx_ids) == 1, f"Expected 1 unique transaction ID, got {len(tx_ids)}: {tx_ids}"


async def test_different_idempotency_keys_create_separate_transactions(
    integration_client, merchant_id
):
    """Different keys should create different transactions (sanity check)."""
    keys = [f"key-{uuid.uuid4()}" for _ in range(5)]

    async def make_request(key):
        return await integration_client.post(
            "/v1/transactions",
            json={
                "merchant_id": str(merchant_id),
                "amount": "50.00",
                "currency": "USD",
            },
            headers={"Idempotency-Key": key},
        )

    responses = await asyncio.gather(*[make_request(k) for k in keys])

    assert all(r.status_code == 201 for r in responses)
    tx_ids = {r.json()["id"] for r in responses}
    assert len(tx_ids) == 5, f"Expected 5 distinct transactions, got {len(tx_ids)}"


async def test_idempotent_replay_returns_same_data(integration_client, merchant_id):
    """Second request with same key returns identical data to the first."""
    key = f"replay-{uuid.uuid4()}"
    body = {
        "merchant_id": str(merchant_id),
        "amount": "250.00",
        "currency": "EUR",
    }

    first = await integration_client.post(
        "/v1/transactions", json=body, headers={"Idempotency-Key": key}
    )
    assert first.status_code == 201

    second = await integration_client.post(
        "/v1/transactions", json=body, headers={"Idempotency-Key": key}
    )
    assert second.status_code == 200

    # Same transaction returned
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["amount"] == second.json()["amount"]
    assert first.json()["state"] == second.json()["state"]
