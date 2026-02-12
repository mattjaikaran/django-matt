"""
Base billing provider class and data types.

All providers implement this interface for consistent billing operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

# Type variable for provider-specific config
ConfigT = TypeVar("ConfigT")


class BillingError(Exception):
    """Base exception for billing errors."""

    def __init__(self, message: str, code: str = "billing_error", details: dict | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class BillingConfigError(BillingError):
    """Configuration error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, "config_error", details)


class BillingAPIError(BillingError):
    """API error from provider."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        details: dict | None = None,
    ):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message, "api_error", details)


class BillingWebhookError(BillingError):
    """Webhook verification or processing error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, "webhook_error", details)


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


@dataclass
class CustomerData:
    """Customer data from provider."""

    id: str
    email: str
    name: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    provider: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductData:
    """Product data from provider."""

    id: str
    name: str
    description: str | None = None
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    provider: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PriceData:
    """Price data from provider."""

    id: str
    product_id: str
    currency: str
    unit_amount: int  # Amount in smallest currency unit (cents)
    interval: PriceInterval = PriceInterval.MONTH
    interval_count: int = 1
    trial_period_days: int | None = None
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def display_amount(self) -> float:
        """Get amount in standard currency units (dollars)."""
        return self.unit_amount / 100


@dataclass
class SubscriptionData:
    """Subscription data from provider."""

    id: str
    customer_id: str
    status: SubscriptionStatus
    price_id: str | None = None
    product_id: str | None = None
    quantity: int = 1
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    canceled_at: datetime | None = None
    trial_start: datetime | None = None
    trial_end: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    provider: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckoutSessionData:
    """Checkout session data from provider."""

    id: str
    url: str
    customer_id: str | None = None
    subscription_id: str | None = None
    status: str = "open"
    mode: str = "subscription"  # subscription, payment, setup
    success_url: str = ""
    cancel_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    provider: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvoiceData:
    """Invoice data from provider."""

    id: str
    customer_id: str
    subscription_id: str | None = None
    status: str = "draft"  # draft, open, paid, uncollectible, void
    currency: str = "usd"
    amount_due: int = 0
    amount_paid: int = 0
    amount_remaining: int = 0
    invoice_pdf: str | None = None
    hosted_invoice_url: str | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None
    provider: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Webhook event data."""

    id: str
    type: str  # e.g., "subscription.created", "invoice.paid"
    provider: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    raw_payload: bytes = b""


class ConnectAccountType(str, Enum):
    """Stripe Connect account type."""

    STANDARD = "standard"
    EXPRESS = "express"
    CUSTOM = "custom"


@dataclass
class ConnectedAccountData:
    """Connected account data from Stripe Connect."""

    id: str
    type: ConnectAccountType
    email: str = ""
    business_name: str = ""
    charges_enabled: bool = False
    payouts_enabled: bool = False
    details_submitted: bool = False
    country: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransferData:
    """Transfer data for Stripe Connect."""

    id: str
    amount: int
    currency: str = "usd"
    destination: str = ""
    source_transaction: str = ""
    description: str = ""
    status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountLinkData:
    """Account link data for Express onboarding."""

    url: str
    expires_at: datetime | None = None


@dataclass
class OAuthLinkData:
    """OAuth link data for Standard onboarding."""

    url: str
    state: str = ""


class BillingProvider(ABC, Generic[ConfigT]):
    """
    Abstract base class for billing providers.

    All providers must implement these methods for consistent billing operations.
    """

    provider_name: str = "base"

    def __init__(self, config: ConfigT):
        self.config = config

    # -------------------------------------------------------------------------
    # Customer Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_customer(
        self,
        email: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        """Create a new customer."""

    @abstractmethod
    async def get_customer(self, customer_id: str) -> CustomerData | None:
        """Get customer by ID."""

    @abstractmethod
    async def update_customer(
        self,
        customer_id: str,
        email: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CustomerData:
        """Update customer details."""

    @abstractmethod
    async def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer."""

    async def get_or_create_customer(
        self,
        email: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[CustomerData, bool]:
        """
        Get existing customer by email or create new one.

        Returns:
            Tuple of (CustomerData, created: bool)
        """
        # Default implementation - providers may override for efficiency
        customers = await self.list_customers(email=email, limit=1)
        if customers:
            return customers[0], False
        customer = await self.create_customer(email, name, metadata)
        return customer, True

    async def list_customers(
        self,
        email: str | None = None,
        limit: int = 10,
        starting_after: str | None = None,
    ) -> list[CustomerData]:
        """List customers with optional filtering."""
        # Optional - providers may override
        return []

    # -------------------------------------------------------------------------
    # Product Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_product(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        """Create a new product."""

    @abstractmethod
    async def get_product(self, product_id: str) -> ProductData | None:
        """Get product by ID."""

    @abstractmethod
    async def update_product(
        self,
        product_id: str,
        name: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductData:
        """Update product details."""

    @abstractmethod
    async def list_products(
        self,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[ProductData]:
        """List products."""

    # -------------------------------------------------------------------------
    # Price Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_price(
        self,
        product_id: str,
        unit_amount: int,
        currency: str = "usd",
        interval: PriceInterval = PriceInterval.MONTH,
        interval_count: int = 1,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PriceData:
        """Create a new price for a product."""

    @abstractmethod
    async def get_price(self, price_id: str) -> PriceData | None:
        """Get price by ID."""

    @abstractmethod
    async def list_prices(
        self,
        product_id: str | None = None,
        active: bool | None = None,
        limit: int = 10,
    ) -> list[PriceData]:
        """List prices."""

    # -------------------------------------------------------------------------
    # Subscription Management
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        quantity: int = 1,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionData:
        """Create a new subscription."""

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> SubscriptionData | None:
        """Get subscription by ID."""

    @abstractmethod
    async def update_subscription(
        self,
        subscription_id: str,
        price_id: str | None = None,
        quantity: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SubscriptionData:
        """Update subscription details."""

    @abstractmethod
    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True,
    ) -> SubscriptionData:
        """Cancel a subscription."""

    @abstractmethod
    async def resume_subscription(self, subscription_id: str) -> SubscriptionData:
        """Resume a canceled subscription (if cancel_at_period_end was True)."""

    @abstractmethod
    async def list_subscriptions(
        self,
        customer_id: str | None = None,
        status: SubscriptionStatus | None = None,
        limit: int = 10,
    ) -> list[SubscriptionData]:
        """List subscriptions."""

    # -------------------------------------------------------------------------
    # Checkout / Payment
    # -------------------------------------------------------------------------

    @abstractmethod
    async def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: str | None = None,
        customer_email: str | None = None,
        mode: str = "subscription",
        quantity: int = 1,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutSessionData:
        """Create a checkout session for payment."""

    @abstractmethod
    async def get_checkout_session(self, session_id: str) -> CheckoutSessionData | None:
        """Get checkout session by ID."""

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        """
        Create a billing portal session for customer self-service.

        Returns the portal URL.
        """
        raise NotImplementedError(f"{self.provider_name} does not support billing portal sessions")

    # -------------------------------------------------------------------------
    # Invoice Management
    # -------------------------------------------------------------------------

    async def get_invoice(self, invoice_id: str) -> InvoiceData | None:
        """Get invoice by ID."""
        return None

    async def list_invoices(
        self,
        customer_id: str | None = None,
        subscription_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[InvoiceData]:
        """List invoices."""
        return []

    async def get_upcoming_invoice(self, customer_id: str) -> InvoiceData | None:
        """Get upcoming invoice for a customer."""
        return None

    # -------------------------------------------------------------------------
    # Webhook Handling
    # -------------------------------------------------------------------------

    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> WebhookEvent:
        """
        Verify and parse a webhook event.

        Args:
            payload: Raw request body
            signature: Signature header from the request

        Returns:
            Parsed WebhookEvent

        Raises:
            BillingWebhookError: If verification fails
        """

    def normalize_webhook_type(self, provider_type: str) -> str:
        """
        Normalize provider-specific webhook type to common format.

        Common types:
        - customer.created, customer.updated, customer.deleted
        - product.created, product.updated
        - price.created, price.updated
        - subscription.created, subscription.updated, subscription.canceled
        - invoice.paid, invoice.payment_failed
        - checkout.completed
        """
        # Default implementation returns as-is
        # Providers should override to normalize their specific event types
        return provider_type

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _add_provider_tag(self, data: Any) -> Any:
        """Add provider name to data object."""
        if hasattr(data, "provider"):
            data.provider = self.provider_name
        return data
