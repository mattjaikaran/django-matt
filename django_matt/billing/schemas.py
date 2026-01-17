"""
Pydantic schemas for billing API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, EmailStr


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class PriceInterval(str, Enum):
    """Billing interval for prices."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ONE_TIME = "one_time"


class SubscriptionStatus(str, Enum):
    """Subscription status."""

    ACTIVE = "active"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class InvoiceStatus(str, Enum):
    """Invoice status."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"


ProviderType = Literal["stripe", "paypal", "polar"]


# -----------------------------------------------------------------------------
# Customer Schemas
# -----------------------------------------------------------------------------


class CustomerBase(BaseModel):
    """Base customer schema."""

    email: EmailStr
    name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CustomerCreate(CustomerBase):
    """Schema for creating a customer."""

    provider: ProviderType | None = None


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""

    email: EmailStr | None = None
    name: str | None = None
    metadata: dict[str, Any] | None = None


class CustomerResponse(CustomerBase):
    """Customer response schema."""

    id: str
    provider: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Product Schemas
# -----------------------------------------------------------------------------


class ProductBase(BaseModel):
    """Base product schema."""

    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    provider: ProviderType | None = None


class ProductUpdate(BaseModel):
    """Schema for updating a product."""

    name: str | None = None
    description: str | None = None
    active: bool | None = None
    metadata: dict[str, Any] | None = None


class ProductResponse(ProductBase):
    """Product response schema."""

    id: str
    provider: str
    active: bool = True
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Price Schemas
# -----------------------------------------------------------------------------


class PriceBase(BaseModel):
    """Base price schema."""

    currency: str = "usd"
    unit_amount: int = Field(..., description="Amount in smallest currency unit (cents)")
    interval: PriceInterval = PriceInterval.MONTH
    interval_count: int = 1
    trial_period_days: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PriceCreate(PriceBase):
    """Schema for creating a price."""

    product_id: str
    provider: ProviderType | None = None


class PriceResponse(PriceBase):
    """Price response schema."""

    id: str
    product_id: str
    provider: str
    active: bool = True
    display_amount: float = Field(..., description="Amount in standard currency units")

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Subscription Schemas
# -----------------------------------------------------------------------------


class SubscriptionBase(BaseModel):
    """Base subscription schema."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription."""

    customer_id: str | None = None
    customer_email: str | None = None
    price_id: str
    quantity: int = 1
    trial_period_days: int | None = None
    provider: ProviderType | None = None


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""

    price_id: str | None = None
    quantity: int | None = None
    metadata: dict[str, Any] | None = None


class SubscriptionCancel(BaseModel):
    """Schema for canceling a subscription."""

    cancel_at_period_end: bool = True


class SubscriptionResponse(SubscriptionBase):
    """Subscription response schema."""

    id: str
    customer_id: str
    status: SubscriptionStatus
    provider: str
    price_id: str | None = None
    product_id: str | None = None
    quantity: int = 1
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    canceled_at: datetime | None = None
    trial_start: datetime | None = None
    trial_end: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SubscriptionListResponse(BaseModel):
    """List of subscriptions response."""

    items: list[SubscriptionResponse]
    total: int = 0


# -----------------------------------------------------------------------------
# Checkout Schemas
# -----------------------------------------------------------------------------


class CheckoutCreate(BaseModel):
    """Schema for creating a checkout session."""

    price_id: str
    success_url: str
    cancel_url: str
    customer_id: str | None = None
    customer_email: EmailStr | None = None
    mode: Literal["subscription", "payment"] = "subscription"
    quantity: int = 1
    trial_period_days: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provider: ProviderType | None = None


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    id: str
    url: str
    provider: str
    customer_id: str | None = None
    subscription_id: str | None = None
    status: str = "open"
    mode: str = "subscription"
    expires_at: datetime | None = None

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Billing Portal Schemas
# -----------------------------------------------------------------------------


class BillingPortalCreate(BaseModel):
    """Schema for creating a billing portal session."""

    customer_id: str
    return_url: str
    provider: ProviderType | None = None


class BillingPortalResponse(BaseModel):
    """Billing portal session response."""

    url: str


# -----------------------------------------------------------------------------
# Invoice Schemas
# -----------------------------------------------------------------------------


class InvoiceResponse(BaseModel):
    """Invoice response schema."""

    id: str
    customer_id: str
    subscription_id: str | None = None
    provider: str
    status: InvoiceStatus
    currency: str = "usd"
    amount_due: int = 0
    amount_paid: int = 0
    amount_remaining: int = 0
    invoice_pdf: str | None = None
    hosted_invoice_url: str | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """List of invoices response."""

    items: list[InvoiceResponse]
    total: int = 0


# -----------------------------------------------------------------------------
# Webhook Schemas
# -----------------------------------------------------------------------------


class WebhookEventResponse(BaseModel):
    """Webhook event response (for debugging/logging)."""

    id: str
    type: str
    provider: str
    processed: bool = False
    received_at: datetime


# -----------------------------------------------------------------------------
# Usage Schemas
# -----------------------------------------------------------------------------


class UsageRecordCreate(BaseModel):
    """Schema for creating a usage record."""

    subscription_id: str
    quantity: int = 1
    action: str = ""
    idempotency_key: str | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageRecordResponse(BaseModel):
    """Usage record response."""

    id: str
    subscription_id: str
    quantity: int
    action: str
    synced_to_provider: bool
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Configuration Schemas
# -----------------------------------------------------------------------------


class BillingConfigResponse(BaseModel):
    """Billing configuration response (safe for frontend)."""

    enabled: bool
    default_provider: ProviderType
    currency: str
    configured_providers: list[ProviderType]
    stripe_publishable_key: str | None = None


# -----------------------------------------------------------------------------
# Error Schemas
# -----------------------------------------------------------------------------


class BillingErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    code: str = "billing_error"
    details: dict[str, Any] = Field(default_factory=dict)
