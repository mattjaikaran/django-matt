"""
Amazon SES email provider.

Requires: pip install boto3
"""

from __future__ import annotations

import logging
from typing import Any

from django_matt.email.providers.base import EmailProviderBase, EmailResult

logger = logging.getLogger(__name__)


class SESProvider(EmailProviderBase):
    """
    Amazon Simple Email Service provider.

    Configuration via Django settings or environment:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_SES_REGION_NAME (default: us-east-1)
    - AWS_SES_CONFIGURATION_SET (optional)
    """

    name = "ses"

    def __init__(self):
        from django.conf import settings

        self.region = getattr(settings, "AWS_SES_REGION_NAME", "us-east-1")
        self.configuration_set = getattr(settings, "AWS_SES_CONFIGURATION_SET", None)
        self._client = None

    @property
    def client(self):
        """Lazy-load boto3 SES client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("ses", region_name=self.region)
            except ImportError:
                raise ImportError(
                    "boto3 is required for SES provider. "
                    "Install with: pip install boto3"
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
        """Send email via Amazon SES."""
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

            # Build destination
            destination = {"ToAddresses": to}
            if cc:
                destination["CcAddresses"] = cc
            if bcc:
                destination["BccAddresses"] = bcc

            # Build message body
            body = {}
            if text:
                body["Text"] = {"Data": text, "Charset": "UTF-8"}
            if html:
                body["Html"] = {"Data": html, "Charset": "UTF-8"}

            # Build message
            message = {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": body,
            }

            # Build request
            send_args: dict[str, Any] = {
                "Source": from_email,
                "Destination": destination,
                "Message": message,
            }

            if reply_to:
                send_args["ReplyToAddresses"] = [reply_to]

            if self.configuration_set:
                send_args["ConfigurationSetName"] = self.configuration_set

            # Add tags
            if tags or metadata:
                message_tags = []
                if tags:
                    for tag in tags[:10]:  # SES limit is 10 tags
                        message_tags.append({"Name": "tag", "Value": tag})
                if metadata:
                    tracking_id = metadata.get("tracking_id")
                    if tracking_id:
                        message_tags.append({
                            "Name": "tracking_id",
                            "Value": str(tracking_id),
                        })
                if message_tags:
                    send_args["Tags"] = message_tags

            # Handle attachments (requires raw email)
            if attachments:
                return self._send_raw_email(
                    to=to,
                    subject=subject,
                    from_email=from_email,
                    text=text,
                    html=html,
                    cc=cc,
                    bcc=bcc,
                    reply_to=reply_to,
                    attachments=attachments,
                )

            # Send
            response = self.client.send_email(**send_args)

            return EmailResult(
                success=True,
                message_id=response["MessageId"],
                provider=self.name,
                raw_response=response,
            )

        except Exception as e:
            logger.exception(f"SES send error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )

    def _send_raw_email(
        self,
        to: list[str],
        subject: str,
        from_email: str,
        text: str | None,
        html: str | None,
        cc: list[str] | None,
        bcc: list[str] | None,
        reply_to: str | None,
        attachments: list[dict[str, Any]],
    ) -> EmailResult:
        """Send raw email with attachments."""
        from email.mime.application import MIMEApplication
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        try:
            # Create multipart message
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = ", ".join(to)

            if cc:
                msg["Cc"] = ", ".join(cc)
            if reply_to:
                msg["Reply-To"] = reply_to

            # Add body
            body_part = MIMEMultipart("alternative")
            if text:
                body_part.attach(MIMEText(text, "plain", "utf-8"))
            if html:
                body_part.attach(MIMEText(html, "html", "utf-8"))
            msg.attach(body_part)

            # Add attachments
            for attachment in attachments:
                content = attachment["content"]
                if isinstance(content, str):
                    content = content.encode()

                part = MIMEApplication(content)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment.get("filename", "attachment"),
                )
                if "content_type" in attachment:
                    part.set_type(attachment["content_type"])
                msg.attach(part)

            # Collect all recipients
            destinations = list(to)
            if cc:
                destinations.extend(cc)
            if bcc:
                destinations.extend(bcc)

            # Send raw email
            response = self.client.send_raw_email(
                Source=from_email,
                Destinations=destinations,
                RawMessage={"Data": msg.as_string()},
            )

            return EmailResult(
                success=True,
                message_id=response["MessageId"],
                provider=self.name,
                raw_response=response,
            )

        except Exception as e:
            logger.exception(f"SES raw email error: {e}")
            return EmailResult(
                success=False,
                provider=self.name,
                error=str(e),
            )

    def send_bulk(
        self,
        messages: list[dict[str, Any]],
    ) -> list[EmailResult]:
        """Send bulk emails using SES bulk template API if possible."""
        # For now, fall back to individual sends
        # SES has send_bulk_templated_email for template-based bulk sending
        return super().send_bulk(messages)
