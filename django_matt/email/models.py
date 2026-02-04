"""
Email models.

Tracks email sending, delivery, and engagement.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models

from django_matt.email.enums import BounceType, EmailStatus, EmailType


class EmailMessageManager(models.Manager):
    """Custom manager for EmailMessage model."""

    def pending(self):
        """Get pending emails."""
        return self.filter(status=EmailStatus.PENDING)

    def queued(self):
        """Get queued emails."""
        return self.filter(status=EmailStatus.QUEUED)

    def sent(self):
        """Get sent emails."""
        return self.filter(
            status__in=[
                EmailStatus.SENT,
                EmailStatus.DELIVERED,
                EmailStatus.OPENED,
                EmailStatus.CLICKED,
            ]
        )

    def failed(self):
        """Get failed emails."""
        return self.filter(
            status__in=[
                EmailStatus.FAILED,
                EmailStatus.BOUNCED,
            ]
        )


class EmailMessage(models.Model):
    """
    Tracks individual email messages.

    Stores email content and delivery status for auditing and tracking.
    """

    # Unique tracking ID
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Sender and recipients
    from_email = models.EmailField()
    to_emails = models.JSONField(default=list)  # List of email addresses
    cc_emails = models.JSONField(default=list, blank=True)
    bcc_emails = models.JSONField(default=list, blank=True)
    reply_to = models.EmailField(blank=True)

    # Content
    subject = models.CharField(max_length=998)  # RFC 2822 limit
    text_body = models.TextField(blank=True)
    html_body = models.TextField(blank=True)

    # Template info
    template_name = models.CharField(max_length=255, blank=True)
    template_context = models.JSONField(default=dict, blank=True)

    # Classification
    email_type = models.CharField(
        max_length=20,
        choices=EmailType.choices,
        default=EmailType.TRANSACTIONAL,
    )
    category = models.CharField(max_length=100, blank=True)  # For filtering/analytics
    tags = models.JSONField(default=list, blank=True)

    # Related user (optional)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emails",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
        db_index=True,
    )

    # Provider info
    provider = models.CharField(max_length=50, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    headers = models.JSONField(default=dict, blank=True)  # Custom headers

    objects = EmailMessageManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["template_name"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"Email to {self.to_emails}: {self.subject[:50]}"

    def mark_sent(self, provider: str = "", message_id: str = "") -> None:
        """Mark email as sent."""
        from django.utils import timezone

        self.status = EmailStatus.SENT
        self.sent_at = timezone.now()
        if provider:
            self.provider = provider
        if message_id:
            self.provider_message_id = message_id
        self.save(update_fields=["status", "sent_at", "provider", "provider_message_id"])

    def mark_delivered(self) -> None:
        """Mark email as delivered."""
        from django.utils import timezone

        self.status = EmailStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at"])

    def mark_failed(self, error: str = "") -> None:
        """Mark email as failed."""
        self.status = EmailStatus.FAILED
        self.error_message = error
        self.retry_count += 1
        self.save(update_fields=["status", "error_message", "retry_count"])

    def mark_bounced(self, bounce_type: BounceType = BounceType.UNDETERMINED) -> None:
        """Mark email as bounced."""
        self.status = EmailStatus.BOUNCED
        self.metadata["bounce_type"] = bounce_type
        self.save(update_fields=["status", "metadata"])

    def schedule_retry(self, delay_seconds: int = 300) -> None:
        """Schedule a retry."""
        from datetime import timedelta

        from django.utils import timezone

        self.status = EmailStatus.QUEUED
        self.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)
        self.save(update_fields=["status", "next_retry_at"])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for sending."""
        return {
            "from_email": self.from_email,
            "to": self.to_emails,
            "cc": self.cc_emails if self.cc_emails else None,
            "bcc": self.bcc_emails if self.bcc_emails else None,
            "reply_to": self.reply_to if self.reply_to else None,
            "subject": self.subject,
            "text": self.text_body if self.text_body else None,
            "html": self.html_body if self.html_body else None,
            "headers": self.headers if self.headers else None,
            "tags": self.tags if self.tags else None,
            "metadata": {
                "tracking_id": str(self.tracking_id),
                **self.metadata,
            },
        }


class EmailEvent(models.Model):
    """
    Tracks email events (opens, clicks, bounces, etc.).

    Populated by webhook handlers from email providers.
    """

    email = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=50)  # open, click, bounce, etc.
    occurred_at = models.DateTimeField()

    # Event details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    url = models.URLField(blank=True)  # For click events

    # Bounce info
    bounce_type = models.CharField(
        max_length=20,
        choices=BounceType.choices,
        blank=True,
    )
    bounce_reason = models.TextField(blank=True)

    # Provider data
    provider_event_id = models.CharField(max_length=255, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["email", "event_type"]),
            models.Index(fields=["occurred_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} for {self.email}"


class EmailTemplate(models.Model):
    """
    Email template storage.

    Stores reusable email templates with versioning.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    # Content
    subject = models.CharField(max_length=998)
    text_body = models.TextField(blank=True)
    html_body = models.TextField()

    # Template settings
    email_type = models.CharField(
        max_length=20,
        choices=EmailType.choices,
        default=EmailType.TRANSACTIONAL,
    )
    category = models.CharField(max_length=100, blank=True)

    # Variables/schema
    variables = models.JSONField(
        default=list,
        blank=True,
        help_text="List of variable names used in template",
    )
    default_context = models.JSONField(default=dict, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Versioning
    version = models.PositiveIntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def render(self, context: dict[str, Any] | None = None) -> tuple[str, str, str]:
        """
        Render template with context.

        Returns (subject, text_body, html_body).
        """
        from django.template import Context, Template

        merged_context = {**self.default_context, **(context or {})}
        ctx = Context(merged_context)

        subject = Template(self.subject).render(ctx)
        text_body = Template(self.text_body).render(ctx) if self.text_body else ""
        html_body = Template(self.html_body).render(ctx)

        return subject, text_body, html_body


class SuppressedEmail(models.Model):
    """
    Email suppression list.

    Stores emails that should not receive messages (bounces, unsubscribes).
    """

    email = models.EmailField(unique=True)
    reason = models.CharField(
        max_length=50,
        choices=[
            ("bounce", "Bounced"),
            ("complaint", "Complaint"),
            ("unsubscribe", "Unsubscribed"),
            ("manual", "Manually Added"),
        ],
    )

    # Bounce info
    bounce_type = models.CharField(
        max_length=20,
        choices=BounceType.choices,
        blank=True,
    )

    # Source email that caused suppression
    source_email = models.ForeignKey(
        EmailMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # For soft bounces

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.reason})"

    @classmethod
    def is_suppressed(cls, email: str) -> bool:
        """Check if an email is suppressed."""
        from django.utils import timezone

        return (
            cls.objects.filter(
                email=email.lower(),
            )
            .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now()))
            .exists()
        )

    @classmethod
    def add_suppression(
        cls,
        email: str,
        reason: str,
        bounce_type: str = "",
        source_email: EmailMessage | None = None,
        expires_at=None,
    ) -> SuppressedEmail:
        """Add an email to the suppression list."""
        suppressed, created = cls.objects.update_or_create(
            email=email.lower(),
            defaults={
                "reason": reason,
                "bounce_type": bounce_type,
                "source_email": source_email,
                "expires_at": expires_at,
            },
        )
        return suppressed
