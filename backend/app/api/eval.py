import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.eval import EvalRun
from app.worker.queue import q
from app.worker.tasks import run_eval_job

log = structlog.get_logger()
router = APIRouter(prefix="/v1/eval", tags=["eval"])


@router.post("/run", status_code=202)
async def trigger_eval_run(
    limit: int = 14,
    session: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger an asynchronous evaluation run."""
    run = EvalRun(status="running")
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Enqueue background task
    q.enqueue(run_eval_job, str(run.id), limit, job_timeout=1200)

    return {"run_id": str(run.id), "status": run.status, "message": "Evaluation job enqueued."}


@router.get("/runs", response_model=list[dict[str, Any]])
async def list_eval_runs(
    skip: int = 0, limit: int = 20, session: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """List historical evaluation runs."""
    from sqlalchemy import select

    stmt = select(EvalRun).order_by(EvalRun.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)

    runs = []
    for run in result.scalars().all():
        runs.append(
            {
                "id": str(run.id),
                "status": run.status,
                "total_cases": run.total_cases,
                "accuracy": run.accuracy,
                "avg_precision": run.avg_precision,
                "avg_recall": run.avg_recall,
                "hallucination_rate": run.hallucination_rate,
                "avg_latency_ms": run.avg_latency_ms,
                "avg_tokens": run.avg_tokens,
                "total_cost_usd": run.total_cost_usd,
                "created_at": run.created_at.isoformat(),
                "updated_at": run.updated_at.isoformat(),
            }
        )
    return runs


@router.get("/runs/{run_id}")
async def get_eval_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the status and results of an evaluation run."""
    run = await session.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="EvalRun not found")

    return {
        "id": str(run.id),
        "status": run.status,
        "total_cases": run.total_cases,
        "accuracy": run.accuracy,
        "avg_precision": run.avg_precision,
        "avg_recall": run.avg_recall,
        "hallucination_rate": run.hallucination_rate,
        "avg_latency_ms": run.avg_latency_ms,
        "avg_tokens": run.avg_tokens,
        "total_cost_usd": run.total_cost_usd,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }
