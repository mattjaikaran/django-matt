from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django_matt.plugins import MattPlugin

if TYPE_CHECKING:
    from django_matt.api import MattAPI

from django_matt_resend.config import get_resend_config

logger = logging.getLogger("django_matt.plugins.resend")


class ResendPlugin(MattPlugin):
    name = "resend"
    version = "0.1.0"
    description = "Resend email backend — transactional email via Resend API"
    author = "Matt Jaikaran"
    django_matt_version = "0.9.0"
    settings_prefix = "MATT_RESEND"

    def setup(self, api: MattAPI) -> None:
        config = get_resend_config()
        errors = config.validate()
        if errors:
            for err in errors:
                logger.warning("Resend plugin config: %s", err)

        # configure Django EMAIL_BACKEND if not already set
        try:
            from django.conf import settings

            current = getattr(settings, "EMAIL_BACKEND", "")
            if (
                not current
                or current
                == "django.core.mail.backends.smtp.EmailBackend"
            ):
                settings.EMAIL_BACKEND = (
                    "django_matt_resend.backend.ResendEmailBackend"
                )
                logger.info(
                    "Set EMAIL_BACKEND to ResendEmailBackend"
                )
        except Exception:
            pass

    def on_startup(self) -> None:
        config = get_resend_config()
        if config.api_key:
            import resend

            resend.api_key = config.api_key
            logger.info("Resend API key configured")

    def get_settings_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "API_KEY": {
                    "type": "string",
                    "description": "Resend API key (re_...)",
                },
                "DEFAULT_FROM": {
                    "type": "string",
                    "description": (
                        "Default sender email address "
                        "(e.g. noreply@yourdomain.com)"
                    ),
                },
                "REPLY_TO": {
                    "type": "string",
                    "description": "Default reply-to address",
                },
            },
            "required": ["API_KEY", "DEFAULT_FROM"],
        }
