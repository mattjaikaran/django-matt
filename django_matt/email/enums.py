"""
Email enums.
"""

from django.db.models import TextChoices


class EmailProvider(TextChoices):
    """Email provider backends."""

    SMTP = "smtp", "SMTP"
    SES = "ses", "Amazon SES"
    SENDGRID = "sendgrid", "SendGrid"
    MAILGUN = "mailgun", "Mailgun"
    POSTMARK = "postmark", "Postmark"
    MAILCHIMP = "mailchimp", "Mailchimp Transactional"
    CONSOLE = "console", "Console (Debug)"


class EmailStatus(TextChoices):
    """Email delivery status."""

    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    OPENED = "opened", "Opened"
    CLICKED = "clicked", "Clicked"
    BOUNCED = "bounced", "Bounced"
    COMPLAINED = "complained", "Complained"
    FAILED = "failed", "Failed"


class EmailType(TextChoices):
    """Type of email."""

    TRANSACTIONAL = "transactional", "Transactional"
    MARKETING = "marketing", "Marketing"
    NOTIFICATION = "notification", "Notification"


class BounceType(TextChoices):
    """Type of email bounce."""

    HARD = "hard", "Hard Bounce"
    SOFT = "soft", "Soft Bounce"
    UNDETERMINED = "undetermined", "Undetermined"
