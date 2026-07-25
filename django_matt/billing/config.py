"""
Billing configuration for django-matt.

Supports multiple payment providers: Stripe, PayPal, and Polar.

Configuration in settings.py:

    DJANGO_MATT_BILLING = {
        "ENABLED": True,
        "DEFAULT_PROVIDER": "stripe",  # stripe, paypal, polar
        "CURRENCY": "usd",
        "WEBHOOK_TOLERANCE_SECONDS": 300,
        "AUTO_CREATE_CUSTOMER": True,
        "SYNC_SUBSCRIPTIONS": True,

        # Stripe configuration
        "STRIPE": {
            "SECRET_KEY": "sk_...",
            "PUBLISHABLE_KEY": "pk_...",
            "WEBHOOK_SECRET": "whsec_...",
            "API_VERSION": "2024-12-18.acacia",
        },

        # PayPal configuration
        "PAYPAL": {
            "CLIENT_ID": "...",
            "CLIENT_SECRET": "...",
            "WEBHOOK_ID": "...",
            "MODE": "sandbox",  # sandbox or live
        },

        # Polar configuration
        "POLAR": {
            "ACCESS_TOKEN": "...",
            "ORGANIZATION_ID": "...",
            "WEBHOOK_SECRET": "...",
            "SANDBOX": True,
        },
    }
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from django.conf import settings

ProviderType = Literal["stripe", "paypal", "polar"]


@dataclass
class StripeConfig:
    """Stripe provider configuration."""

    secret_key: str = ""
    publishable_key: str = ""
    webhook_secret: str = ""
    api_version: str = "2024-12-18.acacia"

    # Stripe Connect configuration
    connect_client_id: str = ""
    connect_webhook_secret: str = ""
    connect_default_account_type: str = "standard"  # standard, express, custom
    connect_application_fee_percent: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.secret_key)

    @property
    def is_connect_configured(self) -> bool:
        return bool(self.secret_key and self.connect_client_id)


@dataclass
class PayPalConfig:
    """PayPal provider configuration."""

    client_id: str = ""
    client_secret: str = ""
    webhook_id: str = ""
    mode: Literal["sandbox", "live"] = "sandbox"

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def base_url(self) -> str:
        if self.mode == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"


@dataclass
class PolarConfig:
    """Polar provider configuration."""

    access_token: str = ""
    organization_id: str = ""
    webhook_secret: str = ""
    sandbox: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)

    @property
    def base_url(self) -> str:
        if self.sandbox:
            return "https://sandbox-api.polar.sh"
        return "https://api.polar.sh"


@dataclass
class BillingConfig:
    """Main billing configuration."""

    enabled: bool = True
    default_provider: ProviderType = "stripe"
    currency: str = "usd"
    webhook_tolerance_seconds: int = 300
    auto_create_customer: bool = True
    sync_subscriptions: bool = True

    # Provider-specific configs
    stripe: StripeConfig = field(default_factory=StripeConfig)
    paypal: PayPalConfig = field(default_factory=PayPalConfig)
    polar: PolarConfig = field(default_factory=PolarConfig)

    # Callback URLs (optional, can be set per-request)
    success_url: str = ""
    cancel_url: str = ""

    @classmethod
    def from_settings(cls) -> "BillingConfig":
        """Load configuration from Django settings."""
        config_dict = getattr(settings, "DJANGO_MATT_BILLING", {})

        stripe_dict = config_dict.get("STRIPE", {})
        stripe_config = StripeConfig(
            secret_key=stripe_dict.get("SECRET_KEY", ""),
            publishable_key=stripe_dict.get("PUBLISHABLE_KEY", ""),
            webhook_secret=stripe_dict.get("WEBHOOK_SECRET", ""),
            api_version=stripe_dict.get("API_VERSION", "2024-12-18.acacia"),
            connect_client_id=stripe_dict.get("CONNECT_CLIENT_ID", ""),
            connect_webhook_secret=stripe_dict.get("CONNECT_WEBHOOK_SECRET", ""),
            connect_default_account_type=stripe_dict.get(
                "CONNECT_DEFAULT_ACCOUNT_TYPE", "standard"
            ),
            connect_application_fee_percent=stripe_dict.get("CONNECT_APPLICATION_FEE_PERCENT", 0.0),
        )

        paypal_dict = config_dict.get("PAYPAL", {})
        paypal_config = PayPalConfig(
            client_id=paypal_dict.get("CLIENT_ID", ""),
            client_secret=paypal_dict.get("CLIENT_SECRET", ""),
            webhook_id=paypal_dict.get("WEBHOOK_ID", ""),
            mode=paypal_dict.get("MODE", "sandbox"),
        )

        polar_dict = config_dict.get("POLAR", {})
        polar_config = PolarConfig(
            access_token=polar_dict.get("ACCESS_TOKEN", ""),
            organization_id=polar_dict.get("ORGANIZATION_ID", ""),
            webhook_secret=polar_dict.get("WEBHOOK_SECRET", ""),
            sandbox=polar_dict.get("SANDBOX", True),
        )

        return cls(
            enabled=config_dict.get("ENABLED", True),
            default_provider=config_dict.get("DEFAULT_PROVIDER", "stripe"),
            currency=config_dict.get("CURRENCY", "usd"),
            webhook_tolerance_seconds=config_dict.get("WEBHOOK_TOLERANCE_SECONDS", 300),
            auto_create_customer=config_dict.get("AUTO_CREATE_CUSTOMER", True),
            sync_subscriptions=config_dict.get("SYNC_SUBSCRIPTIONS", True),
            stripe=stripe_config,
            paypal=paypal_config,
            polar=polar_config,
            success_url=config_dict.get("SUCCESS_URL", ""),
            cancel_url=config_dict.get("CANCEL_URL", ""),
        )

    def get_provider_config(self, provider: ProviderType) -> Any:
        """Get configuration for a specific provider."""
        configs = {
            "stripe": self.stripe,
            "paypal": self.paypal,
            "polar": self.polar,
        }
        return configs.get(provider)

    def get_configured_providers(self) -> list[ProviderType]:
        """Get list of configured providers."""
        providers: list[ProviderType] = []
        if self.stripe.is_configured:
            providers.append("stripe")
        if self.paypal.is_configured:
            providers.append("paypal")
        if self.polar.is_configured:
            providers.append("polar")
        return providers


# Global config instance (lazy-loaded)
_billing_config: BillingConfig | None = None


def get_billing_config() -> BillingConfig:
    """Get the billing configuration singleton."""
    global _billing_config
    if _billing_config is None:
        _billing_config = BillingConfig.from_settings()
    return _billing_config


def billing_config() -> BillingConfig:
    """Alias for get_billing_config()."""
    return get_billing_config()
