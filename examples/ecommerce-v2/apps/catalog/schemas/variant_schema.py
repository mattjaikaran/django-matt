from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VariantSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    name: str
    sku: str
    price_override: Decimal | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VariantCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str = Field(min_length=1, max_length=100)
    price_override: Decimal | None = None


class VariantUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    price_override: Decimal | None = None
    is_active: bool | None = None
