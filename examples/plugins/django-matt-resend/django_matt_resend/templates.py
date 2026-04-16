from __future__ import annotations

import logging
from typing import Any

import resend

from django_matt_resend.config import get_resend_config

logger = logging.getLogger("django_matt.plugins.resend")


async def send_template(
    template_id: str,
    to: list[str],
    data: dict[str, Any] | None = None,
    from_email: str | None = None,
    subject: str | None = None,
    reply_to: list[str] | None = None,
) -> dict[str, Any]:
    """Send an email using a Resend template.

    Args:
        template_id: The Resend template ID.
        to: List of recipient email addresses.
        data: Template variables to interpolate.
        from_email: Sender address. Falls back to DEFAULT_FROM.
        subject: Optional subject override.
        reply_to: Optional reply-to addresses.

    Returns:
        The Resend API response dict.
    """
    from asgiref.sync import sync_to_async

    return await sync_to_async(_send_template_sync)(
        template_id=template_id,
        to=to,
        data=data,
        from_email=from_email,
        subject=subject,
        reply_to=reply_to,
    )


def _send_template_sync(
    template_id: str,
    to: list[str],
    data: dict[str, Any] | None = None,
    from_email: str | None = None,
    subject: str | None = None,
    reply_to: list[str] | None = None,
) -> dict[str, Any]:
    """Synchronous implementation of send_template."""
    config = get_resend_config()
    resend.api_key = config.api_key

    params: dict[str, Any] = {
        "from_": from_email or config.default_from,
        "to": to,
        "template_id": template_id,
    }

    if data:
        params["data"] = data
    if subject:
        params["subject"] = subject

    effective_reply_to = reply_to
    if not effective_reply_to and config.reply_to:
        effective_reply_to = [config.reply_to]
    if effective_reply_to:
        params["reply_to"] = effective_reply_to

    result = resend.Emails.send(params)
    logger.debug(
        "Sent template email via Resend: template=%s to=%s id=%s",
        template_id,
        to,
        result.get("id", ""),
    )
    return result
