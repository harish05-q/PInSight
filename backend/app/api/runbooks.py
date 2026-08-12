import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.runbook import Runbook
from app.schemas.runbook import RunbookCreate, RunbookResponse
from app.worker.queue import q
from app.worker.tasks import embed_and_save_runbook

log = structlog.get_logger()
router = APIRouter(prefix="/v1/runbooks", tags=["runbooks"])


@router.post(
    "",
    response_model=RunbookResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_runbook(
    payload: RunbookCreate,
    session: AsyncSession = Depends(get_db),
):
    """Create a new runbook and enqueue embedding generation asynchronously."""
    runbook = Runbook(
        title=payload.title,
        content=payload.content,
    )
    session.add(runbook)
    await session.commit()
    await session.refresh(runbook)

    log.info("Runbook created, enqueuing embedding task", runbook_id=str(runbook.id))

    # Enqueue background task
    q.enqueue(embed_and_save_runbook, str(runbook.id))

    return runbook
