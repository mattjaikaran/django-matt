"""
Resend email provider.

Requires: uv add resend
"""

from __future__ import annotations

import logging
from typing import Any

from django_matt.email.providers.base import EmailProviderBase, EmailResult

logger = logging.getLogger(__name__)


class ResendProvider(EmailProviderBase):
    """
    Resend email provider.

    Configuration via Django settings:
    - RESEND_API_KEY: Your Resend API key (re_...)
    - DEFAULT_FROM_EMAIL: Default sender address

    Usage:
        # settings.py
        EMAIL_PROVIDER = "resend"
        RESEND_API_KEY = "re_..."
        DEFAULT_FROM_EMAIL = "hello@example.com"
    """

    name = "resend"

    def __init__(self):
        from django.conf import settings

        self.api_key = getattr(settings, "RESEND_API_KEY", None)
        self._client = None

    @property
    def client(self):
        """Lazy-load Resend client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("RESEND_API_KEY is required. Set it in Django settings.")
            try:
                import resend

                resend.api_key = self.api_key
                self._client = resend
            except ImportError:
                raise ImportError(
                    "resend is required for Resend provider. Install with: uv add resend"
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
        """Send email via Resend."""
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

            params: dict[str, Any] = {
                "from_": from_email,
                "to": to,
                "subject": subject,
            }

            if text:
                params["text"] = text
            if html:
                params["html"] = html
            if cc:
                params["cc"] = cc
            if bcc:
                params["bcc"] = bcc
            if reply_to:
                params["reply_to"] = reply_to
            if headers:
                params["headers"] = headers

            # Convert attachments to Resend format
            if attachments:
                resend_attachments = []
                for att in attachments:
                    resend_att: dict[str, Any] = {
                        "filename": att.get("filename", "attachment"),
                    }
                    content = att["content"]
                    if isinstance(content, str):
                        resend_att["content"] = content.encode()
                    elif isinstance(content, bytes):
                        resend_att["content"] = content
                    if att.get("content_type"):
                        resend_att["content_type"] = att["content_type"]
                    resend_attachments.append(resend_att)
                params["attachments"] = resend_attachments

            # Resend supports tags as list of dicts with name/value
            if tags:
                params["tags"] = [{"name": "tag", "value": tag} for tag in tags[:5]]

            response = self.client.Emails.send(params)

            message_id = response.get("id", "") if isinstance(response, dict) else ""

            return EmailResult(
                success=True,
                message_id=message_id,
                provider=self.name,
                raw_response=response if isinstance(response, dict) else {},
            )

        except Exception as e:
            logger.exception(f"Resend send error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )

    def send_bulk(
        self,
        messages: list[dict[str, Any]],
    ) -> list[EmailResult]:
        """
        Send multiple emails via Resend Batch API.

        Falls back to individual sends if batch fails.
        """
        try:
            batch_params = []
            for msg in messages:
                to = self.filter_suppressed(msg.get("to", []))
                if not to:
                    continue

                params: dict[str, Any] = {
                    "from_": msg.get("from_email") or self.get_default_from_email(),
                    "to": to,
                    "subject": msg.get("subject", ""),
                }

                if msg.get("text"):
                    params["text"] = msg["text"]
                if msg.get("html"):
                    params["html"] = msg["html"]
                if msg.get("cc"):
                    params["cc"] = msg["cc"]
                if msg.get("bcc"):
                    params["bcc"] = msg["bcc"]
                if msg.get("reply_to"):
                    params["reply_to"] = msg["reply_to"]

                batch_params.append(params)

            if not batch_params:
                return [
                    EmailResult(
                        success=False,
                        provider=self.name,
                        error="All recipients suppressed",
                    )
                ]

            response = self.client.Batch.send(batch_params)

            results = []
            data = response.get("data", []) if isinstance(response, dict) else []
            for item in data:
                results.append(
                    EmailResult(
                        success=True,
                        message_id=item.get("id", ""),
                        provider=self.name,
                    )
                )

            return results

        except Exception as e:
            logger.exception(f"Resend batch send error: {e}")
            # Fall back to individual sends
            return super().send_bulk(messages)

    def send_template(
        self,
        to: list[str],
        template_name: str,
        context: dict[str, Any] | None = None,
        from_email: str | None = None,
        **kwargs,
    ) -> EmailResult:
        """
        Send using a template.

        Resend doesn't have native templates, so always uses database templates.
        """
        return super().send_template(to, template_name, context, from_email, **kwargs)
