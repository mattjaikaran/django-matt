"""Pydantic schemas for orders app."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from ecommerce.users.schemas import AddressCreate

# =============================================================================
# Coupon Schemas
# =============================================================================


class CouponCreate(BaseModel):
    """Coupon creation schema."""

    code: str
    description: str = ""
    discount_type: str = "percentage"  # percentage, fixed, free_shipping
    discount_value: Decimal = Field(gt=0)
    minimum_purchase: Decimal = Decimal("0.00")
    maximum_discount: Decimal | None = None
    usage_limit: int | None = None
    usage_limit_per_user: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool = True


class CouponUpdate(BaseModel):
    """Coupon update schema."""

    description: str | None = None
    discount_type: str | None = None
    discount_value: Decimal | None = None
    minimum_purchase: Decimal | None = None
    maximum_discount: Decimal | None = None
    usage_limit: int | None = None
    usage_limit_per_user: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None


class CouponResponse(BaseModel):
    """Coupon response schema."""

    id: UUID
    code: str
    description: str
    discount_type: str
    discount_value: Decimal
    minimum_purchase: Decimal
    maximum_discount: Decimal | None
    usage_limit: int | None
    usage_limit_per_user: int | None
    times_used: int
    valid_from: datetime
    valid_until: datetime | None
    is_active: bool
    is_valid: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CouponValidationRequest(BaseModel):
    """Coupon validation request schema."""

    code: str
    subtotal: Decimal


class CouponValidationResponse(BaseModel):
    """Coupon validation response schema."""

    valid: bool
    message: str
    discount_amount: Decimal | None = None
    coupon: CouponResponse | None = None


# =============================================================================
# Order Item Schemas
# =============================================================================


class OrderItemResponse(BaseModel):
    """Order item response schema."""

    id: UUID
    product_id: UUID | None
    product_name: str
    variant_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    discount_amount: Decimal
    total: Decimal
    line_total: Decimal

    class Config:
        from_attributes = True


# =============================================================================
# Order Schemas
# =============================================================================


class CheckoutRequest(BaseModel):
    """Checkout request schema."""

    billing_address: AddressCreate
    shipping_address: AddressCreate | None = None  # If None, use billing address
    same_as_billing: bool = True
    email: EmailStr
    phone: str = ""
    customer_notes: str = ""
    coupon_code: str | None = None


class OrderCreateResponse(BaseModel):
    """Order creation response schema."""

    order_id: UUID
    order_number: str
    total: Decimal
    payment_intent_client_secret: str | None = None
    redirect_url: str | None = None


class OrderListResponse(BaseModel):
    """Order list response schema."""

    id: UUID
    order_number: str
    status: str
    item_count: int
    total: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class OrderDetailResponse(BaseModel):
    """Order detail response schema."""

    id: UUID
    order_number: str
    status: str
    billing_address: dict[str, Any]
    shipping_address: dict[str, Any]
    email: str
    phone: str
    items: list[OrderItemResponse]
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    total: Decimal
    coupon_code: str
    shipping_method: str
    tracking_number: str
    shipped_at: datetime | None
    delivered_at: datetime | None
    customer_notes: str
    currency: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    """Order status update schema."""

    status: str
    notes: str = ""
    tracking_number: str | None = None


class OrderStatusHistoryResponse(BaseModel):
    """Order status history response schema."""

    id: UUID
    status: str
    notes: str
    changed_by_email: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Shipping Schemas
# =============================================================================


class ShippingRateRequest(BaseModel):
    """Shipping rate request schema."""

    address: AddressCreate
    items: list[dict[str, Any]]  # [{product_id, variant_id, quantity}]


class ShippingRateResponse(BaseModel):
    """Shipping rate response schema."""

    method: str
    name: str
    description: str
    price: Decimal
    estimated_days: int
    currency: str = "USD"


class ShippingRatesResponse(BaseModel):
    """Available shipping rates response."""

    rates: list[ShippingRateResponse]
    free_shipping_threshold: Decimal
    subtotal: Decimal
    qualifies_for_free_shipping: bool


# =============================================================================
# Tax Schemas
# =============================================================================


class TaxCalculationRequest(BaseModel):
    """Tax calculation request schema."""

    address: AddressCreate
    subtotal: Decimal


class TaxCalculationResponse(BaseModel):
    """Tax calculation response schema."""

    tax_rate: Decimal
    tax_amount: Decimal
    subtotal: Decimal
    total: Decimal
    jurisdiction: str = ""


# =============================================================================
# Order Analytics Schemas
# =============================================================================


class OrderStatsResponse(BaseModel):
    """Order statistics response."""

    total_orders: int
    total_revenue: Decimal
    average_order_value: Decimal
    orders_by_status: dict[str, int]
    revenue_by_day: list[dict[str, Any]]  # [{date, revenue, order_count}]
