from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class OrderItemProductSchema(BaseModel):
    id: str
    name: str
    slug: str
    price: str
    image_url: str | None = None

    model_config = {"from_attributes": True}


class OrderItemSchema(BaseModel):
    id: str
    product_id: str
    variant_id: str | None
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    product: OrderItemProductSchema | None = None

    model_config = {"from_attributes": True}


class OrderSchema(BaseModel):
    id: str
    user_id: str
    store_id: str
    status: str
    subtotal: Decimal
    tax: Decimal
    shipping_cost: Decimal
    total: Decimal
    shipping_address: str
    billing_address: str
    notes: str
    stripe_payment_intent_id: str | None
    items: list[OrderItemSchema]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderItemCreateSchema(BaseModel):
    product_id: str
    variant_id: str | None = None
    quantity: int = Field(ge=1)


class OrderCreateSchema(BaseModel):
    store_id: str
    shipping_address: str
    billing_address: str = ""
    notes: str = ""
    items: list[OrderItemCreateSchema]


class OrderUpdateSchema(BaseModel):
    status: str | None = None
    notes: str | None = None
