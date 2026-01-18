"""
SendGrid email provider.

Requires: pip install sendgrid
"""

from __future__ import annotations

import logging
from typing import Any

from django_matt.email.providers.base import EmailProviderBase, EmailResult

logger = logging.getLogger(__name__)


class SendGridProvider(EmailProviderBase):
    """
    SendGrid email provider.

    Configuration via Django settings:
    - SENDGRID_API_KEY
    """

    name = "sendgrid"

    def __init__(self):
        from django.conf import settings

        self.api_key = getattr(settings, "SENDGRID_API_KEY", None)
        self._client = None

    @property
    def client(self):
        """Lazy-load SendGrid client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "SENDGRID_API_KEY is required. "
                    "Set it in Django settings."
                )
            try:
                from sendgrid import SendGridAPIClient
                self._client = SendGridAPIClient(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "sendgrid is required for SendGrid provider. "
                    "Install with: pip install sendgrid"
                )
        return self._client

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
        """Send email via SendGrid."""
        try:
            import base64

            from sendgrid.helpers.mail import (
                Attachment,
                Bcc,
                Cc,
                Content,
                CustomArg,
                FileContent,
                FileName,
                FileType,
                Mail,
                ReplyTo,
                To,
            )

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
            message = Mail(
                from_email=from_email,
                to_emails=[To(email) for email in to],
                subject=subject,
            )

            # Add content
            if text:
                message.add_content(Content("text/plain", text))
            if html:
                message.add_content(Content("text/html", html))

            # Add CC/BCC
            if cc:
                for email in cc:
                    message.add_cc(Cc(email))
            if bcc:
                for email in bcc:
                    message.add_bcc(Bcc(email))

            # Add reply-to
            if reply_to:
                message.reply_to = ReplyTo(reply_to)

            # Add custom headers
            if headers:
                for key, value in headers.items():
                    message.add_header({key: value})

            # Add attachments
            if attachments:
                for att in attachments:
                    content = att["content"]
                    if isinstance(content, bytes):
                        content = base64.b64encode(content).decode()
                    elif isinstance(content, str) and not att.get("base64"):
                        content = base64.b64encode(content.encode()).decode()

                    attachment = Attachment(
                        FileContent(content),
                        FileName(att.get("filename", "attachment")),
                        FileType(att.get("content_type", "application/octet-stream")),
                    )
                    message.add_attachment(attachment)

            # Add categories (tags)
            if tags:
                for tag in tags[:10]:  # SendGrid limit
                    message.add_category(tag)

            # Add custom args (metadata)
            if metadata:
                for key, value in metadata.items():
                    message.add_custom_arg(CustomArg(key, str(value)))

            # Send
            response = self.client.send(message)

            # Extract message ID from headers
            message_id = ""
            if response.headers:
                message_id = response.headers.get("X-Message-Id", "")

            success = 200 <= response.status_code < 300

            return EmailResult(
                success=success,
                message_id=message_id,
                provider=self.name,
                error="" if success else f"Status {response.status_code}",
                raw_response={
                    "status_code": response.status_code,
                    "body": response.body,
                    "headers": dict(response.headers) if response.headers else {},
                },
            )

        except Exception as e:
            logger.exception(f"SendGrid send error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )

    def send_template(
        self,
        to: list[str],
        template_name: str,
        context: dict[str, Any] | None = None,
        from_email: str | None = None,
        **kwargs,
    ) -> EmailResult:
        """
        Send using SendGrid dynamic template.

        If template_name starts with 'd-', uses SendGrid's native template system.
        Otherwise, falls back to database template lookup.
        """
        if not template_name.startswith("d-"):
            return super().send_template(to, template_name, context, from_email, **kwargs)

        try:
            from sendgrid.helpers.mail import Mail, To

            # Filter suppressed
            to = self.filter_suppressed(to)
            if not to:
                return EmailResult(
                    success=False,
                    provider=self.name,
                    error="All recipients are suppressed",
                )

            from_email = from_email or self.get_default_from_email()

            message = Mail(
                from_email=from_email,
                to_emails=[To(email) for email in to],
            )
            message.template_id = template_name
            message.dynamic_template_data = context or {}

            response = self.client.send(message)

            message_id = ""
            if response.headers:
                message_id = response.headers.get("X-Message-Id", "")

            success = 200 <= response.status_code < 300

            return EmailResult(
                success=success,
                message_id=message_id,
                provider=self.name,
                error="" if success else f"Status {response.status_code}",
            )

        except Exception as e:
            logger.exception(f"SendGrid template send error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )
