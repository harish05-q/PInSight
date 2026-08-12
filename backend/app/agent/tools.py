import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.reliability import CircuitBreaker, reliable
from app.models.incident import Incident, IncidentEmbedding
from app.models.runbook import Runbook
from app.models.transaction import Transaction
from app.models.transaction_event import TransactionEvent
from app.models.webhook_event import WebhookEvent
from app.services import embedding_service

log = structlog.get_logger()
tools_cb = CircuitBreaker(max_failures=5, cooldown_seconds=30)


@reliable(cb=tools_cb, max_retries=2, timeout_seconds=5.0)
async def query_transaction_db(session: AsyncSession, transaction_id: str) -> dict[str, Any]:
    """Retrieve the full event timeline for a transaction."""
    tx = await session.get(Transaction, uuid.UUID(transaction_id))
    if not tx:
        return {"error": "Transaction not found"}

    # Get transaction events
    result = await session.execute(
        select(TransactionEvent)
        .where(TransactionEvent.transaction_id == tx.id)
        .order_by(TransactionEvent.created_at)
    )
    tx_events = result.scalars().all()

    # Get webhook events
    result = await session.execute(
        select(WebhookEvent)
        .where(WebhookEvent.transaction_id == tx.id)
        .order_by(WebhookEvent.processed_at)
    )
    wh_events = result.scalars().all()

    return {
        "transaction": {
            "id": str(tx.id),
            "amount": str(tx.amount),
            "currency": tx.currency,
            "state": tx.state,
            "created_at": tx.created_at.isoformat(),
        },
        "transaction_events": [
            {
                "type": e.event_type,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in tx_events
        ],
        "webhook_events": [
            {
                "type": e.event_type,
                "provider_event_id": e.provider_event_id,
                "payload": e.payload,
                "processed_at": e.processed_at.isoformat(),
            }
            for e in wh_events
        ],
    }


@reliable(cb=tools_cb, max_retries=2, timeout_seconds=5.0)
async def search_logs(session: AsyncSession, transaction_id: str, query: str) -> list[str]:
    """Search raw gateway/app logs for a transaction.

    (Mocked: returns simulated log lines based on the transaction events).
    """
    tx = await session.get(Transaction, uuid.UUID(transaction_id))
    if not tx:
        return ["Error: Transaction not found"]

    logs = [
        f"[{tx.created_at.isoformat()}] [INFO] Request starting for tx {tx.id}",
        f"[{tx.created_at.isoformat()}] [DEBUG] Idempotency key checked",
    ]

    # If the transaction has many webhook events, simulate a retry storm log
    result = await session.execute(select(WebhookEvent).where(WebhookEvent.transaction_id == tx.id))
    wh_events = result.scalars().all()
    if len(wh_events) > 3:
        logs.append(f"[WARN] High volume of webhooks detected for {tx.id}")

    # Filter by query simply
    return [line for line in logs if query.lower() in line.lower()]


@reliable(cb=tools_cb, max_retries=2, timeout_seconds=10.0)
async def retrieve_similar_incidents(
    session: AsyncSession, query: str, k: int = 3
) -> list[dict[str, Any]]:
    """Retrieve top-k similar incidents using pgvector."""
    query_embedding = embedding_service.generate_embedding(query)

    # Use cosine distance (<=>)
    result = await session.execute(
        select(IncidentEmbedding)
        .order_by(IncidentEmbedding.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    embeddings = result.scalars().all()

    incidents = []
    for emb in embeddings:
        inc = await session.get(Incident, emb.incident_id)
        if inc:
            incidents.append(
                {
                    "id": str(inc.id),
                    "description": inc.description,
                    "status": inc.status,
                }
            )
    return incidents


@reliable(cb=tools_cb, max_retries=2, timeout_seconds=10.0)
async def retrieve_runbooks(session: AsyncSession, query: str, k: int = 2) -> list[dict[str, Any]]:
    """Retrieve top-k relevant runbook sections using pgvector."""
    query_embedding = embedding_service.generate_embedding(query)

    result = await session.execute(
        select(Runbook).order_by(Runbook.embedding.cosine_distance(query_embedding)).limit(k)
    )
    runbooks = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "title": r.title,
            "content": r.content,
        }
        for r in runbooks
    ]


@reliable(cb=tools_cb, max_retries=2, timeout_seconds=5.0)
async def check_failure_signatures(session: AsyncSession, transaction_id: str) -> list[str]:
    """Deterministic rule-based check against known failure patterns."""
    tx_data = await query_transaction_db(session, transaction_id)
    if "error" in tx_data:
        return ["Transaction not found"]

    tx = tx_data["transaction"]
    wh_events = tx_data["webhook_events"]

    signatures = []

    # Check 1: Webhook Retry Storm
    event_ids = [e["provider_event_id"] for e in wh_events]
    if len(event_ids) != len(set(event_ids)):
        signatures.append(
            "SIGNATURE_MATCH: Webhook retry storm detected (duplicate provider_event_ids)."
        )

    # Check 2: Partial Capture
    captures = [e for e in wh_events if e["type"] == "payment.captured"]
    if captures:
        cap_amt = sum(float(e["payload"].get("capture_amount", 0)) for e in captures)
        if cap_amt > 0 and cap_amt < float(tx["amount"]):
            signatures.append(
                "SIGNATURE_MATCH: Partial capture (captured amount < authorized amount)."
            )

    # Check 3: Settlement Mismatch
    settles = [e for e in wh_events if e["type"] == "payment.settled"]
    if captures and settles:
        cap_amt = sum(float(e["payload"].get("capture_amount", 0)) for e in captures)
        set_amt = sum(float(e["payload"].get("settled_amount", 0)) for e in settles)
        if cap_amt != set_amt:
            signatures.append(
                "SIGNATURE_MATCH: Settlement mismatch (settled amount != captured amount)."
            )

    if not signatures:
        signatures.append("No deterministic failure signatures matched.")

    return signatures
