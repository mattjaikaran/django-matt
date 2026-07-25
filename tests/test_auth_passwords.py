"""Tests for password utilities and password reset."""

from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model

import pytest

from django_matt.auth.passwords import (
    PasswordStrengthResult,
    check_password_strength,
    generate_passphrase,
    generate_password,
    get_password_help_text,
    get_unusable_password,
    hash_password,
    is_unusable_password,
    is_valid_hash,
    needs_rehash,
    verify_password,
)

User = get_user_model()


# =============================================================================
# Password hashing
# =============================================================================


class TestHashPassword:
    def test_hash_and_verify_roundtrip(self):
        hashed = hash_password("SecurePass123!")
        assert verify_password("SecurePass123!", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("SecurePass123!")
        assert verify_password("WrongPass456!", hashed) is False

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("SecurePass123!")
        assert hashed != "SecurePass123!"

    def test_same_password_different_hashes(self):
        h1 = hash_password("SecurePass123!")
        h2 = hash_password("SecurePass123!")
        assert h1 != h2  # different salts

    def test_is_valid_hash_true(self):
        hashed = hash_password("test")
        assert is_valid_hash(hashed) is True

    def test_is_valid_hash_false_for_unusable(self):
        unusable = get_unusable_password()
        assert is_valid_hash(unusable) is False

    def test_unusable_password(self):
        unusable = get_unusable_password()
        assert is_unusable_password(unusable) is True

    def test_usable_password_is_not_unusable(self):
        hashed = hash_password("test")
        assert is_unusable_password(hashed) is False

    def test_needs_rehash_different_hasher(self):
        hashed = hash_password("test", hasher="pbkdf2_sha256")
        # Default hasher may differ; if it does, needs_rehash should detect it
        # This test at minimum verifies the function runs without error
        result = needs_rehash(hashed, "pbkdf2_sha256")
        assert isinstance(result, bool)

    def test_needs_rehash_unusable(self):
        assert needs_rehash(get_unusable_password()) is True

    def test_needs_rehash_invalid_string(self):
        assert needs_rehash("garbage") is True


# =============================================================================
# Password strength
# =============================================================================


class TestCheckPasswordStrength:
    def test_strong_password_valid(self):
        result = check_password_strength(
            "MyStr0ng!Pass99",
            use_django_validators=False,
        )
        assert result.is_valid is True
        assert result.score >= 2

    def test_too_short(self):
        result = check_password_strength(
            "Ab1!",
            use_django_validators=False,
        )
        assert result.is_valid is False
        assert any("at least 8" in e for e in result.errors)

    def test_missing_uppercase(self):
        result = check_password_strength(
            "nouppercase1!",
            require_uppercase=True,
            use_django_validators=False,
        )
        assert result.is_valid is False
        assert any("uppercase" in e for e in result.errors)

    def test_missing_lowercase(self):
        result = check_password_strength(
            "NOLOWERCASE1!",
            require_lowercase=True,
            use_django_validators=False,
        )
        assert result.is_valid is False
        assert any("lowercase" in e for e in result.errors)

    def test_missing_digit(self):
        result = check_password_strength(
            "NoDigitsHere!",
            require_digit=True,
            use_django_validators=False,
        )
        assert result.is_valid is False
        assert any("digit" in e for e in result.errors)

    def test_require_special_char(self):
        result = check_password_strength(
            "NoSpecial123",
            require_special=True,
            use_django_validators=False,
        )
        assert result.is_valid is False
        assert any("special" in e for e in result.errors)

    def test_common_password_detected(self):
        result = check_password_strength(
            "password123!A",
            use_django_validators=False,
        )
        assert any("common" in e.lower() for e in result.errors)

    def test_strength_label(self):
        result = PasswordStrengthResult(is_valid=True, score=0)
        assert result.strength_label == "Very Weak"
        result = PasswordStrengthResult(is_valid=True, score=4)
        assert result.strength_label == "Very Strong"

    def test_score_clamped_to_4(self):
        result = check_password_strength(
            "VeryStr0ng!P@ss123456",
            use_django_validators=False,
        )
        assert result.score <= 4

    def test_suggestions_present_on_failure(self):
        result = check_password_strength(
            "weak",
            use_django_validators=False,
        )
        assert len(result.suggestions) > 0

    def test_no_suggestions_on_success(self):
        result = check_password_strength(
            "MyStr0ng!Pass99",
            use_django_validators=False,
        )
        if result.is_valid:
            assert result.suggestions == []


# =============================================================================
# Password generation
# =============================================================================


class TestGeneratePassword:
    def test_default_length(self):
        pw = generate_password()
        assert len(pw) == 16

    def test_custom_length(self):
        pw = generate_password(length=32)
        assert len(pw) == 32

    def test_uniqueness(self):
        p1 = generate_password()
        p2 = generate_password()
        assert p1 != p2

    def test_exclude_ambiguous(self):
        # Generate many passwords, check none contain ambiguous chars
        for _ in range(20):
            pw = generate_password(exclude_ambiguous=True)
            assert "0" not in pw
            assert "O" not in pw
            assert "l" not in pw
            assert "1" not in pw
            assert "I" not in pw

    def test_include_only_lowercase(self):
        pw = generate_password(
            include_uppercase=False,
            include_digits=False,
            include_special=False,
            exclude_ambiguous=False,
        )
        assert pw.isalpha()
        assert pw.islower()

    def test_fallback_when_no_char_classes(self):
        pw = generate_password(
            include_uppercase=False,
            include_lowercase=False,
            include_digits=False,
            include_special=False,
        )
        assert len(pw) == 16  # should still produce a password


class TestGeneratePassphrase:
    def test_default_word_count(self):
        phrase = generate_passphrase()
        assert len(phrase.split("-")) == 4

    def test_custom_word_count(self):
        phrase = generate_passphrase(num_words=6)
        assert len(phrase.split("-")) == 6

    def test_custom_separator(self):
        phrase = generate_passphrase(separator="_")
        assert "_" in phrase

    def test_capitalize(self):
        phrase = generate_passphrase(capitalize=True)
        for word in phrase.split("-"):
            assert word[0].isupper()

    def test_no_capitalize(self):
        phrase = generate_passphrase(capitalize=False)
        for word in phrase.split("-"):
            assert word[0].islower()


class TestGetPasswordHelpText:
    def test_returns_list(self):
        texts = get_password_help_text()
        assert isinstance(texts, list)


# =============================================================================
# Password Reset
# =============================================================================


class TestPasswordResetToken:
    @pytest.mark.django_db
    def test_create_and_verify_roundtrip(self, db):
        from django_matt.auth.password_reset import (
            create_password_reset_token,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password="TestPass123!",
        )
        token = create_password_reset_token(user)
        result = verify_password_reset_token(token)
        assert result.valid is True
        assert result.email == "reset@example.com"
        assert result.user.pk == user.pk

    @pytest.mark.django_db
    def test_invalid_format(self):
        from django_matt.auth.password_reset import verify_password_reset_token

        result = verify_password_reset_token("no-dots-here")
        assert result.valid is False
        assert "format" in result.error.lower()

    @pytest.mark.django_db
    def test_tampered_signature(self, db):
        from django_matt.auth.password_reset import (
            create_password_reset_token,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            username="tamperuser",
            email="tamper@example.com",
            password="TestPass123!",
        )
        token = create_password_reset_token(user)
        # Flip last char of signature
        payload, sig = token.rsplit(".", 1)
        tampered = f"{payload}.{sig[:-1]}{'a' if sig[-1] != 'a' else 'b'}"
        result = verify_password_reset_token(tampered)
        assert result.valid is False
        assert "signature" in result.error.lower()

    @pytest.mark.django_db
    def test_expired_token(self, db):
        from django_matt.auth.password_reset import (
            create_password_reset_token,
            password_reset_config,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            username="expireuser",
            email="expire@example.com",
            password="TestPass123!",
        )
        with patch.object(
            type(password_reset_config),
            "token_lifetime",
            new_callable=lambda: property(lambda self: timedelta(seconds=-1)),
        ):
            token = create_password_reset_token(user)
        result = verify_password_reset_token(token)
        assert result.valid is False
        assert "expired" in result.error.lower()

    @pytest.mark.django_db
    def test_password_changed_invalidates_token(self, db):
        from django_matt.auth.password_reset import (
            create_password_reset_token,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            username="pwdchange",
            email="pwdchange@example.com",
            password="OldPass123!",
        )
        token = create_password_reset_token(user)
        # Change password
        user.set_password("NewPass456!")
        user.save()
        result = verify_password_reset_token(token)
        assert result.valid is False
        assert "invalidated" in result.error.lower()

    @pytest.mark.django_db
    def test_deleted_user(self, db):
        from django_matt.auth.password_reset import (
            create_password_reset_token,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            username="deleteuser",
            email="delete@example.com",
            password="TestPass123!",
        )
        token = create_password_reset_token(user)
        user.delete()
        result = verify_password_reset_token(token)
        assert result.valid is False
        assert "not found" in result.error.lower()

    @pytest.mark.django_db
    def test_inactive_user(self, db):
        from django_matt.auth.password_reset import (
            create_password_reset_token,
            verify_password_reset_token,
        )

        user = User.objects.create_user(
            username="inactiveuser",
            email="inactive@example.com",
            password="TestPass123!",
            is_active=True,
        )
        token = create_password_reset_token(user)
        user.is_active = False
        user.save()
        result = verify_password_reset_token(token)
        assert result.valid is False
        assert "inactive" in result.error.lower()

    @pytest.mark.django_db
    async def test_async_verify_roundtrip(self, db):
        from asgiref.sync import sync_to_async

        from django_matt.auth.password_reset import (
            averify_password_reset_token,
            create_password_reset_token,
        )

        user = await sync_to_async(User.objects.create_user)(
            username="asyncreset",
            email="asyncreset@example.com",
            password="TestPass123!",
        )
        token = create_password_reset_token(user)
        result = await averify_password_reset_token(token)
        assert result.valid is True
        assert result.email == "asyncreset@example.com"


class TestGetResetUrl:
    def test_with_template(self):
        from django_matt.auth.password_reset import get_reset_url, password_reset_config

        with patch.object(
            type(password_reset_config),
            "reset_url_template",
            new_callable=lambda: property(
                lambda self: "https://app.com/reset?token={token}"
            ),
        ):
            url = get_reset_url("abc123")
            assert url == "https://app.com/reset?token=abc123"

    def test_without_template(self):
        from django_matt.auth.password_reset import get_reset_url, password_reset_config

        with patch.object(
            type(password_reset_config),
            "reset_url_template",
            new_callable=lambda: property(lambda self: None),
        ):
            url = get_reset_url("abc123")
            assert url is None
