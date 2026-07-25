from __future__ import annotations

import logging
from typing import Any

import stripe
from django.http import HttpRequest, JsonResponse
from django_matt.core.controller import Controller

from django_matt_stripe_webhooks.config import get_stripe_config
from django_matt_stripe_webhooks.handlers import dispatch_event
from django_matt_stripe_webhooks.schemas import (
    WebhookErrorResponse,
    WebhookResponse,
)

logger = logging.getLogger("django_matt.plugins.stripe")


class StripeWebhookController(Controller):
    prefix = "/webhooks/stripe"
    tags = ["Stripe Webhooks"]
    permission_classes = []  # webhooks are verified via signature, not auth

    async def post(self, request: HttpRequest) -> JsonResponse:
        """Receive and process a Stripe webhook event.

        Verifies the signature, parses the event, dispatches to
        registered handlers, and emits on the django-matt event bus.
        """
        config = get_stripe_config()
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        if not sig_header:
            resp = WebhookErrorResponse(detail="Missing Stripe-Signature header")
            return JsonResponse(resp.model_dump(), status=400)

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=config.webhook_secret,
                tolerance=config.webhook_tolerance,
            )
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("Stripe signature verification failed: %s", exc)
            resp = WebhookErrorResponse(detail="Invalid signature")
            return JsonResponse(resp.model_dump(), status=400)
        except ValueError as exc:
            logger.warning("Invalid Stripe payload: %s", exc)
            resp = WebhookErrorResponse(detail="Invalid payload")
            return JsonResponse(resp.model_dump(), status=400)

        event_type: str = event.get("type", "")
        event_id: str = event.get("id", "")
        event_data: dict[str, Any] = dict(event)

        logger.info("Received Stripe event: %s (%s)", event_type, event_id)

        # dispatch to registered handlers
        handler_count = await dispatch_event(event_type, event_data)

        # emit on the django-matt event bus
        await _emit_bus_event(event_type, event_data)

        logger.info(
            "Processed Stripe event %s — %d handler(s) invoked",
            event_id,
            handler_count,
        )

        resp = WebhookResponse(
            event_id=event_id,
            event_type=event_type,
        )
        return JsonResponse(resp.model_dump(), status=200)


async def _emit_bus_event(event_type: str, event_data: dict[str, Any]) -> None:
    """Emit the Stripe event on the django-matt event bus."""
    try:
        from django_matt.events import Event, get_event_bus

        bus = get_event_bus()
        event = Event(
            event_type=f"stripe.{event_type}",
            metadata={"stripe_event": event_data},
        )
        await bus.emit(event)
    except Exception as exc:
        logger.debug("Event bus emission skipped: %s", exc)
