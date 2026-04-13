"""Pydantic schemas for {{ project_name }}."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StoreCreate(BaseModel):
    name: str
    slug: str
    description: str = ""


class StoreSchema(BaseModel):
    id: int
    name: str
    slug: str
    description: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    title: str
    description: str = ""
    price: Decimal = Field(gt=0)
    image_url: str = ""


class ProductUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ProductSchema(BaseModel):
    id: int
    store_id: int
    title: str
    description: str
    price: Decimal
    image_url: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class ReviewSchema(BaseModel):
    id: int
    product_id: int
    user_id: int
    rating: int
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}
