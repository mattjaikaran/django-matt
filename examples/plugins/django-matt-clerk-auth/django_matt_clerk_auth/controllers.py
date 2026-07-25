from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import orjson
from django.http import HttpRequest, JsonResponse
from django_matt.core.controller import Controller

from django_matt_clerk_auth.config import get_clerk_config
from django_matt_clerk_auth.sync import sync_clerk_user_from_webhook

logger = logging.getLogger("django_matt.plugins.clerk")


class ClerkWebhookController(Controller):
    prefix = "/webhooks/clerk"
    tags = ["Clerk Webhooks"]
    permission_classes = []  # verified via Svix signature

    async def post(self, request: HttpRequest) -> JsonResponse:
        """Receive and process Clerk webhook events.

        Clerk uses Svix for webhook delivery. This endpoint verifies the
        signature, processes user lifecycle events, and emits on the
        django-matt event bus.
        """
        config = get_clerk_config()

        if not self._verify_signature(request, config.webhook_secret):
            return JsonResponse(
                {"status": "error", "detail": "Invalid signature"},
                status=400,
            )

        try:
            payload: dict[str, Any] = orjson.loads(request.body)
        except Exception:
            return JsonResponse(
                {"status": "error", "detail": "Invalid JSON payload"},
                status=400,
            )

        event_type = payload.get("type", "")
        logger.info("Received Clerk webhook: %s", event_type)

        # handle user lifecycle events
        if event_type.startswith("user."):
            await sync_clerk_user_from_webhook(payload)

        # emit on event bus
        await _emit_bus_event(event_type, payload)

        return JsonResponse({"status": "ok", "event_type": event_type}, status=200)

    @staticmethod
    def _verify_signature(request: HttpRequest, webhook_secret: str) -> bool:
        """Verify the Svix webhook signature.

        Clerk webhooks are signed by Svix using HMAC-SHA256. The
        signature components are in the svix-id, svix-timestamp, and
        svix-signature headers.
        """
        if not webhook_secret:
            logger.warning("Clerk webhook secret not configured, skipping verification")
            return True  # allow in dev mode

        svix_id = request.META.get("HTTP_SVIX_ID", "")
        svix_timestamp = request.META.get("HTTP_SVIX_TIMESTAMP", "")
        svix_signature = request.META.get("HTTP_SVIX_SIGNATURE", "")

        if not all([svix_id, svix_timestamp, svix_signature]):
            logger.warning("Missing Svix signature headers")
            return False

        # Svix signs: "{msg_id}.{timestamp}.{body}"
        body = request.body.decode("utf-8")
        signed_content = f"{svix_id}.{svix_timestamp}.{body}"

        # webhook_secret is base64-prefixed with "whsec_"
        import base64

        secret = webhook_secret
        if secret.startswith("whsec_"):
            secret = secret[6:]
        secret_bytes = base64.b64decode(secret)

        expected = hmac.new(
            secret_bytes,
            signed_content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected).decode("utf-8")

        # svix-signature may contain multiple signatures: "v1,sig1 v1,sig2"
        for sig in svix_signature.split(" "):
            if sig.startswith("v1,"):
                sig_value = sig[3:]
                if hmac.compare_digest(sig_value, expected_b64):
                    return True

        logger.warning("Clerk webhook signature mismatch")
        return False


async def _emit_bus_event(event_type: str, event_data: dict[str, Any]) -> None:
    try:
        from django_matt.events import Event, get_event_bus

        bus = get_event_bus()
        event = Event(
            event_type=f"clerk.{event_type}",
            metadata={"clerk_event": event_data},
        )
        await bus.emit(event)
    except Exception as exc:
        logger.debug("Event bus emission skipped: %s", exc)
