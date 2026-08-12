"""incidents and runbooks

Revision ID: 002
Revises: 001
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable vector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # --- incidents ---
    op.create_table(
        "incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("transaction_id", UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_incidents_transaction_id", "incidents", ["transaction_id"])

    # --- incident_embeddings ---
    op.create_table(
        "incident_embeddings",
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id"), primary_key=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=True),
    )

    # --- runbooks ---
    op.create_table(
        "runbooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("runbooks")
    op.drop_table("incident_embeddings")
    op.drop_table("incidents")
