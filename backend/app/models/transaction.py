import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.transaction_event import TransactionEvent
    from app.models.webhook_event import WebhookEvent


class TransactionState(enum.StrEnum):
    """Valid states for a transaction in the payment lifecycle."""

    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    REFUNDED = "refunded"
    FAILED = "failed"


# Valid state transitions — the state machine definition (SRS §FR-2)
VALID_TRANSITIONS: dict[TransactionState, set[TransactionState]] = {
    TransactionState.AUTHORIZED: {
        TransactionState.CAPTURED,
        TransactionState.FAILED,
        TransactionState.REFUNDED,
    },
    TransactionState.CAPTURED: {
        TransactionState.SETTLED,
        TransactionState.REFUNDED,
        TransactionState.FAILED,
    },
    TransactionState.SETTLED: {TransactionState.REFUNDED},
    TransactionState.REFUNDED: set(),
    TransactionState.FAILED: set(),
}


def is_valid_transition(current: TransactionState, target: TransactionState) -> bool:
    """Check if a state transition is valid per the state machine."""
    return target in VALID_TRANSITIONS.get(current, set())


def get_valid_source_states(target: TransactionState) -> set[TransactionState]:
    """Get all states that can legally transition to the target state."""
    return {state for state, targets in VALID_TRANSITIONS.items() if target in targets}


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    state: Mapped[str] = mapped_column(
        String(20), default=TransactionState.AUTHORIZED.value, nullable=False
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    merchant: Mapped["Merchant"] = relationship(back_populates="transactions")
    events: Mapped[list["TransactionEvent"]] = relationship(
        back_populates="transaction", order_by="TransactionEvent.created_at"
    )
    webhook_events: Mapped[list["WebhookEvent"]] = relationship(back_populates="transaction")

    __table_args__ = (
        Index("ix_transactions_merchant_id", "merchant_id"),
        CheckConstraint("amount >= 0", name="ck_transactions_amount_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.id} state={self.state}>"
