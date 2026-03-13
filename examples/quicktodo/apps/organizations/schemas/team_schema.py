from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str = ""
    created_at: datetime


class TeamCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str = ""


class TeamUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None
