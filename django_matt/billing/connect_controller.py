"""
Stripe Connect controller for django-matt.

Provides REST API endpoints for:
- Connected account management (create, get, update, delete, list)
- Onboarding (Express account links, Standard OAuth)
- Payments with platform fees
- Transfers to connected accounts
- Connect webhook handling
"""

import logging

from django.http import HttpRequest, HttpResponse

from django_matt.billing.config import get_billing_config
from django_matt.billing.providers import BillingError, BillingWebhookError
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

logger = logging.getLogger(__name__)


def _get_stripe_provider() -> StripeProvider:
    """Get configured Stripe provider for Connect operations."""
    config = get_billing_config()
    return StripeProvider(config.stripe)


class ConnectController:
    """
    Controller for Stripe Connect operations.

    Usage:
        from django_matt.billing import ConnectController

        api.register_controller(ConnectController, prefix="/connect")

    Endpoints:
        POST /connect/accounts                 - Create connected account
        GET  /connect/accounts                 - List connected accounts
        GET  /connect/accounts/{id}            - Get connected account
        POST /connect/accounts/{id}/update     - Update connected account
        POST /connect/accounts/{id}/delete     - Delete connected account

        POST /connect/onboard/link             - Create Express account link
        POST /connect/onboard/oauth-url        - Get Standard OAuth URL
        POST /connect/onboard/oauth-callback   - Complete Standard OAuth

        POST /connect/payments/create          - Create payment with fee
        POST /connect/transfers/create         - Create transfer
        POST /connect/transfers/{id}/reverse   - Reverse transfer

        POST /connect/webhooks                 - Handle Connect webhooks
    """

    prefix = "connect"
    tags = ["Stripe Connect"]

    # -------------------------------------------------------------------------
    # Account Management
    # -------------------------------------------------------------------------

    @staticmethod
    async def create_account(request: HttpRequest, data: ConnectedAccountCreate) -> dict:
        """Create a new connected account."""
        try:
            provider = _get_stripe_provider()
            account = await provider.create_connected_account(
                type=data.type.value,
                email=data.email,
                country=data.country,
                business_type=data.business_type,
                metadata=data.metadata,
            )
            return ConnectedAccountResponse(
                id=account.id,
                type=data.type,
                email=account.email,
                business_name=account.business_name,
                charges_enabled=account.charges_enabled,
                payouts_enabled=account.payouts_enabled,
                details_submitted=account.details_submitted,
                country=account.country,
                created_at=account.created_at,
            ).model_dump(mode="json")
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def list_accounts(request: HttpRequest) -> dict:
        """List connected accounts."""
        try:
            provider = _get_stripe_provider()
            limit = int(request.GET.get("limit", "10"))
            starting_after = request.GET.get("starting_after")

            accounts = await provider.list_connected_accounts(
                limit=limit,
                starting_after=starting_after,
            )
            return ConnectedAccountListResponse(
                items=[
                    ConnectedAccountResponse(
                        id=a.id,
                        type=a.type.value,
                        email=a.email,
                        business_name=a.business_name,
                        charges_enabled=a.charges_enabled,
                        payouts_enabled=a.payouts_enabled,
                        details_submitted=a.details_submitted,
                        country=a.country,
                        created_at=a.created_at,
                    )
                    for a in accounts
                ],
                total=len(accounts),
            ).model_dump(mode="json")
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def get_account(request: HttpRequest, account_id: str) -> dict:
        """Get a connected account."""
        try:
            provider = _get_stripe_provider()
            account = await provider.get_connected_account(account_id)
            if not account:
                return BillingErrorResponse(
                    error="Account not found", code="not_found"
                ).model_dump()

            return ConnectedAccountResponse(
                id=account.id,
                type=account.type.value,
                email=account.email,
                business_name=account.business_name,
                charges_enabled=account.charges_enabled,
                payouts_enabled=account.payouts_enabled,
                details_submitted=account.details_submitted,
                country=account.country,
                created_at=account.created_at,
            ).model_dump(mode="json")
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def delete_account(request: HttpRequest, account_id: str) -> dict:
        """Delete a connected account."""
        try:
            provider = _get_stripe_provider()
            deleted = await provider.delete_connected_account(account_id)
            return {"deleted": deleted, "id": account_id}
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    # -------------------------------------------------------------------------
    # Onboarding
    # -------------------------------------------------------------------------

    @staticmethod
    async def create_account_link(request: HttpRequest, data: AccountLinkCreate) -> dict:
        """Create an account link for Express onboarding."""
        try:
            provider = _get_stripe_provider()
            link = await provider.create_account_link(
                account_id=data.account_id,
                refresh_url=data.refresh_url,
                return_url=data.return_url,
            )
            return AccountLinkResponse(
                url=link.url,
                expires_at=link.expires_at,
            ).model_dump(mode="json")
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def get_oauth_url(request: HttpRequest, data: OAuthAuthorizeRequest) -> dict:
        """Get OAuth authorize URL for Standard account onboarding."""
        try:
            provider = _get_stripe_provider()
            link = provider.get_oauth_authorize_url(
                redirect_uri=data.redirect_uri,
                state=data.state,
            )
            return OAuthAuthorizeResponse(
                url=link.url,
                state=link.state,
            ).model_dump()
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def oauth_callback(request: HttpRequest, data: OAuthCallbackRequest) -> dict:
        """Complete Standard OAuth flow."""
        try:
            provider = _get_stripe_provider()
            account = await provider.complete_oauth_connect(data.code)
            return ConnectedAccountResponse(
                id=account.id,
                type=account.type.value,
                email=account.email,
                business_name=account.business_name,
                charges_enabled=account.charges_enabled,
                payouts_enabled=account.payouts_enabled,
                details_submitted=account.details_submitted,
                country=account.country,
                created_at=account.created_at,
            ).model_dump(mode="json")
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    # -------------------------------------------------------------------------
    # Payments & Transfers
    # -------------------------------------------------------------------------

    @staticmethod
    async def create_payment_with_fee(
        request: HttpRequest, data: PaymentIntentWithFeeCreate
    ) -> dict:
        """Create a payment intent with platform fee."""
        try:
            provider = _get_stripe_provider()
            intent = await provider.create_payment_intent_with_fee(
                amount=data.amount,
                connected_account_id=data.connected_account_id,
                application_fee_amount=data.application_fee_amount,
                currency=data.currency,
                metadata=data.metadata,
            )
            return intent
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def create_transfer(request: HttpRequest, data: TransferCreate) -> dict:
        """Create a transfer to a connected account."""
        try:
            provider = _get_stripe_provider()
            transfer = await provider.create_transfer(
                amount=data.amount,
                destination=data.destination,
                currency=data.currency,
                description=data.description,
                metadata=data.metadata,
            )
            return TransferResponse(
                id=transfer.id,
                amount=transfer.amount,
                currency=transfer.currency,
                destination=transfer.destination,
                description=transfer.description,
                created_at=transfer.created_at,
            ).model_dump(mode="json")
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    @staticmethod
    async def reverse_transfer(
        request: HttpRequest, transfer_id: str, data: TransferReversalRequest
    ) -> dict:
        """Reverse a transfer (full or partial)."""
        try:
            provider = _get_stripe_provider()
            reversal = await provider.reverse_transfer(
                transfer_id=transfer_id,
                amount=data.amount,
            )
            return reversal
        except BillingError as e:
            return BillingErrorResponse(error=e.message, code=e.code).model_dump()

    # -------------------------------------------------------------------------
    # Connect Webhooks
    # -------------------------------------------------------------------------

    @staticmethod
    async def handle_webhook(request: HttpRequest) -> HttpResponse:
        """Handle Stripe Connect webhook events."""
        try:
            provider = _get_stripe_provider()
            signature = request.headers.get("Stripe-Signature", "")

            event = await provider.verify_connect_webhook(
                payload=request.body,
                signature=signature,
            )

            normalized_type = provider.normalize_webhook_type(event.type)
            logger.info(f"Connect webhook received: {event.type} -> {normalized_type}")

            # Store the event
            from django_matt.billing.models import WebhookEvent as WebhookEventModel

            await WebhookEventModel.objects.acreate(
                provider="stripe",
                provider_event_id=event.id,
                event_type=event.type,
                payload=event.data,
            )

            return HttpResponse(status=200)

        except BillingWebhookError as e:
            logger.warning(f"Connect webhook verification failed: {e}")
            return HttpResponse(status=400)
        except Exception as e:
            logger.exception(f"Connect webhook error: {e}")
            return HttpResponse(status=500)

    @classmethod
    def get_urls(cls):
        """Get URL patterns for this controller."""
        return [
            ("accounts", "POST", cls.create_account, "connect-create-account"),
            ("accounts", "GET", cls.list_accounts, "connect-list-accounts"),
            ("accounts/<str:account_id>", "GET", cls.get_account, "connect-get-account"),
            (
                "accounts/<str:account_id>/delete",
                "POST",
                cls.delete_account,
                "connect-delete-account",
            ),
            ("onboard/link", "POST", cls.create_account_link, "connect-account-link"),
            ("onboard/oauth-url", "POST", cls.get_oauth_url, "connect-oauth-url"),
            ("onboard/oauth-callback", "POST", cls.oauth_callback, "connect-oauth-callback"),
            ("payments/create", "POST", cls.create_payment_with_fee, "connect-payment-create"),
            ("transfers/create", "POST", cls.create_transfer, "connect-transfer-create"),
            (
                "transfers/<str:transfer_id>/reverse",
                "POST",
                cls.reverse_transfer,
                "connect-transfer-reverse",
            ),
            ("webhooks", "POST", cls.handle_webhook, "connect-webhook"),
        ]
