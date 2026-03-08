"""
Billing controllers for django-matt.

Provides REST API endpoints for:
- Checkout sessions
- Subscription management
- Customer management
- Billing portal
- Webhook handling
"""

import logging
from datetime import UTC, datetime
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from asgiref.sync import sync_to_async

from django_matt.billing.config import ProviderType, get_billing_config
from django_matt.billing.providers import (
    BillingError,
    BillingWebhookError,
    get_provider,
)
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
    SubscriptionCancel,
    SubscriptionCreate,
    SubscriptionListResponse,
    SubscriptionResponse,
    SubscriptionUpdate,
)

logger = logging.getLogger(__name__)


def _parse_timestamp(ts: int | str | None) -> datetime | None:
    """Convert a Unix epoch int, ISO-8601 string, or None to a timezone-aware datetime."""
    if ts is None:
        return None
    if isinstance(ts, int):
        return datetime.fromtimestamp(ts, tz=UTC)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            logger.warning("Could not parse timestamp string: %r", ts)
            return None
    return None


class BillingController:
    """
    Controller for billing operations.

    Usage:
        from django_matt.billing import BillingController

        api.register_controller(BillingController, prefix="/billing")

    Endpoints:
        GET  /billing/config               - Get billing configuration
        POST /billing/checkout             - Create checkout session
        GET  /billing/checkout/{id}        - Get checkout session

        POST /billing/customers            - Create customer
        GET  /billing/customers/{id}       - Get customer
        PATCH /billing/customers/{id}      - Update customer

        GET  /billing/subscriptions        - List subscriptions
        POST /billing/subscriptions        - Create subscription
        GET  /billing/subscriptions/{id}   - Get subscription
        PATCH /billing/subscriptions/{id}  - Update subscription
        POST /billing/subscriptions/{id}/cancel - Cancel subscription
        POST /billing/subscriptions/{id}/resume - Resume subscription

        POST /billing/portal               - Create billing portal session

        GET  /billing/invoices             - List invoices
        GET  /billing/invoices/{id}        - Get invoice

        POST /billing/webhooks/{provider}  - Webhook endpoint
    """

    prefix = "billing"
    tags = ["Billing"]

    def _get_provider(self, provider: ProviderType | None = None):
        """Get billing provider instance."""
        return get_provider(provider)

    def _error_response(self, e: BillingError) -> BillingErrorResponse:
        """Convert exception to error response."""
        return BillingErrorResponse(
            error=e.message,
            code=e.code,
            details=e.details,
        )

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    async def get_config(self, request: HttpRequest) -> BillingConfigResponse:
        """
        Get billing configuration.

        Returns safe-for-frontend configuration including:
        - Enabled status
        - Default provider
        - Currency
        - Configured providers
        - Stripe publishable key (if configured)
        """
        config = get_billing_config()

        return BillingConfigResponse(
            enabled=config.enabled,
            default_provider=config.default_provider,
            currency=config.currency,
            configured_providers=config.get_configured_providers(),
            stripe_publishable_key=config.stripe.publishable_key or None,
        )

    # -------------------------------------------------------------------------
    # Checkout
    # -------------------------------------------------------------------------

    async def create_checkout(
        self,
        request: HttpRequest,
        data: CheckoutCreate,
    ) -> CheckoutResponse | BillingErrorResponse:
        """
        Create a checkout session.

        Returns a URL to redirect the customer to for payment.
        """
        try:
            provider = self._get_provider(data.provider)
            session = await provider.create_checkout_session(
                price_id=data.price_id,
                success_url=data.success_url,
                cancel_url=data.cancel_url,
                customer_id=data.customer_id,
                customer_email=data.customer_email,
                mode=data.mode,
                quantity=data.quantity,
                trial_period_days=data.trial_period_days,
                metadata=data.metadata,
            )

            return CheckoutResponse(
                id=session.id,
                url=session.url,
                provider=session.provider,
                customer_id=session.customer_id,
                subscription_id=session.subscription_id,
                status=session.status,
                mode=session.mode,
                expires_at=session.expires_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def get_checkout(
        self,
        request: HttpRequest,
        session_id: str,
        provider: ProviderType | None = None,
    ) -> CheckoutResponse | BillingErrorResponse:
        """Get checkout session by ID."""
        try:
            billing_provider = self._get_provider(provider)
            session = await billing_provider.get_checkout_session(session_id)

            if not session:
                return BillingErrorResponse(
                    error="Checkout session not found",
                    code="not_found",
                )

            return CheckoutResponse(
                id=session.id,
                url=session.url,
                provider=session.provider,
                customer_id=session.customer_id,
                subscription_id=session.subscription_id,
                status=session.status,
                mode=session.mode,
                expires_at=session.expires_at,
            )
        except BillingError as e:
            return self._error_response(e)

    # -------------------------------------------------------------------------
    # Customers
    # -------------------------------------------------------------------------

    async def create_customer(
        self,
        request: HttpRequest,
        data: CustomerCreate,
    ) -> CustomerResponse | BillingErrorResponse:
        """Create a new customer."""
        try:
            provider = self._get_provider(data.provider)
            customer = await provider.create_customer(
                email=data.email,
                name=data.name,
                metadata=data.metadata,
            )

            return CustomerResponse(
                id=customer.id,
                email=customer.email,
                name=customer.name,
                provider=customer.provider,
                metadata=customer.metadata,
                created_at=customer.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def get_customer(
        self,
        request: HttpRequest,
        customer_id: str,
        provider: ProviderType | None = None,
    ) -> CustomerResponse | BillingErrorResponse:
        """Get customer by ID."""
        try:
            billing_provider = self._get_provider(provider)
            customer = await billing_provider.get_customer(customer_id)

            if not customer:
                return BillingErrorResponse(
                    error="Customer not found",
                    code="not_found",
                )

            return CustomerResponse(
                id=customer.id,
                email=customer.email,
                name=customer.name,
                provider=customer.provider,
                metadata=customer.metadata,
                created_at=customer.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def update_customer(
        self,
        request: HttpRequest,
        customer_id: str,
        data: CustomerUpdate,
        provider: ProviderType | None = None,
    ) -> CustomerResponse | BillingErrorResponse:
        """Update customer details."""
        try:
            billing_provider = self._get_provider(provider)
            customer = await billing_provider.update_customer(
                customer_id=customer_id,
                email=data.email,
                name=data.name,
                metadata=data.metadata,
            )

            return CustomerResponse(
                id=customer.id,
                email=customer.email,
                name=customer.name,
                provider=customer.provider,
                metadata=customer.metadata,
                created_at=customer.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    # -------------------------------------------------------------------------
    # Subscriptions
    # -------------------------------------------------------------------------

    async def list_subscriptions(
        self,
        request: HttpRequest,
        customer_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
        provider: ProviderType | None = None,
    ) -> SubscriptionListResponse | BillingErrorResponse:
        """List subscriptions with optional filtering."""
        try:
            from django_matt.billing.providers.base import SubscriptionStatus as SubStatus

            billing_provider = self._get_provider(provider)

            status_enum = None
            if status:
                try:
                    status_enum = SubStatus(status)
                except ValueError:
                    pass

            subscriptions = await billing_provider.list_subscriptions(
                customer_id=customer_id,
                status=status_enum,
                limit=limit,
            )

            items = [
                SubscriptionResponse(
                    id=s.id,
                    customer_id=s.customer_id,
                    status=s.status,
                    provider=s.provider,
                    price_id=s.price_id,
                    product_id=s.product_id,
                    quantity=s.quantity,
                    current_period_start=s.current_period_start,
                    current_period_end=s.current_period_end,
                    cancel_at_period_end=s.cancel_at_period_end,
                    canceled_at=s.canceled_at,
                    trial_start=s.trial_start,
                    trial_end=s.trial_end,
                    metadata=s.metadata,
                    created_at=s.created_at,
                )
                for s in subscriptions
            ]

            return SubscriptionListResponse(items=items, total=len(items))
        except BillingError as e:
            return self._error_response(e)

    async def create_subscription(
        self,
        request: HttpRequest,
        data: SubscriptionCreate,
    ) -> SubscriptionResponse | BillingErrorResponse:
        """Create a new subscription."""
        try:
            provider = self._get_provider(data.provider)

            # Get or create customer
            customer_id = data.customer_id
            if not customer_id and data.customer_email:
                customer, _ = await provider.get_or_create_customer(
                    email=data.customer_email,
                )
                customer_id = customer.id

            if not customer_id:
                return BillingErrorResponse(
                    error="Either customer_id or customer_email is required",
                    code="validation_error",
                )

            subscription = await provider.create_subscription(
                customer_id=customer_id,
                price_id=data.price_id,
                quantity=data.quantity,
                trial_period_days=data.trial_period_days,
                metadata=data.metadata,
            )

            return SubscriptionResponse(
                id=subscription.id,
                customer_id=subscription.customer_id,
                status=subscription.status,
                provider=subscription.provider,
                price_id=subscription.price_id,
                product_id=subscription.product_id,
                quantity=subscription.quantity,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                canceled_at=subscription.canceled_at,
                trial_start=subscription.trial_start,
                trial_end=subscription.trial_end,
                metadata=subscription.metadata,
                created_at=subscription.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def get_subscription(
        self,
        request: HttpRequest,
        subscription_id: str,
        provider: ProviderType | None = None,
    ) -> SubscriptionResponse | BillingErrorResponse:
        """Get subscription by ID."""
        try:
            billing_provider = self._get_provider(provider)
            subscription = await billing_provider.get_subscription(subscription_id)

            if not subscription:
                return BillingErrorResponse(
                    error="Subscription not found",
                    code="not_found",
                )

            return SubscriptionResponse(
                id=subscription.id,
                customer_id=subscription.customer_id,
                status=subscription.status,
                provider=subscription.provider,
                price_id=subscription.price_id,
                product_id=subscription.product_id,
                quantity=subscription.quantity,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                canceled_at=subscription.canceled_at,
                trial_start=subscription.trial_start,
                trial_end=subscription.trial_end,
                metadata=subscription.metadata,
                created_at=subscription.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def update_subscription(
        self,
        request: HttpRequest,
        subscription_id: str,
        data: SubscriptionUpdate,
        provider: ProviderType | None = None,
    ) -> SubscriptionResponse | BillingErrorResponse:
        """Update subscription details."""
        try:
            billing_provider = self._get_provider(provider)
            subscription = await billing_provider.update_subscription(
                subscription_id=subscription_id,
                price_id=data.price_id,
                quantity=data.quantity,
                metadata=data.metadata,
            )

            return SubscriptionResponse(
                id=subscription.id,
                customer_id=subscription.customer_id,
                status=subscription.status,
                provider=subscription.provider,
                price_id=subscription.price_id,
                product_id=subscription.product_id,
                quantity=subscription.quantity,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                canceled_at=subscription.canceled_at,
                trial_start=subscription.trial_start,
                trial_end=subscription.trial_end,
                metadata=subscription.metadata,
                created_at=subscription.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def cancel_subscription(
        self,
        request: HttpRequest,
        subscription_id: str,
        data: SubscriptionCancel,
        provider: ProviderType | None = None,
    ) -> SubscriptionResponse | BillingErrorResponse:
        """Cancel a subscription."""
        try:
            billing_provider = self._get_provider(provider)
            subscription = await billing_provider.cancel_subscription(
                subscription_id=subscription_id,
                cancel_at_period_end=data.cancel_at_period_end,
            )

            return SubscriptionResponse(
                id=subscription.id,
                customer_id=subscription.customer_id,
                status=subscription.status,
                provider=subscription.provider,
                price_id=subscription.price_id,
                product_id=subscription.product_id,
                quantity=subscription.quantity,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                canceled_at=subscription.canceled_at,
                trial_start=subscription.trial_start,
                trial_end=subscription.trial_end,
                metadata=subscription.metadata,
                created_at=subscription.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    async def resume_subscription(
        self,
        request: HttpRequest,
        subscription_id: str,
        provider: ProviderType | None = None,
    ) -> SubscriptionResponse | BillingErrorResponse:
        """Resume a canceled subscription (if cancel_at_period_end was True)."""
        try:
            billing_provider = self._get_provider(provider)
            subscription = await billing_provider.resume_subscription(subscription_id)

            return SubscriptionResponse(
                id=subscription.id,
                customer_id=subscription.customer_id,
                status=subscription.status,
                provider=subscription.provider,
                price_id=subscription.price_id,
                product_id=subscription.product_id,
                quantity=subscription.quantity,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                cancel_at_period_end=subscription.cancel_at_period_end,
                canceled_at=subscription.canceled_at,
                trial_start=subscription.trial_start,
                trial_end=subscription.trial_end,
                metadata=subscription.metadata,
                created_at=subscription.created_at,
            )
        except BillingError as e:
            return self._error_response(e)

    # -------------------------------------------------------------------------
    # Billing Portal
    # -------------------------------------------------------------------------

    async def create_portal_session(
        self,
        request: HttpRequest,
        data: BillingPortalCreate,
    ) -> BillingPortalResponse | BillingErrorResponse:
        """
        Create a billing portal session for customer self-service.

        The portal allows customers to:
        - Update payment methods
        - View invoices
        - Cancel subscriptions
        - Update billing information
        """
        try:
            provider = self._get_provider(data.provider)
            url = await provider.create_billing_portal_session(
                customer_id=data.customer_id,
                return_url=data.return_url,
            )

            return BillingPortalResponse(url=url)
        except NotImplementedError:
            return BillingErrorResponse(
                error="Billing portal is not supported by this provider",
                code="not_supported",
            )
        except BillingError as e:
            return self._error_response(e)

    # -------------------------------------------------------------------------
    # Invoices
    # -------------------------------------------------------------------------

    async def list_invoices(
        self,
        request: HttpRequest,
        customer_id: str | None = None,
        subscription_id: str | None = None,
        status: str | None = None,
        limit: int = 10,
        provider: ProviderType | None = None,
    ) -> InvoiceListResponse | BillingErrorResponse:
        """List invoices with optional filtering."""
        try:
            billing_provider = self._get_provider(provider)
            invoices = await billing_provider.list_invoices(
                customer_id=customer_id,
                subscription_id=subscription_id,
                status=status,
                limit=limit,
            )

            items = [
                InvoiceResponse(
                    id=i.id,
                    customer_id=i.customer_id,
                    subscription_id=i.subscription_id,
                    provider=i.provider,
                    status=i.status,
                    currency=i.currency,
                    amount_due=i.amount_due,
                    amount_paid=i.amount_paid,
                    amount_remaining=i.amount_remaining,
                    invoice_pdf=i.invoice_pdf,
                    hosted_invoice_url=i.hosted_invoice_url,
                    due_date=i.due_date,
                    paid_at=i.paid_at,
                    created_at=i.created_at,
                )
                for i in invoices
            ]

            return InvoiceListResponse(items=items, total=len(items))
        except BillingError as e:
            return self._error_response(e)

    async def get_invoice(
        self,
        request: HttpRequest,
        invoice_id: str,
        provider: ProviderType | None = None,
    ) -> InvoiceResponse | BillingErrorResponse:
        """Get invoice by ID."""
        try:
            billing_provider = self._get_provider(provider)
            invoice = await billing_provider.get_invoice(invoice_id)

            if not invoice:
                return BillingErrorResponse(
                    error="Invoice not found",
                    code="not_found",
                )

            return InvoiceResponse(
                id=invoice.id,
                customer_id=invoice.customer_id,
                subscription_id=invoice.subscription_id,
                provider=invoice.provider,
                status=invoice.status,
                currency=invoice.currency,
                amount_due=invoice.amount_due,
                amount_paid=invoice.amount_paid,
                amount_remaining=invoice.amount_remaining,
                invoice_pdf=invoice.invoice_pdf,
                hosted_invoice_url=invoice.hosted_invoice_url,
                due_date=invoice.due_date,
                paid_at=invoice.paid_at,
                created_at=invoice.created_at,
            )
        except BillingError as e:
            return self._error_response(e)


class WebhookController:
    """
    Controller for handling billing webhooks.

    Usage:
        from django_matt.billing import WebhookController

        api.register_controller(WebhookController, prefix="/billing/webhooks")

    Endpoints:
        POST /billing/webhooks/stripe  - Stripe webhook
        POST /billing/webhooks/paypal  - PayPal webhook
        POST /billing/webhooks/polar   - Polar webhook
    """

    prefix = "billing/webhooks"
    tags = ["Billing Webhooks"]

    async def handle_stripe_webhook(self, request: HttpRequest) -> HttpResponse:
        """Handle Stripe webhook events."""
        return await self._handle_webhook(request, "stripe", "stripe-signature")

    async def handle_paypal_webhook(self, request: HttpRequest) -> HttpResponse:
        """Handle PayPal webhook events."""
        # PayPal uses multiple headers for verification
        signature = request.headers.get("paypal-transmission-sig", "")
        return await self._handle_webhook(
            request, "paypal", signature_header=None, signature=signature
        )

    async def handle_polar_webhook(self, request: HttpRequest) -> HttpResponse:
        """Handle Polar webhook events."""
        return await self._handle_webhook(request, "polar", "x-polar-signature")

    async def _handle_webhook(
        self,
        request: HttpRequest,
        provider_name: ProviderType,
        signature_header: str | None,
        signature: str | None = None,
    ) -> HttpResponse:
        """Generic webhook handler."""
        from django_matt.billing.models import WebhookEvent as WebhookEventModel

        try:
            provider = get_provider(provider_name)

            # Get signature
            if signature is None and signature_header:
                signature = request.headers.get(signature_header, "")

            if not signature:
                logger.warning(f"Missing webhook signature for {provider_name}")
                return HttpResponse(status=400)

            # Get raw body
            payload = request.body

            # Verify and parse
            event = await provider.verify_webhook(payload, signature)

            # Log the event
            webhook_event, created = await WebhookEventModel.objects.aget_or_create(
                provider=provider_name,
                provider_event_id=event.id,
                defaults={
                    "event_type": event.type,
                    "payload": event.data,
                },
            )

            if not created and webhook_event.processed:
                # Already processed, return success
                logger.info(f"Webhook event {event.id} already processed")
                return HttpResponse(status=200)

            # Fire webhook_received signal (before processing)
            from django_matt.billing.signals import webhook_received

            await sync_to_async(webhook_received.send)(
                sender=self.__class__,
                event_id=event.id,
                event_type=event.type,
                provider=provider_name,
                raw_data=event.data,
            )

            # Process the event
            try:
                await self._process_webhook_event(provider_name, event)
                await webhook_event.amark_processed()
            except Exception as e:
                logger.exception(f"Error processing webhook event {event.id}")
                await webhook_event.amark_processed(error=str(e))
                # Still return 200 to acknowledge receipt
                return HttpResponse(status=200)

            return HttpResponse(status=200)

        except BillingWebhookError as e:
            logger.warning(f"Webhook verification failed: {e}")
            return HttpResponse(status=400)
        except Exception as e:
            logger.exception(f"Unexpected webhook error: {e}")
            return HttpResponse(status=500)

    async def _process_webhook_event(
        self,
        provider_name: ProviderType,
        event: Any,
    ) -> None:
        """
        Process a verified webhook event.

        Override this method to add custom webhook handling logic.
        """
        provider = get_provider(provider_name)
        normalized_type = provider.normalize_webhook_type(event.type)

        logger.info(f"Processing webhook: {normalized_type} from {provider_name}")

        # Handle common events
        handlers = {
            "subscription.created": self._handle_subscription_created,
            "subscription.updated": self._handle_subscription_updated,
            "subscription.canceled": self._handle_subscription_canceled,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
            "checkout.completed": self._handle_checkout_completed,
        }

        handler = handlers.get(normalized_type)
        if handler:
            await handler(provider_name, event.data)
        else:
            logger.debug(f"Unhandled webhook type: {normalized_type}")

    async def _handle_subscription_created(
        self,
        provider: ProviderType,
        data: dict,
    ) -> None:
        """Handle subscription.created event — sync to local Subscription model."""
        from django_matt.billing.models import BillingCustomer, Subscription
        from django_matt.billing.signals import subscription_synced

        sub_id = data.get("id", "")
        customer_id = data.get("customer")

        # Resolve BillingCustomer by provider-specific customer ID
        billing_customer: BillingCustomer | None = None
        if customer_id:
            try:
                billing_customer = await BillingCustomer.objects.aget(
                    **{f"{provider}_customer_id": customer_id}
                )
            except BillingCustomer.DoesNotExist:
                logger.warning(
                    "BillingCustomer not found for %s customer_id=%s",
                    provider,
                    customer_id,
                )

        if billing_customer is None:
            logger.warning(
                "Cannot sync subscription %s: no BillingCustomer found", sub_id
            )
            return

        defaults: dict[str, Any] = {
            "status": data.get("status", Subscription.Status.ACTIVE),
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
            "current_period_start": _parse_timestamp(data.get("current_period_start")),
            "current_period_end": _parse_timestamp(data.get("current_period_end")),
            "customer": billing_customer,
        }

        subscription, _ = await Subscription.objects.aupdate_or_create(
            provider=provider,
            provider_subscription_id=sub_id,
            defaults=defaults,
        )

        await sync_to_async(subscription_synced.send)(
            sender=Subscription,
            subscription=subscription,
            provider=provider,
            event_type="created",
            raw_data=data,
        )
        logger.info("Subscription created/synced: %s", sub_id)

    async def _handle_subscription_updated(
        self,
        provider: ProviderType,
        data: dict,
    ) -> None:
        """Handle subscription.updated event — sync status to local Subscription model."""
        from django_matt.billing.models import BillingCustomer, Subscription
        from django_matt.billing.signals import subscription_synced

        sub_id = data.get("id", "")
        customer_id = data.get("customer")

        billing_customer: BillingCustomer | None = None
        if customer_id:
            try:
                billing_customer = await BillingCustomer.objects.aget(
                    **{f"{provider}_customer_id": customer_id}
                )
            except BillingCustomer.DoesNotExist:
                logger.warning(
                    "BillingCustomer not found for %s customer_id=%s",
                    provider,
                    customer_id,
                )

        defaults: dict[str, Any] = {
            "status": data.get("status", Subscription.Status.ACTIVE),
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
            "current_period_start": _parse_timestamp(data.get("current_period_start")),
            "current_period_end": _parse_timestamp(data.get("current_period_end")),
        }
        if billing_customer is not None:
            defaults["customer"] = billing_customer

        subscription, _ = await Subscription.objects.aupdate_or_create(
            provider=provider,
            provider_subscription_id=sub_id,
            defaults=defaults,
        )

        await sync_to_async(subscription_synced.send)(
            sender=Subscription,
            subscription=subscription,
            provider=provider,
            event_type="updated",
            raw_data=data,
        )
        logger.info("Subscription updated/synced: %s", sub_id)

    async def _handle_subscription_canceled(
        self,
        provider: ProviderType,
        data: dict,
    ) -> None:
        """Handle subscription.canceled event — set canceled status in local model."""
        from django_matt.billing.models import BillingCustomer, Subscription
        from django_matt.billing.signals import subscription_canceled, subscription_synced

        sub_id = data.get("id", "")
        customer_id = data.get("customer")

        billing_customer: BillingCustomer | None = None
        if customer_id:
            try:
                billing_customer = await BillingCustomer.objects.aget(
                    **{f"{provider}_customer_id": customer_id}
                )
            except BillingCustomer.DoesNotExist:
                logger.warning(
                    "BillingCustomer not found for %s customer_id=%s",
                    provider,
                    customer_id,
                )

        defaults: dict[str, Any] = {
            "status": Subscription.Status.CANCELED,
            "canceled_at": timezone.now(),
            "cancel_at_period_end": data.get("cancel_at_period_end", False),
            "current_period_start": _parse_timestamp(data.get("current_period_start")),
            "current_period_end": _parse_timestamp(data.get("current_period_end")),
        }
        if billing_customer is not None:
            defaults["customer"] = billing_customer

        subscription, _ = await Subscription.objects.aupdate_or_create(
            provider=provider,
            provider_subscription_id=sub_id,
            defaults=defaults,
        )

        await sync_to_async(subscription_synced.send)(
            sender=Subscription,
            subscription=subscription,
            provider=provider,
            event_type="canceled",
            raw_data=data,
        )
        await sync_to_async(subscription_canceled.send)(
            sender=Subscription,
            subscription=subscription,
            provider=provider,
            raw_data=data,
        )
        logger.info("Subscription canceled/synced: %s", sub_id)

    async def _handle_invoice_paid(
        self,
        provider: ProviderType,
        data: dict,
    ) -> None:
        """Handle invoice.paid event — update local Invoice model and fire signal."""
        from django_matt.billing.models import Invoice
        from django_matt.billing.signals import invoice_paid

        invoice_id = data.get("id", "")
        invoice_obj: Invoice | None = None
        if invoice_id:
            try:
                invoice_obj = await Invoice.objects.aget(
                    provider=provider,
                    provider_invoice_id=invoice_id,
                )
                invoice_obj.status = Invoice.Status.PAID
                invoice_obj.amount_paid = data.get("amount_paid", invoice_obj.amount_paid)
                invoice_obj.amount_remaining = 0
                invoice_obj.paid_at = timezone.now()
                await invoice_obj.asave(
                    update_fields=["status", "amount_paid", "amount_remaining", "paid_at", "updated_at"]
                )
            except Invoice.DoesNotExist:
                logger.warning(
                    "Invoice not found for %s provider_invoice_id=%s; skipping sync",
                    provider,
                    invoice_id,
                )

        await sync_to_async(invoice_paid.send)(
            sender=Invoice,
            invoice=invoice_obj,
            provider=provider,
            raw_data=data,
        )
        logger.info("Invoice paid/synced: %s", invoice_id)

    async def _handle_invoice_payment_failed(
        self,
        provider: ProviderType,
        data: dict,
    ) -> None:
        """Handle invoice.payment_failed event."""
        logger.info(f"Invoice payment failed: {data.get('id')}")
        # Send notification, update status
        # Override in subclass for custom logic

    async def _handle_checkout_completed(
        self,
        provider: ProviderType,
        data: dict,
    ) -> None:
        """Handle checkout.completed event."""
        logger.info(f"Checkout completed: {data.get('id')}")
        # Create subscription record, send welcome email
        # Override in subclass for custom logic
