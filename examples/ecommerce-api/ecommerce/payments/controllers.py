"""API controllers for payments app."""

import json
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db import models
from django.http import HttpRequest
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import NotFoundAPIError, ValidationAPIError
from django_matt.permissions import IsAuthenticated

from ecommerce.orders.models import Order
from ecommerce.payments.models import Payment, PaymentWebhookLog, Refund
from ecommerce.payments.schemas import (
    CheckoutSessionCreateRequest,
    CheckoutSessionResponse,
    PaymentIntentCreateRequest,
    PaymentIntentResponse,
    PaymentListResponse,
    PaymentResponse,
    RefundCreateRequest,
    RefundResponse,
    WebhookResponse,
)
from ecommerce.payments.services import (
    create_checkout_session,
    create_payment_intent,
    create_refund,
    process_stripe_webhook,
)

# =============================================================================
# Payment Controller
# =============================================================================


class PaymentController(APIController):
    """Payment management controller."""

    prefix = "/payments"
    tags = ["Payments"]
    permission_classes = [IsAuthenticated]

    @staticmethod
    @jwt_required
    async def create_payment_intent(
        request, data: PaymentIntentCreateRequest
    ) -> PaymentIntentResponse:
        """Create a payment intent for an order."""
        order = await Order.objects.filter(id=data.order_id, user=request.user).afirst()

        if not order:
            raise NotFoundAPIError("Order not found")

        if order.status != Order.Status.PENDING:
            raise ValidationAPIError("Order is not in pending status")

        # Check if payment already exists
        existing_payment = await Payment.objects.filter(
            order=order, status__in=[Payment.Status.PENDING, Payment.Status.PROCESSING]
        ).afirst()

        if existing_payment and existing_payment.stripe_payment_intent_id:
            # Return existing payment intent
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY
            intent = stripe.PaymentIntent.retrieve(existing_payment.stripe_payment_intent_id)
            return PaymentIntentResponse(
                payment_id=existing_payment.id,
                client_secret=intent.client_secret,
                amount=existing_payment.amount,
                currency=existing_payment.currency,
                status=existing_payment.status,
            )

        # Create new payment intent
        result = await create_payment_intent(order, data.payment_method)

        return PaymentIntentResponse(
            payment_id=result["payment_id"],
            client_secret=result["client_secret"],
            amount=result["amount"],
            currency=result["currency"],
            status="pending",
        )

    @staticmethod
    @jwt_required
    async def create_checkout_session(
        request, data: CheckoutSessionCreateRequest
    ) -> CheckoutSessionResponse:
        """Create a Stripe checkout session."""
        order = await Order.objects.filter(id=data.order_id, user=request.user).afirst()

        if not order:
            raise NotFoundAPIError("Order not found")

        if order.status != Order.Status.PENDING:
            raise ValidationAPIError("Order is not in pending status")

        result = await create_checkout_session(
            order=order,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )

        return CheckoutSessionResponse(
            session_id=result["session_id"],
            url=result["url"],
        )

    @staticmethod
    @jwt_required
    async def list_payments(request) -> list[PaymentListResponse]:
        """List user's payments."""
        payments = (
            Payment.objects.filter(order__user=request.user)
            .select_related("order")
            .order_by("-created_at")
        )

        return [
            PaymentListResponse(
                id=p.id,
                order_id=p.order_id,
                order_number=p.order.order_number,
                status=p.status,
                payment_method=p.payment_method,
                amount=p.amount,
                currency=p.currency,
                card_brand=p.card_brand,
                card_last4=p.card_last4,
                paid_at=p.paid_at,
                created_at=p.created_at,
            )
            async for p in payments
        ]

    @staticmethod
    @jwt_required
    async def get_payment(request, payment_id: UUID) -> PaymentResponse:
        """Get payment details."""
        payment = await Payment.objects.filter(id=payment_id, order__user=request.user).afirst()

        if not payment:
            raise NotFoundAPIError("Payment not found")

        return PaymentResponse.model_validate(payment)

    @staticmethod
    @jwt_required
    async def request_refund(request, data: RefundCreateRequest) -> RefundResponse:
        """Request a refund."""
        payment = await Payment.objects.filter(
            id=data.payment_id, order__user=request.user
        ).afirst()

        if not payment:
            raise NotFoundAPIError("Payment not found")

        if payment.status != Payment.Status.SUCCEEDED:
            raise ValidationAPIError("Payment has not been completed")

        # Calculate refund amount
        amount = data.amount or payment.amount

        # Check if already fully refunded
        existing_refunds = await Refund.objects.filter(
            payment=payment, status=Refund.Status.SUCCEEDED
        ).aggregate(total=models.Sum("amount"))

        refunded_amount = existing_refunds.get("total") or Decimal("0.00")
        if refunded_amount >= payment.amount:
            raise ValidationAPIError("Payment has already been fully refunded")

        if amount > (payment.amount - refunded_amount):
            raise ValidationAPIError(
                f"Refund amount exceeds available amount (${payment.amount - refunded_amount})"
            )

        # Create refund
        refund = await create_refund(
            payment=payment,
            amount=amount,
            reason=data.reason,
            notes=data.notes,
            created_by=request.user,
        )

        return RefundResponse.model_validate(refund)

    @staticmethod
    @jwt_required
    async def list_refunds(request, payment_id: UUID) -> list[RefundResponse]:
        """List refunds for a payment."""
        payment = await Payment.objects.filter(id=payment_id, order__user=request.user).afirst()

        if not payment:
            raise NotFoundAPIError("Payment not found")

        refunds = Refund.objects.filter(payment=payment).order_by("-created_at")
        return [RefundResponse.model_validate(r) async for r in refunds]


# =============================================================================
# Webhook Controller
# =============================================================================


class WebhookController(APIController):
    """Payment webhook controller."""

    prefix = "/payments/webhooks"
    tags = ["Webhooks"]

    @staticmethod
    async def stripe_webhook(request: HttpRequest) -> WebhookResponse:
        """Handle Stripe webhooks."""
        payload = request.body
        sig_header = request.headers.get("Stripe-Signature", "")

        try:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY

            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return WebhookResponse(
                received=True,
                processed=False,
                message="Invalid payload",
            )
        except stripe.error.SignatureVerificationError:
            return WebhookResponse(
                received=True,
                processed=False,
                message="Invalid signature",
            )

        # Log webhook
        await PaymentWebhookLog.objects.acreate(
            provider="stripe",
            event_type=event.type,
            event_id=event.id,
            payload=json.loads(payload),
        )

        # Process webhook
        try:
            await process_stripe_webhook(event)
            return WebhookResponse(
                received=True,
                processed=True,
                message=f"Processed {event.type}",
            )
        except Exception as e:
            # Log error but still return 200 to prevent retries
            await PaymentWebhookLog.objects.filter(event_id=event.id).aupdate(error_message=str(e))
            return WebhookResponse(
                received=True,
                processed=False,
                message=str(e),
            )
