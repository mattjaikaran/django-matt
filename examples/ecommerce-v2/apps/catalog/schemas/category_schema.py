from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str
    parent_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CategoryCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = ""
    parent_id: str | None = None


class CategoryUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    parent_id: str | None = None
