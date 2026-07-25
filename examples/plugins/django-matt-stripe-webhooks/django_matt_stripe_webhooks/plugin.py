from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django_matt.plugins import MattPlugin

if TYPE_CHECKING:
    from django_matt.api import DjangoMattAPI

from django_matt_stripe_webhooks.config import get_stripe_config
from django_matt_stripe_webhooks.controllers import StripeWebhookController

logger = logging.getLogger("django_matt.plugins.stripe")


class StripeWebhooksPlugin(MattPlugin):
    name = "stripe_webhooks"
    version = "0.1.0"
    description = (
        "Stripe webhook integration — auto-registers endpoint, "
        "verifies signatures, emits framework events"
    )
    author = "Matt Jaikaran"
    django_matt_version = "0.9.0"
    settings_prefix = "MATT_STRIPE"

    def setup(self, api: DjangoMattAPI) -> None:
        config = get_stripe_config()
        errors = config.validate()
        if errors:
            for err in errors:
                logger.warning("Stripe plugin config: %s", err)

        # update controller prefix from config
        StripeWebhookController.prefix = config.webhook_path

        api.register_controller(StripeWebhookController)
        logger.info(
            "Stripe webhook endpoint registered at %s",
            config.webhook_path,
        )

    def on_startup(self) -> None:
        config = get_stripe_config()
        if config.api_key:
            import stripe

            stripe.api_key = config.api_key
            logger.info("Stripe API key configured")

    def get_settings_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "WEBHOOK_SECRET": {
                    "type": "string",
                    "description": "Stripe webhook signing secret (whsec_...)",
                },
                "API_KEY": {
                    "type": "string",
                    "description": "Stripe API secret key (sk_...)",
                },
                "WEBHOOK_PATH": {
                    "type": "string",
                    "default": "/webhooks/stripe",
                    "description": "URL path for the webhook endpoint",
                },
                "WEBHOOK_TOLERANCE": {
                    "type": "integer",
                    "default": 300,
                    "description": "Signature verification tolerance in seconds",
                },
            },
            "required": ["WEBHOOK_SECRET", "API_KEY"],
        }
