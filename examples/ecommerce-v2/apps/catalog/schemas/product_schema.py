from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    store_id: str
    category_id: str | None = None
    name: str
    slug: str
    description: str
    price: Decimal
    compare_at_price: Decimal | None = None
    is_active: bool
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductCreateSchema(BaseModel):
    store_id: str
    category_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str = ""
    price: Decimal = Field(gt=0)
    compare_at_price: Decimal | None = None
    image_url: str | None = None


class ProductUpdateSchema(BaseModel):
    category_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    compare_at_price: Decimal | None = None
    is_active: bool | None = None
    image_url: str | None = None


class ProductListSchema(BaseModel):
    items: list[ProductSchema]
    total: int
