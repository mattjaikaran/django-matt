"""Pydantic schemas for cart app."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Cart Item Schemas
# =============================================================================


class CartItemCreate(BaseModel):
    """Cart item creation schema."""

    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(ge=1, default=1)


class CartItemUpdate(BaseModel):
    """Cart item update schema."""

    quantity: int = Field(ge=1)


class CartItemResponse(BaseModel):
    """Cart item response schema."""

    id: UUID
    product_id: UUID
    product_name: str
    product_slug: str
    product_image: str | None = None
    variant_id: UUID | None = None
    variant_name: str | None = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    price_at_add: Decimal | None = None
    price_changed: bool
    in_stock: bool
    available_quantity: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Cart Schemas
# =============================================================================


class CartResponse(BaseModel):
    """Cart response schema."""

    id: UUID
    items: list[CartItemResponse]
    item_count: int
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    total: Decimal
    coupon_code: str | None = None
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CartSummaryResponse(BaseModel):
    """Cart summary response (lightweight)."""

    id: UUID
    item_count: int
    subtotal: Decimal
    total: Decimal

    class Config:
        from_attributes = True


class ApplyCouponRequest(BaseModel):
    """Apply coupon request schema."""

    code: str


class ApplyCouponResponse(BaseModel):
    """Apply coupon response schema."""

    success: bool
    message: str
    discount_amount: Decimal
    new_total: Decimal


class CartNotesUpdate(BaseModel):
    """Update cart notes schema."""

    notes: str
