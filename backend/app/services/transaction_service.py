"""Transaction service — core payment domain logic.

Idempotency (FR-1): UNIQUE constraint on idempotency_key + INSERT ON CONFLICT DO NOTHING.
State machine (FR-2): Optimistic concurrency via UPDATE ... WHERE version = expected.
"""

import uuid
from decimal import Decimal

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import (
    Transaction,
    TransactionState,
    get_valid_source_states,
)
from app.models.transaction_event import TransactionEvent
from app.services.exceptions import (
    ConcurrencyError,
    InvalidTransitionError,
    TransactionNotFoundError,
)

log = structlog.get_logger()


async def create_transaction(
    session: AsyncSession,
    idempotency_key: str,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str = "USD",
) -> tuple[Transaction, bool]:
    """Create a transaction with idempotency enforcement (FR-1).

    Uses INSERT ... ON CONFLICT (idempotency_key) DO NOTHING.
    The UNIQUE constraint is the real enforcement — application code cannot bypass it.

    Returns:
        (transaction, created): created is True if new, False if duplicate key.
    """
    new_id = uuid.uuid4()
    stmt = (
        pg_insert(Transaction)
        .values(
            id=new_id,
            merchant_id=merchant_id,
            idempotency_key=idempotency_key,
            amount=amount,
            currency=currency,
            state=TransactionState.AUTHORIZED.value,
            version=1,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
    )

    result = await session.execute(stmt)
    created = result.rowcount > 0

    # Fetch the transaction (whether newly created or existing)
    select_stmt = select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    transaction = (await session.execute(select_stmt)).scalar_one()

    if created:
        # Record the creation event
        event = TransactionEvent(
            transaction_id=transaction.id,
            event_type="created",
            payload={
                "amount": str(amount),
                "currency": currency,
                "state": TransactionState.AUTHORIZED.value,
            },
        )
        session.add(event)
        await session.flush()
        log.info(
            "transaction_created",
            transaction_id=str(transaction.id),
            idempotency_key=idempotency_key,
        )
    else:
        log.info(
            "transaction_idempotency_hit",
            transaction_id=str(transaction.id),
            idempotency_key=idempotency_key,
        )

    return transaction, created


async def get_transaction(session: AsyncSession, transaction_id: uuid.UUID) -> Transaction:
    """Get a transaction by ID. Raises TransactionNotFoundError if missing."""
    stmt = select(Transaction).where(Transaction.id == transaction_id)
    transaction = (await session.execute(stmt)).scalar_one_or_none()
    if transaction is None:
        raise TransactionNotFoundError(str(transaction_id))
    return transaction


async def get_transaction_timeline(
    session: AsyncSession, transaction_id: uuid.UUID
) -> tuple[Transaction, list[TransactionEvent]]:
    """Get a transaction and its full event timeline."""
    transaction = await get_transaction(session, transaction_id)

    stmt = (
        select(TransactionEvent)
        .where(TransactionEvent.transaction_id == transaction_id)
        .order_by(TransactionEvent.created_at)
    )
    events = list((await session.execute(stmt)).scalars().all())

    return transaction, events


async def transition_state(
    session: AsyncSession,
    transaction_id: uuid.UUID,
    target_state: TransactionState,
    expected_version: int,
) -> Transaction:
    """Transition a transaction to a new state with optimistic concurrency (FR-2).

    Uses UPDATE ... WHERE id = :id AND version = :expected AND state IN (:valid_sources)
    to atomically check-and-update. If no rows match:
    - version mismatch → ConcurrencyError
    - state mismatch → InvalidTransitionError
    """
    valid_sources = get_valid_source_states(target_state)

    if not valid_sources:
        raise InvalidTransitionError("terminal_state", target_state.value)

    # Atomic check-and-update: version + valid source state must both match
    stmt = (
        update(Transaction)
        .where(
            Transaction.id == transaction_id,
            Transaction.version == expected_version,
            Transaction.state.in_([s.value for s in valid_sources]),
        )
        .values(
            state=target_state.value,
            version=Transaction.version + 1,
        )
    )

    result = await session.execute(stmt)

    if result.rowcount == 0:
        # Re-read to diagnose the failure
        current = (
            await session.execute(select(Transaction).where(Transaction.id == transaction_id))
        ).scalar_one_or_none()

        if current is None:
            raise TransactionNotFoundError(str(transaction_id))
        if current.version != expected_version:
            raise ConcurrencyError(str(transaction_id))
        raise InvalidTransitionError(current.state, target_state.value)

    # Record the transition event
    event = TransactionEvent(
        transaction_id=transaction_id,
        event_type=f"state_changed_to_{target_state.value}",
        payload={
            "from_version": expected_version,
            "to_version": expected_version + 1,
            "target_state": target_state.value,
        },
    )
    session.add(event)
    await session.flush()

    # Re-read updated transaction (force fresh from DB, not identity map cache)
    select_stmt = (
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .execution_options(populate_existing=True)
    )
    transaction = (await session.execute(select_stmt)).scalar_one()

    log.info(
        "transaction_state_changed",
        transaction_id=str(transaction_id),
        target_state=target_state.value,
        version=transaction.version,
    )

    return transaction


async def capture_transaction(
    session: AsyncSession, transaction_id: uuid.UUID, expected_version: int
) -> Transaction:
    """Capture an authorized transaction."""
    return await transition_state(
        session, transaction_id, TransactionState.CAPTURED, expected_version
    )


async def refund_transaction(
    session: AsyncSession, transaction_id: uuid.UUID, expected_version: int
) -> Transaction:
    """Refund a captured or settled transaction."""
    return await transition_state(
        session, transaction_id, TransactionState.REFUNDED, expected_version
    )


async def settle_transaction(
    session: AsyncSession, transaction_id: uuid.UUID, expected_version: int
) -> Transaction:
    """Settle a captured transaction."""
    return await transition_state(
        session, transaction_id, TransactionState.SETTLED, expected_version
    )
