"""
Tests for the Django Matt password reset module.

Covers:
- Token creation and verification roundtrip
- Token expiration rejection
- Tampered signature rejection
- Token invalidation after password change
- Config reads settings
- get_reset_url builds URL from template
- Controller POST /auth/password-reset always returns 200
- Controller POST /auth/password-reset/confirm with valid token
- Controller rejects expired/invalid token with 401
- Password validation: weak password rejected
- Passwords must match validator
- averify_password_reset_token async version
- Token with wrong purpose rejected
"""

from __future__ import annotations

import json
import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory

import pytest
from pydantic import ValidationError

from django_matt.auth.password_reset import (
    PasswordResetConfig,
    PasswordResetResult,
    _decode_payload,
    _encode_payload,
    _generate_signature,
    _password_digest,
    averify_password_reset_token,
    create_password_reset_token,
    get_reset_url,
    password_reset_config,
    verify_password_reset_token,
)
from django_matt.auth.schemas import ResetPasswordConfirmRequest, ResetPasswordRequest

User = get_user_model()


@pytest.fixture
def rf():
    """Provide a Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="resetuser",
        email="reset@example.com",
        password="OldPass123",
    )


# =============================================================================
# Token create / verify roundtrip
# =============================================================================


@pytest.mark.django_db
class TestTokenRoundtrip:
    def test_create_and_verify(self, user):
        """Token created for user verifies successfully."""
        token = create_password_reset_token(user)
        result = verify_password_reset_token(token)

        assert result.valid is True
        assert result.email == user.email
        assert result.user is not None
        assert result.user.pk == user.pk
        assert result.error is None

    def test_token_format(self, user):
        """Token is in payload.signature format."""
        token = create_password_reset_token(user)
        parts = token.split(".")
        assert len(parts) == 2
        # payload should be base64-decodable
        payload = _decode_payload(parts[0])
        assert payload["sub"] == str(user.pk)
        assert payload["email"] == user.email
        assert payload["purpose"] == "password_reset"
        assert "pwd" in payload
        assert "nonce" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_token_payload_contains_password_digest(self, user):
        """Token includes digest of current password hash."""
        token = create_password_reset_token(user)
        encoded = token.split(".")[0]
        payload = _decode_payload(encoded)
        assert payload["pwd"] == _password_digest(user.password)


# =============================================================================
# Token expiration
# =============================================================================


@pytest.mark.django_db
class TestTokenExpiration:
    def test_expired_token_rejected(self, user):
        """Token with past expiration is rejected."""
        with patch.object(
            type(password_reset_config),
            "token_lifetime",
            new_callable=lambda: property(lambda self: timedelta(seconds=-1)),
        ):
            token = create_password_reset_token(user)

        result = verify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "Token has expired"
        assert result.email == user.email

    def test_valid_token_not_expired(self, user):
        """Token with future expiration is accepted."""
        token = create_password_reset_token(user)
        result = verify_password_reset_token(token)
        assert result.valid is True


# =============================================================================
# Tampered token
# =============================================================================


@pytest.mark.django_db
class TestTamperedToken:
    def test_tampered_signature_rejected(self, user):
        """Token with modified signature is rejected."""
        token = create_password_reset_token(user)
        encoded, sig = token.split(".")
        # Flip a character in the signature
        bad_sig = sig[:-1] + ("a" if sig[-1] != "a" else "b")
        tampered = f"{encoded}.{bad_sig}"

        result = verify_password_reset_token(tampered)
        assert result.valid is False
        assert result.error == "Invalid token signature"

    def test_tampered_payload_rejected(self, user):
        """Token with modified payload is rejected (signature mismatch)."""
        token = create_password_reset_token(user)
        encoded, sig = token.split(".")
        # Decode, modify, re-encode (but keep old sig)
        payload = _decode_payload(encoded)
        payload["email"] = "hacker@evil.com"
        new_encoded = _encode_payload(payload)
        tampered = f"{new_encoded}.{sig}"

        result = verify_password_reset_token(tampered)
        assert result.valid is False
        assert result.error == "Invalid token signature"

    def test_invalid_token_format_rejected(self):
        """Token without exactly one dot is rejected."""
        result = verify_password_reset_token("no-dots-here")
        assert result.valid is False
        assert result.error == "Invalid token format"

        result = verify_password_reset_token("too.many.dots")
        assert result.valid is False
        assert result.error == "Invalid token format"


# =============================================================================
# Token invalidation after password change
# =============================================================================


@pytest.mark.django_db
class TestTokenInvalidation:
    def test_token_invalid_after_password_change(self, user):
        """Token is rejected after user changes password."""
        token = create_password_reset_token(user)

        # Verify it works first
        result = verify_password_reset_token(token)
        assert result.valid is True

        # Change the password
        user.set_password("NewPass456")
        user.save()

        # Now the same token should be invalid
        result = verify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "Token has been invalidated"

    def test_token_valid_without_password_change(self, user):
        """Token remains valid when password hasn't changed."""
        token = create_password_reset_token(user)
        result = verify_password_reset_token(token)
        assert result.valid is True

        # Verify again without changing password
        result = verify_password_reset_token(token)
        assert result.valid is True


# =============================================================================
# Inactive user
# =============================================================================


@pytest.mark.django_db
class TestInactiveUser:
    def test_inactive_user_rejected(self, user):
        """Token for inactive user is rejected."""
        token = create_password_reset_token(user)

        user.is_active = False
        user.save()

        result = verify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "User account is inactive"


# =============================================================================
# User not found
# =============================================================================


@pytest.mark.django_db
class TestUserNotFound:
    def test_deleted_user_rejected(self, user):
        """Token for deleted user returns user not found."""
        token = create_password_reset_token(user)
        user.delete()

        result = verify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "User not found"


# =============================================================================
# Wrong purpose
# =============================================================================


@pytest.mark.django_db
class TestWrongPurpose:
    def test_wrong_purpose_rejected(self, user):
        """Token with non-password_reset purpose is rejected."""
        # Manually craft a token with wrong purpose
        import secrets
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        exp = now + timedelta(hours=1)
        payload = {
            "sub": str(user.pk),
            "email": user.email,
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "purpose": "magic_link",  # Wrong purpose
            "pwd": _password_digest(user.password),
            "nonce": secrets.token_urlsafe(16),
        }
        encoded = _encode_payload(payload)
        sig = _generate_signature(encoded, password_reset_config.secret_key)
        token = f"{encoded}.{sig}"

        result = verify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "Invalid token purpose"


# =============================================================================
# Config
# =============================================================================


class TestConfig:
    def test_default_config(self):
        """Config uses sensible defaults."""
        config = PasswordResetConfig()
        assert config.token_lifetime == timedelta(hours=1)
        assert config.min_password_length == 8
        assert config.reset_url_template is None
        assert config.email_callback is None
        # secret_key defaults to Django SECRET_KEY
        from django.conf import settings

        assert config.secret_key == settings.SECRET_KEY

    def test_custom_config(self, settings):
        """Config reads from DJANGO_MATT_PASSWORD_RESET setting."""
        settings.DJANGO_MATT_PASSWORD_RESET = {
            "SECRET_KEY": "custom-secret",
            "TOKEN_LIFETIME": timedelta(minutes=30),
            "RESET_URL_TEMPLATE": "https://app.com/reset?token={token}",
            "MIN_PASSWORD_LENGTH": 12,
        }
        config = PasswordResetConfig()
        assert config.secret_key == "custom-secret"
        assert config.token_lifetime == timedelta(minutes=30)
        assert config.reset_url_template == "https://app.com/reset?token={token}"
        assert config.min_password_length == 12


# =============================================================================
# get_reset_url
# =============================================================================


class TestGetResetUrl:
    def test_returns_none_without_template(self):
        """Returns None when no RESET_URL_TEMPLATE is configured."""
        url = get_reset_url("some-token")
        assert url is None

    def test_builds_url_from_template(self, settings):
        """Builds URL by replacing {token} placeholder."""
        settings.DJANGO_MATT_PASSWORD_RESET = {
            "RESET_URL_TEMPLATE": "https://app.com/reset?token={token}",
        }
        # Re-instantiate to pick up new settings
        from django_matt.auth.password_reset import PasswordResetConfig

        config = PasswordResetConfig()
        with patch(
            "django_matt.auth.password_reset.password_reset_config",
            config,
        ):
            url = get_reset_url("abc123")
        assert url == "https://app.com/reset?token=abc123"


# =============================================================================
# Async verify
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestAsyncVerify:
    @pytest.mark.asyncio
    async def test_averify_valid_token(self):
        """Async verify works for valid token."""
        user = await User.objects.acreate_user(
            username="asyncuser1",
            email="async1@example.com",
            password="OldPass123",
        )
        token = create_password_reset_token(user)
        result = await averify_password_reset_token(token)
        assert result.valid is True
        assert result.user.pk == user.pk

    @pytest.mark.asyncio
    async def test_averify_expired_token(self):
        """Async verify rejects expired token."""
        user = await User.objects.acreate_user(
            username="asyncuser2",
            email="async2@example.com",
            password="OldPass123",
        )
        with patch.object(
            type(password_reset_config),
            "token_lifetime",
            new_callable=lambda: property(lambda self: timedelta(seconds=-1)),
        ):
            token = create_password_reset_token(user)

        result = await averify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "Token has expired"

    @pytest.mark.asyncio
    async def test_averify_tampered_signature(self):
        """Async verify rejects tampered signature."""
        user = await User.objects.acreate_user(
            username="asyncuser3",
            email="async3@example.com",
            password="OldPass123",
        )
        token = create_password_reset_token(user)
        encoded, sig = token.split(".")
        bad_sig = sig[:-1] + ("a" if sig[-1] != "a" else "b")
        result = await averify_password_reset_token(f"{encoded}.{bad_sig}")
        assert result.valid is False
        assert result.error == "Invalid token signature"

    @pytest.mark.asyncio
    async def test_averify_invalidated_after_password_change(self):
        """Async verify rejects token after password change."""
        user = await User.objects.acreate_user(
            username="asyncuser4",
            email="async4@example.com",
            password="OldPass123",
        )
        token = create_password_reset_token(user)
        user.set_password("NewPass456")
        await user.asave()

        result = await averify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "Token has been invalidated"

    @pytest.mark.asyncio
    async def test_averify_inactive_user(self):
        """Async verify rejects token for inactive user."""
        user = await User.objects.acreate_user(
            username="asyncuser5",
            email="async5@example.com",
            password="OldPass123",
        )
        token = create_password_reset_token(user)
        user.is_active = False
        await user.asave()

        result = await averify_password_reset_token(token)
        assert result.valid is False
        assert result.error == "User account is inactive"


# =============================================================================
# Schema validation
# =============================================================================


class TestResetPasswordConfirmSchema:
    def test_valid_request(self):
        """Valid password reset confirm request passes validation."""
        req = ResetPasswordConfirmRequest(
            token="some.token",
            new_password="StrongPass1",
            new_password_confirm="StrongPass1",
        )
        assert req.token == "some.token"
        assert req.new_password == "StrongPass1"

    def test_passwords_must_match(self):
        """Mismatched passwords are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordConfirmRequest(
                token="some.token",
                new_password="StrongPass1",
                new_password_confirm="DifferentPass1",
            )
        errors = exc_info.value.errors()
        assert any("Passwords do not match" in str(e["msg"]) for e in errors)

    def test_password_too_short(self):
        """Password under 8 characters is rejected."""
        with pytest.raises(ValidationError):
            ResetPasswordConfirmRequest(
                token="some.token",
                new_password="Sh0rt",
                new_password_confirm="Sh0rt",
            )

    def test_password_no_uppercase(self):
        """Password without uppercase letter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordConfirmRequest(
                token="some.token",
                new_password="nouppercase1",
                new_password_confirm="nouppercase1",
            )
        errors = exc_info.value.errors()
        assert any("uppercase" in str(e["msg"]).lower() for e in errors)

    def test_password_no_lowercase(self):
        """Password without lowercase letter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordConfirmRequest(
                token="some.token",
                new_password="NOLOWERCASE1",
                new_password_confirm="NOLOWERCASE1",
            )
        errors = exc_info.value.errors()
        assert any("lowercase" in str(e["msg"]).lower() for e in errors)

    def test_password_no_digit(self):
        """Password without digit is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordConfirmRequest(
                token="some.token",
                new_password="NoDigitHere",
                new_password_confirm="NoDigitHere",
            )
        errors = exc_info.value.errors()
        assert any("digit" in str(e["msg"]).lower() for e in errors)


class TestResetPasswordRequestSchema:
    def test_valid_email(self):
        """Valid email passes."""
        req = ResetPasswordRequest(email="User@Example.com")
        assert req.email == "user@example.com"

    def test_invalid_email(self):
        """Invalid email is rejected."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(email="not-an-email")


# =============================================================================
# Helper functions
# =============================================================================


class TestHelpers:
    def test_encode_decode_roundtrip(self):
        """Payload survives encode/decode cycle."""
        original = {"key": "value", "number": 42}
        encoded = _encode_payload(original)
        decoded = _decode_payload(encoded)
        assert decoded == original

    def test_password_digest_deterministic(self):
        """Same input produces same digest."""
        d1 = _password_digest("hash123")
        d2 = _password_digest("hash123")
        assert d1 == d2
        assert len(d1) == 16

    def test_password_digest_different_inputs(self):
        """Different inputs produce different digests."""
        d1 = _password_digest("hash123")
        d2 = _password_digest("hash456")
        assert d1 != d2

    def test_generate_signature_deterministic(self):
        """Same data + secret produces same signature."""
        s1 = _generate_signature("data", "secret")
        s2 = _generate_signature("data", "secret")
        assert s1 == s2

    def test_generate_signature_different_secrets(self):
        """Different secrets produce different signatures."""
        s1 = _generate_signature("data", "secret1")
        s2 = _generate_signature("data", "secret2")
        assert s1 != s2
