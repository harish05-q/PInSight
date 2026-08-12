"""Webhook service — exactly-once webhook processing (FR-3).

Uses INSERT ON CONFLICT DO NOTHING on provider_event_id.
If rowcount == 0, the webhook is a duplicate and business logic is skipped.
"""

import uuid

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import TransactionState
from app.models.webhook_event import WebhookEvent
from app.services.exceptions import TransactionError
from app.services.transaction_service import get_transaction, transition_state

log = structlog.get_logger()

# Map webhook event types to transaction state transitions
WEBHOOK_EVENT_TO_STATE: dict[str, TransactionState] = {
    "payment.captured": TransactionState.CAPTURED,
    "payment.settled": TransactionState.SETTLED,
    "payment.refunded": TransactionState.REFUNDED,
    "payment.failed": TransactionState.FAILED,
}


async def process_webhook(
    session: AsyncSession,
    provider_event_id: str,
    transaction_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
) -> dict:
    """Process a webhook event with exactly-once semantics (FR-3).

    1. INSERT INTO webhook_events ... ON CONFLICT (provider_event_id) DO NOTHING
    2. If rowcount == 0 → duplicate, skip business logic
    3. Else → execute the state transition
    """
    stmt = (
        pg_insert(WebhookEvent)
        .values(
            id=uuid.uuid4(),
            provider_event_id=provider_event_id,
            transaction_id=transaction_id,
            event_type=event_type,
            payload=payload or {},
        )
        .on_conflict_do_nothing(index_elements=["provider_event_id"])
    )

    result = await session.execute(stmt)

    if result.rowcount == 0:
        log.info(
            "webhook_duplicate",
            provider_event_id=provider_event_id,
        )
        return {"status": "duplicate", "provider_event_id": provider_event_id}

    # First-time processing — execute the state transition
    target_state = WEBHOOK_EVENT_TO_STATE.get(event_type)
    if target_state is not None:
        try:
            transaction = await get_transaction(session, transaction_id)
            await transition_state(session, transaction_id, target_state, transaction.version)
        except TransactionError as e:
            log.warning(
                "webhook_transition_failed",
                provider_event_id=provider_event_id,
                error=str(e),
            )
            return {
                "status": "processed",
                "provider_event_id": provider_event_id,
                "action_error": str(e),
            }

    log.info(
        "webhook_processed",
        provider_event_id=provider_event_id,
        event_type=event_type,
    )
    return {"status": "processed", "provider_event_id": provider_event_id}
