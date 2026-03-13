from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StoreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str
    logo_url: str | None = None
    is_active: bool
    rating: Decimal
    owner_id: int
    created_at: datetime
    updated_at: datetime


class StoreCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = ""
    logo_url: str | None = None


class StoreUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    logo_url: str | None = None
    is_active: bool | None = None
