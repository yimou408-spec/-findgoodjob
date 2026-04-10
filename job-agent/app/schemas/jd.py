from datetime import datetime

from pydantic import BaseModel, Field


class JDCreate(BaseModel):
    title: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    content: str = Field(..., min_length=10)
    source: str | None = None


class JDOut(BaseModel):
    id: int
    title: str
    company: str
    content: str
    source: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
