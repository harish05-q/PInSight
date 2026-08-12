import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.services import webhook_service

log = structlog.get_logger()
router = APIRouter(prefix="/v1", tags=["webhooks"])


@router.post("/webhooks", response_model=WebhookResponse)
async def receive_webhook(
    body: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Receive a gateway webhook. Deduplicated by provider_event_id (FR-3)."""
    result = await webhook_service.process_webhook(
        session=db,
        provider_event_id=body.provider_event_id,
        transaction_id=body.transaction_id,
        event_type=body.event_type,
        payload=body.data,
    )
    return WebhookResponse(**result)
