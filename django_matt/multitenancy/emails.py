"""
Email utilities for multitenancy.

Handles invitation emails with configurable templates and subjects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django_matt.multitenancy.models import Invitation


class InvitationEmailConfig:
    """
    Invitation email configuration.

    Configure in Django settings:
        DJANGO_MATT_MULTITENANCY = {
            "INVITATION_EMAIL_SUBJECT": "You've been invited to join {organization}",
            "INVITATION_EMAIL_FROM": None,  # Uses DEFAULT_FROM_EMAIL
            "INVITATION_EMAIL_TEMPLATE_HTML": "multitenancy/invitation_email.html",
            "INVITATION_EMAIL_TEMPLATE_TEXT": "multitenancy/invitation_email.txt",
            "INVITATION_BASE_URL": "https://myapp.com",
            "INVITATION_ACCEPT_PATH": "/invitations/accept",
        }
    """

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_MULTITENANCY", {})

    @property
    def email_subject(self) -> str:
        return self._config.get(
            "INVITATION_EMAIL_SUBJECT",
            "You've been invited to join {organization}",
        )

    @property
    def email_from(self) -> str | None:
        return self._config.get("INVITATION_EMAIL_FROM") or getattr(
            settings, "DEFAULT_FROM_EMAIL", None
        )

    @property
    def email_template_html(self) -> str | None:
        return self._config.get("INVITATION_EMAIL_TEMPLATE_HTML")

    @property
    def email_template_text(self) -> str | None:
        return self._config.get("INVITATION_EMAIL_TEMPLATE_TEXT")

    @property
    def base_url(self) -> str | None:
        return self._config.get("INVITATION_BASE_URL")

    @property
    def accept_path(self) -> str:
        return self._config.get("INVITATION_ACCEPT_PATH", "/invitations/accept")


# Global config instance
invitation_email_config = InvitationEmailConfig()


def send_invitation_email(invitation: Invitation) -> bool:
    """
    Send an invitation email.

    Args:
        invitation: The Invitation model instance

    Returns:
        True if email was sent successfully, False otherwise

    Uses DJANGO_MATT_MULTITENANCY settings for configuration.
    If no template is configured, sends a simple plain text email.
    """
    config = invitation_email_config

    # Build the invitation URL
    base_url = config.base_url
    if base_url:
        accept_url = f"{base_url.rstrip('/')}{config.accept_path}?token={invitation.token}"
    else:
        accept_url = f"{config.accept_path}?token={invitation.token}"

    # Prepare context for templates
    context = {
        "invitation": invitation,
        "organization": invitation.organization,
        "team": invitation.team,
        "inviter": invitation.invited_by,
        "accept_url": accept_url,
        "role": invitation.role,
        "email": invitation.email,
    }

    # Prepare subject
    subject = config.email_subject.format(
        organization=invitation.organization.name,
    )

    # Try to render templates
    html_content = None
    text_content = None

    if config.email_template_html:
        try:
            html_content = render_to_string(config.email_template_html, context)
        except Exception:
            pass

    if config.email_template_text:
        try:
            text_content = render_to_string(config.email_template_text, context)
        except Exception:
            pass

    # Fallback to default plain text if no templates
    if not text_content:
        text_content = _default_invitation_text(context)

    # Send the email
    from_email = config.email_from
    if not from_email:
        return False

    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=from_email,
            recipient_list=[invitation.email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception:
        return False


def _default_invitation_text(context: dict) -> str:
    """Generate default plain text invitation email."""
    org_name = context["organization"].name
    inviter_name = ""
    if context["inviter"]:
        inviter_name = getattr(context["inviter"], "get_full_name", lambda: "")()
        if not inviter_name:
            inviter_name = getattr(context["inviter"], "email", "Someone")

    team_text = ""
    if context["team"]:
        team_text = f" and the {context['team'].name} team"

    return f"""Hello,

{inviter_name} has invited you to join {org_name}{team_text} as a {context["role"]}.

Click the link below to accept the invitation:
{context["accept_url"]}

This invitation will expire in 7 days.

If you didn't expect this invitation, you can ignore this email.

Thanks,
The {org_name} Team
"""


__all__ = [
    "InvitationEmailConfig",
    "invitation_email_config",
    "send_invitation_email",
]
