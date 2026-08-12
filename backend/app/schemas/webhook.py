import uuid
from typing import Any

from pydantic import BaseModel


class WebhookPayload(BaseModel):
    """Incoming webhook payload from payment gateway."""

    provider_event_id: str
    transaction_id: uuid.UUID
    event_type: str
    data: dict[str, Any] | None = None


class WebhookResponse(BaseModel):
    """Response after processing a webhook."""

    status: str  # "processed" or "duplicate"
    provider_event_id: str
    action_error: str | None = None
