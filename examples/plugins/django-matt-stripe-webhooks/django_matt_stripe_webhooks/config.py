from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("django_matt.plugins.stripe")


@dataclass(frozen=True, slots=True)
class StripeConfig:
    webhook_secret: str = ""
    api_key: str = ""
    webhook_path: str = "/webhooks/stripe"
    webhook_tolerance: int = 300

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.webhook_secret:
            errors.append(
                "MATT_STRIPE.WEBHOOK_SECRET is required for signature verification"
            )
        if not self.api_key:
            errors.append("MATT_STRIPE.API_KEY is required")
        return errors


_config: StripeConfig | None = None


def get_stripe_config() -> StripeConfig:
    global _config
    if _config is not None:
        return _config

    try:
        from django.conf import settings

        raw: dict[str, Any] = getattr(settings, "MATT_STRIPE", {})
    except Exception:
        raw = {}

    _config = StripeConfig(
        webhook_secret=raw.get("WEBHOOK_SECRET", ""),
        api_key=raw.get("API_KEY", ""),
        webhook_path=raw.get("WEBHOOK_PATH", "/webhooks/stripe"),
        webhook_tolerance=raw.get("WEBHOOK_TOLERANCE", 300),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None
