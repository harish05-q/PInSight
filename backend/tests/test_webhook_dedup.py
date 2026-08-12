"""Webhook deduplication integration tests (FR-3).

Proves: N concurrent webhook deliveries with the same provider_event_id
result in exactly ONE business logic execution (state transition).
The UNIQUE constraint on provider_event_id is the enforcement mechanism.
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


async def test_concurrent_webhook_redelivery_processes_once(integration_client, merchant_id):
    """Send the same webhook (same provider_event_id) 15 times concurrently.
    Exactly 1 should return 'processed', the rest 'duplicate'.
    The state transition should execute exactly once."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]
    event_id = f"evt-{uuid.uuid4()}"

    N = 15
    webhook_body = {
        "provider_event_id": event_id,
        "transaction_id": tx_id,
        "event_type": "payment.captured",
        "data": {"capture_amount": "100.00"},
    }

    responses = await asyncio.gather(
        *[integration_client.post("/v1/webhooks", json=webhook_body) for _ in range(N)]
    )

    # All should succeed (200)
    for r in responses:
        assert r.status_code == 200, f"Unexpected status: {r.status_code} - {r.text}"

    # Exactly 1 should be "processed", the rest "duplicate"
    processed = [r for r in responses if r.json()["status"] == "processed"]
    duplicates = [r for r in responses if r.json()["status"] == "duplicate"]

    assert len(processed) == 1, f"Expected exactly 1 processed, got {len(processed)}"
    assert len(duplicates) == N - 1, f"Expected {N - 1} duplicates, got {len(duplicates)}"

    # Verify the transaction state changed exactly once (to captured)
    get_resp = await integration_client.get(f"/v1/transactions/{tx_id}")
    assert get_resp.json()["state"] == "captured"
    assert get_resp.json()["version"] == 2  # authorized(1) → captured(2)


async def test_different_webhook_events_process_independently(integration_client, merchant_id):
    """Different provider_event_ids should each be processed."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]

    # First webhook: capture
    resp1 = await integration_client.post(
        "/v1/webhooks",
        json={
            "provider_event_id": f"evt-{uuid.uuid4()}",
            "transaction_id": tx_id,
            "event_type": "payment.captured",
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    # Second webhook: settle (different event ID)
    resp2 = await integration_client.post(
        "/v1/webhooks",
        json={
            "provider_event_id": f"evt-{uuid.uuid4()}",
            "transaction_id": tx_id,
            "event_type": "payment.settled",
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "processed"

    # Transaction should now be settled
    get_resp = await integration_client.get(f"/v1/transactions/{tx_id}")
    assert get_resp.json()["state"] == "settled"
    assert get_resp.json()["version"] == 3  # authorized → captured → settled


async def test_webhook_retry_storm_is_safe(integration_client, merchant_id):
    """Simulate a webhook retry storm: 5+ redeliveries of the same event.
    Per SRS §4.4 failure class 2."""
    tx = await _create_authorized_transaction(integration_client, merchant_id)
    tx_id = tx["id"]
    event_id = f"storm-{uuid.uuid4()}"

    # Simulate a storm of 25 redeliveries
    N = 25
    responses = await asyncio.gather(
        *[
            integration_client.post(
                "/v1/webhooks",
                json={
                    "provider_event_id": event_id,
                    "transaction_id": tx_id,
                    "event_type": "payment.captured",
                },
            )
            for _ in range(N)
        ]
    )

    processed = [r for r in responses if r.json()["status"] == "processed"]
    duplicates = [r for r in responses if r.json()["status"] == "duplicate"]

    assert len(processed) == 1
    assert len(duplicates) == N - 1

    # Timeline should have exactly 2 events: created + state_changed_to_captured
    timeline_resp = await integration_client.get(f"/v1/transactions/{tx_id}/timeline")
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()["events"]
    assert len(events) == 2, (
        f"Expected 2 events, got {len(events)}: {[e['event_type'] for e in events]}"
    )
