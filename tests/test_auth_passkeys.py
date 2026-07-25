"""Tests for Passkey/WebAuthn authentication."""

from __future__ import annotations

import json
import secrets
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

import pytest

webauthn = pytest.importorskip("webauthn")

from django_matt.auth.passkeys.config import PasskeyConfig, get_passkey_config
from django_matt.auth.passkeys.models import PasskeyChallenge, PasskeyCredential
from django_matt.auth.passkeys.webauthn import (
    PasskeyAuthenticationError,
    PasskeyCredentialNotFoundError,
    PasskeyRegistrationError,
    _delete_challenge,
    _generate_challenge,
    _get_challenge,
    _store_challenge,
    _user_id_from_bytes,
    _user_id_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CONFIG = PasskeyConfig(
    rp_id="example.com",
    rp_name="Test App",
    origin="https://example.com",
)

# Patches used on almost every test — extracted to reduce duplication.
_CONFIG_PATCH_TARGET = "django_matt.auth.passkeys.webauthn.get_passkey_config"
_B64_ENCODE_TARGET = "django_matt.auth.passkeys.webauthn.bytes_to_base64url"
_B64_DECODE_TARGET = "django_matt.auth.passkeys.webauthn.base64url_to_bytes"
_OPTIONS_JSON_TARGET = "django_matt.auth.passkeys.webauthn.options_to_json"
_GEN_REG_TARGET = "django_matt.auth.passkeys.webauthn._generate_registration_options"
_VER_REG_TARGET = "django_matt.auth.passkeys.webauthn._verify_registration_response"
_GEN_AUTH_TARGET = "django_matt.auth.passkeys.webauthn._generate_authentication_options"
_VER_AUTH_TARGET = "django_matt.auth.passkeys.webauthn._verify_authentication_response"


def _mock_config():
    """Patch get_passkey_config() to return VALID_CONFIG."""
    return patch(_CONFIG_PATCH_TARGET, return_value=VALID_CONFIG)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear Django cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
@pytest.mark.django_db
def credential(user):
    """Create a test passkey credential."""
    return PasskeyCredential.objects.create(
        user=user,
        credential_id="dGVzdC1jcmVkZW50aWFsLWlk",
        public_key="dGVzdC1wdWJsaWMta2V5",
        sign_count=5,
        device_type="single_device",
        backed_up=False,
        transports=["internal"],
        aaguid="00000000-0000-0000-0000-000000000000",
        name="Test Key",
    )


# ==========================================================================
# Config tests
# ==========================================================================


class TestPasskeyConfig:
    """Tests for PasskeyConfig validation."""

    def test_valid_config_passes_validation(self):
        config = PasskeyConfig(
            rp_id="example.com",
            rp_name="Test App",
            origin="https://example.com",
        )
        errors = config.validate()
        assert errors == []

    def test_missing_rp_id(self):
        config = PasskeyConfig(rp_id="", rp_name="Test App", origin="https://example.com")
        errors = config.validate()
        assert any("RP_ID" in e for e in errors)

    def test_missing_rp_name(self):
        config = PasskeyConfig(rp_id="example.com", rp_name="", origin="https://example.com")
        errors = config.validate()
        assert any("RP_NAME" in e for e in errors)

    def test_missing_origin(self):
        config = PasskeyConfig(rp_id="example.com", rp_name="Test App", origin="")
        errors = config.validate()
        assert any("ORIGIN" in e for e in errors)

    def test_invalid_origin_scheme(self):
        config = PasskeyConfig(
            rp_id="example.com",
            rp_name="Test App",
            origin="ftp://example.com",
        )
        errors = config.validate()
        assert any("http://" in e or "https://" in e for e in errors)

    def test_all_fields_missing(self):
        config = PasskeyConfig()
        errors = config.validate()
        assert len(errors) >= 3  # rp_id, rp_name, origin


# ==========================================================================
# Model tests
# ==========================================================================


class TestPasskeyCredentialModel:
    """Tests for the PasskeyCredential model."""

    @pytest.mark.django_db
    def test_create_credential(self, user):
        cred = PasskeyCredential.objects.create(
            user=user,
            credential_id="Y3JlZC0xMjM",
            public_key="cHVibGljLWtleQ",
            sign_count=0,
            device_type="single_device",
        )
        assert cred.pk is not None
        assert cred.credential_id == "Y3JlZC0xMjM"
        assert cred.user == user

    @pytest.mark.django_db
    def test_unique_credential_id(self, user):
        PasskeyCredential.objects.create(
            user=user,
            credential_id="dW5pcXVlLWlk",
            public_key="a2V5",
            sign_count=0,
        )
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            PasskeyCredential.objects.create(
                user=user,
                credential_id="dW5pcXVlLWlk",
                public_key="a2V5Mg",
                sign_count=0,
            )

    @pytest.mark.django_db
    def test_update_sign_count_valid_increment(self, credential):
        assert credential.sign_count == 5
        result = credential.update_sign_count(10)
        assert result is True
        credential.refresh_from_db()
        assert credential.sign_count == 10

    @pytest.mark.django_db
    def test_update_sign_count_replay_detected(self, credential):
        assert credential.sign_count == 5
        result = credential.update_sign_count(3)
        assert result is False
        credential.refresh_from_db()
        assert credential.sign_count == 5  # unchanged

    @pytest.mark.django_db
    def test_update_sign_count_zero_to_zero(self, user):
        cred = PasskeyCredential.objects.create(
            user=user,
            credential_id="emVyby1jb3VudA",
            public_key="a2V5",
            sign_count=0,
        )
        result = cred.update_sign_count(0)
        assert result is True  # authenticators that don't implement counters

    @pytest.mark.django_db
    def test_str_representation(self, credential):
        s = str(credential)
        assert "testuser" in s
        assert "Test Key" in s


class TestPasskeyChallengeModel:
    """Tests for the PasskeyChallenge model."""

    @pytest.mark.django_db
    def test_is_expired_true(self, user):
        challenge = PasskeyChallenge.objects.create(
            challenge_id="expired-challenge",
            challenge="Y2hhbGxlbmdl",
            challenge_type="registration",
            user=user,
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        assert challenge.is_expired is True

    @pytest.mark.django_db
    def test_is_expired_false(self, user):
        challenge = PasskeyChallenge.objects.create(
            challenge_id="valid-challenge",
            challenge="Y2hhbGxlbmdl",
            challenge_type="authentication",
            user=user,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        assert challenge.is_expired is False


# ==========================================================================
# Helper function tests
# ==========================================================================


class TestHelperFunctions:
    """Tests for passkey helper functions."""

    def test_user_id_round_trip_int(self):
        original = 42
        as_bytes = _user_id_to_bytes(original)
        assert isinstance(as_bytes, bytes)
        back = _user_id_from_bytes(as_bytes)
        assert back == "42"

    def test_user_id_round_trip_string(self):
        original = "abc-123"
        as_bytes = _user_id_to_bytes(original)
        back = _user_id_from_bytes(as_bytes)
        assert back == original

    def test_generate_challenge_length(self):
        challenge = _generate_challenge()
        assert isinstance(challenge, bytes)
        assert len(challenge) == 32

    def test_generate_challenge_randomness(self):
        c1 = _generate_challenge()
        c2 = _generate_challenge()
        assert c1 != c2

    def test_challenge_store_get_delete(self):
        """Verify cache round-trip: store -> get -> delete -> get returns None."""
        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
        ):
            cid = "test-challenge-id"
            _store_challenge(cid, b"0" * 32, "registration", user_id=1)

            data = _get_challenge(cid)
            assert data is not None
            assert data["type"] == "registration"
            assert data["user_id"] == 1
            assert data["challenge"] == "ZW5jb2RlZA"

            _delete_challenge(cid)
            assert _get_challenge(cid) is None


# ==========================================================================
# Registration flow tests
# ==========================================================================


class TestRegistrationFlow:
    """Tests for the passkey registration flow."""

    @pytest.mark.django_db
    def test_generate_registration_options_returns_challenge_id(self, user):
        mock_options = MagicMock()
        mock_options.challenge = b"x" * 32

        with (
            _mock_config(),
            patch(_GEN_REG_TARGET, return_value=mock_options),
            patch(_OPTIONS_JSON_TARGET, return_value='{"publicKey": {}}'),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZC1jaGFsbGVuZ2U"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
        ):
            result = generate_registration_options(user)

        assert "challenge_id" in result
        assert isinstance(result["challenge_id"], str)
        assert len(result["challenge_id"]) > 0

    @pytest.mark.django_db
    def test_generate_registration_options_stores_challenge(self, user):
        mock_options = MagicMock()
        mock_options.challenge = b"x" * 32

        with (
            _mock_config(),
            patch(_GEN_REG_TARGET, return_value=mock_options),
            patch(_OPTIONS_JSON_TARGET, return_value='{"publicKey": {}}'),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZC1jaGFsbGVuZ2U"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
        ):
            result = generate_registration_options(user)

            # Assert inside mock context because _get_challenge needs get_passkey_config
            challenge_id = result["challenge_id"]
            stored = _get_challenge(challenge_id)
            assert stored is not None
            assert stored["type"] == "registration"
            assert stored["user_id"] == user.pk

    @pytest.mark.django_db
    def test_generate_registration_options_max_credentials_reached(self, user):
        config = PasskeyConfig(
            rp_id="example.com",
            rp_name="Test App",
            origin="https://example.com",
            max_credentials_per_user=2,
        )
        # Create 2 credentials to hit the limit
        for i in range(2):
            PasskeyCredential.objects.create(
                user=user,
                credential_id=f"Y3JlZC17aX0-{i}",
                public_key="a2V5",
                sign_count=0,
            )

        with patch(_CONFIG_PATCH_TARGET, return_value=config):
            with pytest.raises(PasskeyRegistrationError, match="Maximum number of credentials"):
                generate_registration_options(user)

    @pytest.mark.django_db
    def test_verify_registration_creates_credential(self, user):
        challenge_id = "test-reg-challenge"

        # Store challenge, then verify — all within mock context
        mock_verification = MagicMock()
        mock_verification.credential_public_key = b"public-key-bytes"
        mock_verification.sign_count = 0
        mock_verification.credential_backed_up = False
        mock_verification.aaguid = "00000000-0000-0000-0000-000000000000"

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="cHVibGljLWtleQ"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
            patch(_VER_REG_TARGET, return_value=mock_verification),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "registration",
                user_id=user.pk,
                extra_data={"credential_name": "My Key"},
            )
            cred = verify_registration_response(
                user=user,
                credential_id="bmV3LWNyZWQ",
                client_data_json="Y2xpZW50RGF0YQ",
                attestation_object="YXR0ZXN0YXRpb24",
                challenge_id=challenge_id,
                transports=["internal"],
                credential_name="My Key",
            )

        assert cred.pk is not None
        assert cred.user == user
        assert cred.credential_id == "bmV3LWNyZWQ"
        assert cred.name == "My Key"
        assert cred.transports == ["internal"]

    @pytest.mark.django_db
    def test_verify_registration_expired_challenge(self, user):
        with _mock_config():
            with pytest.raises(PasskeyRegistrationError, match="Challenge not found or expired"):
                verify_registration_response(
                    user=user,
                    credential_id="Y3JlZA",
                    client_data_json="Y2xpZW50",
                    attestation_object="YXR0ZXN0",
                    challenge_id="nonexistent-challenge",
                )

    @pytest.mark.django_db
    def test_verify_registration_wrong_user(self, user):
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )
        challenge_id = "wrong-user-challenge"

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "registration",
                user_id=other_user.pk,
            )
            with pytest.raises(PasskeyRegistrationError, match="Challenge does not match user"):
                verify_registration_response(
                    user=user,
                    credential_id="Y3JlZA",
                    client_data_json="Y2xpZW50",
                    attestation_object="YXR0ZXN0",
                    challenge_id=challenge_id,
                )

    @pytest.mark.django_db
    def test_verify_registration_wrong_challenge_type(self, user):
        challenge_id = "auth-type-challenge"

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "authentication",  # wrong type for registration verify
                user_id=user.pk,
            )
            with pytest.raises(PasskeyRegistrationError, match="Invalid challenge type"):
                verify_registration_response(
                    user=user,
                    credential_id="Y3JlZA",
                    client_data_json="Y2xpZW50",
                    attestation_object="YXR0ZXN0",
                    challenge_id=challenge_id,
                )


# ==========================================================================
# Authentication flow tests
# ==========================================================================


class TestAuthenticationFlow:
    """Tests for the passkey authentication flow."""

    @pytest.mark.django_db
    def test_generate_authentication_options_returns_challenge_id(self, user):
        mock_options = MagicMock()
        mock_options.challenge = b"y" * 32

        with (
            _mock_config(),
            patch(_GEN_AUTH_TARGET, return_value=mock_options),
            patch(_OPTIONS_JSON_TARGET, return_value='{"publicKey": {}}'),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
        ):
            result = generate_authentication_options()

        assert "challenge_id" in result
        assert isinstance(result["challenge_id"], str)

    @pytest.mark.django_db
    def test_generate_authentication_options_with_user_includes_allow_credentials(
        self, user, credential
    ):
        mock_options = MagicMock()
        mock_options.challenge = b"y" * 32

        with (
            _mock_config(),
            patch(_GEN_AUTH_TARGET, return_value=mock_options) as mock_gen,
            patch(_OPTIONS_JSON_TARGET, return_value='{"publicKey": {}}'),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
        ):
            result = generate_authentication_options(user=user)

        # The call should have included allow_credentials (not None)
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["allow_credentials"] is not None
        assert len(call_kwargs["allow_credentials"]) == 1

    @pytest.mark.django_db
    def test_generate_authentication_options_stores_challenge(self, user):
        mock_options = MagicMock()
        mock_options.challenge = b"y" * 32

        with (
            _mock_config(),
            patch(_GEN_AUTH_TARGET, return_value=mock_options),
            patch(_OPTIONS_JSON_TARGET, return_value='{"publicKey": {}}'),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
        ):
            result = generate_authentication_options(user=user)

            # Assert inside mock context
            challenge_id = result["challenge_id"]
            stored = _get_challenge(challenge_id)
            assert stored is not None
            assert stored["type"] == "authentication"

    @pytest.mark.django_db
    def test_verify_authentication_returns_user_and_credential(self, user, credential):
        challenge_id = "auth-challenge"

        mock_verification = MagicMock()
        mock_verification.new_sign_count = 10

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
            patch(_VER_AUTH_TARGET, return_value=mock_verification),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "authentication",
                user_id=user.pk,
            )
            returned_user, returned_cred = verify_authentication_response(
                credential_id=credential.credential_id,
                client_data_json="Y2xpZW50RGF0YQ",
                authenticator_data="YXV0aERhdGE",
                signature="c2lnbmF0dXJl",
                challenge_id=challenge_id,
            )

        assert returned_user.pk == user.pk
        assert returned_cred.pk == credential.pk
        returned_cred.refresh_from_db()
        assert returned_cred.sign_count == 10

    @pytest.mark.django_db
    def test_verify_authentication_missing_credential(self, user):
        challenge_id = "auth-challenge-missing"

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "authentication",
                user_id=user.pk,
            )
            with pytest.raises(PasskeyCredentialNotFoundError, match="Credential not found"):
                verify_authentication_response(
                    credential_id="bm9uZXhpc3RlbnQ",
                    client_data_json="Y2xpZW50",
                    authenticator_data="YXV0aA",
                    signature="c2ln",
                    challenge_id=challenge_id,
                )

    @pytest.mark.django_db
    def test_verify_authentication_wrong_challenge_type(self, user, credential):
        challenge_id = "reg-type-auth"

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "registration",  # wrong type for authentication
                user_id=user.pk,
            )
            with pytest.raises(PasskeyAuthenticationError, match="Invalid challenge type"):
                verify_authentication_response(
                    credential_id=credential.credential_id,
                    client_data_json="Y2xpZW50",
                    authenticator_data="YXV0aA",
                    signature="c2ln",
                    challenge_id=challenge_id,
                )

    @pytest.mark.django_db
    def test_verify_authentication_expired_challenge(self, user, credential):
        with _mock_config():
            with pytest.raises(PasskeyAuthenticationError, match="Challenge not found or expired"):
                verify_authentication_response(
                    credential_id=credential.credential_id,
                    client_data_json="Y2xpZW50",
                    authenticator_data="YXV0aA",
                    signature="c2ln",
                    challenge_id="nonexistent-auth-challenge",
                )

    @pytest.mark.django_db
    def test_verify_authentication_cleans_up_challenge(self, user, credential):
        challenge_id = "cleanup-challenge"

        mock_verification = MagicMock()
        mock_verification.new_sign_count = 10

        with (
            _mock_config(),
            patch(_B64_ENCODE_TARGET, return_value="ZW5jb2RlZA"),
            patch(_B64_DECODE_TARGET, return_value=b"decoded"),
            patch(_VER_AUTH_TARGET, return_value=mock_verification),
        ):
            _store_challenge(
                challenge_id,
                b"x" * 32,
                "authentication",
                user_id=user.pk,
            )
            verify_authentication_response(
                credential_id=credential.credential_id,
                client_data_json="Y2xpZW50RGF0YQ",
                authenticator_data="YXV0aERhdGE",
                signature="c2lnbmF0dXJl",
                challenge_id=challenge_id,
            )

            # Challenge should be deleted after use
            stored = _get_challenge(challenge_id)
            assert stored is None
