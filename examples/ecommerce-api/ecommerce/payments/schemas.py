"""Pydantic schemas for payments app."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

# =============================================================================
# Payment Schemas
# =============================================================================


class PaymentIntentCreateRequest(BaseModel):
    """Create payment intent request schema."""

    order_id: UUID
    payment_method: str = "card"  # card, paypal, apple_pay, google_pay


class PaymentIntentResponse(BaseModel):
    """Payment intent response schema."""

    payment_id: UUID
    client_secret: str
    amount: Decimal
    currency: str
    status: str


class PaymentMethodCreate(BaseModel):
    """Payment method creation schema (for saved cards)."""

    stripe_payment_method_id: str
    is_default: bool = False


class PaymentResponse(BaseModel):
    """Payment response schema."""

    id: UUID
    order_id: UUID
    status: str
    payment_method: str
    amount: Decimal
    currency: str
    card_brand: str
    card_last4: str
    stripe_payment_intent_id: str
    error_code: str
    error_message: str
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """Payment list response schema."""

    id: UUID
    order_id: UUID
    order_number: str
    status: str
    payment_method: str
    amount: Decimal
    currency: str
    card_brand: str
    card_last4: str
    paid_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Refund Schemas
# =============================================================================


class RefundCreateRequest(BaseModel):
    """Refund creation request schema."""

    payment_id: UUID
    amount: Decimal | None = None  # If None, full refund
    reason: str = "requested_by_customer"
    notes: str = ""


class RefundResponse(BaseModel):
    """Refund response schema."""

    id: UUID
    payment_id: UUID
    order_id: UUID
    status: str
    amount: Decimal
    reason: str
    notes: str
    stripe_refund_id: str
    error_code: str
    error_message: str
    refunded_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Webhook Schemas
# =============================================================================


class StripeWebhookEvent(BaseModel):
    """Stripe webhook event schema."""

    id: str
    type: str
    data: dict[str, Any]
    created: int


class WebhookResponse(BaseModel):
    """Webhook response schema."""

    received: bool
    processed: bool
    message: str = ""


# =============================================================================
# Checkout Session Schemas
# =============================================================================


class CheckoutSessionCreateRequest(BaseModel):
    """Create checkout session request."""

    order_id: UUID
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Checkout session response."""

    session_id: str
    url: str


# =============================================================================
# Customer Portal Schemas
# =============================================================================


class CustomerPortalRequest(BaseModel):
    """Customer billing portal request."""

    return_url: str


class CustomerPortalResponse(BaseModel):
    """Customer billing portal response."""

    url: str
