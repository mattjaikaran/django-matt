"""
Django Matt Billing - Multi-provider subscription and payment management.

Supports:
- Stripe: Full-featured payment processing
- PayPal: Global payment processing
- Polar: Developer-focused billing (Merchant of Record)

Configuration in settings.py:

    DJANGO_MATT_BILLING = {
        "ENABLED": True,
        "DEFAULT_PROVIDER": "stripe",
        "CURRENCY": "usd",

        "STRIPE": {
            "SECRET_KEY": "sk_...",
            "PUBLISHABLE_KEY": "pk_...",
            "WEBHOOK_SECRET": "whsec_...",
        },

        "PAYPAL": {
            "CLIENT_ID": "...",
            "CLIENT_SECRET": "...",
            "MODE": "sandbox",  # or "live"
        },

        "POLAR": {
            "ACCESS_TOKEN": "...",
            "ORGANIZATION_ID": "...",
            "WEBHOOK_SECRET": "...",
            "SANDBOX": True,
        },
    }

Example usage:

    from django_matt.billing import BillingController, WebhookController

    # Register controllers
    api.register_controller(BillingController, prefix="/billing")
    api.register_controller(WebhookController, prefix="/billing/webhooks")

    # Or use providers directly
    from django_matt.billing import get_provider

    provider = get_provider("stripe")
    checkout = await provider.create_checkout_session(
        price_id="price_xxx",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        customer_email="user@example.com",
    )
"""

# Configuration
from django_matt.billing.config import (
    BillingConfig,
    PayPalConfig,
    PolarConfig,
    ProviderType,
    StripeConfig,
    billing_config,
    get_billing_config,
)

# Controllers
from django_matt.billing.controllers import (
    BillingController,
    WebhookController,
)

# Providers
from django_matt.billing.providers import (
    BillingAPIError,
    BillingConfigError,
    BillingError,
    BillingProvider,
    BillingWebhookError,
    CheckoutSessionData,
    CustomerData,
    InvoiceData,
    PayPalProvider,
    PolarProvider,
    PriceData,
    PriceInterval,
    ProductData,
    StripeProvider,
    SubscriptionData,
    SubscriptionStatus,
    WebhookEvent,
    get_provider,
    get_provider_instance,
)

# Schemas
from django_matt.billing.schemas import (
    BillingConfigResponse,
    BillingErrorResponse,
    BillingPortalCreate,
    BillingPortalResponse,
    CheckoutCreate,
    CheckoutResponse,
    CustomerBase,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    InvoiceListResponse,
    InvoiceResponse,
    PriceBase,
    PriceCreate,
    PriceResponse,
    ProductBase,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    SubscriptionBase,
    SubscriptionCancel,
    SubscriptionCreate,
    SubscriptionListResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
    UsageRecordCreate,
    UsageRecordResponse,
)

# Signals
from django_matt.billing.signals import (
    invoice_paid,
    subscription_canceled,
    subscription_synced,
    webhook_received,
)

# Testing helpers
from django_matt.billing.testing import (
    mock_paypal_event,
    mock_polar_event,
    mock_stripe_event,
)

# Models (import separately to avoid Django app loading issues)
# from django_matt.billing.models import (
#     BillingCustomer,
#     BillingProduct,
#     BillingPrice,
#     Subscription,
#     Invoice,
#     WebhookEvent as WebhookEventModel,
#     UsageRecord,
# )

__all__ = [
    # Configuration
    "BillingConfig",
    "StripeConfig",
    "PayPalConfig",
    "PolarConfig",
    "ProviderType",
    "get_billing_config",
    "billing_config",
    # Provider base
    "BillingProvider",
    "BillingError",
    "BillingConfigError",
    "BillingAPIError",
    "BillingWebhookError",
    # Data types
    "CustomerData",
    "ProductData",
    "PriceData",
    "SubscriptionData",
    "CheckoutSessionData",
    "InvoiceData",
    "WebhookEvent",
    "PriceInterval",
    "SubscriptionStatus",
    # Providers
    "StripeProvider",
    "PayPalProvider",
    "PolarProvider",
    "get_provider",
    "get_provider_instance",
    # Schemas
    "CustomerBase",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "ProductBase",
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "PriceBase",
    "PriceCreate",
    "PriceResponse",
    "SubscriptionBase",
    "SubscriptionCreate",
    "SubscriptionUpdate",
    "SubscriptionCancel",
    "SubscriptionResponse",
    "SubscriptionListResponse",
    "CheckoutCreate",
    "CheckoutResponse",
    "BillingPortalCreate",
    "BillingPortalResponse",
    "InvoiceResponse",
    "InvoiceListResponse",
    "UsageRecordCreate",
    "UsageRecordResponse",
    "BillingConfigResponse",
    "BillingErrorResponse",
    # Controllers
    "BillingController",
    "WebhookController",
    # Signals
    "subscription_synced",
    "subscription_canceled",
    "invoice_paid",
    "webhook_received",
    # Testing helpers
    "mock_stripe_event",
    "mock_paypal_event",
    "mock_polar_event",
]
