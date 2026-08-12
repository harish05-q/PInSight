import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import run_investigation_and_save
from app.api.deps import get_current_user
from app.db import get_db

log = structlog.get_logger()
router = APIRouter(prefix="/v1/investigations", tags=["investigations"])


@router.post("/{incident_id}")
async def investigate_incident_endpoint(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Run an agentic investigation for an incident."""
    log.info("Starting investigation", incident_id=str(incident_id))
    try:
        final_answer = await run_investigation_and_save(session, str(incident_id))
        return final_answer
    except ValueError as e:
        if str(e) == "Incident not found":
            raise HTTPException(status_code=404, detail="Incident not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Investigation failed", error=str(e))
        raise HTTPException(status_code=500, detail="Investigation failed internally")


@router.get("/{incident_id}/trace")
async def get_investigation_trace(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get the full trace of an investigation."""
    from sqlalchemy import select

    from app.models.agent import AgentTrace

    result = await session.execute(
        select(AgentTrace)
        .where(AgentTrace.incident_id == incident_id)
        .order_by(AgentTrace.step_number)
    )
    traces = result.scalars().all()

    return {
        "incident_id": str(incident_id),
        "trace": [
            {
                "step": t.step_number,
                "tool": t.tool_name,
                "args": t.args,
                "result": t.result,
                "latency_ms": t.latency_ms,
            }
            for t in traces
        ],
    }
