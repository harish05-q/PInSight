import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models.incident import Incident


class EvalCase(Base):
    """Ground truth dataset for evaluating the agent."""

    __tablename__ = "eval_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id"), nullable=False, index=True
    )
    expected_root_cause: Mapped[str] = mapped_column(String(255), nullable=False)
    # List of dicts: {"source_tool": "...", "source_ref": "..."}
    expected_evidence: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    incident: Mapped["Incident"] = relationship()


class EvalRun(Base):
    """An asynchronous evaluation run over a batch of cases."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy: Mapped[float] = mapped_column(Float, nullable=True)
    avg_precision: Mapped[float] = mapped_column(Float, nullable=True)
    avg_recall: Mapped[float] = mapped_column(Float, nullable=True)
    hallucination_rate: Mapped[float] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvalResult(Base):
    """The result of a single incident investigation during an eval run."""

    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id"), nullable=False, index=True
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_root_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    precision: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hallucinated_citations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    run: Mapped["EvalRun"] = relationship(back_populates="results")
    incident: Mapped["Incident"] = relationship()
