"""
Login-by-email configuration for django-matt.

Provides a simple toggle to switch authentication from username to email
without requiring a custom user model.

Usage:
    # In settings.py
    MATT_AUTH = {
        "login_field": "email",  # or "username" (default)
        "case_insensitive": True,
        "strip_whitespace": True,
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


@dataclass(frozen=True)
class LoginConfig:
    """Login configuration resolved from MATT_AUTH settings."""

    login_field: str = "email"
    case_insensitive: bool = True
    strip_whitespace: bool = True
    require_email_verified: bool = False
    allow_inactive: bool = False
    max_login_attempts: int = 0  # 0 = no limit
    lockout_duration: int = 300  # seconds


_config: LoginConfig | None = None


def get_login_config() -> LoginConfig:
    """Get login configuration from Django settings."""
    global _config
    if _config is not None:
        return _config

    try:
        from django.conf import settings

        raw: dict[str, Any] = getattr(settings, "MATT_AUTH", {})
    except Exception:
        raw = {}

    _config = LoginConfig(
        login_field=raw.get("login_field", "email"),
        case_insensitive=raw.get("case_insensitive", True),
        strip_whitespace=raw.get("strip_whitespace", True),
        require_email_verified=raw.get("require_email_verified", False),
        allow_inactive=raw.get("allow_inactive", False),
        max_login_attempts=raw.get("max_login_attempts", 0),
        lockout_duration=raw.get("lockout_duration", 300),
    )
    return _config


def reset_login_config() -> None:
    """Reset cached config (for testing)."""
    global _config
    _config = None


class EmailOrUsernameBackend(ModelBackend):
    """
    Authentication backend that supports login by email or username.

    Reads MATT_AUTH["login_field"] to determine the primary login field.
    Always falls back to username if email lookup fails.

    Add to AUTHENTICATION_BACKENDS:
        AUTHENTICATION_BACKENDS = [
            "django_matt.auth.login_config.EmailOrUsernameBackend",
        ]
    """

    def authenticate(
        self,
        request: Any = None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if username is None or password is None:
            return None

        config = get_login_config()
        User = get_user_model()

        credential = username
        if config.strip_whitespace:
            credential = credential.strip()

        # Try the configured login field first
        user = self._try_login(User, config.login_field, credential, password, config)
        if user is not None:
            return user

        # Fallback: if login_field is email, also try username
        if config.login_field == "email":
            user = self._try_login(User, "username", credential, password, config)
            if user is not None:
                return user

        # Fallback: if login_field is username, also try email
        if config.login_field == "username":
            user = self._try_login(User, "email", credential, password, config)
            if user is not None:
                return user

        return None

    def _try_login(
        self,
        user_model: type,
        field: str,
        credential: str,
        password: str,
        config: LoginConfig,
    ) -> Any:
        """Attempt login with the given field."""
        if not hasattr(user_model, field):
            return None

        lookup = field
        if config.case_insensitive:
            lookup = f"{field}__iexact"

        try:
            user = user_model._default_manager.get(**{lookup: credential})
        except user_model.DoesNotExist:
            # Run the password hasher to prevent timing attacks
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            # Multiple users with same email/username — try exact match
            try:
                user = user_model._default_manager.get(**{field: credential})
            except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
                return None

        if not config.allow_inactive and not user.is_active:
            return None

        if user.check_password(password):
            return user

        return None


class AsyncEmailOrUsernameBackend(EmailOrUsernameBackend):
    """
    Async version of EmailOrUsernameBackend.

    Uses async ORM methods for Django 5.0+ compatibility.
    """

    async def aauthenticate(
        self,
        request: Any = None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if username is None or password is None:
            return None

        config = get_login_config()
        User = get_user_model()

        credential = username
        if config.strip_whitespace:
            credential = credential.strip()

        user = await self._atry_login(User, config.login_field, credential, password, config)
        if user is not None:
            return user

        if config.login_field == "email":
            user = await self._atry_login(User, "username", credential, password, config)
            if user is not None:
                return user

        if config.login_field == "username":
            user = await self._atry_login(User, "email", credential, password, config)
            if user is not None:
                return user

        return None

    async def _atry_login(
        self,
        user_model: type,
        field: str,
        credential: str,
        password: str,
        config: LoginConfig,
    ) -> Any:
        """Async attempt login with the given field."""
        if not hasattr(user_model, field):
            return None

        lookup = field
        if config.case_insensitive:
            lookup = f"{field}__iexact"

        try:
            user = await user_model._default_manager.aget(**{lookup: credential})
        except user_model.DoesNotExist:
            return None
        except user_model.MultipleObjectsReturned:
            try:
                user = await user_model._default_manager.aget(**{field: credential})
            except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
                return None

        if not config.allow_inactive and not user.is_active:
            return None

        if user.check_password(password):
            return user

        return None
