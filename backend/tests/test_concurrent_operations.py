"""Concurrent operation integration tests (FR-2).

Proves:
- Concurrent capture + refund on the same transaction: exactly one wins.
- Concurrent double-capture: exactly one succeeds.
- No double-refund, no negative-balance scenarios.

The optimistic concurrency control (version column) is the enforcement mechanism.
"""

import asyncio
import uuid

import pytest

from tests.conftest_integration import requires_postgres

pytestmark = [pytest.mark.asyncio, requires_postgres]


async def _create_authorized_transaction(client, merchant_id: uuid.UUID) -> dict:
    """Helper: create a fresh authorized transaction."""
    key = f"tx-{uuid.uuid4()}"
    resp = await client.post(
        "/v1/transactions",
        json={
            "merchant_id": str(merchant_id),
            "amount": "100.00",
            "currency": "USD",
        },
        headers={"Idempotency-Key": key},
    )
    assert resp.status_code == 201
    return resp.json()


async def test_concurrent_capture_and_refund_exactly_one_wins(integration_client, merchant_id):
    """Fire capture and refund simultaneously on an authorized transaction.
    Exactly ONE must succeed — the other gets a 409 Conflict.
    Final state is either CAPTURED or REFUNDED, never both."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]

    # Fire capture and refund concurrently
    capture_task = integration_client.post(f"/v1/transactions/{tx_id}/capture")
    refund_task = integration_client.post(f"/v1/transactions/{tx_id}/refund")

    capture_resp, refund_resp = await asyncio.gather(capture_task, refund_task)

    statuses = {capture_resp.status_code, refund_resp.status_code}

    # One should succeed (200), one should fail (409)
    assert 200 in statuses, f"Expected one 200, got {statuses}"
    assert 409 in statuses, f"Expected one 409, got {statuses}"

    # Verify final state is consistent
    get_resp = await integration_client.get(f"/v1/transactions/{tx_id}")
    final_state = get_resp.json()["state"]
    assert final_state in ("captured", "refunded"), f"Unexpected final state: {final_state}"

    # Version should be exactly 2 (one successful transition from version 1)
    assert get_resp.json()["version"] == 2


async def test_no_double_capture(integration_client, merchant_id):
    """Fire N concurrent capture requests on the same authorized transaction.
    Exactly ONE capture must succeed."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]
    N = 10

    responses = await asyncio.gather(
        *[integration_client.post(f"/v1/transactions/{tx_id}/capture") for _ in range(N)]
    )

    successes = [r for r in responses if r.status_code == 200]
    conflicts = [r for r in responses if r.status_code == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == N - 1, f"Expected {N - 1} conflicts, got {len(conflicts)}"

    # Verify final state
    get_resp = await integration_client.get(f"/v1/transactions/{tx_id}")
    assert get_resp.json()["state"] == "captured"
    assert get_resp.json()["version"] == 2


async def test_no_double_refund(integration_client, merchant_id):
    """Capture a transaction, then fire N concurrent refund requests.
    Exactly ONE refund must succeed."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]

    # First capture (sequential, to get to captured state)
    capture_resp = await integration_client.post(f"/v1/transactions/{tx_id}/capture")
    assert capture_resp.status_code == 200

    # Now fire concurrent refunds
    N = 10
    responses = await asyncio.gather(
        *[integration_client.post(f"/v1/transactions/{tx_id}/refund") for _ in range(N)]
    )

    successes = [r for r in responses if r.status_code == 200]
    conflicts = [r for r in responses if r.status_code == 409]

    assert len(successes) == 1, f"Expected exactly 1 refund success, got {len(successes)}"
    assert len(conflicts) == N - 1

    # Verify final state
    get_resp = await integration_client.get(f"/v1/transactions/{tx_id}")
    assert get_resp.json()["state"] == "refunded"
    assert get_resp.json()["version"] == 3  # authorized(1) → captured(2) → refunded(3)


async def test_refund_after_capture_after_refund_fails(integration_client, merchant_id):
    """Once refunded, no further transitions are allowed (terminal state)."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]

    # Capture
    resp = await integration_client.post(f"/v1/transactions/{tx_id}/capture")
    assert resp.status_code == 200

    # Refund
    resp = await integration_client.post(f"/v1/transactions/{tx_id}/refund")
    assert resp.status_code == 200

    # Try to capture again — should fail (refunded is terminal)
    resp = await integration_client.post(f"/v1/transactions/{tx_id}/capture")
    assert resp.status_code == 409

    # Try to refund again — should fail (already refunded)
    resp = await integration_client.post(f"/v1/transactions/{tx_id}/refund")
    assert resp.status_code == 409
