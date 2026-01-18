"""
Email providers.
"""

from django_matt.email.providers.base import EmailProviderBase
from django_matt.email.providers.console import ConsoleProvider
from django_matt.email.providers.mailgun import MailgunProvider
from django_matt.email.providers.sendgrid import SendGridProvider
from django_matt.email.providers.ses import SESProvider
from django_matt.email.providers.smtp import SMTPProvider

__all__ = [
    "EmailProviderBase",
    "SMTPProvider",
    "SESProvider",
    "SendGridProvider",
    "MailgunProvider",
    "ConsoleProvider",
    "get_provider",
]


def get_provider(name: str | None = None) -> EmailProviderBase:
    """
    Get an email provider by name.

    If name is None, returns the default provider from settings.
    """
    from django.conf import settings

    if name is None:
        name = getattr(settings, "EMAIL_PROVIDER", "smtp")

    providers = {
        "smtp": SMTPProvider,
        "ses": SESProvider,
        "sendgrid": SendGridProvider,
        "mailgun": MailgunProvider,
        "console": ConsoleProvider,
    }

    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(f"Unknown email provider: {name}")

    return provider_class()
