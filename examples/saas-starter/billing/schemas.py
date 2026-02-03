"""
Pydantic schemas for billing app.

Includes:
- Subscription schemas
- Invoice schemas
- Payment method schemas
- Checkout schemas
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from core.schemas import OrganizationMiniResponse


# =============================================================================
# Plan Schemas
# =============================================================================

class PlanLimits(BaseModel):
    projects: int = -1
    members_per_org: int = -1
    storage_gb: int = -1


class PlanResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    price_monthly: int  # In cents
    price_yearly: int  # In cents
    limits: PlanLimits
    features: list[str] = []
    is_popular: bool = False


class PlansListResponse(BaseModel):
    plans: list[PlanResponse]


# =============================================================================
# Subscription Schemas
# =============================================================================

class SubscriptionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    stripe_subscription_id: str
    plan_name: str
    plan_interval: str
    status: str
    quantity: int
    current_period_start: datetime
    current_period_end: datetime
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool
    canceled_at: Optional[datetime] = None
    days_until_renewal: int = 0
    is_active: bool
    is_trialing: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionDetailResponse(SubscriptionResponse):
    """Subscription with organization and metadata."""
    organization: OrganizationMiniResponse
    metadata: dict = {}
    cancellation_reason: str = ""


class SubscriptionUpdateRequest(BaseModel):
    plan_id: str  # Stripe price ID
    quantity: Optional[int] = None


class SubscriptionCancelRequest(BaseModel):
    cancel_at_period_end: bool = True
    reason: str = ""
    feedback: str = ""


class SubscriptionReactivateRequest(BaseModel):
    """Reactivate a canceled subscription."""
    pass


# =============================================================================
# Invoice Schemas
# =============================================================================

class InvoiceLineItem(BaseModel):
    description: str
    quantity: int
    unit_amount: int  # In cents
    amount: int  # In cents


class InvoiceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    stripe_invoice_id: str
    number: str
    status: str
    subtotal: int
    tax: int
    total: int
    amount_paid: int
    amount_due: int
    currency: str
    invoice_date: datetime
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    invoice_pdf_url: str = ""
    hosted_invoice_url: str = ""
    is_paid: bool
    total_dollars: float
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceDetailResponse(InvoiceResponse):
    """Invoice with line items."""
    line_items: list[InvoiceLineItem] = []
    subscription_id: Optional[UUID] = None
    metadata: dict = {}


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Payment Method Schemas
# =============================================================================

class PaymentMethodResponse(BaseModel):
    id: UUID
    stripe_payment_method_id: str
    type: str
    card_brand: str = ""
    card_last4: str = ""
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    billing_name: str = ""
    billing_email: str = ""
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentMethodCreateRequest(BaseModel):
    payment_method_id: str  # Stripe PaymentMethod ID from Elements


class PaymentMethodSetDefaultRequest(BaseModel):
    payment_method_id: UUID


class BillingAddress(BaseModel):
    line1: str
    line2: str = ""
    city: str
    state: str = ""
    postal_code: str
    country: str  # ISO 2-letter code


class PaymentMethodUpdateRequest(BaseModel):
    billing_name: Optional[str] = None
    billing_email: Optional[str] = None
    billing_address: Optional[BillingAddress] = None


# =============================================================================
# Checkout Schemas
# =============================================================================

class CheckoutSessionRequest(BaseModel):
    price_id: str  # Stripe price ID
    quantity: int = 1
    success_url: str
    cancel_url: str
    coupon_code: Optional[str] = None
    trial_days: Optional[int] = None


class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str


class SetupIntentRequest(BaseModel):
    """Create a SetupIntent for adding payment method without immediate payment."""
    pass


class SetupIntentResponse(BaseModel):
    client_secret: str
    setup_intent_id: str


# =============================================================================
# Billing Portal Schemas
# =============================================================================

class BillingPortalRequest(BaseModel):
    return_url: str


class BillingPortalResponse(BaseModel):
    portal_url: str


# =============================================================================
# Usage Schemas
# =============================================================================

class UsageRecordCreate(BaseModel):
    metric: str
    quantity: Decimal
    action: str = "increment"
    timestamp: Optional[datetime] = None


class UsageRecordResponse(BaseModel):
    id: UUID
    metric: str
    quantity: Decimal
    action: str
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class UsageSummaryResponse(BaseModel):
    metric: str
    total: Decimal
    period_start: datetime
    period_end: datetime
    limit: Optional[int] = None
    percentage_used: Optional[float] = None


class UsageDashboardResponse(BaseModel):
    metrics: list[UsageSummaryResponse]
    subscription: Optional[SubscriptionResponse] = None


# =============================================================================
# Coupon Schemas
# =============================================================================

class CouponResponse(BaseModel):
    id: UUID
    code: str
    name: str
    discount_type: str
    discount_value: Decimal
    currency: str
    duration: str
    duration_months: Optional[int] = None
    is_valid: bool
    valid_until: Optional[datetime] = None

    class Config:
        from_attributes = True


class CouponApplyRequest(BaseModel):
    code: str


class CouponApplyResponse(BaseModel):
    coupon: CouponResponse
    discount_amount: int  # In cents
    message: str


# =============================================================================
# Webhook Schemas
# =============================================================================

class WebhookEventResponse(BaseModel):
    event_type: str
    processed: bool
    message: str


# =============================================================================
# Billing Overview Schemas
# =============================================================================

class BillingOverviewResponse(BaseModel):
    """Complete billing overview for organization."""
    subscription: Optional[SubscriptionResponse] = None
    upcoming_invoice: Optional[InvoiceResponse] = None
    default_payment_method: Optional[PaymentMethodResponse] = None
    usage: list[UsageSummaryResponse] = []
    recent_invoices: list[InvoiceResponse] = []
