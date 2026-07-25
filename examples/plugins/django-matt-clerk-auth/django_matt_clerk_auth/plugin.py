from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django_matt.plugins import MattPlugin

if TYPE_CHECKING:
    from django_matt.api import MattAPI

from django_matt_clerk_auth.config import get_clerk_config
from django_matt_clerk_auth.controllers import ClerkWebhookController
from django_matt_clerk_auth.middleware import ClerkAuthMiddleware

logger = logging.getLogger("django_matt.plugins.clerk")


class ClerkAuthPlugin(MattPlugin):
    name = "clerk_auth"
    version = "0.1.0"
    description = "Clerk authentication — JWT verification, user sync, webhook handling"
    author = "Matt Jaikaran"
    django_matt_version = "0.9.0"
    settings_prefix = "MATT_CLERK"

    def setup(self, api: MattAPI) -> None:
        config = get_clerk_config()
        errors = config.validate()
        if errors:
            for err in errors:
                logger.warning("Clerk plugin config: %s", err)

        ClerkWebhookController.prefix = config.webhook_path
        api.register_controller(ClerkWebhookController)
        logger.info(
            "Clerk webhook endpoint registered at %s",
            config.webhook_path,
        )

    def get_middleware(self) -> list:
        return [ClerkAuthMiddleware]

    def get_settings_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "PUBLISHABLE_KEY": {
                    "type": "string",
                    "description": "Clerk publishable key (pk_...)",
                },
                "SECRET_KEY": {
                    "type": "string",
                    "description": "Clerk secret key (sk_...)",
                },
                "WEBHOOK_SECRET": {
                    "type": "string",
                    "description": ("Clerk webhook signing secret (whsec_...)"),
                },
                "JWKS_URL": {
                    "type": "string",
                    "description": "JWKS endpoint URL for JWT verification",
                },
                "API_BASE_URL": {
                    "type": "string",
                    "default": "https://api.clerk.com/v1",
                },
                "AUTO_CREATE_USER": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "Auto-create Django user on first JWT verification"
                    ),
                },
                "WEBHOOK_PATH": {
                    "type": "string",
                    "default": "/webhooks/clerk",
                },
            },
            "required": ["SECRET_KEY"],
        }
