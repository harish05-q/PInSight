import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    """Request body for creating a transaction."""

    merchant_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class TransactionResponse(BaseModel):
    """Response body for a transaction."""

    id: uuid.UUID
    merchant_id: uuid.UUID
    idempotency_key: str
    amount: Decimal
    currency: str
    state: str
    version: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TransactionEventResponse(BaseModel):
    """Response body for a transaction event."""

    id: uuid.UUID
    transaction_id: uuid.UUID
    event_type: str
    payload: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionTimelineResponse(BaseModel):
    """Full transaction with its event timeline."""

    transaction: TransactionResponse
    events: list[TransactionEventResponse]
