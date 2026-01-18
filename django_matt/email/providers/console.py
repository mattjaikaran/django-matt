"""
Console email provider for development/debugging.

Prints emails to stdout instead of sending them.
"""
# ruff: noqa: T201

from __future__ import annotations

import logging
import uuid
from typing import Any

from django_matt.email.providers.base import EmailProviderBase, EmailResult

logger = logging.getLogger(__name__)


class ConsoleProvider(EmailProviderBase):
    """
    Console email provider for development.

    Prints email details to stdout for debugging.
    """

    name = "console"

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
        """Print email to console."""
        message_id = str(uuid.uuid4())
        from_email = from_email or self.get_default_from_email()

        separator = "=" * 60
        print(f"\n{separator}")
        print("📧 EMAIL (Console Provider)")
        print(separator)
        print(f"Message ID: {message_id}")
        print(f"From: {from_email}")
        print(f"To: {', '.join(to)}")

        if cc:
            print(f"CC: {', '.join(cc)}")
        if bcc:
            print(f"BCC: {', '.join(bcc)}")
        if reply_to:
            print(f"Reply-To: {reply_to}")

        print(f"Subject: {subject}")

        if headers:
            print(f"Headers: {headers}")

        if tags:
            print(f"Tags: {', '.join(tags)}")

        if metadata:
            print(f"Metadata: {metadata}")

        if attachments:
            print(f"Attachments: {len(attachments)} file(s)")
            for att in attachments:
                print(f"  - {att.get('filename', 'unnamed')} ({att.get('content_type', 'unknown')})")

        print(separator)

        if text:
            print("📝 TEXT BODY:")
            print("-" * 40)
            # Truncate very long text
            if len(text) > 2000:
                print(text[:2000])
                print(f"... (truncated, {len(text)} chars total)")
            else:
                print(text)
            print("-" * 40)

        if html:
            print("🌐 HTML BODY:")
            print("-" * 40)
            # Show just a preview for HTML
            html_preview = html[:500] if len(html) > 500 else html
            print(html_preview)
            if len(html) > 500:
                print(f"... (truncated, {len(html)} chars total)")
            print("-" * 40)

        print(f"{separator}\n")

        return EmailResult(
            success=True,
            message_id=message_id,
            provider=self.name,
        )
