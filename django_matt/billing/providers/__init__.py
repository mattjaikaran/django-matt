"""
Billing providers for django-matt.

Supports:
- Stripe: Full-featured payment processing
- PayPal: Global payment processing
- Polar: Developer-focused billing with MoR

Example:
    from django_matt.billing.providers import get_provider

    provider = get_provider("stripe")
    checkout = await provider.create_checkout_session(
        customer_id="cus_xxx",
        price_id="price_xxx",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
    )
"""

from django_matt.billing.config import ProviderType, get_billing_config
from django_matt.billing.providers.base import (
    BillingAPIError,
    BillingConfigError,
    BillingError,
    BillingProvider,
    BillingWebhookError,
    CheckoutSessionData,
    CustomerData,
    InvoiceData,
    PriceData,
    PriceInterval,
    ProductData,
    SubscriptionData,
    SubscriptionStatus,
    WebhookEvent,
)
from django_matt.billing.providers.paypal import PayPalProvider
from django_matt.billing.providers.polar import PolarProvider
from django_matt.billing.providers.stripe import StripeProvider


def get_provider(provider_name: ProviderType | None = None) -> BillingProvider:
    """
    Get a billing provider instance.

    Args:
        provider_name: The provider to use. If None, uses the default from settings.

    Returns:
        BillingProvider instance

    Raises:
        BillingConfigError: If the provider is not configured
    """
    config = get_billing_config()

    if provider_name is None:
        provider_name = config.default_provider

    providers: dict[ProviderType, type[BillingProvider]] = {
        "stripe": StripeProvider,
        "paypal": PayPalProvider,
        "polar": PolarProvider,
    }

    provider_class = providers.get(provider_name)
    if not provider_class:
        raise BillingConfigError(f"Unknown provider: {provider_name}")

    provider_config = config.get_provider_config(provider_name)
    if not provider_config.is_configured:
        raise BillingConfigError(
            f"Provider '{provider_name}' is not configured. "
            f"Please set DJANGO_MATT_BILLING['{provider_name.upper()}'] in settings."
        )

    return provider_class(provider_config)


def get_provider_instance(provider_name: ProviderType) -> BillingProvider:
    """Alias for get_provider()."""
    return get_provider(provider_name)


__all__ = [
    # Base classes
    "BillingProvider",
    "BillingError",
    "BillingConfigError",
    "BillingAPIError",
    "BillingWebhookError",
    # Data classes
    "CustomerData",
    "ProductData",
    "PriceData",
    "SubscriptionData",
    "CheckoutSessionData",
    "InvoiceData",
    "WebhookEvent",
    # Enums
    "PriceInterval",
    "SubscriptionStatus",
    # Providers
    "StripeProvider",
    "PayPalProvider",
    "PolarProvider",
    # Factory
    "get_provider",
    "get_provider_instance",
]
