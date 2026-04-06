"""
Tests for django-matt billing module — Stripe Connect, models, controllers, and edge cases.

Covers areas not in test_billing.py:
- ConnectedAccount, Transfer, ApplicationFee models
- ConnectController endpoints
- Stripe Connect provider methods (mocked)
- Connect-specific schemas
- _parse_timestamp controller helper
- Invoice webhook DB sync path
- PayPal httpx client/request flow
- Testing helpers as standalone units
- Edge cases: expired subscriptions, webhook replay, concurrent events
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest

stripe_lib = pytest.importorskip("stripe", reason="stripe package required")

from django_matt.billing.config import (
    BillingConfig,
    PayPalConfig,
    PolarConfig,
    StripeConfig,
)
from django_matt.billing.connect_controller import ConnectController, _get_stripe_provider
from django_matt.billing.controllers import (
    BillingController,
    WebhookController,
    _parse_timestamp,
)
from django_matt.billing.models import (
    ApplicationFee,
    BillingCustomer,
    BillingPrice,
    BillingProduct,
    ConnectedAccount,
    Invoice,
    Subscription,
    Transfer,
    UsageRecord,
)
from django_matt.billing.models import WebhookEvent as WebhookEventModel
from django_matt.billing.providers.base import (
    AccountLinkData,
    BillingAPIError,
    BillingError,
    BillingWebhookError,
    CheckoutSessionData,
    ConnectAccountType,
    ConnectedAccountData,
    CustomerData,
    InvoiceData,
    OAuthLinkData,
    PriceData,
    PriceInterval,
    SubscriptionData,
    SubscriptionStatus,
    TransferData,
    WebhookEvent,
)
from django_matt.billing.providers.paypal import PayPalProvider
from django_matt.billing.providers.stripe import StripeProvider
from django_matt.billing.schemas import (
    AccountLinkCreate,
    AccountLinkResponse,
    BillingErrorResponse,
    ConnectedAccountCreate,
    ConnectedAccountListResponse,
    ConnectedAccountResponse,
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    PaymentIntentWithFeeCreate,
    TransferCreate,
    TransferResponse,
    TransferReversalRequest,
)
from django_matt.billing.schemas import (
    ConnectAccountType as SchemaConnectAccountType,
)
from django_matt.billing.testing import (
    mock_paypal_event,
    mock_polar_event,
    mock_stripe_event,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def stripe_config():
    return StripeConfig(
        secret_key="sk_test_abc123",
        publishable_key="pk_test_abc123",
        webhook_secret="whsec_test_abc123",
        api_version="2024-12-18.acacia",
        connect_client_id="ca_test_abc123",
        connect_webhook_secret="whsec_connect_test",
        connect_default_account_type="standard",
        connect_application_fee_percent=10.0,
    )


@pytest.fixture
def paypal_config():
    return PayPalConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        webhook_id="test_webhook_id",
        mode="sandbox",
    )


@pytest.fixture
def polar_config():
    return PolarConfig(
        access_token="test_access_token",
        organization_id="test_org_id",
        webhook_secret="test_webhook_secret",
        sandbox=True,
    )


@pytest.fixture
def billing_config_full(stripe_config, paypal_config, polar_config):
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
    return User.objects.create_user(
        username="connectuser",
        email="connect@example.com",
        password="testpass123",
    )


@pytest.fixture
@pytest.mark.django_db
def billing_customer(test_user):
    return BillingCustomer.objects.create(
        user=test_user,
        stripe_customer_id="cus_stripe_connect",
        paypal_customer_id="paypal_connect@example.com",
        polar_customer_id="cus_polar_connect",
        default_provider="stripe",
    )


@pytest.fixture
@pytest.mark.django_db
def connected_account(test_user):
    return ConnectedAccount.objects.create(
        user=test_user,
        stripe_account_id="acct_test_123",
        account_type=ConnectedAccount.AccountType.EXPRESS,
        status=ConnectedAccount.Status.ACTIVE,
        charges_enabled=True,
        payouts_enabled=True,
        details_submitted=True,
        business_name="Test Business",
        email="business@example.com",
        country="US",
    )


@pytest.fixture
@pytest.mark.django_db
def billing_product():
    return BillingProduct.objects.create(
        provider="stripe",
        provider_product_id="prod_connect_test",
        name="Connect Plan",
        description="Plan for connected accounts",
        active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def billing_price(billing_product):
    return BillingPrice.objects.create(
        provider="stripe",
        provider_price_id="price_connect_test",
        product=billing_product,
        currency="usd",
        unit_amount=4999,
        interval=BillingPrice.Interval.MONTH,
    )


@pytest.fixture
@pytest.mark.django_db
def subscription(billing_customer, billing_price):
    now = timezone.now()
    return Subscription.objects.create(
        customer=billing_customer,
        price=billing_price,
        provider="stripe",
        provider_subscription_id="sub_connect_test",
        status=Subscription.Status.ACTIVE,
        quantity=1,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )


# ---------------------------------------------------------------------------
# ConnectedAccount Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConnectedAccountModel:

    def test_create_connected_account(self, test_user):
        acct = ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_new_123",
            account_type=ConnectedAccount.AccountType.STANDARD,
            status=ConnectedAccount.Status.PENDING,
        )
        assert acct.stripe_account_id == "acct_new_123"
        assert acct.account_type == ConnectedAccount.AccountType.STANDARD
        assert acct.status == ConnectedAccount.Status.PENDING
        assert acct.charges_enabled is False
        assert acct.payouts_enabled is False
        assert acct.details_submitted is False

    def test_str_representation(self, connected_account):
        result = str(connected_account)
        assert "acct_test_123" in result
        assert "express" in result

    def test_is_fully_onboarded_true(self, connected_account):
        assert connected_account.is_fully_onboarded is True

    def test_is_fully_onboarded_false_charges(self, test_user):
        acct = ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_partial_1",
            charges_enabled=False,
            payouts_enabled=True,
            details_submitted=True,
        )
        assert acct.is_fully_onboarded is False

    def test_is_fully_onboarded_false_payouts(self, test_user):
        acct = ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_partial_2",
            charges_enabled=True,
            payouts_enabled=False,
            details_submitted=True,
        )
        assert acct.is_fully_onboarded is False

    def test_is_fully_onboarded_false_details(self, test_user):
        acct = ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_partial_3",
            charges_enabled=True,
            payouts_enabled=True,
            details_submitted=False,
        )
        assert acct.is_fully_onboarded is False

    def test_uuid_primary_key(self, connected_account):
        assert isinstance(connected_account.id, uuid.UUID)

    def test_unique_stripe_account_id(self, connected_account, test_user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            ConnectedAccount.objects.create(
                user=test_user,
                stripe_account_id="acct_test_123",
            )

    def test_account_type_choices(self):
        assert ConnectedAccount.AccountType.STANDARD == "standard"
        assert ConnectedAccount.AccountType.EXPRESS == "express"
        assert ConnectedAccount.AccountType.CUSTOM == "custom"

    def test_status_choices(self):
        assert ConnectedAccount.Status.PENDING == "pending"
        assert ConnectedAccount.Status.ACTIVE == "active"
        assert ConnectedAccount.Status.RESTRICTED == "restricted"
        assert ConnectedAccount.Status.DISABLED == "disabled"

    def test_metadata_default(self, test_user):
        acct = ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_meta_test",
        )
        assert acct.metadata == {}

    def test_user_relationship(self, connected_account, test_user):
        assert connected_account.user == test_user
        assert test_user.connected_accounts.count() == 1


@pytest.mark.django_db
class TestTransferModel:

    def test_create_transfer(self, connected_account):
        transfer = Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_test_123",
            amount=5000,
            currency="usd",
            status=Transfer.Status.PENDING,
            description="Test transfer",
        )
        assert transfer.amount == 5000
        assert transfer.currency == "usd"
        assert transfer.status == Transfer.Status.PENDING

    def test_str_representation(self, connected_account):
        transfer = Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_str_test",
            amount=1000,
        )
        result = str(transfer)
        assert "tr_str_test" in result
        assert "1000" in result

    def test_uuid_primary_key(self, connected_account):
        transfer = Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_uuid_test",
            amount=100,
        )
        assert isinstance(transfer.id, uuid.UUID)

    def test_unique_stripe_transfer_id(self, connected_account):
        from django.db import IntegrityError

        Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_dup_test",
            amount=100,
        )
        with pytest.raises(IntegrityError):
            Transfer.objects.create(
                connected_account=connected_account,
                stripe_transfer_id="tr_dup_test",
                amount=200,
            )

    def test_status_choices(self):
        assert Transfer.Status.PENDING == "pending"
        assert Transfer.Status.PAID == "paid"
        assert Transfer.Status.FAILED == "failed"
        assert Transfer.Status.CANCELED == "canceled"

    def test_ordering(self, connected_account):
        t1 = Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_order_1",
            amount=100,
        )
        t2 = Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_order_2",
            amount=200,
        )
        transfers = list(Transfer.objects.all())
        assert transfers[0].id == t2.id

    def test_connected_account_relationship(self, connected_account):
        Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_rel_test",
            amount=100,
        )
        assert connected_account.transfers.count() == 1

    def test_cascade_delete(self, connected_account):
        Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_cascade",
            amount=100,
        )
        connected_account.delete()
        assert Transfer.objects.filter(stripe_transfer_id="tr_cascade").count() == 0


@pytest.mark.django_db
class TestApplicationFeeModel:

    def test_create_application_fee(self, connected_account):
        fee = ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_test_123",
            amount=500,
            currency="usd",
            charge_id="ch_test_123",
        )
        assert fee.amount == 500
        assert fee.charge_id == "ch_test_123"

    def test_str_representation(self, connected_account):
        fee = ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_str_test",
            amount=250,
        )
        result = str(fee)
        assert "fee_str_test" in result
        assert "250" in result

    def test_unique_stripe_fee_id(self, connected_account):
        from django.db import IntegrityError

        ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_dup",
            amount=100,
        )
        with pytest.raises(IntegrityError):
            ApplicationFee.objects.create(
                connected_account=connected_account,
                stripe_fee_id="fee_dup",
                amount=200,
            )

    def test_connected_account_relationship(self, connected_account):
        ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_rel_1",
            amount=100,
        )
        ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_rel_2",
            amount=200,
        )
        assert connected_account.application_fees.count() == 2


# ---------------------------------------------------------------------------
# _parse_timestamp Tests
# ---------------------------------------------------------------------------


class TestParseTimestamp:

    def test_unix_timestamp_int(self):
        result = _parse_timestamp(1700000000)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_iso_string_with_tz(self):
        result = _parse_timestamp("2024-01-15T12:00:00+00:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1

    def test_iso_string_without_tz(self):
        result = _parse_timestamp("2024-01-15T12:00:00")
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_none_returns_none(self):
        assert _parse_timestamp(None) is None

    def test_invalid_string_returns_none(self):
        assert _parse_timestamp("not-a-date") is None

    def test_unsupported_type_returns_none(self):
        assert _parse_timestamp(3.14) is None


# ---------------------------------------------------------------------------
# Connect-specific Schema Tests
# ---------------------------------------------------------------------------


class TestConnectSchemas:

    def test_connected_account_create_defaults(self):
        schema = ConnectedAccountCreate()
        assert schema.type == SchemaConnectAccountType.STANDARD
        assert schema.email is None
        assert schema.country is None
        assert schema.metadata == {}

    def test_connected_account_create_express(self):
        schema = ConnectedAccountCreate(
            type=SchemaConnectAccountType.EXPRESS,
            email="seller@example.com",
            country="US",
            business_type="individual",
        )
        assert schema.type == SchemaConnectAccountType.EXPRESS
        assert schema.email == "seller@example.com"

    def test_connected_account_response(self):
        resp = ConnectedAccountResponse(
            id="acct_123",
            type=SchemaConnectAccountType.EXPRESS,
            email="test@example.com",
            charges_enabled=True,
            payouts_enabled=True,
            details_submitted=True,
        )
        assert resp.id == "acct_123"
        assert resp.charges_enabled is True

    def test_connected_account_list_response(self):
        resp = ConnectedAccountListResponse(items=[], total=0)
        assert resp.items == []
        assert resp.total == 0

    def test_account_link_create(self):
        schema = AccountLinkCreate(
            account_id="acct_123",
            refresh_url="https://example.com/refresh",
            return_url="https://example.com/return",
        )
        assert schema.account_id == "acct_123"

    def test_account_link_response(self):
        resp = AccountLinkResponse(url="https://connect.stripe.com/link")
        assert resp.url == "https://connect.stripe.com/link"

    def test_oauth_authorize_request(self):
        schema = OAuthAuthorizeRequest(
            redirect_uri="https://example.com/callback",
            state="test_state",
        )
        assert schema.redirect_uri == "https://example.com/callback"
        assert schema.state == "test_state"

    def test_oauth_authorize_response(self):
        resp = OAuthAuthorizeResponse(url="https://connect.stripe.com/oauth", state="abc")
        assert resp.state == "abc"

    def test_oauth_callback_request(self):
        schema = OAuthCallbackRequest(code="ac_test_code")
        assert schema.code == "ac_test_code"

    def test_payment_intent_with_fee_create(self):
        schema = PaymentIntentWithFeeCreate(
            amount=10000,
            connected_account_id="acct_123",
            application_fee_amount=1000,
        )
        assert schema.amount == 10000
        assert schema.application_fee_amount == 1000
        assert schema.currency == "usd"

    def test_transfer_create(self):
        schema = TransferCreate(
            amount=5000,
            destination="acct_123",
            description="Platform payout",
        )
        assert schema.amount == 5000
        assert schema.destination == "acct_123"

    def test_transfer_response(self):
        resp = TransferResponse(
            id="tr_123",
            amount=5000,
            currency="usd",
            destination="acct_123",
        )
        assert resp.id == "tr_123"

    def test_transfer_reversal_request_full(self):
        schema = TransferReversalRequest()
        assert schema.amount is None

    def test_transfer_reversal_request_partial(self):
        schema = TransferReversalRequest(amount=2500)
        assert schema.amount == 2500


# ---------------------------------------------------------------------------
# Stripe Connect Provider Tests
# ---------------------------------------------------------------------------


class TestStripeConnectProvider:

    def test_connect_config_properties(self, stripe_config):
        assert stripe_config.is_connect_configured is True
        assert stripe_config.connect_client_id == "ca_test_abc123"

    def test_connect_config_not_configured(self):
        config = StripeConfig(secret_key="sk_test")
        assert config.is_connect_configured is False

    @patch("stripe.Account.create")
    async def test_create_connected_account(self, mock_create, stripe_config):
        mock_account = MagicMock()
        mock_account.id = "acct_new"
        mock_account.type = "express"
        mock_account.email = "seller@test.com"
        mock_account.business_profile = MagicMock()
        mock_account.business_profile.name = "Test Biz"
        mock_account.charges_enabled = False
        mock_account.payouts_enabled = False
        mock_account.details_submitted = False
        mock_account.country = "US"
        mock_account.metadata = {}
        mock_account.created = 1700000000
        mock_account.to_dict.return_value = {}
        mock_create.return_value = mock_account

        provider = StripeProvider(stripe_config)
        result = await provider.create_connected_account(
            type="express",
            email="seller@test.com",
            country="US",
        )
        assert result.id == "acct_new"
        assert result.type == ConnectAccountType.EXPRESS
        assert result.email == "seller@test.com"
        mock_create.assert_called_once()

    @patch("stripe.Account.retrieve")
    async def test_get_connected_account(self, mock_retrieve, stripe_config):
        mock_account = MagicMock()
        mock_account.id = "acct_get"
        mock_account.type = "standard"
        mock_account.email = "get@test.com"
        mock_account.business_profile = MagicMock()
        mock_account.business_profile.name = None
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.details_submitted = True
        mock_account.country = "US"
        mock_account.metadata = {}
        mock_account.created = 1700000000
        mock_account.to_dict.return_value = {}
        mock_retrieve.return_value = mock_account

        provider = StripeProvider(stripe_config)
        result = await provider.get_connected_account("acct_get")
        assert result.id == "acct_get"
        assert result.business_name == ""

    @patch("stripe.Account.retrieve")
    async def test_get_connected_account_not_found(self, mock_retrieve, stripe_config):
        mock_retrieve.side_effect = stripe_lib.error.InvalidRequestError(
            "No such account", "id"
        )
        provider = StripeProvider(stripe_config)
        result = await provider.get_connected_account("acct_nonexistent")
        assert result is None

    @patch("stripe.Account.delete")
    async def test_delete_connected_account(self, mock_delete, stripe_config):
        mock_delete.return_value = MagicMock(deleted=True)
        provider = StripeProvider(stripe_config)
        result = await provider.delete_connected_account("acct_del")
        assert result is True

    @patch("stripe.Account.list")
    async def test_list_connected_accounts(self, mock_list, stripe_config):
        mock_account = MagicMock()
        mock_account.id = "acct_list_1"
        mock_account.type = "express"
        mock_account.email = "list@test.com"
        mock_account.business_profile = MagicMock()
        mock_account.business_profile.name = "Biz"
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.details_submitted = True
        mock_account.country = "US"
        mock_account.metadata = {}
        mock_account.created = 1700000000
        mock_account.to_dict.return_value = {}
        mock_list.return_value = MagicMock(data=[mock_account])

        provider = StripeProvider(stripe_config)
        result = await provider.list_connected_accounts(limit=5)
        assert len(result) == 1
        assert result[0].id == "acct_list_1"

    @patch("stripe.AccountLink.create")
    async def test_create_account_link(self, mock_link, stripe_config):
        mock_link.return_value = MagicMock(
            url="https://connect.stripe.com/setup/abc",
            expires_at=1700000000,
        )
        provider = StripeProvider(stripe_config)
        result = await provider.create_account_link(
            account_id="acct_link",
            refresh_url="https://example.com/refresh",
            return_url="https://example.com/return",
        )
        assert isinstance(result, AccountLinkData)
        assert "connect.stripe.com" in result.url

    def test_get_oauth_authorize_url(self, stripe_config):
        provider = StripeProvider(stripe_config)
        result = provider.get_oauth_authorize_url(
            redirect_uri="https://example.com/callback",
            state="test_state",
        )
        assert isinstance(result, OAuthLinkData)
        assert "connect.stripe.com/oauth/authorize" in result.url
        assert result.state == "test_state"
        assert "ca_test_abc123" in result.url

    def test_get_oauth_authorize_url_generates_state(self, stripe_config):
        provider = StripeProvider(stripe_config)
        result = provider.get_oauth_authorize_url(
            redirect_uri="https://example.com/callback",
        )
        assert result.state != ""
        assert len(result.state) > 10

    @patch("stripe.Transfer.create")
    async def test_create_transfer(self, mock_create, stripe_config):
        mock_transfer = MagicMock()
        mock_transfer.id = "tr_new"
        mock_transfer.amount = 5000
        mock_transfer.currency = "usd"
        mock_transfer.destination = "acct_dest"
        mock_transfer.source_transaction = ""
        mock_transfer.description = "Payout"
        mock_transfer.metadata = {}
        mock_transfer.created = 1700000000
        mock_transfer.to_dict.return_value = {}
        mock_create.return_value = mock_transfer

        provider = StripeProvider(stripe_config)
        result = await provider.create_transfer(
            amount=5000,
            destination="acct_dest",
            description="Payout",
        )
        assert isinstance(result, TransferData)
        assert result.amount == 5000
        assert result.destination == "acct_dest"

    @patch("stripe.PaymentIntent.create")
    async def test_create_payment_intent_with_fee(self, mock_create, stripe_config):
        mock_intent = MagicMock()
        mock_intent.to_dict.return_value = {
            "id": "pi_test",
            "amount": 10000,
            "application_fee_amount": 1000,
        }
        mock_create.return_value = mock_intent

        provider = StripeProvider(stripe_config)
        result = await provider.create_payment_intent_with_fee(
            amount=10000,
            connected_account_id="acct_fee",
            application_fee_amount=1000,
        )
        assert result["id"] == "pi_test"

    @patch("stripe.PaymentIntent.create")
    async def test_payment_intent_auto_fee_from_config(self, mock_create, stripe_config):
        mock_intent = MagicMock()
        mock_intent.to_dict.return_value = {"id": "pi_auto_fee"}
        mock_create.return_value = mock_intent

        provider = StripeProvider(stripe_config)
        await provider.create_payment_intent_with_fee(
            amount=10000,
            connected_account_id="acct_auto",
        )
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["application_fee_amount"] == 1000  # 10% of 10000

    @patch("stripe.Transfer.create_reversal")
    async def test_reverse_transfer_full(self, mock_reversal, stripe_config):
        mock_reversal.return_value = MagicMock(
            to_dict=MagicMock(return_value={"id": "trr_full", "amount": 5000})
        )
        provider = StripeProvider(stripe_config)
        result = await provider.reverse_transfer("tr_123")
        assert result["id"] == "trr_full"

    @patch("stripe.Transfer.create_reversal")
    async def test_reverse_transfer_partial(self, mock_reversal, stripe_config):
        mock_reversal.return_value = MagicMock(
            to_dict=MagicMock(return_value={"id": "trr_partial", "amount": 2500})
        )
        provider = StripeProvider(stripe_config)
        result = await provider.reverse_transfer("tr_123", amount=2500)
        assert result["amount"] == 2500

    @patch("stripe.Webhook.construct_event")
    async def test_verify_connect_webhook_valid(self, mock_construct, stripe_config):
        mock_event = MagicMock()
        mock_event.id = "evt_connect"
        mock_event.type = "account.updated"
        mock_event.created = 1700000000
        mock_event.data.object.to_dict.return_value = {"id": "acct_updated"}
        mock_construct.return_value = mock_event

        provider = StripeProvider(stripe_config)
        result = await provider.verify_connect_webhook(b"payload", "sig")
        assert result.id == "evt_connect"
        assert result.type == "account.updated"
        mock_construct.assert_called_with(b"payload", "sig", "whsec_connect_test")

    @patch("stripe.Webhook.construct_event")
    async def test_verify_connect_webhook_invalid_sig(self, mock_construct, stripe_config):
        mock_construct.side_effect = stripe_lib.error.SignatureVerificationError(
            "bad sig", "sig_header"
        )
        provider = StripeProvider(stripe_config)
        with pytest.raises(BillingWebhookError, match="Invalid Connect webhook signature"):
            await provider.verify_connect_webhook(b"payload", "bad_sig")

    def test_normalize_connect_webhook_types(self, stripe_config):
        provider = StripeProvider(stripe_config)
        assert provider.normalize_webhook_type("account.updated") == "connect.account.updated"
        assert (
            provider.normalize_webhook_type("account.application.deauthorized")
            == "connect.account.deauthorized"
        )
        assert provider.normalize_webhook_type("transfer.created") == "connect.transfer.created"


# ---------------------------------------------------------------------------
# ConnectController Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConnectController:

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_create_account_success(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.create_connected_account = AsyncMock(
            return_value=ConnectedAccountData(
                id="acct_ctrl_new",
                type=ConnectAccountType.EXPRESS,
                email="new@test.com",
                charges_enabled=False,
                payouts_enabled=False,
                details_submitted=False,
                country="US",
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/accounts")
        data = ConnectedAccountCreate(
            type=SchemaConnectAccountType.EXPRESS,
            email="new@test.com",
            country="US",
        )
        result = await ConnectController.create_account(request, data)
        assert result["id"] == "acct_ctrl_new"
        assert result["charges_enabled"] is False

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_create_account_error(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.create_connected_account = AsyncMock(
            side_effect=BillingAPIError("Stripe error", provider="stripe", status_code=400)
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/accounts")
        data = ConnectedAccountCreate()
        result = await ConnectController.create_account(request, data)
        assert "error" in result

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_list_accounts(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.list_connected_accounts = AsyncMock(
            return_value=[
                ConnectedAccountData(
                    id="acct_list_1",
                    type=ConnectAccountType.EXPRESS,
                    email="a@test.com",
                    created_at=datetime(2024, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.get("/connect/accounts")
        result = await ConnectController.list_accounts(request)
        assert result["total"] == 1
        assert result["items"][0]["id"] == "acct_list_1"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_get_account_found(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.get_connected_account = AsyncMock(
            return_value=ConnectedAccountData(
                id="acct_found",
                type=ConnectAccountType.STANDARD,
                email="found@test.com",
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.get("/connect/accounts/acct_found")
        result = await ConnectController.get_account(request, "acct_found")
        assert result["id"] == "acct_found"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_get_account_not_found(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.get_connected_account = AsyncMock(return_value=None)
        mock_provider_fn.return_value = mock_provider

        request = rf.get("/connect/accounts/acct_missing")
        result = await ConnectController.get_account(request, "acct_missing")
        assert result["code"] == "not_found"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_delete_account(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.delete_connected_account = AsyncMock(return_value=True)
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/accounts/acct_del/delete")
        result = await ConnectController.delete_account(request, "acct_del")
        assert result["deleted"] is True
        assert result["id"] == "acct_del"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_create_account_link(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.create_account_link = AsyncMock(
            return_value=AccountLinkData(
                url="https://connect.stripe.com/setup/abc",
                expires_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/onboard/link")
        data = AccountLinkCreate(
            account_id="acct_onboard",
            refresh_url="https://example.com/refresh",
            return_url="https://example.com/return",
        )
        result = await ConnectController.create_account_link(request, data)
        assert "connect.stripe.com" in result["url"]

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_get_oauth_url(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.get_oauth_authorize_url.return_value = OAuthLinkData(
            url="https://connect.stripe.com/oauth/authorize?foo=bar",
            state="generated_state",
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/onboard/oauth-url")
        data = OAuthAuthorizeRequest(
            redirect_uri="https://example.com/callback",
        )
        result = await ConnectController.get_oauth_url(request, data)
        assert "connect.stripe.com" in result["url"]
        assert result["state"] == "generated_state"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_create_payment_with_fee(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.create_payment_intent_with_fee = AsyncMock(
            return_value={"id": "pi_ctrl", "amount": 10000}
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/payments/create")
        data = PaymentIntentWithFeeCreate(
            amount=10000,
            connected_account_id="acct_pay",
            application_fee_amount=1000,
        )
        result = await ConnectController.create_payment_with_fee(request, data)
        assert result["id"] == "pi_ctrl"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_create_transfer(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.create_transfer = AsyncMock(
            return_value=TransferData(
                id="tr_ctrl",
                amount=5000,
                currency="usd",
                destination="acct_dest",
                description="Payout",
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/transfers/create")
        data = TransferCreate(amount=5000, destination="acct_dest", description="Payout")
        result = await ConnectController.create_transfer(request, data)
        assert result["id"] == "tr_ctrl"
        assert result["amount"] == 5000

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_reverse_transfer(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.reverse_transfer = AsyncMock(
            return_value={"id": "trr_ctrl", "amount": 2500}
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post("/connect/transfers/tr_123/reverse")
        data = TransferReversalRequest(amount=2500)
        result = await ConnectController.reverse_transfer(request, "tr_123", data)
        assert result["id"] == "trr_ctrl"

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_handle_webhook_success(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.verify_connect_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_connect_wh",
                type="account.updated",
                provider="stripe",
                data={"id": "acct_updated"},
            )
        )
        mock_provider.normalize_webhook_type.return_value = "connect.account.updated"
        mock_provider_fn.return_value = mock_provider

        request = rf.post(
            "/connect/webhooks",
            data=b'{"id":"evt_connect_wh"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=abc"

        response = await ConnectController.handle_webhook(request)
        assert response.status_code == 200

        assert await WebhookEventModel.objects.filter(
            provider_event_id="evt_connect_wh"
        ).aexists()

    @patch("django_matt.billing.connect_controller._get_stripe_provider")
    async def test_handle_webhook_invalid_signature(self, mock_provider_fn, rf):
        mock_provider = MagicMock()
        mock_provider.verify_connect_webhook = AsyncMock(
            side_effect=BillingWebhookError("Invalid signature")
        )
        mock_provider_fn.return_value = mock_provider

        request = rf.post(
            "/connect/webhooks",
            data=b"bad",
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "bad_sig"

        response = await ConnectController.handle_webhook(request)
        assert response.status_code == 400

    def test_get_urls(self):
        urls = ConnectController.get_urls()
        assert len(urls) == 11
        paths = [u[0] for u in urls]
        assert "accounts" in paths
        assert "webhooks" in paths
        assert "onboard/link" in paths
        assert "payments/create" in paths
        assert "transfers/create" in paths


# ---------------------------------------------------------------------------
# Invoice Webhook DB Sync Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvoiceWebhookSync:

    @patch("django_matt.billing.controllers.get_provider")
    async def test_invoice_paid_updates_local_record(
        self, mock_get_provider, rf
    ):
        user = await User.objects.acreate_user(
            username="inv_sync_user",
            email="inv_sync@example.com",
            password="testpass",
        )
        bc = await BillingCustomer.objects.acreate(
            user=user,
            stripe_customer_id="cus_inv_sync",
            default_provider="stripe",
        )
        inv = await Invoice.objects.acreate(
            customer=bc,
            provider="stripe",
            provider_invoice_id="inv_paid_sync",
            status=Invoice.Status.OPEN,
            currency="usd",
            amount_due=2999,
            amount_paid=0,
            amount_remaining=2999,
        )

        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_inv_paid",
                type="invoice.paid",
                provider="stripe",
                data={
                    "id": "inv_paid_sync",
                    "amount_paid": 2999,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "invoice.paid"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id":"evt_inv_paid"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=abc"

        response = await controller.handle_stripe_webhook(request)
        assert response.status_code == 200

        await inv.arefresh_from_db()
        assert inv.status == Invoice.Status.PAID
        assert inv.amount_paid == 2999
        assert inv.amount_remaining == 0
        assert inv.paid_at is not None

    @patch("django_matt.billing.controllers.get_provider")
    async def test_invoice_paid_missing_local_record_no_crash(
        self, mock_get_provider, rf
    ):
        mock_provider = MagicMock()
        mock_provider.verify_webhook = AsyncMock(
            return_value=WebhookEvent(
                id="evt_inv_missing",
                type="invoice.paid",
                provider="stripe",
                data={
                    "id": "inv_does_not_exist",
                    "amount_paid": 1000,
                },
            )
        )
        mock_provider.normalize_webhook_type.return_value = "invoice.paid"
        mock_get_provider.return_value = mock_provider

        controller = WebhookController()
        request = rf.post(
            "/billing/webhooks/stripe",
            data=b'{"id":"evt_inv_missing"}',
            content_type="application/json",
        )
        request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=abc"

        response = await controller.handle_stripe_webhook(request)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Testing Helper Unit Tests
# ---------------------------------------------------------------------------


class TestMockEventHelpers:

    def test_mock_stripe_event_structure(self):
        payload, sig_header = mock_stripe_event(
            "customer.subscription.created",
            data={"id": "sub_123", "status": "active"},
        )
        assert isinstance(payload, bytes)
        assert sig_header.startswith("t=")
        assert ",v1=" in sig_header

        import orjson

        parsed = orjson.loads(payload)
        assert parsed["type"] == "customer.subscription.created"
        assert parsed["data"]["object"]["id"] == "sub_123"
        assert "id" in parsed
        assert parsed["object"] == "event"

    def test_mock_stripe_event_custom_id(self):
        payload, _ = mock_stripe_event(
            "invoice.paid",
            data={"id": "inv_1"},
            event_id="evt_custom_id",
        )
        import orjson

        parsed = orjson.loads(payload)
        assert parsed["id"] == "evt_custom_id"

    def test_mock_stripe_event_custom_secret(self):
        secret = "whsec_custom"
        payload, sig_header = mock_stripe_event(
            "test.event",
            data={},
            secret=secret,
        )
        ts_str = sig_header.split(",")[0].split("=")[1]
        sig_str = sig_header.split(",")[1].split("=")[1]

        signed_payload = f"{ts_str}.".encode() + payload
        expected = hmac.new(
            secret.encode(), signed_payload, hashlib.sha256
        ).hexdigest()
        assert sig_str == expected

    def test_mock_paypal_event_structure(self):
        payload, headers = mock_paypal_event(
            "BILLING.SUBSCRIPTION.CREATED",
            data={"id": "I-PAY123"},
        )
        assert isinstance(payload, bytes)
        assert "PAYPAL-TRANSMISSION-ID" in headers
        assert "PAYPAL-TRANSMISSION-TIME" in headers
        assert "PAYPAL-TRANSMISSION-SIG" in headers

        import orjson

        parsed = orjson.loads(payload)
        assert parsed["event_type"] == "BILLING.SUBSCRIPTION.CREATED"
        assert parsed["resource"]["id"] == "I-PAY123"

    def test_mock_paypal_event_custom_ids(self):
        payload, headers = mock_paypal_event(
            "PAYMENT.SALE.COMPLETED",
            data={"id": "sale_1"},
            event_id="custom_transmission_id",
        )
        assert headers["PAYPAL-TRANSMISSION-ID"] == "custom_transmission_id"

    def test_mock_polar_event_structure(self):
        payload, sig_header = mock_polar_event(
            "subscription.created",
            data={"id": "sub_polar_1"},
        )
        assert isinstance(payload, bytes)
        assert sig_header.startswith("sha256=")

        import orjson

        parsed = orjson.loads(payload)
        assert parsed["type"] == "subscription.created"
        assert parsed["data"]["id"] == "sub_polar_1"

    def test_mock_polar_event_custom_secret(self):
        secret = "polar_custom_secret"
        payload, sig_header = mock_polar_event(
            "test.event",
            data={},
            secret=secret,
        )
        sig = sig_header.replace("sha256=", "")
        expected = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        assert sig == expected


# ---------------------------------------------------------------------------
# PayPal Webhook Edge Cases
# ---------------------------------------------------------------------------


class TestPayPalWebhookEdgeCases:

    async def test_verify_webhook_missing_headers(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        import orjson

        payload = orjson.dumps({"id": "evt_1", "event_type": "TEST"})
        with pytest.raises(BillingWebhookError, match="Missing required PayPal webhook headers"):
            await provider.verify_webhook(payload, "", headers={})

    async def test_verify_webhook_missing_signature(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        import orjson

        payload = orjson.dumps({"id": "evt_1", "event_type": "TEST"})
        with pytest.raises(BillingWebhookError, match="Missing PayPal webhook signature"):
            await provider.verify_webhook(
                payload,
                "",
                headers={
                    "PAYPAL-TRANSMISSION-ID": "tid_1",
                    "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
                },
            )

    async def test_verify_webhook_missing_webhook_id_config(self):
        config = PayPalConfig(
            client_id="test_id",
            client_secret="test_secret",
            webhook_id="",
            mode="sandbox",
        )
        provider = PayPalProvider(config)
        import orjson

        payload = orjson.dumps({"id": "evt_1", "event_type": "TEST"})
        with pytest.raises(BillingWebhookError, match="webhook_id is not configured"):
            await provider.verify_webhook(
                payload,
                "sig",
                headers={
                    "PAYPAL-TRANSMISSION-ID": "tid_1",
                    "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
                    "PAYPAL-TRANSMISSION-SIG": "bad_sig",
                },
            )

    async def test_verify_webhook_invalid_base64_sig(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        import orjson

        payload = orjson.dumps({"id": "evt_1", "event_type": "TEST"})
        with pytest.raises(BillingWebhookError, match="Invalid base64"):
            await provider.verify_webhook(
                payload,
                "not-valid-base64!!!",
                headers={
                    "PAYPAL-TRANSMISSION-ID": "tid_1",
                    "PAYPAL-TRANSMISSION-TIME": "2024-01-01T00:00:00Z",
                },
            )

    async def test_verify_webhook_tampered_payload(self, paypal_config):
        import orjson

        payload, headers = mock_paypal_event(
            "BILLING.SUBSCRIPTION.CREATED",
            data={"id": "sub_1"},
            client_secret=paypal_config.client_secret,
            webhook_id=paypal_config.webhook_id,
        )
        # Tamper the payload but keep it valid JSON so it reaches sig check
        data = orjson.loads(payload)
        data["event_type"] = "TAMPERED"
        tampered_payload = orjson.dumps(data)
        provider = PayPalProvider(paypal_config)
        with pytest.raises(BillingWebhookError, match="signature verification failed"):
            await provider.verify_webhook(
                tampered_payload,
                headers["PAYPAL-TRANSMISSION-SIG"],
                headers=headers,
            )


# ---------------------------------------------------------------------------
# Subscription Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSubscriptionEdgeCases:

    def test_expired_subscription_not_active(self, billing_customer, billing_price):
        past = timezone.now() - timedelta(days=60)
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_expired",
            status=Subscription.Status.CANCELED,
            current_period_start=past,
            current_period_end=past + timedelta(days=30),
            canceled_at=past + timedelta(days=15),
        )
        assert sub.is_active is False
        assert sub.is_trialing is False

    def test_incomplete_expired_not_active(self, billing_customer, billing_price):
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=billing_price,
            provider="stripe",
            provider_subscription_id="sub_inc_exp",
            status=Subscription.Status.INCOMPLETE_EXPIRED,
        )
        assert sub.is_active is False

    def test_multiple_subscriptions_per_customer(self, billing_customer, billing_price):
        for i in range(3):
            Subscription.objects.create(
                customer=billing_customer,
                price=billing_price,
                provider="stripe",
                provider_subscription_id=f"sub_multi_{i}",
                status=Subscription.Status.ACTIVE,
            )
        assert billing_customer.subscriptions.count() == 3

    def test_subscription_without_price(self, billing_customer):
        sub = Subscription.objects.create(
            customer=billing_customer,
            price=None,
            provider="stripe",
            provider_subscription_id="sub_no_price",
            status=Subscription.Status.ACTIVE,
        )
        assert sub.price is None
        assert sub.is_active is True


# ---------------------------------------------------------------------------
# Webhook Event Idempotency Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWebhookIdempotency:

    async def test_different_providers_same_event_id_stored_separately(self):
        await WebhookEventModel.objects.acreate(
            provider="stripe",
            provider_event_id="evt_shared_id",
            event_type="test.event",
            payload={"source": "stripe"},
        )
        await WebhookEventModel.objects.acreate(
            provider="polar",
            provider_event_id="evt_shared_id",
            event_type="test.event",
            payload={"source": "polar"},
        )
        count = await WebhookEventModel.objects.filter(
            provider_event_id="evt_shared_id"
        ).acount()
        assert count == 2

    async def test_webhook_amark_processed_sets_timestamp(self):
        evt = await WebhookEventModel.objects.acreate(
            provider="stripe",
            provider_event_id="evt_mark_ts",
            event_type="test",
            payload={},
        )
        assert evt.processed is False
        assert evt.processed_at is None

        await evt.amark_processed()
        await evt.arefresh_from_db()
        assert evt.processed is True
        assert evt.processed_at is not None

    async def test_webhook_amark_processed_with_error_stores_message(self):
        evt = await WebhookEventModel.objects.acreate(
            provider="stripe",
            provider_event_id="evt_mark_err",
            event_type="test",
            payload={},
        )
        await evt.amark_processed(error="Handler crashed")
        await evt.arefresh_from_db()
        assert evt.processed is True
        assert evt.processing_error == "Handler crashed"


# ---------------------------------------------------------------------------
# Billing Signals Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBillingSignals:

    @patch("django_matt.billing.controllers.get_provider")
    async def test_invoice_paid_signal_fires(self, mock_get_provider, rf):
        from django_matt.billing.signals import invoice_paid

        received_signals = []

        def signal_handler(sender, **kwargs):
            received_signals.append(kwargs)

        invoice_paid.connect(signal_handler)
        try:
            mock_provider = MagicMock()
            mock_provider.verify_webhook = AsyncMock(
                return_value=WebhookEvent(
                    id="evt_sig_inv",
                    type="invoice.paid",
                    provider="stripe",
                    data={"id": "inv_signal_test", "amount_paid": 1000},
                )
            )
            mock_provider.normalize_webhook_type.return_value = "invoice.paid"
            mock_get_provider.return_value = mock_provider

            controller = WebhookController()
            request = rf.post(
                "/billing/webhooks/stripe",
                data=b'{"id":"evt_sig_inv"}',
                content_type="application/json",
            )
            request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=abc"

            await controller.handle_stripe_webhook(request)
            assert len(received_signals) == 1
            assert received_signals[0]["provider"] == "stripe"
        finally:
            invoice_paid.disconnect(signal_handler)

    @patch("django_matt.billing.controllers.get_provider")
    async def test_subscription_canceled_signal_fires(self, mock_get_provider, rf):
        from django_matt.billing.signals import subscription_canceled

        user = await User.objects.acreate_user(
            username="sig_cancel_user",
            email="sig_cancel@example.com",
            password="testpass",
        )
        bc = await BillingCustomer.objects.acreate(
            user=user,
            stripe_customer_id="cus_sig_cancel",
            default_provider="stripe",
        )

        received_signals = []

        def signal_handler(sender, **kwargs):
            received_signals.append(kwargs)

        subscription_canceled.connect(signal_handler)
        try:
            mock_provider = MagicMock()
            mock_provider.verify_webhook = AsyncMock(
                return_value=WebhookEvent(
                    id="evt_sig_cancel",
                    type="subscription.canceled",
                    provider="stripe",
                    data={
                        "id": "sub_sig_cancel",
                        "status": "canceled",
                        "customer": bc.stripe_customer_id,
                    },
                )
            )
            mock_provider.normalize_webhook_type.return_value = "subscription.canceled"
            mock_get_provider.return_value = mock_provider

            controller = WebhookController()
            request = rf.post(
                "/billing/webhooks/stripe",
                data=b'{"id":"evt_sig_cancel"}',
                content_type="application/json",
            )
            request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=abc"

            await controller.handle_stripe_webhook(request)
            assert len(received_signals) == 1
            assert received_signals[0]["provider"] == "stripe"
        finally:
            subscription_canceled.disconnect(signal_handler)

    @patch("django_matt.billing.controllers.get_provider")
    async def test_webhook_received_signal_fires_before_processing(
        self, mock_get_provider, rf
    ):
        from django_matt.billing.signals import webhook_received

        received_signals = []

        def signal_handler(sender, **kwargs):
            received_signals.append(kwargs)

        webhook_received.connect(signal_handler)
        try:
            mock_provider = MagicMock()
            mock_provider.verify_webhook = AsyncMock(
                return_value=WebhookEvent(
                    id="evt_sig_received",
                    type="checkout.completed",
                    provider="stripe",
                    data={"id": "cs_123"},
                )
            )
            mock_provider.normalize_webhook_type.return_value = "checkout.completed"
            mock_get_provider.return_value = mock_provider

            controller = WebhookController()
            request = rf.post(
                "/billing/webhooks/stripe",
                data=b'{"id":"evt_sig_received"}',
                content_type="application/json",
            )
            request.META["HTTP_STRIPE_SIGNATURE"] = "t=123,v1=abc"

            await controller.handle_stripe_webhook(request)
            assert len(received_signals) == 1
            assert received_signals[0]["event_type"] == "checkout.completed"
        finally:
            webhook_received.disconnect(signal_handler)


# ---------------------------------------------------------------------------
# PayPal Provider Track/Untrack Subscriptions
# ---------------------------------------------------------------------------


class TestPayPalTrackSubscriptions:

    def test_track_subscription(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        provider.track_subscription("cus_1", "sub_1")
        provider.track_subscription("cus_1", "sub_2")
        assert "sub_1" in provider._tracked_subscriptions["cus_1"]
        assert "sub_2" in provider._tracked_subscriptions["cus_1"]

    def test_untrack_subscription(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        provider.track_subscription("cus_1", "sub_1")
        provider.untrack_subscription("cus_1", "sub_1")
        assert "sub_1" not in provider._tracked_subscriptions.get("cus_1", set())

    def test_untrack_nonexistent_customer(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        provider.untrack_subscription("no_customer", "sub_1")

    def test_untrack_nonexistent_subscription(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        provider.track_subscription("cus_1", "sub_1")
        provider.untrack_subscription("cus_1", "sub_nonexistent")
        assert "sub_1" in provider._tracked_subscriptions["cus_1"]


# ---------------------------------------------------------------------------
# Base Provider Tests
# ---------------------------------------------------------------------------


class TestBaseProviderMethods:

    def test_add_provider_tag(self, stripe_config):
        provider = StripeProvider(stripe_config)
        data = CustomerData(id="cus_1", email="test@test.com")
        result = provider._add_provider_tag(data)
        assert result.provider == "stripe"

    def test_normalize_webhook_type_default(self, stripe_config):
        provider = StripeProvider(stripe_config)
        assert provider.normalize_webhook_type("unknown.type") == "unknown.type"

    async def test_create_billing_portal_not_implemented_paypal(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        with pytest.raises(NotImplementedError, match="paypal"):
            await provider.create_billing_portal_session("cus_1", "https://return.url")

    async def test_list_customers_default_empty(self, paypal_config):
        """PayPal list_customers should return empty by default (no bulk list API)."""
        provider = PayPalProvider(paypal_config)
        # PayPal overrides to return empty list (no customer management API)
        result = await provider.list_customers()
        assert result == []

    async def test_get_invoice_default_none(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        result = await provider.get_invoice("inv_1")
        assert result is None

    async def test_list_invoices_default_empty(self, paypal_config):
        provider = PayPalProvider(paypal_config)
        result = await provider.list_invoices()
        assert result == []


# ---------------------------------------------------------------------------
# Connected Account + Transfer Relationship Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConnectModelRelationships:

    def test_connected_account_transfers(self, connected_account):
        Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_rel_1",
            amount=1000,
        )
        Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_rel_2",
            amount=2000,
        )
        assert connected_account.transfers.count() == 2

    def test_connected_account_application_fees(self, connected_account):
        ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_1",
            amount=100,
        )
        assert connected_account.application_fees.count() == 1

    def test_cascade_delete_connected_account(self, connected_account):
        Transfer.objects.create(
            connected_account=connected_account,
            stripe_transfer_id="tr_cascade_rel",
            amount=100,
        )
        ApplicationFee.objects.create(
            connected_account=connected_account,
            stripe_fee_id="fee_cascade_rel",
            amount=50,
        )
        acct_id = connected_account.id
        connected_account.delete()
        assert Transfer.objects.filter(connected_account_id=acct_id).count() == 0
        assert ApplicationFee.objects.filter(connected_account_id=acct_id).count() == 0

    def test_user_connected_accounts(self, test_user):
        ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_multi_1",
        )
        ConnectedAccount.objects.create(
            user=test_user,
            stripe_account_id="acct_multi_2",
        )
        assert test_user.connected_accounts.count() == 2
