from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("django_matt.plugins.resend")


@dataclass(frozen=True, slots=True)
class ResendConfig:
    api_key: str = ""
    default_from: str = ""
    reply_to: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.api_key:
            errors.append("MATT_RESEND.API_KEY is required")
        if not self.default_from:
            errors.append(
                "MATT_RESEND.DEFAULT_FROM is required (e.g. noreply@yourdomain.com)"
            )
        return errors


_config: ResendConfig | None = None


def get_resend_config() -> ResendConfig:
    global _config
    if _config is not None:
        return _config

    try:
        from django.conf import settings

        raw: dict[str, Any] = getattr(settings, "MATT_RESEND", {})
    except Exception:
        raw = {}

    _config = ResendConfig(
        api_key=raw.get("API_KEY", ""),
        default_from=raw.get("DEFAULT_FROM", ""),
        reply_to=raw.get("REPLY_TO", ""),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None
