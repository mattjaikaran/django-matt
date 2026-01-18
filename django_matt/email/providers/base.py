"""
Base email provider class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailResult:
    """Result of sending an email."""

    success: bool
    message_id: str = ""
    provider: str = ""
    error: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)


class EmailProviderBase(ABC):
    """
    Abstract base class for email providers.

    All email providers must implement this interface.
    """

    name: str = "base"

    @abstractmethod
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
        """
        Send an email.

        Args:
            to: List of recipient email addresses
            subject: Email subject
            from_email: Sender email (uses default if not provided)
            text: Plain text body
            html: HTML body
            cc: CC recipients
            bcc: BCC recipients
            reply_to: Reply-to address
            headers: Custom headers
            attachments: List of attachment dicts with 'filename', 'content', 'content_type'
            tags: Tags for categorization
            metadata: Custom metadata

        Returns:
            EmailResult with success status and message ID
        """

    def send_template(
        self,
        to: list[str],
        template_name: str,
        context: dict[str, Any] | None = None,
        from_email: str | None = None,
        **kwargs,
    ) -> EmailResult:
        """
        Send an email using a template.

        Default implementation looks up template from database and renders it.
        Provider-specific implementations may use native template features.

        Args:
            to: List of recipient email addresses
            template_name: Name of the template
            context: Template context variables
            from_email: Sender email
            **kwargs: Additional arguments passed to send()

        Returns:
            EmailResult with success status and message ID
        """
        from django_matt.email.models import EmailTemplate

        try:
            template = EmailTemplate.objects.get(name=template_name, is_active=True)
        except EmailTemplate.DoesNotExist:
            return EmailResult(
                success=False,
                provider=self.name,
                error=f"Template not found: {template_name}",
            )

        subject, text, html = template.render(context)

        return self.send(
            to=to,
            subject=subject,
            from_email=from_email,
            text=text,
            html=html,
            **kwargs,
        )

    def send_bulk(
        self,
        messages: list[dict[str, Any]],
    ) -> list[EmailResult]:
        """
        Send multiple emails.

        Default implementation sends emails one by one.
        Providers may override with batch API support.

        Args:
            messages: List of message dicts with same args as send()

        Returns:
            List of EmailResult for each message
        """
        results = []
        for message in messages:
            result = self.send(**message)
            results.append(result)
        return results

    def get_default_from_email(self) -> str:
        """Get the default from email address."""
        from django.conf import settings

        return getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")

    def validate_email(self, email: str) -> bool:
        """Validate an email address format."""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    def is_suppressed(self, email: str) -> bool:
        """Check if an email is in the suppression list."""
        from django_matt.email.models import SuppressedEmail

        return SuppressedEmail.is_suppressed(email)

    def filter_suppressed(self, emails: list[str]) -> list[str]:
        """Filter out suppressed emails from a list."""
        return [e for e in emails if not self.is_suppressed(e)]
