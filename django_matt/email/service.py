"""
Email service.

High-level email sending API with tracking and templating.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from django_matt.email.enums import EmailStatus, EmailType
from django_matt.email.models import EmailMessage, EmailTemplate
from django_matt.email.providers import EmailProviderBase, get_provider

logger = logging.getLogger(__name__)


class EmailService:
    """
    High-level email service.

    Provides email sending with:
    - Automatic tracking
    - Template support
    - Suppression list handling
    - Retry logic
    - Scheduling
    """

    @staticmethod
    def send(
        to: str | list[str],
        subject: str,
        from_email: str | None = None,
        text: str | None = None,
        html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        user=None,
        email_type: EmailType = EmailType.TRANSACTIONAL,
        category: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        provider: EmailProviderBase | str | None = None,
        track: bool = True,
        scheduled_at=None,
    ) -> EmailMessage:
        """
        Send an email.

        Args:
            to: Recipient email(s)
            subject: Email subject
            from_email: Sender email
            text: Plain text body
            html: HTML body
            cc: CC recipients
            bcc: BCC recipients
            reply_to: Reply-to address
            attachments: List of attachment dicts
            user: Related user
            email_type: Type of email
            category: Category for analytics
            tags: Tags for categorization
            metadata: Custom metadata
            provider: Email provider to use
            track: Whether to track this email
            scheduled_at: When to send (None = now)

        Returns:
            EmailMessage record
        """
        # Normalize to list
        if isinstance(to, str):
            to = [to]

        # Get provider
        if isinstance(provider, str):
            provider = get_provider(provider)
        elif provider is None:
            provider = get_provider()

        # Get from email
        if not from_email:
            from_email = provider.get_default_from_email()

        # Create email record
        email = EmailMessage.objects.create(
            from_email=from_email,
            to_emails=to,
            cc_emails=cc or [],
            bcc_emails=bcc or [],
            reply_to=reply_to or "",
            subject=subject,
            text_body=text or "",
            html_body=html or "",
            email_type=email_type,
            category=category,
            tags=tags or [],
            user=user,
            metadata=metadata or {},
            status=EmailStatus.QUEUED if scheduled_at else EmailStatus.PENDING,
            scheduled_at=scheduled_at,
        )

        # Send immediately if not scheduled
        if not scheduled_at:
            EmailService._send_email(email, provider)

        return email

    @staticmethod
    def send_template(
        to: str | list[str],
        template_name: str,
        context: dict[str, Any] | None = None,
        from_email: str | None = None,
        user=None,
        **kwargs,
    ) -> EmailMessage:
        """
        Send an email using a template.

        Args:
            to: Recipient email(s)
            template_name: Template name
            context: Template context
            from_email: Sender email
            user: Related user
            **kwargs: Additional args passed to send()

        Returns:
            EmailMessage record
        """
        # Look up template
        try:
            template = EmailTemplate.objects.get(name=template_name, is_active=True)
        except EmailTemplate.DoesNotExist:
            raise ValueError(f"Template not found: {template_name}")

        # Render template
        subject, text, html = template.render(context)

        # Normalize to list
        if isinstance(to, str):
            to = [to]

        # Create email record with template info
        email = EmailMessage.objects.create(
            from_email=from_email or "",
            to_emails=to,
            subject=subject,
            text_body=text,
            html_body=html,
            template_name=template_name,
            template_context=context or {},
            email_type=template.email_type,
            category=template.category,
            user=user,
            status=EmailStatus.PENDING,
            **{k: v for k, v in kwargs.items() if k in [
                "cc", "bcc", "reply_to", "tags", "metadata"
            ]},
        )

        # Send
        EmailService._send_email(email, get_provider())

        return email

    @staticmethod
    def _send_email(email: EmailMessage, provider: EmailProviderBase) -> bool:
        """Actually send an email."""
        try:
            # Filter suppressed recipients
            valid_to = provider.filter_suppressed(email.to_emails)

            if not valid_to:
                email.status = EmailStatus.FAILED
                email.error_message = "All recipients are suppressed"
                email.save(update_fields=["status", "error_message"])
                return False

            # Update recipient list
            email.to_emails = valid_to
            email.save(update_fields=["to_emails"])

            # Send
            result = provider.send(
                to=valid_to,
                subject=email.subject,
                from_email=email.from_email,
                text=email.text_body or None,
                html=email.html_body or None,
                cc=email.cc_emails or None,
                bcc=email.bcc_emails or None,
                reply_to=email.reply_to or None,
                headers=email.headers or None,
                tags=email.tags or None,
                metadata={
                    "tracking_id": str(email.tracking_id),
                    **email.metadata,
                },
            )

            if result.success:
                email.mark_sent(
                    provider=result.provider,
                    message_id=result.message_id,
                )
                return True
            email.mark_failed(result.error)
            return False

        except Exception as e:
            logger.exception(f"Email send error: {e}")
            email.mark_failed(str(e))
            return False

    @staticmethod
    def send_bulk(
        emails: list[dict[str, Any]],
        provider: EmailProviderBase | str | None = None,
    ) -> list[EmailMessage]:
        """
        Send multiple emails.

        Args:
            emails: List of email dicts with same args as send()
            provider: Email provider to use

        Returns:
            List of EmailMessage records
        """
        if isinstance(provider, str):
            provider = get_provider(provider)
        elif provider is None:
            provider = get_provider()

        results = []
        for email_data in emails:
            email = EmailService.send(provider=provider, **email_data)
            results.append(email)

        return results

    @staticmethod
    def process_scheduled():
        """
        Process scheduled emails that are ready to send.

        Should be called periodically (e.g., via cron or Celery beat).
        """
        now = timezone.now()
        scheduled = EmailMessage.objects.filter(
            status=EmailStatus.QUEUED,
            scheduled_at__lte=now,
        )

        provider = get_provider()
        sent_count = 0

        for email in scheduled:
            if EmailService._send_email(email, provider):
                sent_count += 1

        return sent_count

    @staticmethod
    def retry_failed(max_retries: int = 3, retry_after_minutes: int = 5):
        """
        Retry failed emails.

        Args:
            max_retries: Maximum retry attempts
            retry_after_minutes: Minimum minutes between retries

        Returns:
            Number of emails retried
        """
        now = timezone.now()
        cutoff = now - timedelta(minutes=retry_after_minutes)

        failed = EmailMessage.objects.filter(
            status=EmailStatus.FAILED,
            retry_count__lt=max_retries,
        ).filter(
            # Only retry if last attempt was long enough ago
            models.Q(sent_at__lt=cutoff) | models.Q(sent_at__isnull=True)
        )

        provider = get_provider()
        retried = 0

        for email in failed:
            email.status = EmailStatus.PENDING
            email.save(update_fields=["status"])

            if EmailService._send_email(email, provider):
                retried += 1

        return retried

    @staticmethod
    def get_email_stats(
        start_date=None,
        end_date=None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """
        Get email statistics.

        Args:
            start_date: Start of date range
            end_date: End of date range
            category: Filter by category

        Returns:
            Statistics dict
        """
        from django.db.models import Count, Q

        qs = EmailMessage.objects.all()

        if start_date:
            qs = qs.filter(created_at__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__lte=end_date)
        if category:
            qs = qs.filter(category=category)

        stats = qs.aggregate(
            total=Count("id"),
            sent=Count("id", filter=Q(status__in=[
                EmailStatus.SENT,
                EmailStatus.DELIVERED,
                EmailStatus.OPENED,
                EmailStatus.CLICKED,
            ])),
            delivered=Count("id", filter=Q(status=EmailStatus.DELIVERED)),
            opened=Count("id", filter=Q(status=EmailStatus.OPENED)),
            clicked=Count("id", filter=Q(status=EmailStatus.CLICKED)),
            bounced=Count("id", filter=Q(status=EmailStatus.BOUNCED)),
            failed=Count("id", filter=Q(status=EmailStatus.FAILED)),
            pending=Count("id", filter=Q(status=EmailStatus.PENDING)),
        )

        # Calculate rates
        if stats["sent"] > 0:
            stats["delivery_rate"] = round(stats["delivered"] / stats["sent"] * 100, 2)
            stats["open_rate"] = round(stats["opened"] / stats["sent"] * 100, 2)
            stats["click_rate"] = round(stats["clicked"] / stats["sent"] * 100, 2)
            stats["bounce_rate"] = round(stats["bounced"] / stats["sent"] * 100, 2)
        else:
            stats["delivery_rate"] = 0
            stats["open_rate"] = 0
            stats["click_rate"] = 0
            stats["bounce_rate"] = 0

        return stats


# Import models for the retry_failed function
from django.db import models

# Convenience functions

def send_email(
    to: str | list[str],
    subject: str,
    **kwargs,
) -> EmailMessage:
    """Send an email. Shortcut for EmailService.send()."""
    return EmailService.send(to=to, subject=subject, **kwargs)


def send_template_email(
    to: str | list[str],
    template_name: str,
    context: dict[str, Any] | None = None,
    **kwargs,
) -> EmailMessage:
    """Send a template email. Shortcut for EmailService.send_template()."""
    return EmailService.send_template(
        to=to,
        template_name=template_name,
        context=context,
        **kwargs,
    )
