from __future__ import annotations

import logging
from typing import Any

import resend
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

from django_matt_resend.config import get_resend_config

logger = logging.getLogger("django_matt.plugins.resend")


class ResendEmailBackend(BaseEmailBackend):
    """Django email backend that sends via the Resend API.

    Supports both sync and async sending. Handles plain text,
    HTML, and attachments.
    """

    def __init__(
        self,
        api_key: str | None = None,
        fail_silently: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        config = get_resend_config()
        self._api_key = api_key or config.api_key
        self._default_from = config.default_from
        self._reply_to = config.reply_to
        self._opened = False

    def open(self) -> bool:
        if self._opened:
            return False
        resend.api_key = self._api_key
        self._opened = True
        return True

    def close(self) -> None:
        self._opened = False

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        if not email_messages:
            return 0

        self.open()
        sent_count = 0

        for message in email_messages:
            try:
                self._send_one(message)
                sent_count += 1
            except Exception as exc:
                if not self.fail_silently:
                    raise
                logger.error("Failed to send email via Resend: %s", exc)

        return sent_count

    async def asend_messages(
        self, email_messages: list[EmailMessage]
    ) -> int:
        """Async variant — Resend's Python SDK is sync, so we use
        sync_to_async under the hood. For true async, use httpx directly.
        """
        from asgiref.sync import sync_to_async

        return await sync_to_async(self.send_messages)(email_messages)

    def _send_one(self, message: EmailMessage) -> dict[str, Any]:
        """Send a single EmailMessage via the Resend API."""
        from_email = message.from_email or self._default_from

        params: dict[str, Any] = {
            "from_": from_email,
            "to": list(message.to),
            "subject": message.subject,
        }

        # handle HTML vs plain text
        if hasattr(message, "alternatives") and message.alternatives:
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    params["html"] = content
                    break
            # also include plain text body
            if message.body:
                params["text"] = message.body
        else:
            params["text"] = message.body

        # CC and BCC
        if message.cc:
            params["cc"] = list(message.cc)
        if message.bcc:
            params["bcc"] = list(message.bcc)

        # reply-to
        reply_to = None
        if message.reply_to:
            reply_to = list(message.reply_to)
        elif self._reply_to:
            reply_to = [self._reply_to]
        if reply_to:
            params["reply_to"] = reply_to

        # headers
        if message.extra_headers:
            params["headers"] = message.extra_headers

        # attachments
        attachments = self._build_attachments(message)
        if attachments:
            params["attachments"] = attachments

        result = resend.Emails.send(params)
        logger.debug(
            "Sent email via Resend: to=%s subject=%s id=%s",
            message.to,
            message.subject,
            result.get("id", ""),
        )
        return result

    @staticmethod
    def _build_attachments(
        message: EmailMessage,
    ) -> list[dict[str, Any]]:
        """Convert Django email attachments to Resend format."""
        if not message.attachments:
            return []

        result: list[dict[str, Any]] = []
        for attachment in message.attachments:
            if isinstance(attachment, tuple):
                filename, content, mimetype = attachment
                result.append(
                    {
                        "filename": filename or "attachment",
                        "content": content,
                        "type": mimetype or "application/octet-stream",
                    }
                )
            else:
                # MIMEBase attachment
                result.append(
                    {
                        "filename": (
                            attachment.get_filename() or "attachment"
                        ),
                        "content": attachment.get_payload(decode=True),
                        "type": attachment.get_content_type(),
                    }
                )

        return result
