"""
Mailgun email provider.

Requires: uv add requests
"""

from __future__ import annotations

import logging
from typing import Any

from django_matt.email.providers.base import EmailProviderBase, EmailResult

logger = logging.getLogger(__name__)


class MailgunProvider(EmailProviderBase):
    """
    Mailgun email provider.

    Configuration via Django settings:
    - MAILGUN_API_KEY
    - MAILGUN_DOMAIN
    - MAILGUN_API_URL (optional, default: https://api.mailgun.net/v3)
    """

    name = "mailgun"

    def __init__(self):
        from django.conf import settings

        self.api_key = getattr(settings, "MAILGUN_API_KEY", None)
        self.domain = getattr(settings, "MAILGUN_DOMAIN", None)
        self.api_url = getattr(
            settings,
            "MAILGUN_API_URL",
            "https://api.mailgun.net/v3",
        )

    def _get_api_url(self) -> str:
        """Get the API URL for sending."""
        if not self.domain:
            raise ValueError("MAILGUN_DOMAIN is required. Set it in Django settings.")
        return f"{self.api_url}/{self.domain}/messages"

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
        """Send email via Mailgun."""
        try:
            import requests

            if not self.api_key:
                raise ValueError("MAILGUN_API_KEY is required. Set it in Django settings.")

            # Filter suppressed emails
            to = self.filter_suppressed(to)
            if not to:
                return EmailResult(
                    success=False,
                    provider=self.name,
                    error="All recipients are suppressed",
                )

            from_email = from_email or self.get_default_from_email()

            # Build request data
            data: dict[str, Any] = {
                "from": from_email,
                "to": to,
                "subject": subject,
            }

            if text:
                data["text"] = text
            if html:
                data["html"] = html
            if cc:
                data["cc"] = cc
            if bcc:
                data["bcc"] = bcc
            if reply_to:
                data["h:Reply-To"] = reply_to

            # Add custom headers
            if headers:
                for key, value in headers.items():
                    data[f"h:{key}"] = value

            # Add tags
            if tags:
                data["o:tag"] = tags[:3]  # Mailgun limit is 3 tags

            # Add tracking metadata
            if metadata:
                for key, value in metadata.items():
                    data[f"v:{key}"] = str(value)

            # Prepare files for attachments
            files = []
            if attachments:
                for att in attachments:
                    content = att["content"]
                    if isinstance(content, str):
                        content = content.encode()
                    files.append(
                        (
                            "attachment",
                            (
                                att.get("filename", "attachment"),
                                content,
                                att.get("content_type", "application/octet-stream"),
                            ),
                        )
                    )

            # Send request
            response = requests.post(
                self._get_api_url(),
                auth=("api", self.api_key),
                data=data,
                files=files if files else None,
                timeout=30,
            )

            response_data = response.json()
            success = response.status_code == 200

            return EmailResult(
                success=success,
                message_id=response_data.get("id", ""),
                provider=self.name,
                error="" if success else response_data.get("message", ""),
                raw_response=response_data,
            )

        except Exception as e:
            logger.exception(f"Mailgun send error: {e}")
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
        Send using Mailgun template.

        Uses Mailgun's stored templates feature.
        """
        try:
            import requests

            if not self.api_key:
                raise ValueError("MAILGUN_API_KEY is required")

            # Filter suppressed
            to = self.filter_suppressed(to)
            if not to:
                return EmailResult(
                    success=False,
                    provider=self.name,
                    error="All recipients are suppressed",
                )

            from_email = from_email or self.get_default_from_email()

            # Build request data
            data: dict[str, Any] = {
                "from": from_email,
                "to": to,
                "template": template_name,
            }

            # Add template variables
            if context:
                import orjson

                data["h:X-Mailgun-Variables"] = orjson.dumps(context).decode()

            response = requests.post(
                self._get_api_url(),
                auth=("api", self.api_key),
                data=data,
                timeout=30,
            )

            response_data = response.json()
            success = response.status_code == 200

            return EmailResult(
                success=success,
                message_id=response_data.get("id", ""),
                provider=self.name,
                error="" if success else response_data.get("message", ""),
                raw_response=response_data,
            )

        except Exception as e:
            logger.exception(f"Mailgun template send error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )
