"""agent traces and evidence

Revision ID: 003
Revises: 002
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- agent_traces ---
    op.create_table(
        "agent_traces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("args", JSONB(), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_traces_incident_id", "agent_traces", ["incident_id"])

    # --- incident_evidence ---
    op.create_table(
        "incident_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("tool_args", JSONB(), nullable=True),
        sa.Column("tool_result", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"])


def downgrade() -> None:
    op.drop_table("incident_evidence")
    op.drop_table("agent_traces")
