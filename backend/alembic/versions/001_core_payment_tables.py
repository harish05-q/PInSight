"""core payment tables

Revision ID: 001
Revises:
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable uuid-ossp extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # --- merchants ---
    op.create_table(
        "merchants",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
        ),
        sa.Column("merchant_id", UUID(as_uuid=True), sa.ForeignKey("merchants.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("state", sa.String(20), nullable=False, server_default="authorized"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
        sa.CheckConstraint("amount >= 0", name="ck_transactions_amount_non_negative"),
    )
    op.create_index("ix_transactions_merchant_id", "transactions", ["merchant_id"])

    # --- transaction_events ---
    op.create_table(
        "transaction_events",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
        ),
        sa.Column(
            "transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_transaction_events_transaction_id", "transaction_events", ["transaction_id"]
    )

    # --- webhook_events ---
    op.create_table(
        "webhook_events",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
        ),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column(
            "transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # Dedup constraint (FR-3)
        sa.UniqueConstraint("provider_event_id", name="uq_webhook_events_provider_event_id"),
    )
    op.create_index("ix_webhook_events_transaction_id", "webhook_events", ["transaction_id"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("transaction_events")
    op.drop_table("transactions")
    op.drop_table("merchants")
