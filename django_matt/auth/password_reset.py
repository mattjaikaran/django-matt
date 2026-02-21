"""Password Reset for Django Matt.

Stateless HMAC-based password reset tokens. The token includes a digest of
the user's current password hash, so tokens auto-invalidate after password change.
"""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model

import orjson
from pydantic import BaseModel


class PasswordResetConfig:
    """Config from DJANGO_MATT_PASSWORD_RESET settings."""

    def __init__(self):
        self._config = getattr(settings, "DJANGO_MATT_PASSWORD_RESET", {})

    @property
    def secret_key(self) -> str:
        return self._config.get("SECRET_KEY", settings.SECRET_KEY)

    @property
    def token_lifetime(self) -> timedelta:
        return self._config.get("TOKEN_LIFETIME", timedelta(hours=1))

    @property
    def reset_url_template(self) -> str | None:
        """URL template with {token} placeholder, e.g. 'https://app.com/reset?token={token}'"""
        return self._config.get("RESET_URL_TEMPLATE")

    @property
    def email_callback(self) -> Callable | None:
        """Optional async callback: async def send(email, reset_url, token): ..."""
        return self._config.get("EMAIL_CALLBACK")

    @property
    def min_password_length(self) -> int:
        return self._config.get("MIN_PASSWORD_LENGTH", 8)


password_reset_config = PasswordResetConfig()


class PasswordResetResult(BaseModel):
    """Result of password reset token verification."""

    valid: bool
    email: str | None = None
    user: Any | None = None
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


def _generate_signature(data: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for data."""
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


def _encode_payload(payload: dict) -> str:
    """Encode payload to URL-safe base64."""
    json_bytes = orjson.dumps(payload)
    return base64.urlsafe_b64encode(json_bytes).decode().rstrip("=")


def _decode_payload(encoded: str) -> dict:
    """Decode URL-safe base64 payload."""
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    decoded_bytes = base64.urlsafe_b64decode(encoded.encode())
    return orjson.loads(decoded_bytes)


def _password_digest(password_hash: str) -> str:
    """Create a short digest of the user's password hash for token binding."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_password_reset_token(user) -> str:
    """Create a stateless HMAC password reset token.

    The token payload includes a digest of the user's current password hash,
    so it auto-invalidates when the password changes.

    Args:
        user: Django user instance.

    Returns:
        URL-safe token string in the format ``base64_payload.hex_signature``.
    """
    now = datetime.now(UTC)
    exp = now + password_reset_config.token_lifetime

    payload = {
        "sub": str(user.pk),
        "email": user.email,
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
        "purpose": "password_reset",
        "pwd": _password_digest(user.password),
        "nonce": secrets.token_urlsafe(16),
    }

    encoded = _encode_payload(payload)
    signature = _generate_signature(encoded, password_reset_config.secret_key)
    return f"{encoded}.{signature}"


def verify_password_reset_token(token: str) -> PasswordResetResult:
    """Verify a password reset token synchronously.

    Checks signature, expiration, purpose, user existence, password digest,
    and active status.

    Args:
        token: The password reset token to verify.

    Returns:
        PasswordResetResult with verification status and user.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return PasswordResetResult(valid=False, error="Invalid token format")

        encoded, signature = parts
        expected = _generate_signature(encoded, password_reset_config.secret_key)
        if not hmac.compare_digest(signature, expected):
            return PasswordResetResult(valid=False, error="Invalid token signature")

        payload = _decode_payload(encoded)

        if payload.get("purpose") != "password_reset":
            return PasswordResetResult(valid=False, error="Invalid token purpose")

        now = datetime.now(UTC).timestamp()
        if now > payload.get("exp", 0):
            return PasswordResetResult(
                valid=False, email=payload.get("email"), error="Token has expired"
            )

        email = payload.get("email")
        if not email:
            return PasswordResetResult(valid=False, error="Token missing email")

        User = get_user_model()
        try:
            user = User.objects.get(pk=payload["sub"])
        except User.DoesNotExist:
            return PasswordResetResult(valid=False, email=email, error="User not found")

        # Check password hasn't changed since token was issued
        if _password_digest(user.password) != payload.get("pwd"):
            return PasswordResetResult(
                valid=False, email=email, error="Token has been invalidated"
            )

        if not user.is_active:
            return PasswordResetResult(
                valid=False, email=email, error="User account is inactive"
            )

        return PasswordResetResult(valid=True, email=email, user=user)

    except Exception as e:
        return PasswordResetResult(valid=False, error=f"Token verification failed: {e}")


async def averify_password_reset_token(token: str) -> PasswordResetResult:
    """Verify a password reset token asynchronously (uses async ORM).

    Same checks as :func:`verify_password_reset_token` but uses ``aget``
    instead of ``get`` to avoid blocking the event loop.

    Args:
        token: The password reset token to verify.

    Returns:
        PasswordResetResult with verification status and user.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return PasswordResetResult(valid=False, error="Invalid token format")

        encoded, signature = parts
        expected = _generate_signature(encoded, password_reset_config.secret_key)
        if not hmac.compare_digest(signature, expected):
            return PasswordResetResult(valid=False, error="Invalid token signature")

        payload = _decode_payload(encoded)

        if payload.get("purpose") != "password_reset":
            return PasswordResetResult(valid=False, error="Invalid token purpose")

        now = datetime.now(UTC).timestamp()
        if now > payload.get("exp", 0):
            return PasswordResetResult(
                valid=False, email=payload.get("email"), error="Token has expired"
            )

        email = payload.get("email")
        if not email:
            return PasswordResetResult(valid=False, error="Token missing email")

        User = get_user_model()
        try:
            user = await User.objects.aget(pk=payload["sub"])
        except User.DoesNotExist:
            return PasswordResetResult(valid=False, email=email, error="User not found")

        if _password_digest(user.password) != payload.get("pwd"):
            return PasswordResetResult(
                valid=False, email=email, error="Token has been invalidated"
            )

        if not user.is_active:
            return PasswordResetResult(
                valid=False, email=email, error="User account is inactive"
            )

        return PasswordResetResult(valid=True, email=email, user=user)

    except Exception as e:
        return PasswordResetResult(valid=False, error=f"Token verification failed: {e}")


def get_reset_url(token: str) -> str | None:
    """Build reset URL from config template.

    Args:
        token: The password reset token.

    Returns:
        Full URL string or None if no template is configured.
    """
    template = password_reset_config.reset_url_template
    if not template:
        return None
    return template.replace("{token}", token)


__all__ = [
    "PasswordResetConfig",
    "PasswordResetResult",
    "averify_password_reset_token",
    "create_password_reset_token",
    "get_reset_url",
    "password_reset_config",
    "verify_password_reset_token",
]
