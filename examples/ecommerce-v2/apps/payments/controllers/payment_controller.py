import logging

from django.conf import settings
from django.http import HttpRequest
from django_matt.auth import jwt_required
from django_matt.core import APIController
from django_matt.core.errors import APIError, NotFoundAPIError

from apps.orders.models import Order
from apps.payments.schemas import CreatePaymentIntentSchema, PaymentIntentSchema

logger = logging.getLogger(__name__)


class PaymentController(APIController):
    prefix = "/payments"
    tags = ["Payments"]

    @staticmethod
    @jwt_required
    async def create_payment_intent(request, body: CreatePaymentIntentSchema) -> dict:
        """Create a Stripe PaymentIntent for an order."""
        order = await Order.objects.filter(
            id=body.order_id, user=request.user
        ).afirst()
        if not order:
            raise NotFoundAPIError("Order not found")

        if order.status != "pending":
            raise APIError(status_code=400, message="Order is not in pending status")

        amount = int(order.total * 100)  # Convert to cents

        try:
            import stripe

            stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=order.currency,
                metadata={"order_id": str(order.id)},
            )
            client_secret = intent.client_secret
            payment_intent_id = intent.id
        except ImportError:
            # Stripe not installed — return mock data for testing
            client_secret = f"pi_mock_secret_{order.id}"
            payment_intent_id = f"pi_mock_{order.id}"

        return PaymentIntentSchema(
            client_secret=client_secret,
            payment_intent_id=payment_intent_id,
            amount=amount,
            currency=order.currency,
        ).model_dump(mode="json")

    @staticmethod
    async def webhook(request: HttpRequest) -> dict:
        """Handle Stripe webhook events."""
        raw_body = request.body
        sig_header = request.headers.get("Stripe-Signature", "")

        try:
            import stripe

            stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
            webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

            event = stripe.Webhook.construct_event(
                raw_body, sig_header, webhook_secret
            )
        except ImportError:
            # Stripe not installed — parse raw body as JSON fallback
            import json

            try:
                event_data = json.loads(raw_body)
            except (json.JSONDecodeError, ValueError):
                raise APIError(status_code=400, message="Invalid payload")
            event = type(
                "Event",
                (),
                {
                    "type": event_data.get("type", ""),
                    "data": type(
                        "Data",
                        (),
                        {
                            "object": event_data.get("data", {}).get("object", {}),
                        },
                    )(),
                },
            )()
        except ValueError:
            raise APIError(status_code=400, message="Invalid payload")
        except Exception as e:
            if "SignatureVerificationError" in type(e).__name__:
                raise APIError(status_code=400, message="Invalid signature")
            raise

        event_type = event.type

        if event_type == "payment_intent.succeeded":
            payment_intent = event.data.object
            order_id = (
                payment_intent.get("metadata", {}).get("order_id")
                if isinstance(payment_intent, dict)
                else getattr(payment_intent, "metadata", {}).get("order_id")
            )
            if order_id:
                order = await Order.objects.filter(id=order_id).afirst()
                if order:
                    order.status = "confirmed"
                    await order.asave()
                    logger.info("Order %s confirmed via Stripe webhook", order_id)

        elif event_type == "payment_intent.payment_failed":
            payment_intent = event.data.object
            order_id = (
                payment_intent.get("metadata", {}).get("order_id")
                if isinstance(payment_intent, dict)
                else getattr(payment_intent, "metadata", {}).get("order_id")
            )
            logger.error(
                "Payment failed for order %s",
                order_id or "unknown",
            )

        return {"received": True}
