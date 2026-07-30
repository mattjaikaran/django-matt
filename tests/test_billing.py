"""
Tests for the Django Matt billing module.

Tests cover:
- Models: BillingCustomer, Subscription, Invoice, BillingProduct, BillingPrice, WebhookEvent, UsageRecord
- Providers: Stripe, PayPal, Polar (all external API calls mocked)
- Factory function: get_provider() returns correct provider instances
- Webhook handling: signature verification, event processing, idempotency
- Controllers: BillingController, WebhookController
- Subscription lifecycle: create, activate, cancel, resume state transitions
- Configuration: BillingConfig, StripeConfig, PayPalConfig, PolarConfig
- Schemas: Pydantic schema validation
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest

from django_matt.billing.config import (
    BillingConfig,
    PayPalConfig,
    PolarConfig,
    StripeConfig,
    get_billing_config,
)
from django_matt.billing.controllers import BillingController, WebhookController
from django_matt.billing.models import (
    BillingCustomer,
    BillingPrice,
    BillingProduct,
    Invoice,
    Subscription,
    UsageRecord,
)
from django_matt.billing.models import (
    WebhookEvent as WebhookEventModel,
)
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

stripe_lib = pytest.importorskip("stripe", reason="stripe package required for billing tests")
from django_matt.billing.schemas import (
    BillingConfigResponse,
    BillingErrorResponse,
    BillingPortalCreate,
    BillingPortalResponse,
    CheckoutCreate,
    CheckoutResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    InvoiceListResponse,
    InvoiceResponse,
    PriceCreate,
    PriceResponse,
    ProductCreate,
    ProductResponse,
    SubscriptionCancel,
    SubscriptionCreate,
    SubscriptionListResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
    UsageRecordCreate,
    UsageRecordResponse,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rf():
    """Provide a Django RequestFactory for tests."""
    return RequestFactory()


@pytest.fixture
def stripe_config():
    """Create a Stripe configuration for testing."""
    return StripeConfig(
        secret_key="sk_test_abc123",
        publishable_key="pk_test_abc123",
        webhook_secret="whsec_test_abc123",
        api_version="2024-12-18.acacia",
    )


@pytest.fixture
def paypal_config():
    """Create a PayPal configuration for testing."""
    return PayPalConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        webhook_id="test_webhook_id",
        mode="sandbox",
    )


@pytest.fixture
def polar_config():
    """Create a Polar configuration for testing."""
    return PolarConfig(
        access_token="test_access_token",
        organization_id="test_org_id",
        webhook_secret="test_webhook_secret",
        sandbox=True,
    )


@pytest.fixture
def billing_config_full(stripe_config, paypal_config, polar_config):
    """Create a full billing configuration for testing."""
    return BillingConfig(
        enabled=True,
        default_provider="stripe",
        currency="usd",
        stripe=stripe_config,
        paypal=paypal_config,
        polar=polar_config,
    )


@pytest.fixture
@pytest.mark.django_db
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="billinguser",
        email="billing@example.com",
        password="testpass123",
    )


@pytest.fixture
@pytest.mark.django_db
def billing_customer(test_user):
    """Create a test billing customer."""
    return BillingCustomer.objects.create(
        user=test_user,
        stripe_customer_id="cus_stripe_123",
        paypal_customer_id="paypal_user@example.com",
        polar_customer_id="cus_polar_123",
        default_provider="stripe",
    )


@pytest.fixture
@pytest.mark.django_db
def billing_product():
    """Create a test billing product."""
    return BillingProduct.objects.create(
        provider="stripe",
        provider_product_id="prod_test_123",
        name="Pro Plan",
        description="Professional plan with all features",
        active=True,
        features=["Feature A", "Feature B"],
        metadata={"tier": "pro"},
    )


@pytest.fixture
@pytest.mark.django_db
def billing_price(billing_product):
    """Create a test billing price."""
    return BillingPrice.objects.create(
        provider="stripe",
        provider_price_id="price_test_123",
        product=billing_product,
        currency="usd",
        unit_amount=2999,
        interval=BillingPrice.Interval.MONTH,
        interval_count=1,
        trial_period_days=14,
        active=True,
        nickname="Monthly",
    )


@pytest.fixture
@pytest.mark.django_db
def subscription(billing_customer, billing_price):
    """Create a test subscription."""
    now = timezone.now()
    return Subscription.objects.create(
        customer=billing_customer,
        price=billing_price,
        provider="stripe",
        provider_subscription_id="sub_test_123",
        status=Subscription.Status.ACTIVE,
        quantity=1,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )


@pytest.fixture
@pytest.mark.django_db
def invoice(billing_customer, subscription):
    """Create a test invoice."""
    return Invoice.objects.create(
        customer=billing_customer,
        subscription=subscription,
        provider="stripe",
        provider_invoice_id="inv_test_123",
        status=Invoice.Status.PAID,
        currency="usd",
        amount_due=2999,
        amount_paid=2999,
        amount_remaining=0,
        paid_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Configuration Tests
# ---------------------------------------------------------------------------


class TestStripeConfig:
    """Test StripeConfig dataclass."""

    def test_default_values(self):
        """Stripe config should have sensible defaults."""
        config = StripeConfig()
        assert config.secret_key == ""
        assert config.publishable_key == ""
        assert config.webhook_secret == ""
        assert config.api_version == "2024-12-18.acacia"

    def test_is_configured_false_when_empty(self):
        """Should not be configured without secret key."""
        config = StripeConfig()
        assert config.is_configured is False

    def test_is_configured_true_with_key(self, stripe_config):
        """Should be configured with secret key."""
        assert stripe_config.is_configured is True


class TestPayPalConfig:
    """Test PayPalConfig dataclass."""

    def test_default_values(self):
        """PayPal config should have sensible defaults."""
        config = PayPalConfig()
        assert config.client_id == ""
        assert config.client_secret == ""
        assert config.mode == "sandbox"

    def test_is_configured_false_when_empty(self):
        """Should not be configured without credentials."""
        config = PayPalConfig()
        assert config.is_configured is False

    def test_is_configured_true_with_credentials(self, paypal_config):
        """Should be configured with both client_id and client_secret."""
        assert paypal_config.is_configured is True

    def test_is_configured_false_with_partial_credentials(self):
        """Should not be configured with only client_id."""
        config = PayPalConfig(client_id="test_id")
        assert config.is_configured is False

    def test_sandbox_base_url(self):
        """Sandbox mode should use sandbox URL."""
        config = PayPalConfig(mode="sandbox")
        assert config.base_url == "https://api-m.sandbox.paypal.com"

    def test_live_base_url(self):
        """Live mode should use production URL."""
        config = PayPalConfig(mode="live")
        assert config.base_url == "https://api-m.paypal.com"


class TestPolarConfig:
    """Test PolarConfig dataclass."""

    def test_default_values(self):
        """Polar config should have sensible defaults."""
        config = PolarConfig()
        assert config.access_token == ""
        assert config.organization_id == ""
        assert config.sandbox is True

    def test_is_configured_false_when_empty(self):
        """Should not be configured without access token."""
        config = PolarConfig()
        assert config.is_configured is False

    def test_is_configured_true_with_token(self, polar_config):
        """Should be configured with access token."""
        assert polar_config.is_configured is True

    def test_sandbox_base_url(self):
        """Sandbox mode should use sandbox URL."""
        config = PolarConfig(sandbox=True)
        assert config.base_url == "https://sandbox-api.polar.sh"

    def test_production_base_url(self):
        """Production mode should use production URL."""
        config = PolarConfig(sandbox=False)
        assert config.base_url == "https://api.polar.sh"


class TestBillingConfig:
    """Test BillingConfig dataclass."""

    def test_default_values(self):
        """Billing config should have sensible defaults."""
        config = BillingConfig()
        assert config.enabled is True
        assert config.default_provider == "stripe"
        assert config.currency == "usd"
        assert config.webhook_tolerance_seconds == 300
        assert config.auto_create_customer is True
        assert config.sync_subscriptions is True

    def test_get_provider_config(self, billing_config_full):
        """Should return correct provider config by name."""
        stripe = billing_config_full.get_provider_config("stripe")
        assert isinstance(stripe, StripeConfig)
        assert stripe.secret_key == "sk_test_abc123"

        paypal = billing_config_full.get_provider_config("paypal")
        assert isinstance(paypal, PayPalConfig)
        assert paypal.client_id == "test_client_id"

        polar = billing_config_full.get_provider_config("polar")
        assert isinstance(polar, PolarConfig)
        assert polar.access_token == "test_access_token"

    def test_get_configured_providers(self, billing_config_full):
        """Should return list of configured providers."""
        providers = billing_config_full.get_configured_providers()
        assert "stripe" in providers
        assert "paypal" in providers
        assert "polar" in providers

    def test_get_configured_providers_empty(self):
        """Should return empty list when no providers are configured."""
        config = BillingConfig()
        providers = config.get_configured_providers()
        assert providers == []

    def test_get_configured_providers_partial(self, stripe_config):
        """Should return only configured providers."""
        config = BillingConfig(stripe=stripe_config)
        providers = config.get_configured_providers()
        assert providers == ["stripe"]

    def test_from_settings(self, settings):
        """Should load configuration from Django settings."""
        settings.DJANGO_MATT_BILLING = {
            "ENABLED": True,
            "DEFAULT_PROVIDER": "stripe",
            "CURRENCY": "eur",
            "STRIPE": {
                "SECRET_KEY": "sk_test_fromdjango",
                "PUBLISHABLE_KEY": "pk_test_fromdjango",
                "WEBHOOK_SECRET": "whsec_fromdjango",
            },
        }
        # Reset the cached global config
        import django_matt.billing.config as config_module

        config_module._billing_config = None

        config = BillingConfig.from_settings()
        assert config.enabled is True
        assert config.default_provider == "stripe"
        assert config.currency == "eur"
        assert config.stripe.secret_key == "sk_test_fromdjango"
        assert config.stripe.publishable_key == "pk_test_fromdjango"


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBillingCustomerModel:
    """Test BillingCustomer model."""

    def test_create_billing_customer(self, test_user):
        """Should create a billing customer linked to a user."""
        customer = BillingCustomer.objects.create(
            user=test_user,
            stripe_customer_id="cus_test",
            default_provider="stripe",
        )
        assert customer.pk is not None
        assert customer.user == test_user
        assert customer.stripe_customer_id == "cus_test"
        assert customer.default_provider == "stripe"

    def test_str_representation(self, billing_customer):
        """String representation should include user and provider."""
        result = str(billing_customer)
        assert "BillingCustomer(" in result
        assert "stripe" in result

    def test_get_customer_id_default_provider(self, billing_customer):
        """Should return customer ID for the default provider."""
        customer_id = billing_customer.get_customer_id()
        assert customer_id == "cus_stripe_123"

    def test_get_customer_id_specific_provider(self, billing_customer):
        """Should return customer ID for a specific provider."""
        assert billing_customer.get_customer_id("stripe") == "cus_stripe_123"
        assert billing_customer.get_customer_id("paypal") == "paypal_user@example.com"
        assert billing_customer.get_customer_id("polar") == "cus_polar_123"

    def test_get_customer_id_unknown_provider(self, billing_customer):
        """Should return None for unknown provider."""
        assert billing_customer.get_customer_id("unknown") is None

    def test_set_customer_id(self, billing_customer):
        """Should update customer ID for a specific provider."""
        billing_customer.set_customer_id("stripe", "cus_new_stripe")
        billing_customer.refresh_from_db()
        assert billing_customer.stripe_customer_id == "cus_new_stripe"

    def test_uuid_primary_key(self, billing_customer):
        """Should use UUID as primary key."""
        assert isinstance(billing_customer.pk, uuid.UUID)

    def test_metadata_default(self, test_user):
        """Metadata should default to empty dict."""
        customer = BillingCustomer.objects.create(
            user=test_user,
            stripe_customer_id="cus_meta_test",
        )
        assert customer.metadata == {}

    def test_user_relationship(self, billing_customer, test_user):
        """Should be accessible from user's related manager."""
        assert test_user.billing_customers.count() == 1
        assert test_user.billing_customers.first() == billing_customer


@pytest.mark.django_db
class TestBillingProductModel:
    """Test BillingProduct model."""

    def test_create_product(self):
        """Should create a billing product."""
        product = BillingProduct.objects.create(
            provider="stripe",
            provider_product_id="prod_abc",
            name="Enterprise Plan",
            description="Full enterprise features",
            active=True,
        )
        assert product.pk is not None
        assert product.name == "Enterprise Plan"
        assert product.provider == "stripe"

    def test_str_representation(self, billing_product):
        """String representation should include name and provider."""
        result = str(billing_product)
        assert "Pro Plan" in result
        assert "stripe" in result

    def test_unique_together(self, billing_product):
        """Should enforce unique constraint on provider + product_id."""
        with pytest.raises(IntegrityError):
            BillingProduct.objects.create(
                provider="stripe",
                provider_product_id="prod_test_123",
                name="Duplicate",
            )

    def test_features_json_field(self, billing_product):
        """Features should be stored as JSON list."""
        assert billing_product.features == ["Feature A", "Feature B"]

    def test_metadata_json_field(self, billing_product):
        """Metadata should be stored as JSON dict."""
        assert billing_product.metadata == {"tier": "pro"}


@pytest.mark.django_db
class TestBillingPriceModel:
    """Test BillingPrice model."""

    def test_create_price(self, billing_product):
        """Should create a billing price linked to a product."""
        price = BillingPrice.objects.create(
            provider="stripe",
            provider_price_id="price_new",
            product=billing_product,
            currency="usd",
            unit_amount=4999,
            interval=BillingPrice.Interval.YEAR,
        )
        assert price.pk is not None
        assert price.unit_amount == 4999
        assert price.interval == "year"

    def test_display_amount(self, billing_price):
        """Should format amount as dollars."""
        assert billing_price.display_amount == "29.99"

    def test_display_amount_zero(self, billing_product):
        """Should format zero amount correctly."""
        price = BillingPrice.objects.create(
            provider="stripe",
            provider_price_id="price_free",
            product=billing_product,
            unit_amount=0,
        )
        assert price.display_amount == "0.00"

    def test_str_representation(self, billing_price):
        """String representation should include amount, currency, and interval."""
        result = str(billing_price)
        assert "29.99" in result
        assert "USD" in result
        assert "month" in result

    def test_interval_choices(self):
        """Should have all expected interval choices."""
        choices = [c[0] for c in BillingPrice.Interval.choices]
        assert "day" in choices
        assert "week" in choices
        assert "month" in choices
        assert "year" in choices
        assert "one_time" in choices

    def test_product_relationship(self, billing_price, billing_product):
        """Price should be linked to product through FK."""
        assert billing_price.product == billing_product
        assert billing_product.prices.count() == 1

    def test_unique_together(self, billing_price):
        """Should enforce unique constraint on provider + price_id."""
        with pytest.raises(IntegrityError):
            BillingPrice.objects.create(
                provider="stripe",
                provider_price_id="price_test_123",
                unit_amount=1000,
            )


@pytest.mark.django_db
class TestSubscriptionModel:
    """Test Subscription model."""

    def test_create_subscription(self, billing_customer, billing_price):
        """Should create a subscription."""
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_new",
            status=Subscription.Status.ACTIVE,
        )
        assert sub.pk is not None
        assert sub.status == "active"
        assert sub.quantity == 1

    def test_is_active_for_active_status(self, subscription):
        """is_active should return True for active subscriptions."""
        subscription.status = Subscription.Status.ACTIVE
        assert subscription.is_active is True

    def test_is_active_for_trialing_status(self, subscription):
        """is_active should return True for trialing subscriptions."""
        subscription.status = Subscription.Status.TRIALING
        assert subscription.is_active is True

    def test_is_active_for_canceled_status(self, subscription):
        """is_active should return False for canceled subscriptions."""
        subscription.status = Subscription.Status.CANCELED
        assert subscription.is_active is False

    def test_is_active_for_past_due_status(self, subscription):
        """is_active should return False for past_due subscriptions."""
        subscription.status = Subscription.Status.PAST_DUE
        assert subscription.is_active is False

    def test_is_trialing(self, subscription):
        """is_trialing should correctly identify trial status."""
        subscription.status = Subscription.Status.TRIALING
        assert subscription.is_trialing is True

        subscription.status = Subscription.Status.ACTIVE
        assert subscription.is_trialing is False

    def test_will_cancel_when_cancel_at_period_end(self, subscription):
        """will_cancel should be True when cancel_at_period_end is set and status is active."""
        subscription.cancel_at_period_end = True
        subscription.status = Subscription.Status.ACTIVE
        assert subscription.will_cancel is True

    def test_will_cancel_false_when_not_active(self, subscription):
        """will_cancel should be False when subscription is not active."""
        subscription.cancel_at_period_end = True
        subscription.status = Subscription.Status.CANCELED
        assert subscription.will_cancel is False

    def test_will_cancel_false_when_not_set(self, subscription):
        """will_cancel should be False when cancel_at_period_end is not set."""
        subscription.cancel_at_period_end = False
        subscription.status = Subscription.Status.ACTIVE
        assert subscription.will_cancel is False

    def test_str_representation(self, subscription):
        """String representation should include user and status."""
        result = str(subscription)
        assert "Subscription(" in result
        assert "active" in result

    def test_status_choices(self):
        """Should have all expected status choices."""
        choices = [c[0] for c in Subscription.Status.choices]
        assert "active" in choices
        assert "canceled" in choices
        assert "incomplete" in choices
        assert "past_due" in choices
        assert "paused" in choices
        assert "trialing" in choices
        assert "unpaid" in choices

    def test_customer_relationship(self, subscription, billing_customer):
        """Subscription should be linked to customer."""
        assert subscription.customer == billing_customer
        assert billing_customer.subscriptions.count() == 1


@pytest.mark.django_db
class TestInvoiceModel:
    """Test Invoice model."""

    def test_create_invoice(self, billing_customer):
        """Should create an invoice."""
        inv = Invoice.objects.create(
            customer=billing_customer,
            provider="stripe",
            provider_invoice_id="inv_new",
            status=Invoice.Status.OPEN,
            amount_due=5000,
            amount_paid=0,
            amount_remaining=5000,
        )
        assert inv.pk is not None
        assert inv.status == "open"
        assert inv.amount_due == 5000

    def test_display_amount_due(self, invoice):
        """Should format amount due as dollars."""
        assert invoice.display_amount_due == "29.99"

    def test_str_representation(self, invoice):
        """String representation should include invoice ID and status."""
        result = str(invoice)
        assert "inv_test_123" in result
        assert "paid" in result

    def test_status_choices(self):
        """Should have all expected status choices."""
        choices = [c[0] for c in Invoice.Status.choices]
        assert "draft" in choices
        assert "open" in choices
        assert "paid" in choices
        assert "uncollectible" in choices
        assert "void" in choices

    def test_ordering(self, billing_customer):
        """Invoices should be ordered by -created_at."""
        inv1 = Invoice.objects.create(
            customer=billing_customer,
            provider="stripe",
            provider_invoice_id="inv_1",
        )
        inv2 = Invoice.objects.create(
            customer=billing_customer,
            provider="stripe",
            provider_invoice_id="inv_2",
        )
        invoices = list(Invoice.objects.filter(customer=billing_customer))
        # Latest created should come first
        assert invoices[0].provider_invoice_id == "inv_2"
        assert invoices[1].provider_invoice_id == "inv_1"


@pytest.mark.django_db
class TestWebhookEventModel:
    """Test WebhookEvent model."""

    def test_create_webhook_event(self):
        """Should create a webhook event."""
        event = WebhookEventModel.objects.create(
            provider="stripe",
            provider_event_id="evt_test_123",
            event_type="customer.subscription.created",
            payload={"id": "sub_123"},
        )
        assert event.pk is not None
        assert event.processed is False
        assert event.processing_error == ""

    def test_mark_processed_success(self):
        """mark_processed should update processed status and timestamp."""
        event = WebhookEventModel.objects.create(
            provider="stripe",
            provider_event_id="evt_proc_123",
            event_type="invoice.paid",
            payload={},
        )
        event.mark_processed()
        event.refresh_from_db()
        assert event.processed is True
        assert event.processed_at is not None
        assert event.processing_error == ""

    def test_mark_processed_with_error(self):
        """mark_processed should store error message."""
        event = WebhookEventModel.objects.create(
            provider="stripe",
            provider_event_id="evt_err_123",
            event_type="invoice.payment_failed",
            payload={},
        )
        event.mark_processed(error="Database write failed")
        event.refresh_from_db()
        assert event.processed is True
        assert event.processing_error == "Database write failed"

    def test_str_representation(self):
        """String representation should include type and provider."""
        event = WebhookEventModel.objects.create(
            provider="stripe",
            provider_event_id="evt_str_123",
            event_type="subscription.updated",
            payload={},
        )
        result = str(event)
        assert "subscription.updated" in result
        assert "stripe" in result

    def test_unique_together(self):
        """Should enforce unique constraint on provider + event_id."""
        WebhookEventModel.objects.create(
            provider="stripe",
            provider_event_id="evt_dup_123",
            event_type="test",
            payload={},
        )
        with pytest.raises(IntegrityError):
            WebhookEventModel.objects.create(
                provider="stripe",
                provider_event_id="evt_dup_123",
                event_type="test",
                payload={},
            )

    def test_different_providers_same_event_id(self):
        """Same event ID with different providers should be allowed."""
        WebhookEventModel.objects.create(
            provider="stripe",
            provider_event_id="evt_shared_123",
            event_type="test",
            payload={},
        )
        event2 = WebhookEventModel.objects.create(
            provider="paypal",
            provider_event_id="evt_shared_123",
            event_type="test",
            payload={},
        )
        assert event2.pk is not None


@pytest.mark.django_db
class TestUsageRecordModel:
    """Test UsageRecord model."""

    def test_create_usage_record(self, subscription):
        """Should create a usage record."""
        record = UsageRecord.objects.create(
            subscription=subscription,
            quantity=10,
            action="api_call",
            idempotency_key="idem_123",
        )
        assert record.pk is not None
        assert record.quantity == 10
        assert record.action == "api_call"
        assert record.synced_to_provider is False

    def test_str_representation(self, subscription):
        """String representation should include subscription and quantity."""
        record = UsageRecord.objects.create(
            subscription=subscription,
            quantity=5,
        )
        result = str(record)
        assert "UsageRecord(" in result
        assert "5" in result


# ---------------------------------------------------------------------------
# Base Provider Data Type Tests
# ---------------------------------------------------------------------------


class TestBaseDataTypes:
    """Test base provider data types."""

    def test_customer_data_creation(self):
        """Should create CustomerData with all fields."""
        customer = CustomerData(
            id="cus_123",
            email="test@example.com",
            name="Test User",
            phone="+1234567890",
            metadata={"plan": "pro"},
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            provider="stripe",
        )
        assert customer.id == "cus_123"
        assert customer.email == "test@example.com"
        assert customer.name == "Test User"

    def test_product_data_creation(self):
        """Should create ProductData with all fields."""
        product = ProductData(
            id="prod_123",
            name="Pro Plan",
            description="Professional plan",
            active=True,
            provider="stripe",
        )
        assert product.id == "prod_123"
        assert product.active is True

    def test_price_data_display_amount(self):
        """PriceData display_amount should convert cents to dollars."""
        price = PriceData(
            id="price_123",
            product_id="prod_123",
            currency="usd",
            unit_amount=2999,
        )
        assert price.display_amount == 29.99

    def test_price_data_display_amount_zero(self):
        """PriceData display_amount should handle zero."""
        price = PriceData(
            id="price_free",
            product_id="prod_123",
            currency="usd",
            unit_amount=0,
        )
        assert price.display_amount == 0.0

    def test_subscription_data_creation(self):
        """Should create SubscriptionData with all fields."""
        sub = SubscriptionData(
            id="sub_123",
            customer_id="cus_123",
            status=SubscriptionStatus.ACTIVE,
            price_id="price_123",
            product_id="prod_123",
            quantity=1,
            cancel_at_period_end=False,
        )
        assert sub.id == "sub_123"
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_checkout_session_data_creation(self):
        """Should create CheckoutSessionData with all fields."""
        session = CheckoutSessionData(
            id="cs_123",
            url="https://checkout.example.com/cs_123",
            customer_id="cus_123",
            status="open",
            mode="subscription",
        )
        assert session.id == "cs_123"
        assert session.url == "https://checkout.example.com/cs_123"

    def test_invoice_data_creation(self):
        """Should create InvoiceData with all fields."""
        inv = InvoiceData(
            id="inv_123",
            customer_id="cus_123",
            status="paid",
            amount_due=2999,
            amount_paid=2999,
            amount_remaining=0,
        )
        assert inv.id == "inv_123"
        assert inv.status == "paid"

    def test_webhook_event_creation(self):
        """Should create WebhookEvent with all fields."""
        event = WebhookEvent(
            id="evt_123",
            type="invoice.paid",
            provider="stripe",
            data={"id": "inv_123"},
        )
        assert event.id == "evt_123"
        assert event.type == "invoice.paid"

    def test_price_interval_enum(self):
        """PriceInterval should have all expected values."""
        assert PriceInterval.DAY.value == "day"
        assert PriceInterval.WEEK.value == "week"
        assert PriceInterval.MONTH.value == "month"
        assert PriceInterval.YEAR.value == "year"
        assert PriceInterval.ONE_TIME.value == "one_time"

    def test_subscription_status_enum(self):
        """SubscriptionStatus should have all expected values."""
        assert SubscriptionStatus.ACTIVE.value == "active"
        assert SubscriptionStatus.CANCELED.value == "canceled"
        assert SubscriptionStatus.TRIALING.value == "trialing"
        assert SubscriptionStatus.PAST_DUE.value == "past_due"
        assert SubscriptionStatus.PAUSED.value == "paused"


# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestBillingExceptions:
    """Test billing exception hierarchy."""

    def test_billing_error_base(self):
        """BillingError should store message, code, and details."""
        err = BillingError("Something failed", "test_error", {"key": "value"})
        assert err.message == "Something failed"
        assert err.code == "test_error"
        assert err.details == {"key": "value"}
        assert str(err) == "Something failed"

    def test_billing_error_defaults(self):
        """BillingError should have default code and empty details."""
        err = BillingError("Simple error")
        assert err.code == "billing_error"
        assert err.details == {}

    def test_billing_config_error(self):
        """BillingConfigError should be a BillingError with config_error code."""
        err = BillingConfigError("Missing key")
        assert isinstance(err, BillingError)
        assert err.code == "config_error"

    def test_billing_api_error(self):
        """BillingAPIError should include provider and status code."""
        err = BillingAPIError(
            "API call failed",
            provider="stripe",
            status_code=400,
            details={"param": "price_id"},
        )
        assert isinstance(err, BillingError)
        assert err.code == "api_error"
        assert err.provider == "stripe"
        assert err.status_code == 400

    def test_billing_webhook_error(self):
        """BillingWebhookError should be a BillingError with webhook_error code."""
        err = BillingWebhookError("Invalid signature")
        assert isinstance(err, BillingError)
        assert err.code == "webhook_error"


# ---------------------------------------------------------------------------
# Provider Factory Tests
# ---------------------------------------------------------------------------


class TestGetProvider:
    """Test get_provider factory function."""

    @patch("django_matt.billing.providers.get_billing_config")
    def test_returns_stripe_provider(self, mock_config, stripe_config):
        """Should return StripeProvider when 'stripe' is requested."""
        mock_config.return_value = BillingConfig(
            stripe=stripe_config,
            default_provider="stripe",
        )
        from django_matt.billing.providers import get_provider

        provider = get_provider("stripe")
        assert isinstance(provider, StripeProvider)

    @patch("django_matt.billing.providers.get_billing_config")
    def test_returns_paypal_provider(self, mock_config, paypal_config):
        """Should return PayPalProvider when 'paypal' is requested."""
        mock_config.return_value = BillingConfig(
            paypal=paypal_config,
            default_provider="paypal",
        )
        from django_matt.billing.providers import get_provider

        provider = get_provider("paypal")
        assert isinstance(provider, PayPalProvider)

    @patch("django_matt.billing.providers.get_billing_config")
    def test_returns_polar_provider(self, mock_config, polar_config):
        """Should return PolarProvider when 'polar' is requested."""
        mock_config.return_value = BillingConfig(
            polar=polar_config,
            default_provider="polar",
        )
        from django_matt.billing.providers import get_provider

        provider = get_provider("polar")
        assert isinstance(provider, PolarProvider)

    @patch("django_matt.billing.providers.get_billing_config")
    def test_returns_default_provider(self, mock_config, stripe_config):
        """Should return default provider when None is passed."""
        mock_config.return_value = BillingConfig(
            stripe=stripe_config,
            default_provider="stripe",
        )
        from django_matt.billing.providers import get_provider

        provider = get_provider(None)
        assert isinstance(provider, StripeProvider)

    @patch("django_matt.billing.providers.get_billing_config")
    def test_raises_for_unconfigured_provider(self, mock_config):
        """Should raise BillingConfigError for unconfigured provider."""
        mock_config.return_value = BillingConfig()
        from django_matt.billing.providers import get_provider

        with pytest.raises(BillingConfigError, match="not configured"):
            get_provider("stripe")


# ---------------------------------------------------------------------------
# Stripe Provider Tests
# ---------------------------------------------------------------------------


class TestStripeProvider:
    """Test StripeProvider with mocked Stripe API."""

    def test_provider_name(self, stripe_config):
        """Should identify as 'stripe'."""
        provider = StripeProvider(stripe_config)
        assert provider.provider_name == "stripe"

    def test_timestamp_to_datetime(self, stripe_config):
        """Should convert Unix timestamp to datetime."""
        provider = StripeProvider(stripe_config)
        dt = provider._timestamp_to_datetime(1704067200)  # 2024-01-01 00:00:00 UTC
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

    def test_timestamp_to_datetime_none(self, stripe_config):
        """Should return None for None timestamp."""
        provider = StripeProvider(stripe_config)
        assert provider._timestamp_to_datetime(None) is None

    @patch("stripe.Customer.create")
    @patch("stripe.api_key", "sk_test_abc123")
    @pytest.mark.asyncio
    async def test_create_customer(self, mock_create, stripe_config):
        """Should create a Stripe customer."""
        mock_customer = MagicMock()
        mock_customer.id = "cus_test_new"
        mock_customer.email = "new@example.com"
        mock_customer.name = "New User"
        mock_customer.phone = None
        mock_customer.metadata = {}
        mock_customer.created = 1704067200
        mock_customer.to_dict.return_value = {"id": "cus_test_new"}
        mock_create.return_value = mock_customer

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Customer.create.return_value = mock_customer

        customer = await provider.create_customer(
            email="new@example.com",
            name="New User",
        )

        assert customer.id == "cus_test_new"
        assert customer.email == "new@example.com"
        assert customer.provider == "stripe"

    @pytest.mark.asyncio
    async def test_create_checkout_session(self, stripe_config):
        """Should create a Stripe checkout session."""
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/cs_test_123"
        mock_session.customer = "cus_123"
        mock_session.subscription = None
        mock_session.status = "open"
        mock_session.mode = "subscription"
        mock_session.success_url = "https://example.com/success"
        mock_session.cancel_url = "https://example.com/cancel"
        mock_session.metadata = {}
        mock_session.expires_at = 1704070800
        mock_session.to_dict.return_value = {"id": "cs_test_123"}

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.checkout.Session.create.return_value = mock_session

        session = await provider.create_checkout_session(
            price_id="price_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_id="cus_123",
        )

        assert session.id == "cs_test_123"
        assert session.url == "https://checkout.stripe.com/cs_test_123"
        assert session.provider == "stripe"
        assert session.mode == "subscription"

    @pytest.mark.asyncio
    async def test_get_subscription(self, stripe_config):
        """Should retrieve a Stripe subscription."""
        mock_item = MagicMock()
        mock_item.price.id = "price_123"
        mock_item.price.product = "prod_123"
        mock_item.quantity = 1

        mock_sub = MagicMock()
        mock_sub.id = "sub_test_123"
        mock_sub.customer = "cus_123"
        mock_sub.status = "active"
        mock_sub.items.data = [mock_item]
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600
        mock_sub.cancel_at_period_end = False
        mock_sub.canceled_at = None
        mock_sub.trial_start = None
        mock_sub.trial_end = None
        mock_sub.metadata = {}
        mock_sub.created = 1704067200
        mock_sub.to_dict.return_value = {"id": "sub_test_123"}

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Subscription.retrieve.return_value = mock_sub

        subscription = await provider.get_subscription("sub_test_123")

        assert subscription.id == "sub_test_123"
        assert subscription.customer_id == "cus_123"
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.price_id == "price_123"
        assert subscription.provider == "stripe"

    @pytest.mark.asyncio
    async def test_cancel_subscription_at_period_end(self, stripe_config):
        """Should cancel subscription at period end."""
        mock_item = MagicMock()
        mock_item.price.id = "price_123"
        mock_item.price.product = "prod_123"
        mock_item.quantity = 1

        mock_sub = MagicMock()
        mock_sub.id = "sub_cancel_123"
        mock_sub.customer = "cus_123"
        mock_sub.status = "active"
        mock_sub.items.data = [mock_item]
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600
        mock_sub.cancel_at_period_end = True
        mock_sub.canceled_at = 1704153600
        mock_sub.trial_start = None
        mock_sub.trial_end = None
        mock_sub.metadata = {}
        mock_sub.created = 1704067200
        mock_sub.to_dict.return_value = {"id": "sub_cancel_123"}

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Subscription.modify.return_value = mock_sub

        result = await provider.cancel_subscription("sub_cancel_123", cancel_at_period_end=True)

        provider._stripe.Subscription.modify.assert_called_once_with(
            "sub_cancel_123", cancel_at_period_end=True
        )
        assert result.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediately(self, stripe_config):
        """Should cancel subscription immediately."""
        mock_item = MagicMock()
        mock_item.price.id = "price_123"
        mock_item.price.product = "prod_123"
        mock_item.quantity = 1

        mock_sub = MagicMock()
        mock_sub.id = "sub_cancel_now"
        mock_sub.customer = "cus_123"
        mock_sub.status = "canceled"
        mock_sub.items.data = [mock_item]
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600
        mock_sub.cancel_at_period_end = False
        mock_sub.canceled_at = 1704153600
        mock_sub.trial_start = None
        mock_sub.trial_end = None
        mock_sub.metadata = {}
        mock_sub.created = 1704067200
        mock_sub.to_dict.return_value = {"id": "sub_cancel_now"}

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Subscription.cancel.return_value = mock_sub

        result = await provider.cancel_subscription("sub_cancel_now", cancel_at_period_end=False)

        provider._stripe.Subscription.cancel.assert_called_once_with("sub_cancel_now")
        assert result.status == SubscriptionStatus.CANCELED

    @pytest.mark.asyncio
    async def test_resume_subscription(self, stripe_config):
        """Should resume a canceled subscription."""
        mock_item = MagicMock()
        mock_item.price.id = "price_123"
        mock_item.price.product = "prod_123"
        mock_item.quantity = 1

        mock_sub = MagicMock()
        mock_sub.id = "sub_resume_123"
        mock_sub.customer = "cus_123"
        mock_sub.status = "active"
        mock_sub.items.data = [mock_item]
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600
        mock_sub.cancel_at_period_end = False
        mock_sub.canceled_at = None
        mock_sub.trial_start = None
        mock_sub.trial_end = None
        mock_sub.metadata = {}
        mock_sub.created = 1704067200
        mock_sub.to_dict.return_value = {"id": "sub_resume_123"}

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Subscription.modify.return_value = mock_sub

        result = await provider.resume_subscription("sub_resume_123")

        provider._stripe.Subscription.modify.assert_called_once_with(
            "sub_resume_123", cancel_at_period_end=False
        )
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_verify_webhook_valid(self, stripe_config):
        """Should verify a valid Stripe webhook signature."""
        mock_event_data_object = MagicMock()
        mock_event_data_object.to_dict.return_value = {"id": "sub_123"}

        mock_event_data = MagicMock()
        mock_event_data.object = mock_event_data_object

        mock_event = MagicMock()
        mock_event.id = "evt_123"
        mock_event.type = "customer.subscription.created"
        mock_event.data = mock_event_data
        mock_event.created = 1704067200

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Webhook.construct_event.return_value = mock_event

        event = await provider.verify_webhook(b'{"test": true}', "sig_test")

        assert event.id == "evt_123"
        assert event.type == "customer.subscription.created"
        assert event.provider == "stripe"
        assert event.data == {"id": "sub_123"}

    @pytest.mark.asyncio
    async def test_verify_webhook_invalid_signature(self, stripe_config):
        """Should raise BillingWebhookError for invalid signature."""

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Webhook.construct_event.side_effect = (
            stripe_lib.error.SignatureVerificationError("bad sig", "sig_header")
        )
        provider._stripe.error = stripe_lib.error

        with pytest.raises(BillingWebhookError, match="Invalid webhook signature"):
            await provider.verify_webhook(b'{"test": true}', "bad_sig")

    def test_normalize_webhook_type_subscription_created(self, stripe_config):
        """Should normalize Stripe subscription created event."""
        provider = StripeProvider(stripe_config)
        assert (
            provider.normalize_webhook_type("customer.subscription.created")
            == "subscription.created"
        )

    def test_normalize_webhook_type_subscription_deleted(self, stripe_config):
        """Should normalize Stripe subscription deleted to canceled."""
        provider = StripeProvider(stripe_config)
        assert (
            provider.normalize_webhook_type("customer.subscription.deleted")
            == "subscription.canceled"
        )

    def test_normalize_webhook_type_checkout_completed(self, stripe_config):
        """Should normalize Stripe checkout completed event."""
        provider = StripeProvider(stripe_config)
        assert provider.normalize_webhook_type("checkout.session.completed") == "checkout.completed"

    def test_normalize_webhook_type_unknown(self, stripe_config):
        """Should return original type for unknown events."""
        provider = StripeProvider(stripe_config)
        assert provider.normalize_webhook_type("unknown.event") == "unknown.event"

    @pytest.mark.asyncio
    async def test_create_billing_portal_session(self, stripe_config):
        """Should create a Stripe billing portal session."""
        mock_session = MagicMock()
        mock_session.url = "https://billing.stripe.com/session/portal_test"

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.billing_portal.Session.create.return_value = mock_session

        url = await provider.create_billing_portal_session(
            customer_id="cus_123",
            return_url="https://example.com/account",
        )

        assert url == "https://billing.stripe.com/session/portal_test"

    @pytest.mark.asyncio
    async def test_list_subscriptions(self, stripe_config):
        """Should list subscriptions."""
        mock_item = MagicMock()
        mock_item.price.id = "price_123"
        mock_item.price.product = "prod_123"
        mock_item.quantity = 1

        mock_sub1 = MagicMock()
        mock_sub1.id = "sub_1"
        mock_sub1.customer = "cus_123"
        mock_sub1.status = "active"
        mock_sub1.items.data = [mock_item]
        mock_sub1.current_period_start = 1704067200
        mock_sub1.current_period_end = 1706745600
        mock_sub1.cancel_at_period_end = False
        mock_sub1.canceled_at = None
        mock_sub1.trial_start = None
        mock_sub1.trial_end = None
        mock_sub1.metadata = {}
        mock_sub1.created = 1704067200
        mock_sub1.to_dict.return_value = {"id": "sub_1"}

        mock_result = MagicMock()
        mock_result.data = [mock_sub1]

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Subscription.list.return_value = mock_result

        subs = await provider.list_subscriptions(customer_id="cus_123")

        assert len(subs) == 1
        assert subs[0].id == "sub_1"
        assert subs[0].provider == "stripe"

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, stripe_config):
        """Should return None for deleted customer."""
        mock_customer = MagicMock()
        mock_customer.deleted = True

        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        provider._stripe.Customer.retrieve.return_value = mock_customer

        result = await provider.get_customer("cus_deleted")
        assert result is None

    def test_add_provider_tag(self, stripe_config):
        """Should add provider name to data objects."""
        provider = StripeProvider(stripe_config)
        data = CustomerData(id="cus_test", email="test@example.com", provider="")
        tagged = provider._add_provider_tag(data)
        assert tagged.provider == "stripe"


# ---------------------------------------------------------------------------
# PayPal Provider Tests
# ---------------------------------------------------------------------------


class TestPayPalProvider:
    """Test PayPalProvider with mocked HTTP API."""

    def test_provider_name(self, paypal_config):
        """Should identify as 'paypal'."""
        provider = PayPalProvider(paypal_config)
        assert provider.provider_name == "paypal"

    @pytest.mark.asyncio
    async def test_create_customer_uses_email_as_id(self, paypal_config):
        """PayPal should use email as customer ID since it lacks customer API."""
        provider = PayPalProvider(paypal_config)
        customer = await provider.create_customer(
            email="buyer@example.com",
            name="PayPal Buyer",
        )
        assert customer.id == "buyer@example.com"
        assert customer.email == "buyer@example.com"
        assert customer.name == "PayPal Buyer"
        assert customer.provider == "paypal"

    @pytest.mark.asyncio
    async def test_get_customer_with_email(self, paypal_config):
        """PayPal should return customer with email detection."""
        provider = PayPalProvider(paypal_config)
        customer = await provider.get_customer("buyer@example.com")
        assert customer.id == "buyer@example.com"
        assert customer.email == "buyer@example.com"

    @pytest.mark.asyncio
    async def test_get_customer_with_payer_id(self, paypal_config):
        """PayPal should return customer with empty email for payer_id."""
        provider = PayPalProvider(paypal_config)
        customer = await provider.get_customer("PAYERID123")
        assert customer.id == "PAYERID123"
        assert customer.email == ""

    @pytest.mark.asyncio
    async def test_delete_customer_always_true(self, paypal_config):
        """PayPal delete customer should always return True."""
        provider = PayPalProvider(paypal_config)
        result = await provider.delete_customer("any_id")
        assert result is True

    @pytest.mark.asyncio
    async def test_list_subscriptions_returns_empty(self, paypal_config):
        """PayPal list subscriptions should return empty list (API limitation)."""
        provider = PayPalProvider(paypal_config)
        result = await provider.list_subscriptions()
        assert result == []

    @pytest.mark.asyncio
    async def test_verify_webhook_valid_json(self, paypal_config):
        """Should parse valid PayPal webhook payload."""
        import base64
        import hashlib
        import hmac as hmac_mod
        import zlib

        payload = json.dumps(
            {
                "id": "WH-123",
                "event_type": "BILLING.SUBSCRIPTION.CREATED",
                "resource": {"id": "sub_pp_123"},
                "create_time": "2024-01-01T00:00:00Z",
            }
        ).encode()

        provider = PayPalProvider(paypal_config)
        # Build valid HMAC signature matching PayPal's verification scheme
        transmission_id = "test-transmission-id"
        transmission_time = "2024-01-01T00:00:00Z"
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        message = f"{transmission_id}|{transmission_time}|{paypal_config.webhook_id}|{crc}"
        sig_bytes = hmac_mod.new(
            paypal_config.client_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).digest()
        sig = base64.b64encode(sig_bytes).decode()
        headers = {
            "PAYPAL-TRANSMISSION-ID": transmission_id,
            "PAYPAL-TRANSMISSION-TIME": transmission_time,
            "PAYPAL-TRANSMISSION-SIG": sig,
        }
        event = await provider.verify_webhook(payload, sig, headers=headers)

        assert event.id == "WH-123"
        assert event.type == "BILLING.SUBSCRIPTION.CREATED"
        assert event.provider == "paypal"
        assert event.data == {"id": "sub_pp_123"}

    @pytest.mark.asyncio
    async def test_verify_webhook_invalid_json(self, paypal_config):
        """Should raise BillingWebhookError for invalid JSON."""
        provider = PayPalProvider(paypal_config)
        with pytest.raises(BillingWebhookError, match="Invalid JSON"):
            await provider.verify_webhook(b"not-json", "sig")

    def test_normalize_webhook_type_subscription(self, paypal_config):
        """Should normalize PayPal subscription events."""
        provider = PayPalProvider(paypal_config)
        assert (
            provider.normalize_webhook_type("BILLING.SUBSCRIPTION.CREATED")
            == "subscription.created"
        )
        assert (
            provider.normalize_webhook_type("BILLING.SUBSCRIPTION.CANCELLED")
            == "subscription.canceled"
        )

    def test_normalize_webhook_type_payment(self, paypal_config):
        """Should normalize PayPal payment events."""
        provider = PayPalProvider(paypal_config)
        assert provider.normalize_webhook_type("PAYMENT.SALE.COMPLETED") == "invoice.paid"
        assert provider.normalize_webhook_type("PAYMENT.SALE.DENIED") == "invoice.payment_failed"

    def test_normalize_webhook_type_checkout(self, paypal_config):
        """Should normalize PayPal checkout events."""
        provider = PayPalProvider(paypal_config)
        assert provider.normalize_webhook_type("CHECKOUT.ORDER.APPROVED") == "checkout.completed"

    def test_normalize_webhook_type_unknown(self, paypal_config):
        """Should lowercase and underscore unknown PayPal events."""
        provider = PayPalProvider(paypal_config)
        result = provider.normalize_webhook_type("UNKNOWN.EVENT.TYPE")
        assert result == "unknown_event_type"

    def test_parse_datetime_valid(self, paypal_config):
        """Should parse ISO datetime strings."""
        provider = PayPalProvider(paypal_config)
        dt = provider._parse_datetime("2024-01-01T00:00:00Z")
        assert dt is not None
        assert dt.year == 2024

    def test_parse_datetime_none(self, paypal_config):
        """Should return None for None input."""
        provider = PayPalProvider(paypal_config)
        assert provider._parse_datetime(None) is None

    def test_parse_datetime_invalid(self, paypal_config):
        """Should return None for invalid datetime."""
        provider = PayPalProvider(paypal_config)
        assert provider._parse_datetime("not-a-date") is None

    def test_parse_subscription(self, paypal_config):
        """Should parse PayPal subscription response."""
        provider = PayPalProvider(paypal_config)
        sub_data = {
            "id": "I-PPSUBID123",
            "status": "ACTIVE",
            "plan_id": "P-PLAN123",
            "subscriber": {"payer_id": "PAYER123"},
            "quantity": "1",
            "billing_info": {
                "next_billing_time": "2024-02-01T00:00:00Z",
            },
            "create_time": "2024-01-01T00:00:00Z",
        }
        result = provider._parse_subscription(sub_data)
        assert result.id == "I-PPSUBID123"
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.customer_id == "PAYER123"
        assert result.price_id == "P-PLAN123"
        assert result.provider == "paypal"

    def test_parse_subscription_cancelled_status(self, paypal_config):
        """Should map PayPal CANCELLED to CANCELED."""
        provider = PayPalProvider(paypal_config)
        sub_data = {
            "id": "I-CANCELLED",
            "status": "CANCELLED",
            "subscriber": {"payer_id": "PAYER123"},
            "billing_info": {},
        }
        result = provider._parse_subscription(sub_data)
        assert result.status == SubscriptionStatus.CANCELED

    def test_parse_subscription_suspended_status(self, paypal_config):
        """Should map PayPal SUSPENDED to PAUSED."""
        provider = PayPalProvider(paypal_config)
        sub_data = {
            "id": "I-SUSPENDED",
            "status": "SUSPENDED",
            "subscriber": {"payer_id": "PAYER123"},
            "billing_info": {},
        }
        result = provider._parse_subscription(sub_data)
        assert result.status == SubscriptionStatus.PAUSED


# ---------------------------------------------------------------------------
# Polar Provider Tests
# ---------------------------------------------------------------------------


class TestPolarProvider:
    """Test PolarProvider with mocked HTTP API."""

    def test_provider_name(self, polar_config):
        """Should identify as 'polar'."""
        provider = PolarProvider(polar_config)
        assert provider.provider_name == "polar"

    @pytest.mark.asyncio
    async def test_verify_webhook_valid_signature(self, polar_config):
        """Should verify a valid Polar webhook signature (HMAC-SHA256)."""
        payload = json.dumps(
            {
                "id": "polar_evt_123",
                "type": "subscription.created",
                "data": {"id": "sub_polar_123"},
                "created_at": "2024-01-01T00:00:00Z",
            }
        ).encode()

        # Compute correct HMAC signature
        expected_sig = hmac.new(
            polar_config.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        provider = PolarProvider(polar_config)
        event = await provider.verify_webhook(payload, f"sha256={expected_sig}")

        assert event.id == "polar_evt_123"
        assert event.type == "subscription.created"
        assert event.provider == "polar"
        assert event.data == {"id": "sub_polar_123"}

    @pytest.mark.asyncio
    async def test_verify_webhook_valid_signature_without_prefix(self, polar_config):
        """Should verify signature without sha256= prefix."""
        payload = json.dumps(
            {
                "id": "polar_evt_456",
                "type": "order.paid",
                "data": {},
            }
        ).encode()

        sig = hmac.new(
            polar_config.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        provider = PolarProvider(polar_config)
        event = await provider.verify_webhook(payload, sig)

        assert event.id == "polar_evt_456"

    @pytest.mark.asyncio
    async def test_verify_webhook_invalid_signature(self, polar_config):
        """Should raise BillingWebhookError for invalid signature."""
        payload = json.dumps({"id": "polar_evt_bad"}).encode()

        provider = PolarProvider(polar_config)
        with pytest.raises(BillingWebhookError, match="Invalid webhook signature"):
            await provider.verify_webhook(payload, "sha256=invalid_signature_here")

    @pytest.mark.asyncio
    async def test_verify_webhook_invalid_json(self, polar_config):
        """Should raise BillingWebhookError for invalid JSON."""
        invalid_payload = b"not-json"
        # Compute valid signature for the invalid payload
        sig = hmac.new(
            polar_config.webhook_secret.encode(),
            invalid_payload,
            hashlib.sha256,
        ).hexdigest()

        provider = PolarProvider(polar_config)
        with pytest.raises(BillingWebhookError, match="Invalid JSON"):
            await provider.verify_webhook(invalid_payload, f"sha256={sig}")

    def test_normalize_webhook_type_subscription(self, polar_config):
        """Should normalize Polar subscription events."""
        provider = PolarProvider(polar_config)
        assert provider.normalize_webhook_type("subscription.created") == "subscription.created"
        assert provider.normalize_webhook_type("subscription.canceled") == "subscription.canceled"

    def test_normalize_webhook_type_order(self, polar_config):
        """Should normalize Polar order events to invoice."""
        provider = PolarProvider(polar_config)
        assert provider.normalize_webhook_type("order.paid") == "invoice.paid"
        assert provider.normalize_webhook_type("order.created") == "invoice.created"

    def test_normalize_webhook_type_checkout(self, polar_config):
        """Should normalize Polar checkout events."""
        provider = PolarProvider(polar_config)
        assert provider.normalize_webhook_type("checkout.updated") == "checkout.completed"

    def test_parse_subscription(self, polar_config):
        """Should parse Polar subscription response."""
        provider = PolarProvider(polar_config)
        sub_data = {
            "id": "sub_polar_123",
            "customer_id": "cus_polar_456",
            "status": "active",
            "price_id": "price_polar_789",
            "product_id": "prod_polar_101",
            "current_period_start": "2024-01-01T00:00:00Z",
            "current_period_end": "2024-02-01T00:00:00Z",
            "cancel_at_period_end": False,
            "canceled_at": None,
            "trial_end": None,
            "metadata": {"key": "value"},
            "created_at": "2024-01-01T00:00:00Z",
        }
        result = provider._parse_subscription(sub_data)
        assert result.id == "sub_polar_123"
        assert result.customer_id == "cus_polar_456"
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.provider == "polar"
        assert result.metadata == {"key": "value"}

    def test_parse_subscription_canceled(self, polar_config):
        """Should parse canceled Polar subscription."""
        provider = PolarProvider(polar_config)
        sub_data = {
            "id": "sub_polar_canceled",
            "customer_id": "cus_123",
            "status": "canceled",
            "canceled_at": "2024-01-15T00:00:00Z",
            "cancel_at_period_end": True,
        }
        result = provider._parse_subscription(sub_data)
        assert result.status == SubscriptionStatus.CANCELED
        assert result.canceled_at is not None

    def test_parse_customer(self, polar_config):
        """Should parse Polar customer response."""
        provider = PolarProvider(polar_config)
        customer_data = {
            "id": "cus_polar_test",
            "email": "polar@example.com",
            "name": "Polar User",
            "metadata": {"source": "website"},
            "created_at": "2024-01-01T00:00:00Z",
        }
        result = provider._parse_customer(customer_data)
        assert result.id == "cus_polar_test"
        assert result.email == "polar@example.com"
        assert result.name == "Polar User"
        assert result.provider == "polar"

    def test_parse_product(self, polar_config):
        """Should parse Polar product response."""
        provider = PolarProvider(polar_config)
        product_data = {
            "id": "prod_polar_123",
            "name": "Dev Pro",
            "description": "For developers",
            "is_archived": False,
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
        }
        result = provider._parse_product(product_data)
        assert result.id == "prod_polar_123"
        assert result.name == "Dev Pro"
        assert result.active is True
        assert result.provider == "polar"

    def test_parse_product_archived(self, polar_config):
        """Should mark archived products as inactive."""
        provider = PolarProvider(polar_config)
        product_data = {
            "id": "prod_archived",
            "name": "Old Plan",
            "is_archived": True,
        }
        result = provider._parse_product(product_data)
        assert result.active is False

    def test_parse_price(self, polar_config):
        """Should parse Polar price data."""
        provider = PolarProvider(polar_config)
        price_data = {
            "id": "price_polar_123",
            "price_amount": 1999,
            "price_currency": "USD",
            "recurring_interval": "month",
        }
        result = provider._parse_price(price_data, product_id="prod_123")
        assert result.id == "price_polar_123"
        assert result.unit_amount == 1999
        assert result.currency == "usd"
        assert result.interval == PriceInterval.MONTH
        assert result.product_id == "prod_123"

    def test_parse_price_one_time(self, polar_config):
        """Should parse one-time price (no recurring)."""
        provider = PolarProvider(polar_config)
        price_data = {
            "id": "price_onetime",
            "price_amount": 4999,
            "price_currency": "USD",
        }
        result = provider._parse_price(price_data)
        assert result.interval == PriceInterval.ONE_TIME

    def test_parse_order_paid(self, polar_config):
        """Should parse paid Polar order."""
        provider = PolarProvider(polar_config)
        order_data = {
            "id": "order_123",
            "customer_id": "cus_123",
            "subscription_id": "sub_123",
            "amount": 2999,
            "currency": "usd",
            "paid_at": "2024-01-01T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
        }
        result = provider._parse_order(order_data)
        assert result.id == "order_123"
        assert result.status == "paid"
        assert result.amount_paid == 2999
        assert result.amount_remaining == 0

    def test_parse_order_unpaid(self, polar_config):
        """Should parse unpaid Polar order."""
        provider = PolarProvider(polar_config)
        order_data = {
            "id": "order_unpaid",
            "customer_id": "cus_123",
            "amount": 2999,
            "currency": "usd",
            "paid_at": None,
        }
        result = provider._parse_order(order_data)
        assert result.status == "open"
        assert result.amount_paid == 0
        assert result.amount_remaining == 2999


# ---------------------------------------------------------------------------
# Schema Validation Tests
# ---------------------------------------------------------------------------


class TestBillingSchemas:
    """Test Pydantic billing schemas."""

    def test_customer_create_schema(self):
        """Should validate customer creation input."""
        data = CustomerCreate(
            email="test@example.com",
            name="Test User",
            provider="stripe",
        )
        assert data.email == "test@example.com"
        assert data.provider == "stripe"

    def test_customer_create_invalid_email(self):
        """Should reject invalid email."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CustomerCreate(email="not-an-email", name="Test")

    def test_customer_update_schema_partial(self):
        """Should allow partial updates."""
        data = CustomerUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.email is None
        assert data.metadata is None

    def test_customer_response_schema(self):
        """Should serialize customer response."""
        data = CustomerResponse(
            id="cus_123",
            email="test@example.com",
            name="Test User",
            provider="stripe",
        )
        assert data.id == "cus_123"
        assert data.provider == "stripe"

    def test_checkout_create_schema(self):
        """Should validate checkout session input."""
        data = CheckoutCreate(
            price_id="price_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_email="buyer@example.com",
        )
        assert data.mode == "subscription"
        assert data.quantity == 1

    def test_subscription_create_schema(self):
        """Should validate subscription creation input."""
        data = SubscriptionCreate(
            price_id="price_123",
            customer_id="cus_123",
            quantity=2,
            trial_period_days=14,
        )
        assert data.price_id == "price_123"
        assert data.quantity == 2
        assert data.trial_period_days == 14

    def test_subscription_cancel_default(self):
        """SubscriptionCancel should default to cancel_at_period_end=True."""
        data = SubscriptionCancel()
        assert data.cancel_at_period_end is True

    def test_subscription_response_schema(self):
        """Should serialize subscription response."""
        from django_matt.billing.schemas import SubscriptionStatus as SchemaSubStatus

        data = SubscriptionResponse(
            id="sub_123",
            customer_id="cus_123",
            status=SchemaSubStatus.ACTIVE,
            provider="stripe",
        )
        assert data.id == "sub_123"
        assert data.status.value == "active"

    def test_subscription_list_response_schema(self):
        """Should serialize subscription list response."""
        from django_matt.billing.schemas import SubscriptionStatus as SchemaSubStatus

        data = SubscriptionListResponse(
            items=[
                SubscriptionResponse(
                    id="sub_1",
                    customer_id="cus_1",
                    status=SchemaSubStatus.ACTIVE,
                    provider="stripe",
                ),
            ],
            total=1,
        )
        assert len(data.items) == 1
        assert data.total == 1

    def test_product_create_schema(self):
        """Should validate product creation input."""
        data = ProductCreate(name="Enterprise Plan", description="Full features")
        assert data.name == "Enterprise Plan"

    def test_price_create_schema(self):
        """Should validate price creation input."""
        from django_matt.billing.schemas import PriceInterval as SchemaPriceInterval

        data = PriceCreate(
            product_id="prod_123",
            unit_amount=4999,
            currency="usd",
            interval=SchemaPriceInterval.YEAR,
        )
        assert data.unit_amount == 4999
        assert data.interval.value == "year"

    def test_billing_portal_create_schema(self):
        """Should validate billing portal creation input."""
        data = BillingPortalCreate(
            customer_id="cus_123",
            return_url="https://example.com/account",
        )
        assert data.customer_id == "cus_123"

    def test_invoice_response_schema(self):
        """Should serialize invoice response."""
        from django_matt.billing.schemas import InvoiceStatus

        data = InvoiceResponse(
            id="inv_123",
            customer_id="cus_123",
            provider="stripe",
            status=InvoiceStatus.PAID,
            amount_due=2999,
            amount_paid=2999,
        )
        assert data.status.value == "paid"

    def test_usage_record_create_schema(self):
        """Should validate usage record creation input."""
        data = UsageRecordCreate(
            subscription_id="sub_123",
            quantity=10,
            action="api_call",
            idempotency_key="idem_123",
        )
        assert data.quantity == 10
        assert data.action == "api_call"

    def test_billing_config_response(self):
        """Should serialize billing config response."""
        data = BillingConfigResponse(
            enabled=True,
            default_provider="stripe",
            currency="usd",
            configured_providers=["stripe", "polar"],
            stripe_publishable_key="pk_test_123",
        )
        assert data.enabled is True
        assert len(data.configured_providers) == 2

    def test_billing_error_response(self):
        """Should serialize error response."""
        data = BillingErrorResponse(
            error="Something went wrong",
            code="api_error",
            details={"param": "price_id"},
        )
        assert data.error == "Something went wrong"
        assert data.code == "api_error"


# ---------------------------------------------------------------------------
# Controller Tests
# ---------------------------------------------------------------------------


class TestBillingController:
    """Test BillingController."""

    def test_controller_attributes(self):
        """Controller should have correct prefix and tags."""
        controller = BillingController()
        assert controller.prefix == "billing"
        assert controller.tags == ["Billing"]

    def test_error_response_conversion(self):
        """Should convert BillingError to BillingErrorResponse."""
        controller = BillingController()
        err = BillingError("Test error", "test_code", {"key": "value"})
        response = controller._error_response(err)
        assert isinstance(response, BillingErrorResponse)
        assert response.error == "Test error"
        assert response.code == "test_code"
        assert response.details == {"key": "value"}

    @patch("django_matt.billing.controllers.get_billing_config")
    @pytest.mark.asyncio
    async def test_get_config(self, mock_config, rf, stripe_config):
        """Should return safe billing configuration."""
        mock_config.return_value = BillingConfig(
            enabled=True,
            default_provider="stripe",
            currency="usd",
            stripe=stripe_config,
        )

        controller = BillingController()
        request = rf.get("/billing/config")
        response = await controller.get_config(request)

        assert isinstance(response, BillingConfigResponse)
        assert response.enabled is True
        assert response.default_provider == "stripe"
        assert response.currency == "usd"
        assert response.stripe_publishable_key == "pk_test_abc123"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_checkout_success(self, mock_get_provider, rf):
        """Should create a checkout session successfully."""
        mock_provider = AsyncMock()
        mock_provider.create_checkout_session.return_value = CheckoutSessionData(
            id="cs_123",
            url="https://checkout.example.com/cs_123",
            customer_id="cus_123",
            status="open",
            mode="subscription",
            provider="stripe",
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/checkout")
        data = CheckoutCreate(
            price_id="price_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        response = await controller.create_checkout(request, data)

        assert isinstance(response, CheckoutResponse)
        assert response.id == "cs_123"
        assert response.url == "https://checkout.example.com/cs_123"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_checkout_billing_error(self, mock_get_provider, rf):
        """Should return error response on billing error."""
        mock_provider = AsyncMock()
        mock_provider.create_checkout_session.side_effect = BillingAPIError(
            "Invalid price ID",
            provider="stripe",
            status_code=400,
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/checkout")
        data = CheckoutCreate(
            price_id="price_invalid",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        response = await controller.create_checkout(request, data)

        assert isinstance(response, BillingErrorResponse)
        assert "Invalid price ID" in response.error

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_customer_success(self, mock_get_provider, rf):
        """Should create a customer successfully."""
        mock_provider = AsyncMock()
        mock_provider.create_customer.return_value = CustomerData(
            id="cus_new",
            email="new@example.com",
            name="New Customer",
            provider="stripe",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/customers")
        data = CustomerCreate(email="new@example.com", name="New Customer")
        response = await controller.create_customer(request, data)

        assert isinstance(response, CustomerResponse)
        assert response.id == "cus_new"
        assert response.email == "new@example.com"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, mock_get_provider, rf):
        """Should return error for non-existent customer."""
        mock_provider = AsyncMock()
        mock_provider.get_customer.return_value = None
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.get("/billing/customers/cus_nonexistent")
        response = await controller.get_customer(request, "cus_nonexistent")

        assert isinstance(response, BillingErrorResponse)
        assert response.code == "not_found"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_subscription_success(self, mock_get_provider, rf):
        """Should create a subscription successfully."""
        mock_provider = AsyncMock()
        mock_provider.create_subscription.return_value = SubscriptionData(
            id="sub_new",
            customer_id="cus_123",
            status=SubscriptionStatus.ACTIVE,
            price_id="price_123",
            provider="stripe",
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/subscriptions")
        data = SubscriptionCreate(
            price_id="price_123",
            customer_id="cus_123",
        )
        response = await controller.create_subscription(request, data)

        assert isinstance(response, SubscriptionResponse)
        assert response.id == "sub_new"
        assert response.status.value == "active"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_subscription_no_customer(self, mock_get_provider, rf):
        """Should return validation error when no customer_id or email provided."""
        mock_get_provider.return_value = AsyncMock()

        controller = BillingController()
        request = rf.post("/billing/subscriptions")
        data = SubscriptionCreate(price_id="price_123")
        response = await controller.create_subscription(request, data)

        assert isinstance(response, BillingErrorResponse)
        assert response.code == "validation_error"
        assert "customer_id or customer_email" in response.error

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_subscription_with_email(self, mock_get_provider, rf):
        """Should get_or_create customer when email provided."""
        mock_provider = AsyncMock()
        mock_provider.get_or_create_customer.return_value = (
            CustomerData(id="cus_auto", email="auto@example.com", provider="stripe"),
            True,
        )
        mock_provider.create_subscription.return_value = SubscriptionData(
            id="sub_auto",
            customer_id="cus_auto",
            status=SubscriptionStatus.ACTIVE,
            provider="stripe",
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/subscriptions")
        data = SubscriptionCreate(
            price_id="price_123",
            customer_email="auto@example.com",
        )
        response = await controller.create_subscription(request, data)

        assert isinstance(response, SubscriptionResponse)
        assert response.id == "sub_auto"
        mock_provider.get_or_create_customer.assert_called_once()

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_cancel_subscription_success(self, mock_get_provider, rf):
        """Should cancel a subscription successfully."""
        mock_provider = AsyncMock()
        mock_provider.cancel_subscription.return_value = SubscriptionData(
            id="sub_canceling",
            customer_id="cus_123",
            status=SubscriptionStatus.ACTIVE,
            cancel_at_period_end=True,
            provider="stripe",
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/subscriptions/sub_canceling/cancel")
        data = SubscriptionCancel(cancel_at_period_end=True)
        response = await controller.cancel_subscription(request, "sub_canceling", data)

        assert isinstance(response, SubscriptionResponse)
        assert response.cancel_at_period_end is True

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_resume_subscription_success(self, mock_get_provider, rf):
        """Should resume a subscription successfully."""
        mock_provider = AsyncMock()
        mock_provider.resume_subscription.return_value = SubscriptionData(
            id="sub_resumed",
            customer_id="cus_123",
            status=SubscriptionStatus.ACTIVE,
            cancel_at_period_end=False,
            provider="stripe",
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.get("/billing/subscriptions/sub_resumed/resume")
        response = await controller.resume_subscription(request, "sub_resumed")

        assert isinstance(response, SubscriptionResponse)
        assert response.cancel_at_period_end is False

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_portal_session_success(self, mock_get_provider, rf):
        """Should create a billing portal session."""
        mock_provider = AsyncMock()
        mock_provider.create_billing_portal_session.return_value = (
            "https://billing.example.com/portal"
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/portal")
        data = BillingPortalCreate(
            customer_id="cus_123",
            return_url="https://example.com/account",
        )
        response = await controller.create_portal_session(request, data)

        assert isinstance(response, BillingPortalResponse)
        assert response.url == "https://billing.example.com/portal"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_create_portal_not_supported(self, mock_get_provider, rf):
        """Should return error when provider doesn't support portal."""
        mock_provider = AsyncMock()
        mock_provider.create_billing_portal_session.side_effect = NotImplementedError(
            "Not supported"
        )
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.post("/billing/portal")
        data = BillingPortalCreate(
            customer_id="cus_123",
            return_url="https://example.com/account",
        )
        response = await controller.create_portal_session(request, data)

        assert isinstance(response, BillingErrorResponse)
        assert response.code == "not_supported"

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_list_subscriptions(self, mock_get_provider, rf):
        """Should list subscriptions."""
        mock_provider = AsyncMock()
        mock_provider.list_subscriptions.return_value = [
            SubscriptionData(
                id="sub_1",
                customer_id="cus_123",
                status=SubscriptionStatus.ACTIVE,
                provider="stripe",
            ),
            SubscriptionData(
                id="sub_2",
                customer_id="cus_123",
                status=SubscriptionStatus.CANCELED,
                provider="stripe",
            ),
        ]
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.get("/billing/subscriptions?customer_id=cus_123")
        response = await controller.list_subscriptions(request, customer_id="cus_123")

        assert isinstance(response, SubscriptionListResponse)
        assert response.total == 2
        assert len(response.items) == 2

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_list_invoices(self, mock_get_provider, rf):
        """Should list invoices."""
        mock_provider = AsyncMock()
        mock_provider.list_invoices.return_value = [
            InvoiceData(
                id="inv_1",
                customer_id="cus_123",
                status="paid",
                amount_due=2999,
                amount_paid=2999,
                provider="stripe",
            ),
        ]
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.get("/billing/invoices")
        response = await controller.list_invoices(request, customer_id="cus_123")

        assert isinstance(response, InvoiceListResponse)
        assert response.total == 1

    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, mock_get_provider, rf):
        """Should return error for non-existent invoice."""
        mock_provider = AsyncMock()
        mock_provider.get_invoice.return_value = None
        mock_get_provider.return_value = mock_provider

        controller = BillingController()
        request = rf.get("/billing/invoices/inv_nonexistent")
        response = await controller.get_invoice(request, "inv_nonexistent")

        assert isinstance(response, BillingErrorResponse)
        assert response.code == "not_found"


class TestWebhookController:
    """Test WebhookController."""

    def test_controller_attributes(self):
        """Controller should have correct prefix and tags."""
        controller = WebhookController()
        assert controller.prefix == "billing/webhooks"
        assert controller.tags == ["Billing Webhooks"]

    @pytest.mark.django_db
    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_handle_stripe_webhook_success(self, mock_get_provider, rf):
        """Should process a valid Stripe webhook and return 200."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_stripe_123",
                type="customer.subscription.created",
                provider="stripe",
                data={"id": "sub_123"},
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.created"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_stripe_123"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=sig"

        response = await controller.handle_stripe_webhook(request)

        assert response.status_code == 200

    @pytest.mark.django_db
    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_handle_webhook_missing_signature(self, mock_get_provider, rf):
        """Should return 400 for missing webhook signature."""
        mock_get_provider.return_value = MagicMock()

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_123"}',
            content_type="application/json",
        )
        # No signature header

        response = await controller._handle_webhook(request, "stripe", "stripe-signature")

        assert response.status_code == 400

    @pytest.mark.django_db
    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_signature(self, mock_get_provider, rf):
        """Should return 400 for invalid webhook signature."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            side_effect=BillingWebhookError("Invalid signature")
        )
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_123"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "bad_sig"

        response = await controller._handle_webhook(request, "stripe", "stripe-signature")

        assert response.status_code == 400

    @pytest.mark.django_db
    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_handle_webhook_idempotency(self, mock_get_provider, rf):
        """Should not re-process already-processed webhook events."""
        # Create an already-processed event
        existing_event = await WebhookEventModel.objects.acreate(
            provider="stripe",
            provider_event_id="evt_already_processed",
            event_type="invoice.paid",
            payload={"id": "inv_123"},
            processed=True,
            processed_at=timezone.now(),
        )

        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_already_processed",
                type="invoice.paid",
                provider="stripe",
                data={"id": "inv_123"},
            )
        )
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_already_processed"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "sig_test"

        response = await controller._handle_webhook(request, "stripe", "stripe-signature")

        # Should return 200 without re-processing
        assert response.status_code == 200

    @pytest.mark.django_db
    @patch("django_matt.billing.controllers.get_provider")
    @pytest.mark.asyncio
    async def test_handle_webhook_processing_error(self, mock_get_provider, rf):
        """Should return 200 even when processing fails (acknowledge receipt)."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_proc_fail",
                type="unknown.event.type",
                provider="stripe",
                data={},
            )
        )
        mock_provider.normalize_webhook_type.side_effect = Exception("Processing bug")
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_proc_fail"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "sig_test"

        response = await controller._handle_webhook(request, "stripe", "stripe-signature")

        # Should still return 200 to acknowledge receipt
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Subscription Lifecycle Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSubscriptionLifecycle:
    """Test subscription state transitions."""

    def test_new_subscription_is_active(self, subscription):
        """New subscription should be active."""
        assert subscription.status == Subscription.Status.ACTIVE
        assert subscription.is_active is True
        assert subscription.will_cancel is False

    def test_subscription_enters_trial(self, billing_customer, billing_price):
        """Should support trialing state."""
        now = timezone.now()
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_trial",
            status=Subscription.Status.TRIALING,
            trial_start=now,
            trial_end=now + timedelta(days=14),
        )
        assert sub.is_active is True
        assert sub.is_trialing is True

    def test_subscription_trial_to_active(self, billing_customer, billing_price):
        """Subscription should transition from trialing to active."""
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_trial_to_active",
            status=Subscription.Status.TRIALING,
        )
        assert sub.is_trialing is True

        sub.status = Subscription.Status.ACTIVE
        sub.save()
        sub.refresh_from_db()
        assert sub.is_active is True
        assert sub.is_trialing is False

    def test_subscription_cancel_at_period_end(self, subscription):
        """Subscription cancel_at_period_end should preserve active status."""
        subscription.cancel_at_period_end = True
        subscription.canceled_at = timezone.now()
        subscription.save()
        subscription.refresh_from_db()

        assert subscription.is_active is True
        assert subscription.will_cancel is True

    def test_subscription_immediate_cancel(self, subscription):
        """Immediate cancellation should change status."""
        subscription.status = Subscription.Status.CANCELED
        subscription.canceled_at = timezone.now()
        subscription.save()
        subscription.refresh_from_db()

        assert subscription.is_active is False
        assert subscription.will_cancel is False

    def test_subscription_past_due(self, subscription):
        """Past due subscription should not be active."""
        subscription.status = Subscription.Status.PAST_DUE
        subscription.save()
        subscription.refresh_from_db()

        assert subscription.is_active is False

    def test_subscription_unpaid(self, subscription):
        """Unpaid subscription should not be active."""
        subscription.status = Subscription.Status.UNPAID
        subscription.save()
        subscription.refresh_from_db()

        assert subscription.is_active is False

    def test_subscription_paused(self, subscription):
        """Paused subscription should not be active."""
        subscription.status = Subscription.Status.PAUSED
        subscription.save()
        subscription.refresh_from_db()

        assert subscription.is_active is False

    def test_subscription_resume_after_cancel_at_period_end(self, subscription):
        """Resuming should clear cancel_at_period_end."""
        subscription.cancel_at_period_end = True
        subscription.save()
        assert subscription.will_cancel is True

        subscription.cancel_at_period_end = False
        subscription.save()
        subscription.refresh_from_db()

        assert subscription.will_cancel is False
        assert subscription.is_active is True

    def test_subscription_with_different_prices(self, billing_customer):
        """Should support changing prices (plan upgrade/downgrade)."""
        product = BillingProduct.objects.create(
            provider="stripe",
            provider_product_id="prod_upgrade",
            name="Upgrade Plan",
        )
        basic_price = BillingPrice.objects.create(
            provider="stripe",
            provider_price_id="price_basic",
            product=product,
            unit_amount=999,
            interval=BillingPrice.Interval.MONTH,
        )
        pro_price = BillingPrice.objects.create(
            provider="stripe",
            provider_price_id="price_pro_upgrade",
            product=product,
            unit_amount=2999,
            interval=BillingPrice.Interval.MONTH,
        )

        sub = Subscription.objects.create(
            customer=billing_customer,
            price=basic_price,
            provider="stripe",
            provider_subscription_id="sub_upgrade",
            status=Subscription.Status.ACTIVE,
        )
        assert sub.price == basic_price

        sub.price = pro_price
        sub.save()
        sub.refresh_from_db()
        assert sub.price == pro_price

    def test_full_lifecycle(self, billing_customer, billing_price):
        """Test full subscription lifecycle: create -> trial -> active -> cancel -> canceled."""
        now = timezone.now()

        # Step 1: Create with trial
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_lifecycle",
            status=Subscription.Status.TRIALING,
            trial_start=now,
            trial_end=now + timedelta(days=14),
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
        )
        assert sub.is_trialing is True
        assert sub.is_active is True

        # Step 2: Trial ends, becomes active
        sub.status = Subscription.Status.ACTIVE
        sub.current_period_start = now + timedelta(days=14)
        sub.current_period_end = now + timedelta(days=44)
        sub.save()
        assert sub.is_active is True
        assert sub.is_trialing is False

        # Step 3: User requests cancellation at period end
        sub.cancel_at_period_end = True
        sub.canceled_at = now + timedelta(days=20)
        sub.save()
        assert sub.will_cancel is True
        assert sub.is_active is True

        # Step 4: User changes mind, resumes
        sub.cancel_at_period_end = False
        sub.save()
        assert sub.will_cancel is False
        assert sub.is_active is True

        # Step 5: User cancels again at period end, period ends
        sub.cancel_at_period_end = True
        sub.save()
        assert sub.will_cancel is True

        # Step 6: Period ends, subscription becomes canceled
        sub.status = Subscription.Status.CANCELED
        sub.save()
        assert sub.is_active is False
        assert sub.will_cancel is False


# ---------------------------------------------------------------------------
# Provider-Specific Parsing Tests
# ---------------------------------------------------------------------------


class TestStripeSubscriptionStatusMapping:
    """Test all Stripe subscription status mappings."""

    @pytest.fixture
    def provider(self, stripe_config):
        provider = StripeProvider(stripe_config)
        provider._stripe = MagicMock()
        return provider

    def _make_mock_sub(self, status, **kwargs):
        mock_item = MagicMock()
        mock_item.price.id = "price_123"
        mock_item.price.product = "prod_123"
        mock_item.quantity = 1

        mock_sub = MagicMock()
        mock_sub.id = f"sub_{status}"
        mock_sub.customer = "cus_123"
        mock_sub.status = status
        mock_sub.items.data = [mock_item]
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600
        mock_sub.cancel_at_period_end = kwargs.get("cancel_at_period_end", False)
        mock_sub.canceled_at = kwargs.get("canceled_at")
        mock_sub.trial_start = kwargs.get("trial_start")
        mock_sub.trial_end = kwargs.get("trial_end")
        mock_sub.metadata = {}
        mock_sub.created = 1704067200
        mock_sub.to_dict.return_value = {"id": f"sub_{status}"}
        return mock_sub

    def test_active_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("active"))
        assert result.status == SubscriptionStatus.ACTIVE

    def test_canceled_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("canceled"))
        assert result.status == SubscriptionStatus.CANCELED

    def test_incomplete_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("incomplete"))
        assert result.status == SubscriptionStatus.INCOMPLETE

    def test_incomplete_expired_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("incomplete_expired"))
        assert result.status == SubscriptionStatus.INCOMPLETE_EXPIRED

    def test_past_due_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("past_due"))
        assert result.status == SubscriptionStatus.PAST_DUE

    def test_paused_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("paused"))
        assert result.status == SubscriptionStatus.PAUSED

    def test_trialing_status(self, provider):
        result = provider._parse_subscription(
            self._make_mock_sub(
                "trialing",
                trial_start=1704067200,
                trial_end=1705276800,
            )
        )
        assert result.status == SubscriptionStatus.TRIALING
        assert result.trial_start is not None
        assert result.trial_end is not None

    def test_unpaid_status(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("unpaid"))
        assert result.status == SubscriptionStatus.UNPAID

    def test_unknown_status_defaults_to_active(self, provider):
        result = provider._parse_subscription(self._make_mock_sub("brand_new_status"))
        assert result.status == SubscriptionStatus.ACTIVE


# ---------------------------------------------------------------------------
# Integration-style Tests (no real external calls)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBillingModelRelationships:
    """Test relationships between billing models."""

    def test_customer_subscriptions(self, billing_customer, billing_price):
        """Customer should have subscriptions."""
        sub1 = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_rel_1",
            status=Subscription.Status.ACTIVE,
        )
        sub2 = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_rel_2",
            status=Subscription.Status.CANCELED,
        )
        assert billing_customer.subscriptions.count() == 2
        assert set(billing_customer.subscriptions.values_list("id", flat=True)) == {
            sub1.pk,
            sub2.pk,
        }

    def test_customer_invoices(self, billing_customer):
        """Customer should have invoices."""
        inv = Invoice.objects.create(
            customer=billing_customer,
            provider="stripe",
            provider_invoice_id="inv_rel_1",
        )
        assert billing_customer.invoices.count() == 1

    def test_subscription_invoices(self, subscription, billing_customer):
        """Subscription should have invoices."""
        inv = Invoice.objects.create(
            customer=billing_customer,
            subscription=subscription,
            provider="stripe",
            provider_invoice_id="inv_sub_1",
        )
        assert subscription.invoices.count() == 1
        assert subscription.invoices.first() == inv

    def test_subscription_usage_records(self, subscription):
        """Subscription should have usage records."""
        UsageRecord.objects.create(
            subscription=subscription,
            quantity=5,
            action="api_call",
        )
        UsageRecord.objects.create(
            subscription=subscription,
            quantity=10,
            action="storage",
        )
        assert subscription.usage_records.count() == 2

    def test_product_prices(self, billing_product):
        """Product should have prices."""
        BillingPrice.objects.create(
            provider="stripe",
            provider_price_id="price_monthly",
            product=billing_product,
            unit_amount=999,
            interval=BillingPrice.Interval.MONTH,
        )
        BillingPrice.objects.create(
            provider="stripe",
            provider_price_id="price_yearly",
            product=billing_product,
            unit_amount=9999,
            interval=BillingPrice.Interval.YEAR,
        )
        assert billing_product.prices.count() == 2

    def test_cascade_delete_customer(self, billing_customer, subscription, invoice):
        """Deleting customer should cascade to subscriptions and invoices."""
        customer_pk = billing_customer.pk
        billing_customer.delete()

        assert Subscription.objects.filter(customer_id=customer_pk).count() == 0
        assert Invoice.objects.filter(customer_id=customer_pk).count() == 0

    def test_set_null_on_price_delete(self, subscription, billing_price):
        """Deleting price should SET_NULL on subscriptions."""
        billing_price.delete()
        subscription.refresh_from_db()
        assert subscription.price is None

    def test_set_null_on_subscription_delete(self, invoice, subscription):
        """Deleting subscription should SET_NULL on invoices."""
        subscription.delete()
        invoice.refresh_from_db()
        assert invoice.subscription is None


# ---------------------------------------------------------------------------
# Webhook Lifecycle Sync Tests (Phase 05-01)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestWebhookLifecycleSync:
    """End-to-end webhook-to-DB-sync tests for all three providers."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_mock_provider(self, webhook_event_obj):
        """Return a MagicMock provider that verify_webhook returns the given event."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(return_value=webhook_event_obj)
        mock_provider.normalize_webhook_type.return_value = "subscription.created"
        return mock_provider

    # ------------------------------------------------------------------
    # amark_processed
    # ------------------------------------------------------------------

    async def test_amark_processed_async(self):
        """amark_processed() should update processed=True and processed_at without SynchronousOnlyOperation."""
        event = await WebhookEventModel.objects.acreate(
            provider="stripe",
            provider_event_id="evt_amark_test",
            event_type="customer.subscription.created",
            payload={"id": "sub_test"},
        )
        assert event.processed is False
        assert event.processed_at is None

        await event.amark_processed()

        await event.arefresh_from_db()
        assert event.processed is True
        assert event.processed_at is not None

    async def test_amark_processed_with_error(self):
        """amark_processed(error=...) should store the error string."""
        event = await WebhookEventModel.objects.acreate(
            provider="stripe",
            provider_event_id="evt_amark_error_test",
            event_type="invoice.paid",
            payload={"id": "inv_test"},
        )
        await event.amark_processed(error="something went wrong")

        await event.arefresh_from_db()
        assert event.processed is True
        assert event.processing_error == "something went wrong"

    # ------------------------------------------------------------------
    # Mock factory signature validity
    # ------------------------------------------------------------------

    async def test_mock_stripe_event_valid_signature(self, stripe_config):
        """mock_stripe_event() output should pass StripeProvider.verify_webhook()."""
        from django_matt.billing.testing import mock_stripe_event

        secret = stripe_config.webhook_secret
        payload, sig_header = mock_stripe_event(
            "customer.subscription.created",
            data={"id": "sub_123", "status": "active", "customer": "cus_stripe_123"},
            secret=secret,
        )

        provider = StripeProvider(stripe_config)
        event = await provider.verify_webhook(payload, sig_header)
        assert event.type == "customer.subscription.created"
        assert event.provider == "stripe"

    async def test_mock_polar_event_valid_signature(self, polar_config):
        """mock_polar_event() output should pass PolarProvider.verify_webhook()."""
        from django_matt.billing.testing import mock_polar_event

        secret = polar_config.webhook_secret
        payload, sig_header = mock_polar_event(
            "subscription.created",
            data={"id": "sub_polar_123", "customer_id": "cus_polar_123"},
            secret=secret,
        )

        provider = PolarProvider(polar_config)
        event = await provider.verify_webhook(payload, sig_header)
        assert event.provider == "polar"

    async def test_mock_paypal_event_valid_signature(self, paypal_config):
        """mock_paypal_event() output should pass PayPalProvider.verify_webhook()."""
        from django_matt.billing.testing import mock_paypal_event

        payload, headers = mock_paypal_event(
            "BILLING.SUBSCRIPTION.CREATED",
            data={"id": "I-PAYPAL123"},
            client_secret=paypal_config.client_secret,
            webhook_id=paypal_config.webhook_id,
        )

        provider = PayPalProvider(paypal_config)
        # PayPal verify_webhook needs headers kwarg
        event = await provider.verify_webhook(
            payload, headers.get("PAYPAL-TRANSMISSION-SIG", ""), headers=headers
        )
        assert event.provider == "paypal"

    # ------------------------------------------------------------------
    # Stripe webhook creates Subscription in DB (BILL-01)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_stripe_webhook_creates_subscription(
        self, mock_get_provider, billing_customer, rf
    ):
        """Stripe subscription.created webhook should create a local Subscription record."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_stripe_create",
                type="customer.subscription.created",
                provider="stripe",
                data={
                    "id": "sub_stripe_new",
                    "status": "active",
                    "customer": billing_customer.stripe_customer_id,
                    "current_period_start": 1700000000,
                    "current_period_end": 1702592000,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.created"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_stripe_create"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=1,v1=sig"

        response = await controller.handle_stripe_webhook(request)
        assert response.status_code == 200

        # Subscription must exist in DB
        assert await Subscription.objects.filter(
            provider="stripe", provider_subscription_id="sub_stripe_new"
        ).aexists()

        sub = await Subscription.objects.aget(
            provider="stripe", provider_subscription_id="sub_stripe_new"
        )
        assert sub.status == Subscription.Status.ACTIVE

    # ------------------------------------------------------------------
    # Subscription.updated changes status (BILL-04)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_subscription_updated_changes_status(
        self, mock_get_provider, billing_customer, billing_price, rf
    ):
        """subscription.updated webhook should update existing subscription status."""
        # Pre-create a subscription
        sub = await Subscription.objects.acreate(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_to_update",
            status=Subscription.Status.ACTIVE,
        )

        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_stripe_update",
                type="customer.subscription.updated",
                provider="stripe",
                data={
                    "id": "sub_to_update",
                    "status": "past_due",
                    "customer": billing_customer.stripe_customer_id,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.updated"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_stripe_update"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=1,v1=sig"

        response = await controller.handle_stripe_webhook(request)
        assert response.status_code == 200

        await sub.arefresh_from_db()
        assert sub.status == "past_due"

    # ------------------------------------------------------------------
    # Subscription.canceled sets status + canceled_at (BILL-04)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_subscription_canceled_sets_canceled_at(
        self, mock_get_provider, billing_customer, billing_price, rf
    ):
        """subscription.canceled webhook should set status=canceled and canceled_at."""
        sub = await Subscription.objects.acreate(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_to_cancel",
            status=Subscription.Status.ACTIVE,
        )

        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_stripe_cancel",
                type="customer.subscription.deleted",
                provider="stripe",
                data={
                    "id": "sub_to_cancel",
                    "status": "canceled",
                    "customer": billing_customer.stripe_customer_id,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.canceled"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_stripe_cancel"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=1,v1=sig"

        response = await controller.handle_stripe_webhook(request)
        assert response.status_code == 200

        await sub.arefresh_from_db()
        assert sub.status == Subscription.Status.CANCELED
        assert sub.canceled_at is not None

    # ------------------------------------------------------------------
    # Duplicate webhook skipped (BILL-05)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_duplicate_webhook_skipped(self, mock_get_provider, billing_customer, rf):
        """Same webhook event_id sent twice should be idempotent — only one Subscription row."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_dup_test",
                type="customer.subscription.created",
                provider="stripe",
                data={
                    "id": "sub_dup",
                    "status": "active",
                    "customer": billing_customer.stripe_customer_id,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.created"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_dup_test"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=1,v1=sig"

        # First call
        r1 = await controller.handle_stripe_webhook(request)
        assert r1.status_code == 200

        # Second call with same event_id
        r2 = await controller.handle_stripe_webhook(request)
        assert r2.status_code == 200

        # Only ONE WebhookEvent and ONE Subscription should exist
        assert (
            await WebhookEventModel.objects.filter(
                provider="stripe", provider_event_id="evt_dup_test"
            ).acount()
            == 1
        )
        assert (
            await Subscription.objects.filter(
                provider="stripe", provider_subscription_id="sub_dup"
            ).acount()
            == 1
        )

    # ------------------------------------------------------------------
    # Invalid signature returns 400 (BILL-05)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_invalid_signature_returns_400(self, mock_get_provider, rf):
        """Webhook with invalid signature should return 400."""
        from django_matt.billing.providers.base import BillingWebhookError as BWE

        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(side_effect=BWE("Bad signature"))
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id": "evt_bad"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "bad_signature"

        response = await controller.handle_stripe_webhook(request)
        assert response.status_code == 400

    # ------------------------------------------------------------------
    # Django signal fires after subscription sync
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_subscription_synced_signal_fires(self, mock_get_provider, billing_customer, rf):
        """subscription_synced signal should fire with correct kwargs after webhook sync."""
        from django_matt.billing.signals import subscription_synced

        fired_kwargs: dict = {}

        def on_synced(sender, **kwargs):
            fired_kwargs.update(kwargs)

        subscription_synced.connect(on_synced)
        try:
            mock_provider = MagicMock()
            mock_provider.verify_webhook = AsyncMock(
                return_value=WebhookEvent(
                    id="evt_signal_test",
                    type="customer.subscription.created",
                    provider="stripe",
                    data={
                        "id": "sub_signal_test",
                        "status": "active",
                        "customer": billing_customer.stripe_customer_id,
                    },
                )
            )
            mock_provider.normalize_webhook_type.return_value = "subscription.created"
            mock_get_provider.return_value = mock_provider

            controller = WebhookController()
            request = rf.post(
                "/billing/webhooks/stripe",
                data=b'{"id": "evt_signal_test"}',
                content_type="application/json",
            )
            request.META["HTTP_STRIPE_SIGNATURE"] = "t=1,v1=sig"

            response = await controller.handle_stripe_webhook(request)
            assert response.status_code == 200
        finally:
            subscription_synced.disconnect(on_synced)

        assert "subscription" in fired_kwargs
        assert fired_kwargs.get("event_type") == "created"
        assert fired_kwargs.get("provider") == "stripe"

    # ------------------------------------------------------------------
    # PayPal webhook syncs subscription (BILL-02)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_paypal_webhook_creates_subscription(
        self, mock_get_provider, billing_customer, rf
    ):
        """PayPal subscription.created webhook should create a local Subscription record."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_paypal_create",
                type="BILLING.SUBSCRIPTION.CREATED",
                provider="paypal",
                data={
                    "id": "I-PAYPAL_SUB",
                    "status": "ACTIVE",
                    "subscriber": {"payer_id": billing_customer.paypal_customer_id},
                    "customer": billing_customer.paypal_customer_id,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.created"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/paypal",
            data=b'{"id": "evt_paypal_create"}',
            content_type="application/json",
        )
        request.META["HTTP_PAYPAL_TRANSMISSION_SIG"] = "test_sig"

        response = await controller.handle_paypal_webhook(request)
        assert response.status_code == 200

        assert await Subscription.objects.filter(
            provider="paypal", provider_subscription_id="I-PAYPAL_SUB"
        ).aexists()

    # ------------------------------------------------------------------
    # Polar webhook creates subscription (BILL-03)
    # ------------------------------------------------------------------

    @patch("django_matt.billing.controllers.get_provider")
    async def test_polar_webhook_creates_subscription(
        self, mock_get_provider, billing_customer, rf
    ):
        """Polar subscription.created webhook should create a local Subscription record."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_polar_create",
                type="subscription.created",
                provider="polar",
                data={
                    "id": "sub_polar_new",
                    "status": "active",
                    "customer": billing_customer.polar_customer_id,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "subscription.created"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/polar",
            data=b'{"id": "evt_polar_create"}',
            content_type="application/json",
        )
        request.META["HTTP_X_POLAR_SIGNATURE"] = "sha256=test_sig"

        response = await controller.handle_polar_webhook(request)
        assert response.status_code == 200

        assert await Subscription.objects.filter(
            provider="polar", provider_subscription_id="sub_polar_new"
        ).aexists()
