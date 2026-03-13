from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    slug: str
    description: str
    environment: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = ""
    environment: str = "development"


class ProjectUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    environment: str | None = None
    is_active: bool | None = None
