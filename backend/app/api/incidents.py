import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentResponse
from app.worker.queue import q
from app.worker.tasks import embed_and_save_incident

log = structlog.get_logger()
router = APIRouter(prefix="/v1/incidents", tags=["incidents"])


class CreateIncidentRequest(BaseModel):
    transaction_id: uuid.UUID
    description: str


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_incident(
    payload: CreateIncidentRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new incident and enqueue embedding generation asynchronously."""
    incident = Incident(
        transaction_id=payload.transaction_id,
        description=payload.description,
        status="open",
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)

    log.info("Incident created, enqueuing embedding task", incident_id=str(incident.id))

    # Enqueue background task
    q.enqueue(embed_and_save_incident, str(incident.id))

    return incident


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List incidents."""
    stmt = select(Incident).order_by(Incident.created_at.desc()).offset(skip).limit(limit)
    if status:
        stmt = stmt.where(Incident.status == status)
    result = await session.execute(stmt)

    # Format response
    incidents = []
    for inc in result.scalars().all():
        incidents.append(
            {
                "id": inc.id,
                "transaction_id": inc.transaction_id,
                "description": inc.description,
                "status": inc.status,
                "created_at": inc.created_at,
                "updated_at": inc.updated_at,
            }
        )
    return incidents


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a single incident."""
    incident = await session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "id": incident.id,
        "transaction_id": incident.transaction_id,
        "description": incident.description,
        "status": incident.status,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
    }
