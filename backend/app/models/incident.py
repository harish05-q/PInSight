import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class Incident(Base):
    """An incident that requires investigation."""

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    transaction: Mapped["Transaction"] = relationship()
    embedding: Mapped["IncidentEmbedding"] = relationship(
        back_populates="incident", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Incident {self.id} status={self.status}>"


class IncidentEmbedding(Base):
    """Vector embeddings for incidents to enable semantic search."""

    __tablename__ = "incident_embeddings"

    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="embedding")
