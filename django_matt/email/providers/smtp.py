"""
SMTP email provider.

Uses Django's built-in email backend.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.mail import EmailMultiAlternatives

from django_matt.email.providers.base import EmailProviderBase, EmailResult

logger = logging.getLogger(__name__)


class SMTPProvider(EmailProviderBase):
    """
    SMTP email provider using Django's email backend.

    Configuration via Django settings:
    - EMAIL_HOST
    - EMAIL_PORT
    - EMAIL_HOST_USER
    - EMAIL_HOST_PASSWORD
    - EMAIL_USE_TLS
    - EMAIL_USE_SSL
    """

    name = "smtp"

    def send(
        self,
        to: list[str],
        subject: str,
        from_email: str | None = None,
        text: str | None = None,
        html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EmailResult:
        """Send email via SMTP."""
        try:
            # Filter suppressed emails
            to = self.filter_suppressed(to)
            if not to:
                return EmailResult(
                    success=False,
                    provider=self.name,
                    error="All recipients are suppressed",
                )

            from_email = from_email or self.get_default_from_email()

            # Create message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text or "",
                from_email=from_email,
                to=to,
                cc=cc,
                bcc=bcc,
                reply_to=[reply_to] if reply_to else None,
                headers=headers,
            )

            # Add HTML alternative
            if html:
                msg.attach_alternative(html, "text/html")

            # Add attachments
            if attachments:
                for attachment in attachments:
                    if "content" in attachment:
                        msg.attach(
                            attachment.get("filename", "attachment"),
                            attachment["content"],
                            attachment.get("content_type", "application/octet-stream"),
                        )

            # Add custom headers for tracking
            if metadata:
                tracking_id = metadata.get("tracking_id")
                if tracking_id:
                    msg.extra_headers["X-Tracking-ID"] = tracking_id

            if tags:
                msg.extra_headers["X-Tags"] = ",".join(tags)

            # Send
            msg.send(fail_silently=False)

            # Generate a pseudo message ID (SMTP doesn't return one reliably)
            import uuid
            message_id = str(uuid.uuid4())

            return EmailResult(
                success=True,
                message_id=message_id,
                provider=self.name,
            )

        except Exception as e:
            logger.exception(f"SMTP send error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )
