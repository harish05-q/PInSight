import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.schemas.transaction import (
    TransactionCreate,
    TransactionEventResponse,
    TransactionResponse,
    TransactionTimelineResponse,
)
from app.services import transaction_service
from app.services.exceptions import (
    ConcurrencyError,
    InvalidTransitionError,
    TransactionNotFoundError,
)

log = structlog.get_logger()
router = APIRouter(prefix="/v1/transactions", tags=["transactions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TransactionResponse)
async def create_transaction(
    body: TransactionCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    """Create a new transaction. Requires Idempotency-Key header.

    Returns 201 on create, 200 on duplicate key (idempotent replay).
    """
    transaction, created = await transaction_service.create_transaction(
        session=db,
        idempotency_key=idempotency_key,
        merchant_id=body.merchant_id,
        amount=body.amount,
        currency=body.currency,
    )

    response_data = TransactionResponse.model_validate(transaction)

    if not created:
        return JSONResponse(
            content=response_data.model_dump(mode="json"),
            status_code=status.HTTP_200_OK,
        )

    return response_data


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    skip: int = 0,
    limit: int = 50,
    merchant_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List transactions."""
    from app.models.transaction import Transaction

    stmt = select(Transaction).order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    if merchant_id:
        stmt = stmt.where(Transaction.merchant_id == merchant_id)

    result = await db.execute(stmt)

    transactions = []
    for tx in result.scalars().all():
        transactions.append(TransactionResponse.model_validate(tx).model_dump(mode="json"))
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a transaction by ID."""
    try:
        tx = await transaction_service.get_transaction(db, transaction_id)
        return TransactionResponse.model_validate(tx)
    except TransactionNotFoundError:
        raise HTTPException(status_code=404, detail="Transaction not found")


@router.get("/{transaction_id}/timeline", response_model=TransactionTimelineResponse)
async def get_transaction_timeline(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full event timeline for a transaction."""
    try:
        tx, events = await transaction_service.get_transaction_timeline(db, transaction_id)
        return TransactionTimelineResponse(
            transaction=TransactionResponse.model_validate(tx),
            events=[TransactionEventResponse.model_validate(e) for e in events],
        )
    except TransactionNotFoundError:
        raise HTTPException(status_code=404, detail="Transaction not found")


@router.post("/{transaction_id}/capture", response_model=TransactionResponse)
async def capture_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Capture an authorized transaction."""
    try:
        tx = await transaction_service.get_transaction(db, transaction_id)
        updated = await transaction_service.capture_transaction(db, transaction_id, tx.version)
        return TransactionResponse.model_validate(updated)
    except TransactionNotFoundError:
        raise HTTPException(status_code=404, detail="Transaction not found")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{transaction_id}/refund", response_model=TransactionResponse)
async def refund_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Refund a transaction (captured or settled)."""
    try:
        tx = await transaction_service.get_transaction(db, transaction_id)
        updated = await transaction_service.refund_transaction(db, transaction_id, tx.version)
        return TransactionResponse.model_validate(updated)
    except TransactionNotFoundError:
        raise HTTPException(status_code=404, detail="Transaction not found")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
