from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("django_matt.plugins.clerk")


@dataclass(frozen=True, slots=True)
class ClerkConfig:
    publishable_key: str = ""
    secret_key: str = ""
    webhook_secret: str = ""
    jwks_url: str = ""
    api_base_url: str = "https://api.clerk.com/v1"
    auto_create_user: bool = True
    webhook_path: str = "/webhooks/clerk"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.secret_key:
            errors.append("MATT_CLERK.SECRET_KEY is required")
        if not self.jwks_url and not self.publishable_key:
            errors.append(
                "MATT_CLERK.JWKS_URL or MATT_CLERK.PUBLISHABLE_KEY is required"
            )
        return errors


_config: ClerkConfig | None = None


def get_clerk_config() -> ClerkConfig:
    global _config
    if _config is not None:
        return _config

    try:
        from django.conf import settings

        raw: dict[str, Any] = getattr(settings, "MATT_CLERK", {})
    except Exception:
        raw = {}

    _config = ClerkConfig(
        publishable_key=raw.get("PUBLISHABLE_KEY", ""),
        secret_key=raw.get("SECRET_KEY", ""),
        webhook_secret=raw.get("WEBHOOK_SECRET", ""),
        jwks_url=raw.get("JWKS_URL", ""),
        api_base_url=raw.get("API_BASE_URL", "https://api.clerk.com/v1"),
        auto_create_user=raw.get("AUTO_CREATE_USER", True),
        webhook_path=raw.get("WEBHOOK_PATH", "/webhooks/clerk"),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None
