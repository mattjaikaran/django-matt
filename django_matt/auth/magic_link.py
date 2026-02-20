"""
Magic Link Passwordless Authentication for Django Matt.

Provides secure, time-limited magic link token generation and verification
for passwordless authentication flows.

The implementation is stateless - tokens are self-contained signed tokens
that include all necessary information for verification.

Usage:
    from django_matt.auth import (
        create_magic_link_token,
        verify_magic_link_token,
        send_magic_link,
    )

    # Generate and send magic link
    token = create_magic_link_token(email="user@example.com")
    url = f"https://myapp.com/auth/verify?token={token}"
    send_magic_link(email, url)  # Uses configured email backend

    # Verify magic link (in verify endpoint)
    result = verify_magic_link_token(token)
    if result.valid:
        user = result.user
        tokens = create_token_pair(user)
"""

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string

from pydantic import BaseModel, Field


class MagicLinkConfig:
    """
    Magic Link configuration with sensible defaults.

    Configure in Django settings:
        DJANGO_MATT_MAGIC_LINK = {
            "SECRET_KEY": "your-secret-key",  # defaults to Django SECRET_KEY
            "TOKEN_LIFETIME": timedelta(minutes=15),  # Link expiration
            "MAX_USES": 1,  # Single-use by default
            "BASE_URL": "https://myapp.com",  # For generating full URLs
            "VERIFY_PATH": "/auth/magic-link/verify",  # Verification endpoint path
            "EMAIL_SUBJECT": "Your login link",
            "EMAIL_FROM": None,  # Uses DEFAULT_FROM_EMAIL
            "EMAIL_TEMPLATE": "auth/magic_link_email.html",  # Optional custom template
            "CREATE_USER_IF_NOT_EXISTS": False,  # Auto-create users
            "ALLOW_REGISTRATION": True,  # Allow new users via magic link
        }
    """

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_MAGIC_LINK", {})

    @property
    def secret_key(self) -> str:
        return self._config.get("SECRET_KEY", settings.SECRET_KEY)

    @property
    def token_lifetime(self) -> timedelta:
        return self._config.get("TOKEN_LIFETIME", timedelta(minutes=15))

    @property
    def max_uses(self) -> int:
        return self._config.get("MAX_USES", 1)

    @property
    def base_url(self) -> str | None:
        return self._config.get("BASE_URL")

    @property
    def verify_path(self) -> str:
        return self._config.get("VERIFY_PATH", "/auth/magic-link/verify")

    @property
    def email_subject(self) -> str:
        return self._config.get("EMAIL_SUBJECT", "Your login link")

    @property
    def email_from(self) -> str | None:
        return self._config.get("EMAIL_FROM") or getattr(settings, "DEFAULT_FROM_EMAIL", None)

    @property
    def email_template(self) -> str | None:
        return self._config.get("EMAIL_TEMPLATE")

    @property
    def create_user_if_not_exists(self) -> bool:
        return self._config.get("CREATE_USER_IF_NOT_EXISTS", False)

    @property
    def allow_registration(self) -> bool:
        return self._config.get("ALLOW_REGISTRATION", True)


# Global config instance
magic_link_config = MagicLinkConfig()


class MagicLinkTokenError(Exception):
    """Base exception for magic link token errors."""


class MagicLinkExpiredError(MagicLinkTokenError):
    """Raised when a magic link token has expired."""


class MagicLinkInvalidError(MagicLinkTokenError):
    """Raised when a magic link token is invalid."""


class MagicLinkUserNotFoundError(MagicLinkTokenError):
    """Raised when the user for a magic link doesn't exist."""


class MagicLinkAlreadyUsedError(MagicLinkTokenError):
    """Raised when a magic link token has already been used."""


class MagicLinkVerifyResult(BaseModel):
    """Result of magic link token verification."""

    valid: bool = Field(..., description="Whether the token is valid")
    email: str | None = Field(None, description="Email from token")
    user: Any | None = Field(None, description="Django user if found")
    user_created: bool = Field(False, description="Whether user was just created")
    error: str | None = Field(None, description="Error message if invalid")

    model_config = {"arbitrary_types_allowed": True}


def _generate_signature(data: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for data."""
    return hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_payload(payload: dict) -> str:
    """Encode payload to URL-safe base64."""
    json_str = json.dumps(payload, separators=(",", ":"))
    return base64.urlsafe_b64encode(json_str.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_payload(encoded: str) -> dict:
    """Decode URL-safe base64 payload."""
    # Add padding back
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding

    try:
        json_str = base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8")
        return json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        raise MagicLinkInvalidError(f"Invalid token format: {e}")


def _get_token_cache_key(token: str) -> str:
    """Generate a cache key for tracking used tokens.

    Uses SHA256 hash of the full token to avoid storing the raw token in cache.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"magic_link:used:{token_hash}"


def create_magic_link_token(
    email: str,
    extra_data: dict[str, Any] | None = None,
    lifetime: timedelta | None = None,
) -> str:
    """
    Create a secure magic link token for an email address.

    The token is self-contained and includes:
    - Email address
    - Expiration timestamp
    - Unique nonce
    - Optional extra data
    - HMAC signature

    Args:
        email: User's email address
        extra_data: Optional additional data to include in token
        lifetime: Override token lifetime (defaults to config)

    Returns:
        URL-safe token string
    """
    lifetime = lifetime or magic_link_config.token_lifetime
    now = datetime.now(UTC)
    exp = now + lifetime

    payload = {
        "email": email.lower().strip(),
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
        "nonce": secrets.token_urlsafe(16),
    }

    if extra_data:
        payload["data"] = extra_data

    # Encode payload
    encoded_payload = _encode_payload(payload)

    # Generate signature
    signature = _generate_signature(encoded_payload, magic_link_config.secret_key)

    # Combine: payload.signature
    return f"{encoded_payload}.{signature}"


def verify_magic_link_token(
    token: str,
    create_user: bool | None = None,
) -> MagicLinkVerifyResult:
    """
    Verify a magic link token and optionally get/create the user.

    Args:
        token: The magic link token to verify
        create_user: Override config for auto-creating users

    Returns:
        MagicLinkVerifyResult with verification status and user
    """
    if create_user is None:
        create_user = magic_link_config.create_user_if_not_exists

    try:
        # Split token
        parts = token.split(".")
        if len(parts) != 2:
            return MagicLinkVerifyResult(valid=False, error="Invalid token format")

        encoded_payload, signature = parts

        # Verify signature
        expected_signature = _generate_signature(encoded_payload, magic_link_config.secret_key)
        if not hmac.compare_digest(signature, expected_signature):
            return MagicLinkVerifyResult(valid=False, error="Invalid token signature")

        # Decode payload
        payload = _decode_payload(encoded_payload)

        # Check expiration
        exp = payload.get("exp", 0)
        now = datetime.now(UTC).timestamp()
        if now > exp:
            return MagicLinkVerifyResult(
                valid=False, email=payload.get("email"), error="Token has expired"
            )

        email = payload.get("email")
        if not email:
            return MagicLinkVerifyResult(valid=False, error="Token missing email")

        # Check one-time use: reject if token has already been consumed
        cache_key = _get_token_cache_key(token)
        if cache.get(cache_key):
            return MagicLinkVerifyResult(
                valid=False, email=email, error="Token has already been used"
            )

        # Get or create user
        User = get_user_model()
        user = None
        user_created = False

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            if create_user and magic_link_config.allow_registration:
                # Create new user
                username = email.split("@")[0]
                # Ensure unique username
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    is_active=True,
                )
                user_created = True
            elif not magic_link_config.allow_registration:
                return MagicLinkVerifyResult(
                    valid=False, email=email, error="User registration not allowed"
                )
            else:
                return MagicLinkVerifyResult(valid=False, email=email, error="User not found")

        # Check if user is active
        if user and not user.is_active:
            return MagicLinkVerifyResult(valid=False, email=email, error="User account is inactive")

        # Mark token as used. TTL = remaining seconds until token expiry.
        remaining_ttl = max(int(exp - now), 1)
        cache.set(cache_key, True, remaining_ttl)

        return MagicLinkVerifyResult(
            valid=True,
            email=email,
            user=user,
            user_created=user_created,
        )

    except MagicLinkTokenError as e:
        return MagicLinkVerifyResult(valid=False, error=str(e))
    except Exception as e:
        return MagicLinkVerifyResult(valid=False, error=f"Token verification failed: {e}")


def get_magic_link_payload(token: str) -> dict | None:
    """
    Get the payload from a magic link token without full verification.

    Useful for extracting email before verification.

    Args:
        token: The magic link token

    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        encoded_payload, _ = parts
        return _decode_payload(encoded_payload)
    except Exception:
        return None


def create_magic_link_url(
    email: str,
    base_url: str | None = None,
    verify_path: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> str:
    """
    Create a complete magic link URL.

    Args:
        email: User's email address
        base_url: Override base URL (e.g., "https://myapp.com")
        verify_path: Override verification path (e.g., "/auth/verify")
        extra_data: Optional extra data for token

    Returns:
        Complete magic link URL
    """
    base = base_url or magic_link_config.base_url
    if not base:
        raise ValueError(
            "Base URL not configured. Set DJANGO_MATT_MAGIC_LINK['BASE_URL'] "
            "or pass base_url parameter."
        )

    path = verify_path or magic_link_config.verify_path
    token = create_magic_link_token(email, extra_data)

    # Remove trailing slash from base and leading slash handling
    base = base.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path

    return f"{base}{path}?token={token}"


def send_magic_link(
    email: str,
    magic_link_url: str | None = None,
    subject: str | None = None,
    from_email: str | None = None,
    extra_context: dict[str, Any] | None = None,
    send_function: Callable | None = None,
) -> bool:
    """
    Send a magic link email to the user.

    Args:
        email: Recipient email address
        magic_link_url: The magic link URL (auto-generated if not provided)
        subject: Email subject (uses config default)
        from_email: Sender email (uses config default)
        extra_context: Additional context for email template
        send_function: Custom send function (for testing or custom email providers)

    Returns:
        True if email was sent successfully
    """
    # Generate URL if not provided
    if magic_link_url is None:
        try:
            magic_link_url = create_magic_link_url(email)
        except ValueError:
            # Base URL not configured, caller must provide URL
            raise ValueError(
                "Magic link URL required. Either configure DJANGO_MATT_MAGIC_LINK['BASE_URL'] "
                "or pass magic_link_url parameter."
            )

    subject = subject or magic_link_config.email_subject
    from_email = from_email or magic_link_config.email_from

    # Build email context
    context = {
        "magic_link_url": magic_link_url,
        "email": email,
        "expiration_minutes": int(magic_link_config.token_lifetime.total_seconds() / 60),
    }
    if extra_context:
        context.update(extra_context)

    # Render email content
    template = magic_link_config.email_template
    if template:
        try:
            html_content = render_to_string(template, context)
            plain_content = f"Click here to login: {magic_link_url}\n\nThis link expires in {context['expiration_minutes']} minutes."
        except Exception:
            # Template not found, use plain text
            html_content = None
            plain_content = f"Click here to login: {magic_link_url}\n\nThis link expires in {context['expiration_minutes']} minutes."
    else:
        # Default plain text email
        plain_content = (
            f"Hello!\n\n"
            f"Click the link below to login:\n\n"
            f"{magic_link_url}\n\n"
            f"This link will expire in {context['expiration_minutes']} minutes.\n\n"
            f"If you didn't request this link, you can safely ignore this email."
        )
        html_content = None

    # Send email
    if send_function:
        # Use custom send function
        return send_function(
            to_email=email,
            subject=subject,
            plain_content=plain_content,
            html_content=html_content,
            context=context,
        )

    try:
        send_mail(
            subject=subject,
            message=plain_content,
            from_email=from_email,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as e:
        # Log error but don't expose details
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send magic link email: {e}")
        return False


async def send_magic_link_async(
    email: str,
    magic_link_url: str | None = None,
    subject: str | None = None,
    from_email: str | None = None,
    extra_context: dict[str, Any] | None = None,
) -> bool:
    """
    Async version of send_magic_link.

    Uses Django's async email sending capabilities (Django 5.0+).
    """
    from django.core.mail import send_mail as django_send_mail

    from asgiref.sync import sync_to_async

    # Generate URL if not provided
    if magic_link_url is None:
        try:
            magic_link_url = create_magic_link_url(email)
        except ValueError:
            raise ValueError(
                "Magic link URL required. Either configure DJANGO_MATT_MAGIC_LINK['BASE_URL'] "
                "or pass magic_link_url parameter."
            )

    subject = subject or magic_link_config.email_subject
    from_email = from_email or magic_link_config.email_from

    # Build email context
    context = {
        "magic_link_url": magic_link_url,
        "email": email,
        "expiration_minutes": int(magic_link_config.token_lifetime.total_seconds() / 60),
    }
    if extra_context:
        context.update(extra_context)

    # Default plain text email
    plain_content = (
        f"Hello!\n\n"
        f"Click the link below to login:\n\n"
        f"{magic_link_url}\n\n"
        f"This link will expire in {context['expiration_minutes']} minutes.\n\n"
        f"If you didn't request this link, you can safely ignore this email."
    )

    try:
        await sync_to_async(django_send_mail)(
            subject=subject,
            message=plain_content,
            from_email=from_email,
            recipient_list=[email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send magic link email: {e}")
        return False


__all__ = [
    "MagicLinkAlreadyUsedError",
    "MagicLinkConfig",
    "MagicLinkExpiredError",
    "MagicLinkInvalidError",
    "MagicLinkTokenError",
    "MagicLinkUserNotFoundError",
    "MagicLinkVerifyResult",
    "create_magic_link_token",
    "create_magic_link_url",
    "get_magic_link_payload",
    "magic_link_config",
    "send_magic_link",
    "send_magic_link_async",
    "verify_magic_link_token",
]
