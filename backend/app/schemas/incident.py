import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    transaction_id: uuid.UUID
    description: str = Field(..., min_length=1)


class IncidentResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    description: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
