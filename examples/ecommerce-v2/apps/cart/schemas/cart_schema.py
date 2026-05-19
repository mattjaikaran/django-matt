from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CartItemProductSchema(BaseModel):
    id: str
    store_id: str
    name: str
    price: str
    image_url: str | None = None
    slug: str


class CartItemSchema(BaseModel):
    id: str
    product_id: str
    variant_id: str | None
    quantity: int
    created_at: datetime
    product: CartItemProductSchema | None = None

    model_config = {"from_attributes": True}


class CartSchema(BaseModel):
    id: str
    items: list[CartItemSchema]
    item_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AddToCartSchema(BaseModel):
    product_id: str
    variant_id: str | None = None
    quantity: int = Field(default=1, ge=1)


class UpdateCartItemSchema(BaseModel):
    quantity: int = Field(ge=0)  # 0 means remove
