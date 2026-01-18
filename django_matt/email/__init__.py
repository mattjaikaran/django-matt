"""
Django Matt Email Service.

Full-featured email service with multiple provider support,
tracking, templates, and suppression lists.
"""

from django_matt.email.enums import (
    BounceType,
    EmailProvider,
    EmailStatus,
    EmailType,
)
from django_matt.email.models import (
    EmailEvent,
    EmailMessage,
    EmailTemplate,
    SuppressedEmail,
)
from django_matt.email.providers import (
    ConsoleProvider,
    EmailProviderBase,
    MailgunProvider,
    SendGridProvider,
    SESProvider,
    SMTPProvider,
    get_provider,
)
from django_matt.email.service import (
    EmailService,
    send_email,
    send_template_email,
)

__all__ = [
    # Models
    "EmailMessage",
    "EmailEvent",
    "EmailTemplate",
    "SuppressedEmail",
    # Enums
    "EmailProvider",
    "EmailStatus",
    "EmailType",
    "BounceType",
    # Providers
    "EmailProviderBase",
    "SMTPProvider",
    "SESProvider",
    "SendGridProvider",
    "MailgunProvider",
    "ConsoleProvider",
    "get_provider",
    # Service
    "EmailService",
    "send_email",
    "send_template_email",
]
