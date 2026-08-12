from typing import Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.eval import EvalRun
from app.models.incident import Incident
from app.models.transaction import Transaction

log = structlog.get_logger()
router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Lightweight dashboard aggregates."""

    # Incidents
    total_incidents_query = await session.execute(select(func.count(Incident.id)))
    total_incidents = total_incidents_query.scalar() or 0

    open_incidents_query = await session.execute(
        select(func.count(Incident.id)).where(Incident.status == "open")
    )
    open_incidents = open_incidents_query.scalar() or 0

    # Transactions
    total_transactions_query = await session.execute(select(func.count(Transaction.id)))
    total_transactions = total_transactions_query.scalar() or 0

    # Eval
    latest_eval_query = await session.execute(
        select(EvalRun).order_by(EvalRun.created_at.desc()).limit(1)
    )
    latest_eval = latest_eval_query.scalars().first()

    eval_metrics = None
    if latest_eval:
        eval_metrics = {
            "id": str(latest_eval.id),
            "status": latest_eval.status,
            "accuracy": latest_eval.accuracy,
            "avg_latency_ms": latest_eval.avg_latency_ms,
            "hallucination_rate": latest_eval.hallucination_rate,
        }

    return {
        "incidents": {
            "total": total_incidents,
            "open": open_incidents,
            "resolved": total_incidents - open_incidents,
        },
        "transactions": {
            "total": total_transactions,
            # Approximating failed transactions as those with incidents
            "failed_anomalous": total_incidents,
        },
        "latest_eval": eval_metrics,
    }
