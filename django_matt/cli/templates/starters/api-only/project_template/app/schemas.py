"""Pydantic schemas for {{ project_name }}."""

from datetime import datetime

from pydantic import BaseModel


class ItemCreate(BaseModel):
    title: str
    description: str = ""


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ItemSchema(BaseModel):
    id: int
    title: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
