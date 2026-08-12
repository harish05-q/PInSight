import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RunbookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class RunbookResponse(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
