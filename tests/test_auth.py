"""
Tests for the Django Matt authentication module.

Covers:
- JWT token generation, validation, expiration, refresh, decorators
- Magic Link token creation, validation, expiration
- RBAC role creation, hierarchy, permission checks, decorators
- OAuth provider initialization, URL generation, callback handling
- SSO SAML/OIDC provider setup, connection handling
- Passkeys/WebAuthn registration options, authentication options, credential storage
- API Keys generation, validation, scoping
- Auth Controllers login, register, refresh, logout, me endpoints
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory

import pytest
from pydantic import ValidationError

from django_matt.auth.jwt import (
    AsyncJWTAuth,
    ExpiredSignatureError,
    InvalidTokenError,
    JWTAuth,
    JWTAuthentication,
    JWTConfig,
    MattJWTAuth,
    acreate_access_token,
    acreate_token_pair,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    generate_jti,
    get_token_from_request,
    get_user_from_token,
    jwt_config,
    refresh_tokens,
    verify_access_token,
    verify_refresh_token,
)
from django_matt.auth.jwt_builtin import (
    JWTDecodeError,
    JWTError,
    JWTExpiredError,
    JWTInvalidSignatureError,
    decode_jwt,
    encode_jwt,
)
from django_matt.auth.magic_link import (
    MagicLinkConfig,
    MagicLinkInvalidError,
    MagicLinkVerifyResult,
    create_magic_link_token,
    create_magic_link_url,
    get_magic_link_payload,
    magic_link_config,
    send_magic_link,
    verify_magic_link_token,
)
from django_matt.auth.rbac.config import RBACConfig, Role
from django_matt.auth.rbac.utils import (
    get_user_highest_role,
    get_user_permissions,
    get_user_roles,
    user_has_all_roles,
    user_has_any_role,
    user_has_permission,
    user_has_role,
)
from django_matt.auth.schemas import (
    AccessToken,
    AuthResponse,
    ChangePasswordRequest,
    ErrorResponse,
    LoginRequest,
    LoginWithUsernameRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPair,
    TokenPayload,
    UserResponse,
)

User = get_user_model()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def rf():
    """Provide a Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    """Create a basic test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="TestPass123!",
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def inactive_user(db):
    """Create an inactive user."""
    return User.objects.create_user(
        username="inactive",
        email="inactive@example.com",
        password="TestPass123!",
        is_active=False,
    )


@pytest.fixture
@pytest.mark.django_db
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="TestPass123!",
        is_staff=True,
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def superuser(db):
    """Create a superuser."""
    return User.objects.create_superuser(
        username="superadmin",
        email="superadmin@example.com",
        password="TestPass123!",
    )


@pytest.fixture
@pytest.mark.django_db
def user_with_groups(db):
    """Create a user with groups assigned."""
    user = User.objects.create_user(
        username="groupuser",
        email="groupuser@example.com",
        password="TestPass123!",
        is_active=True,
    )
    editor_group, _ = Group.objects.get_or_create(name="editor")
    viewer_group, _ = Group.objects.get_or_create(name="viewer")
    user.groups.add(editor_group, viewer_group)
    return user


@pytest.fixture
def access_token(user):
    """Generate a valid access token for the test user."""
    return create_access_token(user)


@pytest.fixture
def refresh_token_str(user):
    """Generate a valid refresh token for the test user."""
    return create_refresh_token(user)


@pytest.fixture
def token_pair(user):
    """Generate a token pair for the test user."""
    return create_token_pair(user)


# =============================================================================
# JWT Builtin Tests
# =============================================================================


class TestJWTBuiltin:
    """Test the built-in JWT implementation (jwt_builtin.py)."""

    def test_encode_decode_roundtrip(self):
        """Encoding then decoding should return the original payload."""
        payload = {"sub": "123", "role": "admin"}
        secret = "test-secret"
        token = encode_jwt(payload, secret, algorithm="HS256", expires_in=3600)
        decoded = decode_jwt(token, secret, algorithms=["HS256"])
        assert decoded["sub"] == "123"
        assert decoded["role"] == "admin"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_expired_token_raises(self):
        """Decoding an expired token should raise JWTExpiredError."""
        payload = {"sub": "123"}
        secret = "test-secret"
        token = encode_jwt(payload, secret, expires_in=-1)
        with pytest.raises(JWTExpiredError):
            decode_jwt(token, secret)

    def test_invalid_signature_raises(self):
        """Decoding with wrong secret should raise JWTInvalidSignatureError."""
        payload = {"sub": "123"}
        token = encode_jwt(payload, "correct-secret", expires_in=3600)
        with pytest.raises(JWTInvalidSignatureError):
            decode_jwt(token, "wrong-secret")

    def test_malformed_token_raises(self):
        """Decoding a malformed token should raise JWTDecodeError."""
        with pytest.raises(JWTDecodeError):
            decode_jwt("not.a.valid.token.format", "secret")

    def test_empty_token_raises(self):
        """Decoding an empty string should raise JWTDecodeError."""
        with pytest.raises(JWTDecodeError):
            decode_jwt("", "secret")

    def test_algorithm_mismatch_raises(self):
        """Decoding with wrong algorithm list should raise an error."""
        payload = {"sub": "123"}
        token = encode_jwt(payload, "secret", algorithm="HS256", expires_in=3600)
        with pytest.raises(JWTError):
            decode_jwt(token, "secret", algorithms=["HS512"])

    def test_hs384_algorithm(self):
        """HS384 algorithm should work correctly."""
        payload = {"sub": "user1"}
        secret = "test-secret-384"
        token = encode_jwt(payload, secret, algorithm="HS384", expires_in=3600)
        decoded = decode_jwt(token, secret, algorithms=["HS384"])
        assert decoded["sub"] == "user1"

    def test_hs512_algorithm(self):
        """HS512 algorithm should work correctly."""
        payload = {"sub": "user2"}
        secret = "test-secret-512"
        token = encode_jwt(payload, secret, algorithm="HS512", expires_in=3600)
        decoded = decode_jwt(token, secret, algorithms=["HS512"])
        assert decoded["sub"] == "user2"

    def test_issuer_claim_validation(self):
        """Issuer claim should be verified when specified."""
        payload = {"sub": "123"}
        secret = "test-secret"
        token = encode_jwt(payload, secret, expires_in=3600, issuer="myapp")
        decoded = decode_jwt(token, secret, verify_iss="myapp")
        assert decoded["iss"] == "myapp"

    def test_issuer_mismatch_raises(self):
        """Mismatched issuer should raise JWTInvalidClaimError."""
        from django_matt.auth.jwt_builtin import JWTInvalidClaimError

        payload = {"sub": "123"}
        secret = "test-secret"
        token = encode_jwt(payload, secret, expires_in=3600, issuer="myapp")
        with pytest.raises(JWTInvalidClaimError):
            decode_jwt(token, secret, verify_iss="other-app")

    def test_audience_claim_validation(self):
        """Audience claim should be verified when specified."""
        payload = {"sub": "123"}
        secret = "test-secret"
        token = encode_jwt(payload, secret, expires_in=3600, audience="my-audience")
        decoded = decode_jwt(token, secret, verify_aud="my-audience")
        assert "aud" in decoded

    def test_no_expiration(self):
        """Token without expiration should decode without error."""
        payload = {"sub": "123"}
        secret = "test-secret"
        token = encode_jwt(payload, secret)
        decoded = decode_jwt(token, secret, verify_exp=True)
        assert decoded["sub"] == "123"

    def test_custom_headers(self):
        """Custom headers should be included in the token."""
        from django_matt.auth.jwt_builtin import get_unverified_header

        payload = {"sub": "123"}
        secret = "test-secret"
        token = encode_jwt(payload, secret, expires_in=3600, headers={"kid": "key-1"})
        header = get_unverified_header(token)
        assert header["kid"] == "key-1"
        assert header["alg"] == "HS256"


# =============================================================================
# JWT Module Tests (django_matt.auth.jwt)
# =============================================================================


class TestJWTConfig:
    """Test JWT configuration."""

    def test_default_config_values(self):
        """JWTConfig should have sensible defaults."""
        config = JWTConfig()
        assert config.algorithm == "HS256"
        assert config.access_token_lifetime == timedelta(minutes=15)
        assert config.refresh_token_lifetime == timedelta(days=7)
        assert config.rotate_refresh_tokens is True
        assert config.user_id_claim == "sub"
        assert config.auth_header_types == ["Bearer"]
        assert config.auth_header_name == "Authorization"

    def test_secret_key_falls_back_to_django_secret(self):
        """Secret key should default to Django's SECRET_KEY."""
        from django.conf import settings

        config = JWTConfig()
        assert config.secret_key == settings.SECRET_KEY

    def test_signing_key_defaults_to_secret_key(self):
        """Signing key should default to secret_key when not explicitly set."""
        config = JWTConfig()
        assert config.signing_key == config.secret_key

    def test_verifying_key_defaults_to_none(self):
        """Verifying key should be None by default."""
        config = JWTConfig()
        assert config.verifying_key is None


class TestJWTGeneration:
    """Test JWT token generation functions."""

    def test_generate_jti_is_unique(self):
        """Generated JTIs should be unique."""
        jti1 = generate_jti()
        jti2 = generate_jti()
        assert jti1 != jti2
        assert len(jti1) > 0

    @pytest.mark.django_db
    def test_create_access_token(self, user):
        """Should create a valid access token."""
        token = create_access_token(user)
        assert isinstance(token, str)
        assert len(token) > 0

        payload = verify_access_token(token)
        assert payload.sub == str(user.pk)
        assert payload.type == "access"
        assert payload.email == user.email
        assert payload.jti is not None

    @pytest.mark.django_db
    def test_create_access_token_with_extra_claims(self, user):
        """Access token should include extra claims."""
        token = create_access_token(user, extra_claims={"org_id": "org-123"})
        payload = decode_token(token)
        assert payload.org_id == "org-123"

    @pytest.mark.django_db
    def test_create_access_token_with_custom_lifetime(self, user):
        """Access token should respect custom lifetime."""
        short_lifetime = timedelta(seconds=30)
        token = create_access_token(user, lifetime=short_lifetime)
        payload = decode_token(token)
        # exp - iat should be roughly 30 seconds
        exp_ts = payload.exp.timestamp() if isinstance(payload.exp, datetime) else payload.exp
        iat_ts = payload.iat.timestamp() if isinstance(payload.iat, datetime) else payload.iat
        diff = exp_ts - iat_ts
        assert 25 <= diff <= 35

    @pytest.mark.django_db
    def test_create_refresh_token(self, user):
        """Should create a valid refresh token."""
        token = create_refresh_token(user)
        assert isinstance(token, str)
        assert len(token) > 0

        payload = verify_refresh_token(token)
        assert payload.sub == str(user.pk)
        assert payload.type == "refresh"
        assert payload.jti is not None

    @pytest.mark.django_db
    def test_create_token_pair(self, user):
        """Should create both access and refresh tokens."""
        pair = create_token_pair(user)
        assert isinstance(pair, TokenPair)
        assert pair.token_type == "Bearer"
        assert pair.access_token
        assert pair.refresh_token
        assert pair.expires_in == int(jwt_config.access_token_lifetime.total_seconds())
        assert pair.refresh_expires_in == int(jwt_config.refresh_token_lifetime.total_seconds())

    @pytest.mark.django_db
    def test_access_token_contains_roles(self, user_with_groups):
        """Access token should include user roles from groups."""
        token = create_access_token(user_with_groups)
        payload = decode_token(token)
        assert "editor" in payload.roles
        assert "viewer" in payload.roles


class TestJWTVerification:
    """Test JWT token verification."""

    @pytest.mark.django_db
    def test_verify_valid_access_token(self, user):
        """Should verify a valid access token."""
        token = create_access_token(user)
        payload = verify_access_token(token)
        assert payload.sub == str(user.pk)
        assert payload.type == "access"

    @pytest.mark.django_db
    def test_verify_valid_refresh_token(self, user):
        """Should verify a valid refresh token."""
        token = create_refresh_token(user)
        payload = verify_refresh_token(token)
        assert payload.sub == str(user.pk)
        assert payload.type == "refresh"

    @pytest.mark.django_db
    def test_verify_access_rejects_refresh_token(self, user):
        """verify_access_token should reject a refresh token."""
        token = create_refresh_token(user)
        with pytest.raises(InvalidTokenError):
            verify_access_token(token)

    @pytest.mark.django_db
    def test_verify_refresh_rejects_access_token(self, user):
        """verify_refresh_token should reject an access token."""
        token = create_access_token(user)
        with pytest.raises(InvalidTokenError):
            verify_refresh_token(token)

    @pytest.mark.django_db
    def test_expired_access_token_raises(self, user):
        """Expired access token should raise ExpiredSignatureError."""
        token = create_access_token(user, lifetime=timedelta(seconds=-1))
        with pytest.raises(ExpiredSignatureError):
            verify_access_token(token)

    def test_tampered_token_raises(self):
        """A tampered token should raise InvalidTokenError."""
        payload = {"sub": "123", "type": "access", "jti": "test-id"}
        token = encode_jwt(payload, "correct-secret", expires_in=3600)
        # Tamper with the payload
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + "x" + "." + parts[2]
        with pytest.raises((InvalidTokenError, JWTError)):
            decode_token(tampered)

    def test_decode_token_with_invalid_string(self):
        """Should raise on completely invalid token string."""
        with pytest.raises(InvalidTokenError):
            decode_token("not-a-jwt-token")


class TestJWTRefreshTokens:
    """Test JWT token refresh flow."""

    @pytest.mark.django_db
    def test_refresh_tokens_success(self, user):
        """Should return new token pair from valid refresh token."""
        original_pair = create_token_pair(user)
        new_pair = refresh_tokens(original_pair.refresh_token)

        assert isinstance(new_pair, TokenPair)
        assert new_pair.access_token != original_pair.access_token
        assert new_pair.refresh_token != original_pair.refresh_token

    @pytest.mark.django_db
    def test_refresh_tokens_with_expired_refresh(self, user):
        """Should raise on expired refresh token."""
        token = create_refresh_token(user, lifetime=timedelta(seconds=-1))
        with pytest.raises(ExpiredSignatureError):
            refresh_tokens(token)

    @pytest.mark.django_db
    def test_refresh_tokens_with_inactive_user(self, user):
        """Should raise when user is inactive."""
        token = create_refresh_token(user)
        user.is_active = False
        user.save()
        with pytest.raises(InvalidTokenError, match="User is inactive"):
            refresh_tokens(token)

    @pytest.mark.django_db
    def test_refresh_tokens_with_deleted_user(self, user):
        """Should raise when user no longer exists."""
        token = create_refresh_token(user)
        # Mock the user lookup to simulate a deleted user without actually
        # deleting (which cascades to FK tables that may not exist in tests).
        original_get_user_model = get_user_model

        def mock_user_model():
            model = original_get_user_model()

            class MockManager:
                def get(self, **kwargs):
                    raise model.DoesNotExist("User matching query does not exist.")

            class MockModel:
                DoesNotExist = model.DoesNotExist
                objects = MockManager()

            return MockModel

        with (
            patch("django_matt.auth.jwt.get_user_model", mock_user_model),
            pytest.raises(InvalidTokenError, match="User not found"),
        ):
            refresh_tokens(token)

    @pytest.mark.django_db
    def test_refresh_with_access_token_fails(self, user):
        """Using an access token for refresh should fail."""
        token = create_access_token(user)
        with pytest.raises((InvalidTokenError, ExpiredSignatureError)):
            refresh_tokens(token)


class TestJWTRequestHelpers:
    """Test JWT request utility functions."""

    @pytest.mark.django_db
    def test_get_token_from_request_bearer(self, rf, user):
        """Should extract Bearer token from Authorization header."""
        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        extracted = get_token_from_request(request)
        assert extracted == token

    def test_get_token_from_request_no_header(self, rf):
        """Should return None when no Authorization header."""
        request = rf.get("/")
        assert get_token_from_request(request) is None

    def test_get_token_from_request_wrong_type(self, rf):
        """Should return None for non-Bearer auth type."""
        request = rf.get("/", HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz")
        assert get_token_from_request(request) is None

    def test_get_token_from_request_malformed_header(self, rf):
        """Should return None for malformed Authorization header."""
        request = rf.get("/", HTTP_AUTHORIZATION="BearerTokenWithoutSpace")
        assert get_token_from_request(request) is None

    @pytest.mark.django_db
    def test_get_user_from_token_valid(self, user):
        """Should return the user for a valid token."""
        token = create_access_token(user)
        found_user = get_user_from_token(token)
        assert found_user is not None
        assert found_user.pk == user.pk

    def test_get_user_from_token_invalid(self):
        """Should return None for an invalid token."""
        assert get_user_from_token("invalid-token") is None

    @pytest.mark.django_db
    def test_get_user_from_token_expired(self, user):
        """Should return None for expired token."""
        token = create_access_token(user, lifetime=timedelta(seconds=-1))
        assert get_user_from_token(token) is None


class TestJWTAuthentication:
    """Test JWTAuthentication class."""

    @pytest.mark.django_db
    def test_authenticate_success(self, rf, user):
        """Should authenticate with valid token."""
        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = JWTAuthentication()
        result = auth.authenticate(request)
        assert result is not None
        auth_user, auth_token = result
        assert auth_user.pk == user.pk
        assert auth_token == token

    @pytest.mark.django_db
    def test_authenticate_no_token(self, rf):
        """Should return None when no token provided."""
        request = rf.get("/")
        auth = JWTAuthentication()
        assert auth.authenticate(request) is None

    @pytest.mark.django_db
    def test_authenticate_inactive_user(self, rf, inactive_user):
        """Should return None for inactive user."""
        token = create_access_token(inactive_user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = JWTAuthentication()
        assert auth.authenticate(request) is None

    def test_authenticate_header(self, rf):
        """Should return proper WWW-Authenticate header."""
        request = rf.get("/")
        auth = JWTAuthentication()
        header = auth.authenticate_header(request)
        assert "Bearer" in header
        assert "realm" in header


class TestMattJWTAuth:
    """Test MattJWTAuth unified authentication class."""

    def test_aliases_point_to_same_class(self):
        """JWTAuthentication, JWTAuth, AsyncJWTAuth should all be MattJWTAuth."""
        assert JWTAuthentication is MattJWTAuth
        assert JWTAuth is MattJWTAuth
        assert AsyncJWTAuth is MattJWTAuth

    @pytest.mark.django_db
    def test_sync_authenticate_success(self, rf, user):
        """Sync authenticate() should return (user, token) with valid token."""
        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = MattJWTAuth()
        result = auth.authenticate(request)
        assert result is not None
        auth_user, auth_token = result
        assert auth_user.pk == user.pk
        assert auth_token == token

    @pytest.mark.django_db
    def test_sync_authenticate_no_token(self, rf):
        """Sync authenticate() should return None when no token."""
        request = rf.get("/")
        auth = MattJWTAuth()
        assert auth.authenticate(request) is None

    @pytest.mark.django_db
    def test_sync_authenticate_inactive_user(self, rf, inactive_user):
        """Sync authenticate() should return None for inactive user."""
        token = create_access_token(inactive_user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = MattJWTAuth()
        assert auth.authenticate(request) is None

    @pytest.mark.django_db(transaction=True)
    async def test_async_authenticate_success(self, rf):
        """Async aauthenticate() should return (user, token) with valid token."""
        User = get_user_model()
        user = await User.objects.acreate_user(
            username="async_auth_user",
            email="async_auth@example.com",
            password="TestPass123!",
        )
        token = await acreate_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = MattJWTAuth()
        result = await auth.aauthenticate(request)
        assert result is not None
        auth_user, auth_token = result
        assert auth_user.pk == user.pk
        assert auth_token == token

    @pytest.mark.django_db(transaction=True)
    async def test_async_authenticate_no_token(self, rf):
        """Async aauthenticate() should return None when no token."""
        request = rf.get("/")
        auth = MattJWTAuth()
        assert await auth.aauthenticate(request) is None

    @pytest.mark.django_db(transaction=True)
    async def test_async_authenticate_expired_token(self, rf):
        """Async aauthenticate() should return None for expired token."""
        User = get_user_model()
        user = await User.objects.acreate_user(
            username="async_expired_user",
            email="async_expired@example.com",
            password="TestPass123!",
        )
        token = await acreate_access_token(user, lifetime=timedelta(seconds=-1))
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = MattJWTAuth()
        assert await auth.aauthenticate(request) is None

    @pytest.mark.django_db(transaction=True)
    async def test_async_authenticate_inactive_user(self, rf):
        """Async aauthenticate() should return None for inactive user."""
        User = get_user_model()
        user = await User.objects.acreate_user(
            username="async_inactive_user",
            email="async_inactive@example.com",
            password="TestPass123!",
            is_active=False,
        )
        token = await acreate_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        auth = MattJWTAuth()
        assert await auth.aauthenticate(request) is None

    def test_authenticate_header(self, rf):
        """authenticate_header() should return proper WWW-Authenticate value."""
        request = rf.get("/")
        auth = MattJWTAuth()
        header = auth.authenticate_header(request)
        assert "Bearer" in header
        assert "realm" in header

    def test_importable_from_auth_init(self):
        """MattJWTAuth, JWTAuth, AsyncJWTAuth should be importable from django_matt.auth."""
        from django_matt.auth import AsyncJWTAuth as A
        from django_matt.auth import JWTAuth as J
        from django_matt.auth import MattJWTAuth as M

        assert M is MattJWTAuth
        assert J is MattJWTAuth
        assert A is MattJWTAuth


# =============================================================================
# JWT Decorator Tests
# =============================================================================


class TestJWTDecorators:
    """Test jwt_required and jwt_optional decorators."""

    @pytest.mark.django_db
    def test_jwt_required_with_valid_token(self, rf, user):
        """jwt_required should pass with valid token."""
        from django_matt.auth.decorators import jwt_required

        @jwt_required
        def protected_view(request):
            return {"user": request.user.pk}

        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        result = protected_view(request)
        assert isinstance(result, dict)
        assert result["user"] == user.pk

    @pytest.mark.django_db
    def test_jwt_required_without_token(self, rf):
        """jwt_required should return 401 without token."""
        from django_matt.auth.decorators import jwt_required

        @jwt_required
        def protected_view(request):
            return {"user": "should not reach here"}

        request = rf.get("/")
        result = protected_view(request)
        assert result.status_code == 401

    @pytest.mark.django_db
    def test_jwt_required_with_expired_token(self, rf, user):
        """jwt_required should return 401 with expired token."""
        from django_matt.auth.decorators import jwt_required

        @jwt_required
        def protected_view(request):
            return {"user": "should not reach here"}

        token = create_access_token(user, lifetime=timedelta(seconds=-1))
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        result = protected_view(request)
        assert result.status_code == 401

    @pytest.mark.django_db
    def test_jwt_optional_with_valid_token(self, rf, user):
        """jwt_optional should set user when valid token is present."""
        from django_matt.auth.decorators import jwt_optional

        @jwt_optional
        def public_view(request):
            if hasattr(request, "user") and hasattr(request.user, "pk"):
                return {"user": request.user.pk}
            return {"user": None}

        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        result = public_view(request)
        assert isinstance(result, dict)
        assert result["user"] == user.pk

    @pytest.mark.django_db
    def test_jwt_optional_without_token(self, rf):
        """jwt_optional should proceed without setting user when no token."""
        from django_matt.auth.decorators import jwt_optional

        @jwt_optional
        def public_view(request):
            return {"reached": True}

        request = rf.get("/")
        result = public_view(request)
        assert isinstance(result, dict)
        assert result["reached"] is True

    @pytest.mark.django_db
    def test_requires_auth_is_alias(self, rf, user):
        """requires_auth should behave the same as jwt_required."""
        from django_matt.auth.decorators import requires_auth

        @requires_auth
        def protected_view(request):
            return {"user": request.user.pk}

        token = create_access_token(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")
        result = protected_view(request)
        assert isinstance(result, dict)
        assert result["user"] == user.pk


# =============================================================================
# Role Decorator Tests
# =============================================================================


class TestRoleDecorators:
    """Test admin_required, superuser_required, with_roles, with_permission."""

    @pytest.mark.django_db
    def test_admin_required_with_staff_user(self, rf, admin_user):
        """admin_required should pass for staff users."""
        from django_matt.auth.decorators import admin_required

        @admin_required
        def admin_view(request):
            return {"admin": True}

        request = rf.get("/")
        request.user = admin_user
        result = admin_view(request)
        assert isinstance(result, dict)
        assert result["admin"] is True

    @pytest.mark.django_db
    def test_admin_required_with_regular_user(self, rf, user):
        """admin_required should return 403 for regular users."""
        from django_matt.auth.decorators import admin_required

        @admin_required
        def admin_view(request):
            return {"admin": True}

        request = rf.get("/")
        request.user = user
        result = admin_view(request)
        assert result.status_code == 403

    @pytest.mark.django_db
    def test_admin_required_unauthenticated(self, rf):
        """admin_required should return 401 for unauthenticated users."""
        from django_matt.auth.decorators import admin_required

        @admin_required
        def admin_view(request):
            return {"admin": True}

        request = rf.get("/")
        request.user = AnonymousUser()
        result = admin_view(request)
        assert result.status_code == 401

    @pytest.mark.django_db
    def test_superuser_required_with_superuser(self, rf, superuser):
        """superuser_required should pass for superusers."""
        from django_matt.auth.decorators import superuser_required

        @superuser_required
        def super_view(request):
            return {"super": True}

        request = rf.get("/")
        request.user = superuser
        result = super_view(request)
        assert isinstance(result, dict)
        assert result["super"] is True

    @pytest.mark.django_db
    def test_superuser_required_with_staff_user(self, rf, admin_user):
        """superuser_required should return 403 for non-super staff."""
        from django_matt.auth.decorators import superuser_required

        @superuser_required
        def super_view(request):
            return {"super": True}

        request = rf.get("/")
        request.user = admin_user
        result = super_view(request)
        assert result.status_code == 403

    @pytest.mark.django_db
    def test_with_roles_any_match(self, rf, user_with_groups):
        """with_roles should pass if user has any of the specified roles."""
        from django_matt.auth.decorators import with_roles

        @with_roles("editor", "admin")
        def role_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = role_view(request)
        assert isinstance(result, dict)
        assert result["ok"] is True

    @pytest.mark.django_db
    def test_with_roles_no_match(self, rf, user):
        """with_roles should return 403 if user has none of the roles."""
        from django_matt.auth.decorators import with_roles

        @with_roles("admin", "manager")
        def role_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user
        result = role_view(request)
        assert result.status_code == 403

    @pytest.mark.django_db
    def test_with_roles_require_all(self, rf, user_with_groups):
        """with_roles with require_all should require all roles."""
        from django_matt.auth.decorators import with_roles

        @with_roles("editor", "viewer", require_all=True)
        def role_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = role_view(request)
        assert isinstance(result, dict)
        assert result["ok"] is True

    @pytest.mark.django_db
    def test_with_roles_require_all_missing_one(self, rf, user_with_groups):
        """with_roles require_all should fail if missing any role."""
        from django_matt.auth.decorators import with_roles

        @with_roles("editor", "admin", require_all=True)
        def role_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = role_view(request)
        assert result.status_code == 403

    @pytest.mark.django_db
    def test_with_permission_success(self, rf, user_with_groups):
        """with_permission should pass when user has the permission via RBAC."""
        from django_matt.auth.decorators import with_permission

        # editor inherits viewer, which has "read" permission
        @with_permission("read")
        def perm_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = perm_view(request)
        assert isinstance(result, dict)
        assert result["ok"] is True

    @pytest.mark.django_db
    def test_with_permission_denied(self, rf, user):
        """with_permission should return 403 when user lacks permission."""
        from django_matt.auth.decorators import with_permission

        @with_permission("manage_users")
        def perm_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user
        result = perm_view(request)
        assert result.status_code == 403

    @pytest.mark.django_db
    def test_with_permission_unauthenticated(self, rf):
        """with_permission should return 401 for unauthenticated users."""
        from django_matt.auth.decorators import with_permission

        @with_permission("read")
        def perm_view(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = AnonymousUser()
        result = perm_view(request)
        assert result.status_code == 401


# =============================================================================
# Magic Link Tests
# =============================================================================


class TestMagicLinkConfig:
    """Test MagicLinkConfig."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = MagicLinkConfig()
        assert config.token_lifetime == timedelta(minutes=15)
        assert config.max_uses == 1
        assert config.verify_path == "/auth/magic-link/verify"
        assert config.email_subject == "Your login link"
        assert config.create_user_if_not_exists is False
        assert config.allow_registration is True


class TestMagicLinkTokenCreation:
    """Test magic link token creation."""

    def test_create_token_returns_string(self):
        """Should return a non-empty string."""
        token = create_magic_link_token("user@example.com")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_has_two_parts(self):
        """Token should have payload.signature format."""
        token = create_magic_link_token("user@example.com")
        parts = token.split(".")
        assert len(parts) == 2

    def test_create_token_normalizes_email(self):
        """Email should be lowercased and trimmed."""
        token = create_magic_link_token("  User@Example.Com  ")
        payload = get_magic_link_payload(token)
        assert payload["email"] == "user@example.com"

    def test_create_token_includes_extra_data(self):
        """Extra data should be included in the payload."""
        token = create_magic_link_token(
            "user@example.com",
            extra_data={"redirect": "/dashboard"},
        )
        payload = get_magic_link_payload(token)
        assert payload["data"]["redirect"] == "/dashboard"

    def test_create_token_custom_lifetime(self):
        """Custom lifetime should be reflected in expiration."""
        lifetime = timedelta(hours=2)
        token = create_magic_link_token("user@example.com", lifetime=lifetime)
        payload = get_magic_link_payload(token)
        exp = payload["exp"]
        iat = payload["iat"]
        # Should be ~7200 seconds
        assert 7190 <= (exp - iat) <= 7210

    def test_tokens_are_unique(self):
        """Two tokens for the same email should be different (unique nonce)."""
        t1 = create_magic_link_token("user@example.com")
        t2 = create_magic_link_token("user@example.com")
        assert t1 != t2


class TestMagicLinkTokenVerification:
    """Test magic link token verification."""

    @pytest.mark.django_db
    def test_verify_valid_token(self, db):
        """Should verify a valid token and return the user."""
        magic_user = User.objects.create_user(
            username="magic_link_user",
            email="magic_link_unique@example.com",
            password="TestPass123!",
            is_active=True,
        )
        token = create_magic_link_token(magic_user.email)
        result = verify_magic_link_token(token)
        assert result.valid is True
        assert result.email == magic_user.email
        assert result.user is not None
        assert result.user.pk == magic_user.pk
        assert result.user_created is False

    def test_verify_expired_token(self):
        """Should fail for an expired token."""
        token = create_magic_link_token(
            "user@example.com",
            lifetime=timedelta(seconds=-1),
        )
        result = verify_magic_link_token(token)
        assert result.valid is False
        assert "expired" in result.error.lower()

    def test_verify_tampered_signature(self):
        """Should fail if signature is tampered."""
        token = create_magic_link_token("user@example.com")
        parts = token.split(".")
        tampered = parts[0] + ".tampered_signature"
        result = verify_magic_link_token(tampered)
        assert result.valid is False
        assert "signature" in result.error.lower()

    def test_verify_invalid_format(self):
        """Should fail for invalid token format."""
        result = verify_magic_link_token("not.a.valid.token")
        assert result.valid is False

    @pytest.mark.django_db
    def test_verify_nonexistent_user_no_create(self, db):
        """Should fail when user doesn't exist and create_user is False."""
        token = create_magic_link_token("nobody@example.com")
        result = verify_magic_link_token(token, create_user=False)
        assert result.valid is False
        assert result.email == "nobody@example.com"

    @pytest.mark.django_db
    def test_verify_creates_user_when_enabled(self, db):
        """Should create user when create_user=True."""
        token = create_magic_link_token("newuser@example.com")
        result = verify_magic_link_token(token, create_user=True)
        assert result.valid is True
        assert result.user_created is True
        assert result.user is not None
        assert result.user.email == "newuser@example.com"
        # Verify user was actually created in DB
        assert User.objects.filter(email="newuser@example.com").exists()

    @pytest.mark.django_db
    def test_verify_inactive_user(self, inactive_user):
        """Should fail for inactive users."""
        token = create_magic_link_token(inactive_user.email)
        result = verify_magic_link_token(token)
        assert result.valid is False
        assert "inactive" in result.error.lower()


class TestMagicLinkPayload:
    """Test get_magic_link_payload."""

    def test_get_payload_from_valid_token(self):
        """Should extract payload without full verification."""
        token = create_magic_link_token("user@example.com")
        payload = get_magic_link_payload(token)
        assert payload is not None
        assert payload["email"] == "user@example.com"
        assert "exp" in payload
        assert "iat" in payload
        assert "nonce" in payload

    def test_get_payload_from_invalid_token(self):
        """Should return None for invalid token."""
        assert get_magic_link_payload("invalid") is None
        assert get_magic_link_payload("") is None


class TestMagicLinkURL:
    """Test magic link URL generation."""

    def test_create_url_with_base(self):
        """Should create a full URL with base and path."""
        url = create_magic_link_url(
            "user@example.com",
            base_url="https://myapp.com",
        )
        assert url.startswith("https://myapp.com/auth/magic-link/verify?token=")

    def test_create_url_custom_path(self):
        """Should use custom verify path."""
        url = create_magic_link_url(
            "user@example.com",
            base_url="https://myapp.com",
            verify_path="/custom/verify",
        )
        assert "/custom/verify?token=" in url

    def test_create_url_without_base_raises(self):
        """Should raise ValueError when base URL is not configured."""
        with pytest.raises(ValueError, match="Base URL not configured"):
            create_magic_link_url("user@example.com")


class TestSendMagicLink:
    """Test send_magic_link function."""

    @patch("django_matt.auth.magic_link.send_mail")
    def test_send_with_custom_function(self, mock_send_mail):
        """Should use custom send function when provided."""
        custom_sender = MagicMock(return_value=True)
        result = send_magic_link(
            "user@example.com",
            magic_link_url="https://example.com/verify?token=abc",
            send_function=custom_sender,
        )
        assert result is True
        custom_sender.assert_called_once()
        call_kwargs = custom_sender.call_args[1]
        assert call_kwargs["to_email"] == "user@example.com"
        assert "https://example.com/verify?token=abc" in call_kwargs["plain_content"]

    @patch("django_matt.auth.magic_link.send_mail")
    def test_send_via_django_mail(self, mock_send_mail):
        """Should send via Django send_mail when no custom function."""
        mock_send_mail.return_value = 1
        result = send_magic_link(
            "user@example.com",
            magic_link_url="https://example.com/verify?token=abc",
        )
        assert result is True
        mock_send_mail.assert_called_once()

    def test_send_without_url_or_config_raises(self):
        """Should raise when no URL provided and base URL not configured."""
        with pytest.raises(ValueError, match="Magic link URL required"):
            send_magic_link("user@example.com")


# =============================================================================
# RBAC Tests
# =============================================================================


class TestRBACConfig:
    """Test RBAC configuration."""

    def test_default_roles_exist(self):
        """Default config should include standard roles."""
        # Reset singleton for clean test
        RBACConfig._instance = None
        config = RBACConfig()
        roles = config.get_all_roles()
        role_names = [r.name for r in roles]
        assert "viewer" in role_names
        assert "editor" in role_names
        assert "admin" in role_names

    def test_role_dataclass(self):
        """Role should store name, permissions, inherits, and priority."""
        role = Role(
            name="custom",
            permissions=["read", "write"],
            inherits=["viewer"],
            priority=5,
        )
        assert role.name == "custom"
        assert "read" in role.permissions
        assert "viewer" in role.inherits
        assert role.priority == 5

    def test_get_role_by_name(self):
        """Should retrieve a role by name."""
        RBACConfig._instance = None
        config = RBACConfig()
        viewer = config.get_role("viewer")
        assert viewer is not None
        assert viewer.name == "viewer"

    def test_get_nonexistent_role(self):
        """Should return None for nonexistent role."""
        RBACConfig._instance = None
        config = RBACConfig()
        assert config.get_role("nonexistent") is None


class TestRBACPermissionHierarchy:
    """Test RBAC permission inheritance."""

    def test_viewer_permissions(self):
        """Viewer should have basic read permissions."""
        RBACConfig._instance = None
        config = RBACConfig()
        perms = config.get_role_permissions("viewer")
        assert "read" in perms
        assert "list" in perms

    def test_editor_inherits_viewer(self):
        """Editor should inherit viewer permissions."""
        RBACConfig._instance = None
        config = RBACConfig()
        perms = config.get_role_permissions("editor")
        # Editor's own permissions
        assert "create" in perms
        assert "update" in perms
        # Inherited from viewer
        assert "read" in perms
        assert "list" in perms

    def test_admin_inherits_chain(self):
        """Admin should have all permissions through inheritance chain."""
        RBACConfig._instance = None
        config = RBACConfig()
        perms = config.get_role_permissions("admin")
        # Admin's own
        assert "manage_users" in perms
        # From manager
        assert "delete" in perms
        # From editor
        assert "create" in perms
        # From viewer
        assert "read" in perms

    def test_superadmin_wildcard(self):
        """Superadmin should have wildcard permission."""
        RBACConfig._instance = None
        config = RBACConfig()
        perms = config.get_role_permissions("superadmin")
        assert "*" in perms

    def test_has_permission_with_wildcard(self):
        """Wildcard permission should match any permission check."""
        RBACConfig._instance = None
        config = RBACConfig()
        assert config.has_permission("superadmin", "anything") is True
        assert config.has_permission("superadmin", "nonexistent") is True

    def test_has_permission_normal(self):
        """Normal permission check should match exact permissions."""
        RBACConfig._instance = None
        config = RBACConfig()
        assert config.has_permission("viewer", "read") is True
        assert config.has_permission("viewer", "delete") is False


class TestRBACRolePriority:
    """Test RBAC role priority and comparison."""

    def test_role_priorities_ascending(self):
        """Higher roles should have higher priority."""
        RBACConfig._instance = None
        config = RBACConfig()
        assert config.get_role_priority("viewer") < config.get_role_priority("editor")
        assert config.get_role_priority("editor") < config.get_role_priority("admin")
        assert config.get_role_priority("admin") < config.get_role_priority("superadmin")

    def test_is_role_higher(self):
        """is_role_higher should correctly compare priorities."""
        RBACConfig._instance = None
        config = RBACConfig()
        assert config.is_role_higher("admin", "viewer") is True
        assert config.is_role_higher("viewer", "admin") is False

    def test_get_highest_role(self):
        """get_highest_role should return the most privileged role."""
        RBACConfig._instance = None
        config = RBACConfig()
        assert config.get_highest_role(["viewer", "editor", "admin"]) == "admin"
        assert config.get_highest_role(["viewer"]) == "viewer"
        assert config.get_highest_role([]) is None

    def test_register_custom_role(self):
        """Should be able to register a custom role."""
        RBACConfig._instance = None
        config = RBACConfig()
        custom = Role(name="moderator", permissions=["moderate"], priority=2)
        config.register_role(custom)
        assert config.get_role("moderator") is not None
        assert "moderate" in config.get_role_permissions("moderator")


class TestRBACUserUtils:
    """Test RBAC user utility functions."""

    @pytest.mark.django_db
    def test_get_user_roles_from_groups(self, user_with_groups):
        """Should get roles from Django groups."""
        roles = get_user_roles(user_with_groups)
        assert "editor" in roles
        assert "viewer" in roles

    @pytest.mark.django_db
    def test_get_user_roles_superuser(self, superuser):
        """Superuser should have superadmin role."""
        roles = get_user_roles(superuser)
        assert "superadmin" in roles

    @pytest.mark.django_db
    def test_get_user_roles_anonymous(self):
        """Anonymous users should have no roles."""
        roles = get_user_roles(AnonymousUser())
        assert roles == []

    @pytest.mark.django_db
    def test_get_user_roles_none(self):
        """None user should return empty list."""
        assert get_user_roles(None) == []

    @pytest.mark.django_db
    def test_user_has_permission_via_role(self, user_with_groups):
        """User should have permissions through their roles."""
        RBACConfig._instance = None
        RBACConfig()
        # Editor inherits viewer which has "read"
        assert user_has_permission(user_with_groups, "read") is True
        # Editor has "create"
        assert user_has_permission(user_with_groups, "create") is True

    @pytest.mark.django_db
    def test_user_has_permission_denied(self, user):
        """User without required role should not have permission."""
        assert user_has_permission(user, "manage_users") is False

    @pytest.mark.django_db
    def test_superuser_has_all_permissions(self, superuser):
        """Superusers should have all permissions."""
        assert user_has_permission(superuser, "anything") is True
        assert user_has_permission(superuser, "random_perm") is True

    @pytest.mark.django_db
    def test_user_has_role(self, user_with_groups):
        """user_has_role should check role membership."""
        assert user_has_role(user_with_groups, "editor") is True
        assert user_has_role(user_with_groups, "admin") is False

    @pytest.mark.django_db
    def test_user_has_any_role(self, user_with_groups):
        """user_has_any_role should check for any match."""
        assert user_has_any_role(user_with_groups, ["editor", "admin"]) is True
        assert user_has_any_role(user_with_groups, ["admin", "superadmin"]) is False

    @pytest.mark.django_db
    def test_user_has_all_roles(self, user_with_groups):
        """user_has_all_roles should check for all roles."""
        assert user_has_all_roles(user_with_groups, ["editor", "viewer"]) is True
        assert user_has_all_roles(user_with_groups, ["editor", "admin"]) is False

    @pytest.mark.django_db
    def test_get_user_highest_role(self, user_with_groups):
        """Should return the highest priority role."""
        RBACConfig._instance = None
        RBACConfig()
        highest = get_user_highest_role(user_with_groups)
        # Editor has higher priority than viewer
        assert highest == "editor"


class TestRBACDecorators:
    """Test RBAC decorators from rbac/decorators.py."""

    @pytest.mark.django_db
    def test_requires_role_hierarchy_pass(self, rf, user_with_groups):
        """Should pass when user meets minimum role level."""
        from django_matt.auth.rbac.decorators import requires_role_hierarchy

        RBACConfig._instance = None
        RBACConfig()

        @requires_role_hierarchy("viewer")
        def view_func(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = view_func(request)
        assert isinstance(result, dict)
        assert result["ok"] is True

    @pytest.mark.django_db
    def test_requires_role_hierarchy_fail(self, rf, user_with_groups):
        """Should return 403 when user doesn't meet minimum role level."""
        from django_matt.auth.rbac.decorators import requires_role_hierarchy

        RBACConfig._instance = None
        RBACConfig()

        @requires_role_hierarchy("admin")
        def view_func(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = view_func(request)
        assert result.status_code == 403

    @pytest.mark.django_db
    def test_requires_rbac_permission_pass(self, rf, user_with_groups):
        """Should pass when user has required RBAC permission."""
        from django_matt.auth.rbac.decorators import requires_rbac_permission

        RBACConfig._instance = None
        RBACConfig()

        @requires_rbac_permission("read")
        def view_func(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user_with_groups
        result = view_func(request)
        assert isinstance(result, dict)

    @pytest.mark.django_db
    def test_requires_rbac_permission_fail(self, rf, user):
        """Should return 403 when user lacks RBAC permission."""
        from django_matt.auth.rbac.decorators import requires_rbac_permission

        @requires_rbac_permission("manage_users")
        def view_func(request):
            return {"ok": True}

        request = rf.get("/")
        request.user = user
        result = view_func(request)
        assert result.status_code == 403


# =============================================================================
# OAuth Tests
# =============================================================================


class TestOAuthConfig:
    """Test OAuth configuration."""

    def test_oauth_config_from_settings(self):
        """OAuthConfig should load from settings."""
        from django_matt.auth.oauth.config import OAuthConfig, reset_oauth_config

        reset_oauth_config()
        config = OAuthConfig.from_settings()
        assert isinstance(config, OAuthConfig)
        assert isinstance(config.google.scopes, list)

    def test_oauth_provider_config_defaults(self):
        """Provider config should have sensible defaults."""
        from django_matt.auth.oauth.config import OAuthProviderConfig

        config = OAuthProviderConfig()
        assert config.client_id == ""
        assert config.client_secret == ""
        assert config.enabled is True

    def test_get_enabled_providers_empty(self):
        """Should return empty list when no providers configured."""
        from django_matt.auth.oauth.config import OAuthConfig

        config = OAuthConfig()
        assert config.get_enabled_providers() == []

    def test_get_provider_config_unconfigured(self):
        """Should return None for unconfigured provider."""
        from django_matt.auth.oauth.config import OAuthConfig

        config = OAuthConfig()
        assert config.get_provider_config("google") is None

    def test_validate_config_missing_base_url(self):
        """Should report error when redirect_uri_base is missing."""
        from django_matt.auth.oauth.config import OAuthConfig

        config = OAuthConfig()
        errors = config.validate()
        assert any("REDIRECT_URI_BASE" in e for e in errors)


class TestOAuthProviders:
    """Test OAuth provider classes."""

    def test_provider_registry(self):
        """All built-in providers should be in the registry."""
        from django_matt.auth.oauth.providers import PROVIDERS, get_provider

        assert "google" in PROVIDERS
        assert "github" in PROVIDERS
        assert "apple" in PROVIDERS
        assert "microsoft" in PROVIDERS
        assert get_provider("unknown") is None

    def test_google_provider_attributes(self):
        """Google provider should have correct URLs."""
        from django_matt.auth.oauth.providers.google import GoogleOAuthProvider

        assert GoogleOAuthProvider.name == "google"
        assert "accounts.google.com" in GoogleOAuthProvider.authorization_url
        assert "googleapis.com" in GoogleOAuthProvider.token_url
        assert GoogleOAuthProvider.supports_oidc is True

    def test_google_get_user_info(self):
        """Google provider should parse user info correctly."""
        from django_matt.auth.oauth.providers.google import GoogleOAuthProvider

        # Mock the __init__ to avoid loading settings
        with patch.object(GoogleOAuthProvider, "__init__", lambda self: None):
            provider = GoogleOAuthProvider()
            provider.name = "google"

            data = {
                "sub": "google-user-123",
                "email": "user@gmail.com",
                "email_verified": True,
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe",
                "picture": "https://photo.url",
                "locale": "en",
            }
            info = provider.get_user_info(data)
            assert info.provider == "google"
            assert info.provider_user_id == "google-user-123"
            assert info.email == "user@gmail.com"
            assert info.email_verified is True
            assert info.first_name == "John"
            assert info.last_name == "Doe"

    def test_oauth_error_classes(self):
        """OAuth error classes should have correct hierarchy."""
        from django_matt.auth.oauth.providers.base import (
            OAuthAuthenticationError,
            OAuthConfigError,
            OAuthError,
            OAuthUserInfoError,
        )

        assert issubclass(OAuthConfigError, OAuthError)
        assert issubclass(OAuthAuthenticationError, OAuthError)
        assert issubclass(OAuthUserInfoError, OAuthError)

        error = OAuthError("test error", error_code="test_code")
        assert error.message == "test error"
        assert error.error_code == "test_code"

    def test_oauth_token_dataclass(self):
        """OAuthToken should store token data."""
        from django_matt.auth.oauth.providers.base import OAuthToken

        token = OAuthToken(
            access_token="access-123",
            token_type="Bearer",
            refresh_token="refresh-456",
            expires_in=3600,
        )
        assert token.access_token == "access-123"
        assert token.refresh_token == "refresh-456"
        assert token.expires_in == 3600

    def test_oauth_user_info_dataclass(self):
        """OAuthUserInfo should store normalized user data."""
        from django_matt.auth.oauth.providers.base import OAuthUserInfo

        info = OAuthUserInfo(
            provider="github",
            provider_user_id="gh-123",
            email="dev@github.com",
            email_verified=True,
            name="Dev User",
        )
        assert info.provider == "github"
        assert info.email == "dev@github.com"


class TestOAuthProviderAuthorizationURL:
    """Test OAuth authorization URL generation."""

    @patch("django_matt.auth.oauth.config.get_oauth_config")
    def test_google_authorization_url(self, mock_config):
        """Google provider should generate valid authorization URL."""
        from django_matt.auth.oauth.config import OAuthConfig, OAuthProviderConfig
        from django_matt.auth.oauth.providers.google import GoogleOAuthProvider

        mock_cfg = OAuthConfig(
            redirect_uri_base="https://example.com",
            google=OAuthProviderConfig(
                client_id="test-client-id",
                client_secret="test-secret",
                scopes=["openid", "email", "profile"],
            ),
        )
        mock_config.return_value = mock_cfg

        provider = GoogleOAuthProvider()
        url, state = provider.get_authorization_url()

        assert "accounts.google.com" in url
        assert "client_id=test-client-id" in url
        assert "response_type=code" in url
        assert "state=" in url
        assert state is not None
        assert len(state) > 0


# =============================================================================
# SSO Tests
# =============================================================================


class TestSSOConfig:
    """Test SSO configuration."""

    def test_sso_config_defaults(self):
        """SSOConfig should have sensible defaults."""
        from django_matt.auth.sso.config import SSOConfig

        # Create instance directly; SSOConfig.from_settings() has a bug where
        # it references cls.allowed_providers which is a default_factory field
        # and not a class attribute.
        config = SSOConfig()
        assert config.enabled is True
        assert config.auto_create_user is True
        assert config.state_timeout == 600
        assert "saml" in config.allowed_providers
        assert "oidc" in config.allowed_providers

    def test_is_provider_allowed(self):
        """Should correctly check allowed providers."""
        from django_matt.auth.sso.config import SSOConfig

        config = SSOConfig(allowed_providers=["saml", "oidc"])
        assert config.is_provider_allowed("saml") is True
        assert config.is_provider_allowed("SAML") is True
        assert config.is_provider_allowed("ldap") is False

    def test_validate_missing_callback_url(self):
        """Should report error when callback URL is missing."""
        from django_matt.auth.sso.config import SSOConfig

        config = SSOConfig(callback_url_base="")
        errors = config.validate()
        assert any("CALLBACK_URL_BASE" in e for e in errors)


class TestSSOProviders:
    """Test SSO provider registry."""

    def test_provider_registry(self):
        """All providers should be in the registry."""
        from django_matt.auth.sso.providers import PROVIDERS, get_provider_class

        assert "saml" in PROVIDERS
        assert "oidc" in PROVIDERS
        assert "okta" in PROVIDERS
        assert "azure_ad" in PROVIDERS
        assert get_provider_class("unknown") is None

    def test_sso_error_hierarchy(self):
        """SSO error classes should have correct hierarchy."""
        from django_matt.auth.sso.providers.base import (
            SSOAuthenticationError,
            SSOConfigError,
            SSOError,
        )

        assert issubclass(SSOConfigError, SSOError)
        assert issubclass(SSOAuthenticationError, SSOError)

    def test_sso_user_info_dataclass(self):
        """SSOUserInfo should store user data from IdP."""
        from django_matt.auth.sso.providers.base import SSOUserInfo

        info = SSOUserInfo(
            idp_user_id="idp-123",
            email="user@corp.com",
            email_verified=True,
            first_name="Jane",
            last_name="Doe",
            groups=["engineering", "devops"],
            roles=["developer"],
        )
        assert info.idp_user_id == "idp-123"
        assert info.email == "user@corp.com"
        assert "engineering" in info.groups
        assert "developer" in info.roles


class TestSSOProviderBase:
    """Test SSO base provider functionality."""

    def test_attribute_mapping(self):
        """Should map IdP attributes to SSOUserInfo."""
        from django_matt.auth.sso.config import SSOConfig
        from django_matt.auth.sso.providers.base import SSOProvider

        # Create a pre-built config to avoid from_settings() bug
        sso_config = SSOConfig()

        # Create a mock connection
        mock_connection = MagicMock()
        mock_connection.is_active = True
        mock_connection.attribute_mapping = {}
        mock_connection.organization_id = "org-1"
        mock_connection.provider_type = "oidc"

        # Create a concrete subclass for testing
        class TestSSOProvider(SSOProvider):
            provider_type = "test"

            def get_login_url(self, relay_state=None):
                return "https://idp.example.com/login"

            async def process_callback(self, request):
                pass

        # Patch get_sso_config to return our pre-built config
        # (the import happens inside SSOProvider.__init__)
        with patch(
            "django_matt.auth.sso.config.get_sso_config",
            return_value=sso_config,
        ):
            provider = TestSSOProvider(mock_connection)

        raw_attrs = {
            "sub": "user-456",
            "email": "sso@corp.com",
            "email_verified": True,
            "given_name": "SSO",
            "family_name": "User",
            "groups": ["admins"],
        }
        info = provider.map_attributes(raw_attrs)
        assert info.idp_user_id == "user-456"
        assert info.email == "sso@corp.com"
        assert info.email_verified is True
        assert info.first_name == "SSO"
        assert info.last_name == "User"


# =============================================================================
# Passkeys Tests
# =============================================================================


class TestPasskeyConfig:
    """Test Passkey configuration."""

    def test_passkey_config_defaults(self):
        """PasskeyConfig should have sensible defaults."""
        from django_matt.auth.passkeys.config import PasskeyConfig

        config = PasskeyConfig()
        assert config.challenge_timeout == 60000
        assert config.user_verification == "preferred"
        assert config.resident_key == "preferred"
        assert config.attestation == "none"
        assert config.max_credentials_per_user == 10

    def test_passkey_config_validation_empty(self):
        """Validation should fail when required fields are empty."""
        from django_matt.auth.passkeys.config import PasskeyConfig

        config = PasskeyConfig()  # rp_id, rp_name, origin are empty
        errors = config.validate()
        assert len(errors) > 0
        assert any("RP_ID" in e for e in errors)
        assert any("RP_NAME" in e for e in errors)
        assert any("ORIGIN" in e for e in errors)

    def test_passkey_config_validation_valid(self):
        """Validation should pass with required fields set."""
        from django_matt.auth.passkeys.config import PasskeyConfig

        config = PasskeyConfig(
            rp_id="example.com",
            rp_name="Example App",
            origin="https://example.com",
        )
        errors = config.validate()
        assert errors == []

    def test_passkey_config_origin_validation(self):
        """Origin must start with http:// or https://."""
        from django_matt.auth.passkeys.config import PasskeyConfig

        config = PasskeyConfig(
            rp_id="example.com",
            rp_name="Example App",
            origin="ftp://example.com",
        )
        errors = config.validate()
        assert any("ORIGIN" in e for e in errors)


class TestPasskeyErrors:
    """Test passkey error classes."""

    def test_error_hierarchy(self):
        """Error classes should have correct hierarchy."""
        from django_matt.auth.passkeys.webauthn import (
            PasskeyAuthenticationError,
            PasskeyCredentialNotFoundError,
            PasskeyError,
            PasskeyNotInstalledError,
            PasskeyRegistrationError,
        )

        assert issubclass(PasskeyRegistrationError, PasskeyError)
        assert issubclass(PasskeyAuthenticationError, PasskeyError)
        assert issubclass(PasskeyCredentialNotFoundError, PasskeyError)
        assert issubclass(PasskeyNotInstalledError, PasskeyError)

    def test_not_installed_error_message(self):
        """PasskeyNotInstalledError should have helpful message."""
        from django_matt.auth.passkeys.webauthn import PasskeyNotInstalledError

        error = PasskeyNotInstalledError()
        assert "webauthn" in str(error).lower()
        assert "install" in str(error).lower()


class TestPasskeyModel:
    """Test PasskeyCredential model."""

    @pytest.mark.django_db
    def test_passkey_credential_creation(self, user):
        """Should create a passkey credential."""
        from django_matt.auth.passkeys.models import PasskeyCredential

        cred = PasskeyCredential.objects.create(
            user=user,
            credential_id="test-cred-id-base64url",
            public_key="test-public-key-base64",
            sign_count=0,
            device_type="single_device",
            backed_up=False,
            transports=["internal"],
            name="Test MacBook",
        )
        assert cred.pk is not None
        assert cred.user == user
        assert cred.credential_id == "test-cred-id-base64url"
        assert str(cred) == f"{user} - Test MacBook"

    @pytest.mark.django_db
    def test_update_sign_count_valid(self, user):
        """Should update sign count when new count is higher."""
        from django_matt.auth.passkeys.models import PasskeyCredential

        cred = PasskeyCredential.objects.create(
            user=user,
            credential_id="sign-count-test",
            public_key="key",
            sign_count=5,
        )
        assert cred.update_sign_count(6) is True
        cred.refresh_from_db()
        assert cred.sign_count == 6

    @pytest.mark.django_db
    def test_update_sign_count_replay_detection(self, user):
        """Should detect replay when sign count doesn't increase."""
        from django_matt.auth.passkeys.models import PasskeyCredential

        cred = PasskeyCredential.objects.create(
            user=user,
            credential_id="replay-test",
            public_key="key",
            sign_count=10,
        )
        assert cred.update_sign_count(5) is False

    @pytest.mark.django_db
    def test_update_sign_count_zero_to_zero(self, user):
        """Authenticators that don't implement counters (0 -> 0) should pass."""
        from django_matt.auth.passkeys.models import PasskeyCredential

        cred = PasskeyCredential.objects.create(
            user=user,
            credential_id="zero-counter",
            public_key="key",
            sign_count=0,
        )
        assert cred.update_sign_count(0) is True


# =============================================================================
# API Key Tests
# =============================================================================


class TestAPIKeyGeneration:
    """Test API key generation utilities."""

    def test_generate_live_key(self):
        """Should generate key with live prefix."""
        from django_matt.auth.api_keys.utils import generate_api_key

        key = generate_api_key(is_test=False)
        assert key.startswith("sk_live_")
        assert len(key) > 20

    def test_generate_test_key(self):
        """Should generate key with test prefix."""
        from django_matt.auth.api_keys.utils import generate_api_key

        key = generate_api_key(is_test=True)
        assert key.startswith("sk_test_")

    def test_generated_keys_are_unique(self):
        """Two generated keys should never be the same."""
        from django_matt.auth.api_keys.utils import generate_api_key

        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2

    def test_hash_api_key(self):
        """Hash should be deterministic for same key."""
        from django_matt.auth.api_keys.utils import hash_api_key

        key = "sk_live_abc123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_different_keys(self):
        """Different keys should produce different hashes."""
        from django_matt.auth.api_keys.utils import hash_api_key

        assert hash_api_key("key1") != hash_api_key("key2")

    def test_get_key_prefix(self):
        """Should extract the right prefix length."""
        from django_matt.auth.api_keys.utils import get_key_prefix

        key = "sk_live_abcdefghijklmnop"
        prefix = get_key_prefix(key, length=12)
        assert prefix == "sk_live_abcd"
        assert len(prefix) == 12

    def test_mask_api_key(self):
        """Should mask the middle of the key."""
        from django_matt.auth.api_keys.utils import mask_api_key

        key = "sk_live_abcdefghijklmnopqrstuvwxyz"
        masked = mask_api_key(key)
        assert "..." in masked
        assert masked.startswith("sk_live_abcd")
        assert masked.endswith("wxyz")


class TestAPIKeyConfig:
    """Test API key configuration."""

    def test_default_config(self):
        """APIKeyConfig should have sensible defaults."""
        from django_matt.auth.api_keys.utils import APIKeyConfig

        config = APIKeyConfig()
        assert config.prefix_live == "sk_live_"
        assert config.prefix_test == "sk_test_"
        assert config.key_length == 32
        assert config.hash_algorithm == "sha256"
        assert config.header_name == "X-API-Key"
        assert config.track_usage is False
        assert config.rate_limiting is True

    def test_generate_webhook_secret(self):
        """Should generate webhook secrets with proper prefix."""
        from django_matt.auth.api_keys.utils import generate_webhook_secret

        secret = generate_webhook_secret()
        assert secret.startswith("whsec_")
        assert len(secret) > 10


class TestAPIKeyFromRequest:
    """Test extracting API keys from requests."""

    def test_extract_from_custom_header(self, rf):
        """Should extract key from X-API-Key header."""
        from django_matt.auth.api_keys.utils import get_api_key_from_request

        request = rf.get("/", HTTP_X_API_KEY="sk_live_testkey123")
        key = get_api_key_from_request(request)
        assert key == "sk_live_testkey123"

    def test_extract_from_authorization_bearer(self, rf):
        """Should extract key from Authorization: Bearer header."""
        from django_matt.auth.api_keys.utils import get_api_key_from_request

        request = rf.get("/", HTTP_AUTHORIZATION="Bearer sk_live_testkey123")
        key = get_api_key_from_request(request)
        assert key == "sk_live_testkey123"

    def test_extract_from_authorization_apikey(self, rf):
        """Should extract key from Authorization: ApiKey header."""
        from django_matt.auth.api_keys.utils import get_api_key_from_request

        request = rf.get("/", HTTP_AUTHORIZATION="ApiKey sk_live_testkey123")
        key = get_api_key_from_request(request)
        assert key == "sk_live_testkey123"

    def test_no_key_present(self, rf):
        """Should return None when no key is in the request."""
        from django_matt.auth.api_keys.utils import get_api_key_from_request

        request = rf.get("/")
        assert get_api_key_from_request(request) is None


class TestAPIKeyModel:
    """Test APIKey model behavior."""

    @pytest.mark.django_db
    def test_create_api_key(self, user):
        """Should create an API key and return key + raw value."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, raw_key = create_api_key(user, name="Test Key")
        assert api_key.pk is not None
        assert api_key.user == user
        assert api_key.name == "Test Key"
        assert api_key.is_active is True
        assert raw_key.startswith("sk_live_")

    @pytest.mark.django_db
    def test_api_key_scope_check(self, user):
        """Should correctly check scoped permissions."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(user, name="Scoped Key", scopes=["read:users", "write:posts"])
        assert api_key.has_scope("read:users") is True
        assert api_key.has_scope("write:posts") is True
        assert api_key.has_scope("delete:users") is False

    @pytest.mark.django_db
    def test_api_key_wildcard_scope(self, user):
        """Wildcard scope should match everything."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(user, name="Full Access", scopes=["*"])
        assert api_key.has_scope("anything") is True
        assert api_key.has_scope("read:users") is True

    @pytest.mark.django_db
    def test_api_key_partial_wildcard_scope(self, user):
        """Partial wildcard like 'read:*' should match all read scopes."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(user, name="Read All", scopes=["read:*"])
        assert api_key.has_scope("read:users") is True
        assert api_key.has_scope("read:posts") is True
        assert api_key.has_scope("write:posts") is False

    @pytest.mark.django_db
    def test_api_key_no_scopes_means_full_access(self, user):
        """Empty scopes should mean full access."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(user, name="No Scope", scopes=[])
        assert api_key.has_scope("anything") is True

    @pytest.mark.django_db
    def test_api_key_expiration(self, user):
        """Expired key should be marked as expired."""
        from django.utils import timezone

        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(
            user,
            name="Expiring Key",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert api_key.is_expired is True
        assert api_key.is_valid is False

    @pytest.mark.django_db
    def test_api_key_not_expired(self, user):
        """Non-expired key should be valid."""
        from django.utils import timezone

        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(
            user,
            name="Valid Key",
            expires_at=timezone.now() + timedelta(hours=24),
        )
        assert api_key.is_expired is False
        assert api_key.is_valid is True

    @pytest.mark.django_db
    def test_api_key_revoke(self, user):
        """Revoking a key should deactivate it."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(user, name="To Revoke")
        assert api_key.is_active is True
        api_key.revoke()
        api_key.refresh_from_db()
        assert api_key.is_active is False
        assert api_key.is_valid is False

    @pytest.mark.django_db
    def test_api_key_ip_restriction(self, user):
        """Should check allowed IPs."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(
            user,
            name="IP Restricted",
            allowed_ips=["10.0.0.1", "10.0.0.2"],
        )
        assert api_key.is_ip_allowed("10.0.0.1") is True
        assert api_key.is_ip_allowed("192.168.1.1") is False

    @pytest.mark.django_db
    def test_api_key_no_ip_restriction(self, user):
        """Empty allowed_ips should allow all IPs."""
        from django_matt.auth.api_keys.utils import create_api_key

        api_key, _ = create_api_key(user, name="No IP Limit")
        assert api_key.is_ip_allowed("any.ip.here") is True

    @pytest.mark.django_db
    def test_rotate_api_key(self, user):
        """Rotating should revoke old key and create new one."""
        from django_matt.auth.api_keys.utils import create_api_key, rotate_api_key

        old_key, old_raw = create_api_key(user, name="To Rotate", scopes=["read:*"])
        new_key, new_raw = rotate_api_key(old_key)

        old_key.refresh_from_db()
        assert old_key.is_active is False
        assert new_key.is_active is True
        assert new_key.name == "To Rotate"
        assert new_key.scopes == ["read:*"]
        assert new_raw != old_raw

    @pytest.mark.django_db
    def test_get_by_key(self, user):
        """Should find key by raw value."""
        from django_matt.auth.api_keys.models import APIKey
        from django_matt.auth.api_keys.utils import create_api_key

        _, raw_key = create_api_key(user, name="Lookup Test")
        found = APIKey.objects.get_by_key(raw_key)
        assert found is not None
        assert found.name == "Lookup Test"

    @pytest.mark.django_db
    def test_get_by_key_invalid(self, db):
        """Should return None for nonexistent key."""
        from django_matt.auth.api_keys.models import APIKey

        assert APIKey.objects.get_by_key("sk_live_nonexistent") is None


class TestAPIKeyPlanRateLimits:
    """Test API key plan rate limits."""

    def test_plan_rate_limits_defined(self):
        """All plans should have defined rate limits."""
        from django_matt.auth.api_keys.models import PLAN_RATE_LIMITS

        assert "free" in PLAN_RATE_LIMITS
        assert "starter" in PLAN_RATE_LIMITS
        assert "pro" in PLAN_RATE_LIMITS
        assert "enterprise" in PLAN_RATE_LIMITS

    def test_plan_rate_limits_ascending(self):
        """Higher plans should have higher rate limits."""
        from django_matt.auth.api_keys.models import PLAN_RATE_LIMITS

        free = PLAN_RATE_LIMITS["free"]["rate_limit"]
        starter = PLAN_RATE_LIMITS["starter"]["rate_limit"]
        pro = PLAN_RATE_LIMITS["pro"]["rate_limit"]
        enterprise = PLAN_RATE_LIMITS["enterprise"]["rate_limit"]

        assert free < starter < pro < enterprise


# =============================================================================
# Schema Tests
# =============================================================================


class TestAuthSchemas:
    """Test Pydantic auth schemas."""

    def test_login_request_validation(self):
        """LoginRequest should validate and lowercase email."""
        req = LoginRequest(email="USER@Example.COM", password="pass123")
        assert req.email == "user@example.com"

    def test_login_request_invalid_email(self):
        """LoginRequest should reject invalid email."""
        with pytest.raises(ValidationError):
            LoginRequest(email="not-an-email", password="pass123")

    def test_register_request_password_validation(self):
        """RegisterRequest should enforce password rules."""
        # Valid password
        req = RegisterRequest(
            email="user@test.com",
            password="StrongPass1",
            password_confirm="StrongPass1",
        )
        assert req.password == "StrongPass1"

    def test_register_request_weak_password(self):
        """RegisterRequest should reject weak passwords."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@test.com",
                password="weak",
                password_confirm="weak",
            )

    def test_register_request_no_uppercase(self):
        """RegisterRequest should reject passwords without uppercase."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@test.com",
                password="nouppercase1",
                password_confirm="nouppercase1",
            )

    def test_register_request_no_digit(self):
        """RegisterRequest should reject passwords without digits."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@test.com",
                password="NoDigitHere",
                password_confirm="NoDigitHere",
            )

    def test_register_request_password_mismatch(self):
        """RegisterRequest should reject mismatched passwords."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@test.com",
                password="StrongPass1",
                password_confirm="DifferentPass1",
            )

    def test_change_password_request_validation(self):
        """ChangePasswordRequest should validate password match."""
        req = ChangePasswordRequest(
            current_password="old123",
            new_password="NewPass123",
            new_password_confirm="NewPass123",
        )
        assert req.new_password == "NewPass123"

    def test_change_password_mismatch(self):
        """ChangePasswordRequest should reject mismatched passwords."""
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old123",
                new_password="NewPass123",
                new_password_confirm="DifferentPass123",
            )

    def test_token_pair_schema(self):
        """TokenPair should store both tokens."""
        pair = TokenPair(
            access_token="acc-123",
            refresh_token="ref-456",
            token_type="Bearer",
            expires_in=900,
            refresh_expires_in=604800,
        )
        assert pair.access_token == "acc-123"
        assert pair.refresh_token == "ref-456"
        assert pair.token_type == "Bearer"

    def test_token_payload_schema(self):
        """TokenPayload should accept standard JWT claims."""
        payload = TokenPayload(
            sub="user-1",
            exp=datetime.now(UTC),
            iat=datetime.now(UTC),
            type="access",
            jti="unique-id",
            email="user@test.com",
            roles=["admin"],
        )
        assert payload.sub == "user-1"
        assert payload.type == "access"
        assert "admin" in payload.roles

    @pytest.mark.django_db
    def test_user_response_from_user(self, user):
        """UserResponse.from_user should create response from Django user."""
        response = UserResponse.from_user(user)
        assert response.id == user.pk
        assert response.email == user.email
        assert response.username == user.username
        assert response.is_active is True

    def test_message_response(self):
        """MessageResponse should have message and success fields."""
        msg = MessageResponse(message="Done")
        assert msg.message == "Done"
        assert msg.success is True

    def test_error_response(self):
        """ErrorResponse should have detail and code."""
        err = ErrorResponse(detail="Something failed", code="server_error")
        assert err.detail == "Something failed"
        assert err.code == "server_error"


# =============================================================================
# Auth Controller Tests
# =============================================================================


class TestAuthControllerLogin:
    """Test AuthController login endpoint.

    Note: We call unbound class methods (e.g., AuthController.login(controller, request))
    to bypass a closure variable capture bug in Controller._setup_dependencies / _setup_error_handling
    where loop variable 'method' is captured by reference, causing all instance wrappers
    to call the last method iterated.
    """

    @pytest.mark.django_db(transaction=True)
    async def test_login_success(self, rf):
        """Should return tokens for valid credentials."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import AuthController

        User = get_user_model()
        user = await User.objects.acreate_user(
            username="loginuser",
            email="login@example.com",
            password="TestPass123!",
        )

        controller = AuthController()
        body = json.dumps({"email": "login@example.com", "password": "TestPass123!"})
        request = rf.post(
            "/auth/login",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.login(controller, request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    @pytest.mark.django_db(transaction=True)
    async def test_login_wrong_password(self, rf):
        """Should return 401 for wrong password."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import AuthController

        User = get_user_model()
        await User.objects.acreate_user(
            username="wrongpw",
            email="wrongpw@example.com",
            password="TestPass123!",
        )

        controller = AuthController()
        body = json.dumps({"email": "wrongpw@example.com", "password": "WrongPassword1"})
        request = rf.post(
            "/auth/login",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.login(controller, request)
        assert response.status_code == 401

    @pytest.mark.django_db(transaction=True)
    async def test_login_nonexistent_user(self, rf):
        """Should return 401 for nonexistent email."""
        from django_matt.auth.controllers import AuthController

        controller = AuthController()
        body = json.dumps({"email": "nobody@example.com", "password": "Password123"})
        request = rf.post(
            "/auth/login",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.login(controller, request)
        assert response.status_code == 401

    @pytest.mark.django_db(transaction=True)
    async def test_login_inactive_user(self, rf):
        """Should return 401 for inactive user."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import AuthController

        User = get_user_model()
        await User.objects.acreate_user(
            username="inactivelogin",
            email="inactivelogin@example.com",
            password="TestPass123!",
            is_active=False,
        )

        controller = AuthController()
        body = json.dumps({"email": "inactivelogin@example.com", "password": "TestPass123!"})
        request = rf.post(
            "/auth/login",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.login(controller, request)
        assert response.status_code == 401

    @pytest.mark.django_db(transaction=True)
    async def test_login_invalid_json(self, rf):
        """Should return 400 for invalid JSON."""
        from django_matt.auth.controllers import AuthController

        controller = AuthController()
        request = rf.post(
            "/auth/login",
            data="not json",
            content_type="application/json",
        )
        response = await AuthController.login(controller, request)
        assert response.status_code == 400


class TestAuthControllerRegister:
    """Test AuthController register endpoint."""

    @pytest.mark.django_db(transaction=True)
    async def test_register_success(self, rf):
        """Should create user and return tokens."""
        from django_matt.auth.controllers import AuthController

        controller = AuthController()
        body = json.dumps(
            {
                "email": "newuser@example.com",
                "password": "StrongPass1",
                "password_confirm": "StrongPass1",
                "username": "newuser",
                "first_name": "New",
                "last_name": "User",
            }
        )
        request = rf.post(
            "/auth/register",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.register(controller, request)
        assert response.status_code == 201
        data = json.loads(response.content)
        assert "user" in data
        assert "tokens" in data
        assert data["user"]["email"] == "newuser@example.com"

    @pytest.mark.django_db(transaction=True)
    async def test_register_duplicate_email(self, rf):
        """Should return 400 for duplicate email."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import AuthController

        User = get_user_model()
        await User.objects.acreate_user(
            username="existing",
            email="existing@example.com",
            password="TestPass123!",
        )

        controller = AuthController()
        body = json.dumps(
            {
                "email": "existing@example.com",
                "password": "StrongPass1",
                "password_confirm": "StrongPass1",
            }
        )
        request = rf.post(
            "/auth/register",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.register(controller, request)
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["code"] == "email_exists"


class TestAuthControllerRefresh:
    """Test AuthController refresh endpoint."""

    @pytest.mark.django_db(transaction=True)
    async def test_refresh_success(self, rf):
        """Should return new tokens for valid refresh token."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import AuthController

        User = get_user_model()
        user = await User.objects.acreate_user(
            username="refreshuser",
            email="refresh@example.com",
            password="TestPass123!",
        )

        controller = AuthController()
        pair = await acreate_token_pair(user)
        body = json.dumps({"refresh_token": pair.refresh_token})
        request = rf.post(
            "/auth/refresh",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.refresh(controller, request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.django_db(transaction=True)
    async def test_refresh_invalid_token(self, rf):
        """Should return 401 for invalid refresh token."""
        from django_matt.auth.controllers import AuthController

        controller = AuthController()
        body = json.dumps({"refresh_token": "invalid-token"})
        request = rf.post(
            "/auth/refresh",
            data=body,
            content_type="application/json",
        )
        response = await AuthController.refresh(controller, request)
        assert response.status_code == 401


class TestAuthControllerLogout:
    """Test AuthController logout endpoint."""

    @pytest.mark.django_db(transaction=True)
    async def test_logout_returns_success(self, rf):
        """Logout should always return success (stateless JWT)."""
        from django_matt.auth.controllers import AuthController

        controller = AuthController()
        request = rf.post("/auth/logout")
        response = await AuthController.logout(controller, request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "message" in data


class TestAuthControllerMe:
    """Test AuthController me endpoint."""

    @pytest.mark.django_db(transaction=True)
    async def test_me_with_authenticated_user(self, rf):
        """Should return user data when authenticated."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import AuthController

        User = get_user_model()
        user = await User.objects.acreate_user(
            username="meuser",
            email="meuser@example.com",
            password="TestPass123!",
        )

        controller = AuthController()
        token = await acreate_access_token(user)
        request = rf.get("/auth/me", HTTP_AUTHORIZATION=f"Bearer {token}")
        # Simulate jwt_required setting request.user
        request.user = user
        request.token_payload = verify_access_token(token)
        # Call the unwrapped me method (jwt_required wraps it, so use __wrapped__)
        response = await AuthController.me.__wrapped__(controller, request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["email"] == "meuser@example.com"


class TestMinimalAuthController:
    """Test MinimalAuthController."""

    @pytest.mark.django_db(transaction=True)
    async def test_minimal_login(self, rf):
        """MinimalAuthController login should work."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import MinimalAuthController

        User = get_user_model()
        user = await User.objects.acreate_user(
            username="minimallogin",
            email="minimal@example.com",
            password="TestPass123!",
        )

        controller = MinimalAuthController()
        body = json.dumps({"email": "minimal@example.com", "password": "TestPass123!"})
        request = rf.post(
            "/auth/login",
            data=body,
            content_type="application/json",
        )
        response = await MinimalAuthController.login(controller, request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "access_token" in data

    @pytest.mark.django_db(transaction=True)
    async def test_minimal_refresh(self, rf):
        """MinimalAuthController refresh should work."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.controllers import MinimalAuthController

        User = get_user_model()
        user = await User.objects.acreate_user(
            username="minimalrefresh",
            email="minimalrefresh@example.com",
            password="TestPass123!",
        )

        controller = MinimalAuthController()
        pair = await acreate_token_pair(user)
        body = json.dumps({"refresh_token": pair.refresh_token})
        request = rf.post(
            "/auth/refresh",
            data=body,
            content_type="application/json",
        )
        response = await MinimalAuthController.refresh(controller, request)
        assert response.status_code == 200


# =============================================================================
# Org-Aware Permission Classes Tests
# =============================================================================


@pytest.mark.django_db
class TestOrgPermissionClasses:
    """Tests for IsOrgMember, IsOrgAdmin, IsOrgOwner permission classes."""

    @pytest.fixture
    def rf(self):
        return RequestFactory()

    @pytest.fixture
    def org(self):
        from django_matt.multitenancy.models import Organization

        return Organization.objects.create(
            name="Test Org",
            slug="test-org",
        )

    @pytest.fixture
    def member_user(self):
        return User.objects.create_user(
            username="member_user",
            email="member@example.com",
            password="pass123",
        )

    @pytest.fixture
    def admin_user(self):
        return User.objects.create_user(
            username="admin_user",
            email="admin@example.com",
            password="pass123",
        )

    @pytest.fixture
    def owner_user(self):
        return User.objects.create_user(
            username="owner_user",
            email="owner@example.com",
            password="pass123",
        )

    @pytest.fixture
    def superuser(self):
        return User.objects.create_superuser(
            username="super_user",
            email="super@example.com",
            password="pass123",
        )

    @pytest.fixture
    def member_membership(self, org, member_user):
        from django_matt.multitenancy.models import Membership

        return Membership.objects.create(
            organization=org,
            user=member_user,
            role="member",
        )

    @pytest.fixture
    def admin_membership(self, org, admin_user):
        from django_matt.multitenancy.models import Membership

        return Membership.objects.create(
            organization=org,
            user=admin_user,
            role="admin",
        )

    @pytest.fixture
    def owner_membership(self, org, owner_user):
        from django_matt.multitenancy.models import Membership

        return Membership.objects.create(
            organization=org,
            user=owner_user,
            role="owner",
        )

    def _make_request(self, rf, user=None, organization=None):
        """Create a mock request with user and organization attributes."""
        request = rf.get("/")
        if user is not None:
            request.user = user
        if organization is not None:
            request.organization = organization
        return request

    # ------------------------------------------------------------------
    # IsOrgMember
    # ------------------------------------------------------------------

    def test_is_org_member_true_for_member(self, rf, org, member_user, member_membership):
        """IsOrgMember returns True for a user with any membership in request.organization."""
        from django_matt.permissions.common import IsOrgMember

        request = self._make_request(rf, user=member_user, organization=org)
        assert IsOrgMember().has_permission(request) is True

    def test_is_org_member_false_when_no_membership(self, rf, org, member_user):
        """IsOrgMember returns False when user has no membership in request.organization."""
        from django_matt.permissions.common import IsOrgMember

        request = self._make_request(rf, user=member_user, organization=org)
        assert IsOrgMember().has_permission(request) is False

    def test_is_org_member_false_when_no_organization(self, rf, member_user):
        """IsOrgMember returns False when request has no organization attribute."""
        from django_matt.permissions.common import IsOrgMember

        request = self._make_request(rf, user=member_user)
        # No organization set on request
        assert IsOrgMember().has_permission(request) is False

    def test_is_org_member_false_for_unauthenticated(self, rf, org):
        """IsOrgMember returns False for unauthenticated user."""
        from django_matt.permissions.common import IsOrgMember

        request = self._make_request(rf, user=AnonymousUser(), organization=org)
        assert IsOrgMember().has_permission(request) is False

    def test_is_org_member_superuser_bypass_true(self, rf, org, superuser):
        """Superuser passes IsOrgMember even without membership when TENANT_SUPERUSER_BYPASS=True."""
        from django_matt.permissions.common import IsOrgMember

        request = self._make_request(rf, user=superuser, organization=org)
        with patch("django.conf.settings.TENANT_SUPERUSER_BYPASS", True, create=True):
            # No membership created for superuser, should still pass
            assert IsOrgMember().has_permission(request) is True

    def test_is_org_member_superuser_bypass_false(self, rf, org, superuser):
        """Superuser FAILS IsOrgMember when TENANT_SUPERUSER_BYPASS=False and no membership."""
        from django_matt.permissions.common import IsOrgMember

        request = self._make_request(rf, user=superuser, organization=org)
        with patch("django.conf.settings.TENANT_SUPERUSER_BYPASS", False, create=True):
            # No membership, bypass disabled — should fail
            assert IsOrgMember().has_permission(request) is False

    # ------------------------------------------------------------------
    # IsOrgAdmin
    # ------------------------------------------------------------------

    def test_is_org_admin_false_for_member_role(self, rf, org, member_user, member_membership):
        """IsOrgAdmin returns False for member role."""
        from django_matt.permissions.common import IsOrgAdmin

        request = self._make_request(rf, user=member_user, organization=org)
        assert IsOrgAdmin().has_permission(request) is False

    def test_is_org_admin_true_for_admin_role(self, rf, org, admin_user, admin_membership):
        """IsOrgAdmin returns True for admin role."""
        from django_matt.permissions.common import IsOrgAdmin

        request = self._make_request(rf, user=admin_user, organization=org)
        assert IsOrgAdmin().has_permission(request) is True

    def test_is_org_admin_true_for_owner_role(self, rf, org, owner_user, owner_membership):
        """IsOrgAdmin returns True for owner role (owners are also admins)."""
        from django_matt.permissions.common import IsOrgAdmin

        request = self._make_request(rf, user=owner_user, organization=org)
        assert IsOrgAdmin().has_permission(request) is True

    def test_is_org_admin_false_for_unauthenticated(self, rf, org):
        """IsOrgAdmin returns False for unauthenticated user."""
        from django_matt.permissions.common import IsOrgAdmin

        request = self._make_request(rf, user=AnonymousUser(), organization=org)
        assert IsOrgAdmin().has_permission(request) is False

    # ------------------------------------------------------------------
    # IsOrgOwner
    # ------------------------------------------------------------------

    def test_is_org_owner_true_for_owner_role(self, rf, org, owner_user, owner_membership):
        """IsOrgOwner returns True only for owner role."""
        from django_matt.permissions.common import IsOrgOwner

        request = self._make_request(rf, user=owner_user, organization=org)
        assert IsOrgOwner().has_permission(request) is True

    def test_is_org_owner_false_for_admin_role(self, rf, org, admin_user, admin_membership):
        """IsOrgOwner returns False for admin role."""
        from django_matt.permissions.common import IsOrgOwner

        request = self._make_request(rf, user=admin_user, organization=org)
        assert IsOrgOwner().has_permission(request) is False

    def test_is_org_owner_false_for_member_role(self, rf, org, member_user, member_membership):
        """IsOrgOwner returns False for member role."""
        from django_matt.permissions.common import IsOrgOwner

        request = self._make_request(rf, user=member_user, organization=org)
        assert IsOrgOwner().has_permission(request) is False

    def test_is_org_owner_false_for_unauthenticated(self, rf, org):
        """IsOrgOwner returns False for unauthenticated user."""
        from django_matt.permissions.common import IsOrgOwner

        request = self._make_request(rf, user=AnonymousUser(), organization=org)
        assert IsOrgOwner().has_permission(request) is False


# =============================================================================
# JWT blacklist integration tests: logout and change_password
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestLogoutBlacklistsToken:
    """Test that logout blacklists the access token JTI."""

    @pytest.mark.asyncio
    async def test_logout_blacklists_jti(self, rf, settings):
        """After logout, the access token JTI should be blacklisted."""
        import json

        from asgiref.sync import sync_to_async

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        from django_matt.auth.blacklist.core import reset_backend

        reset_backend()

        # Create user in async context to avoid SQLite locking
        test_user = await sync_to_async(User.objects.create_user)(
            username="logout_test_user",
            email="logout_test@example.com",
            password="TestPass123!",
        )

        from django_matt.auth.controllers import AuthController
        from django_matt.auth.jwt import acreate_access_token, decode_token

        # Use async token creation to avoid sync ORM in async context
        token = await acreate_access_token(test_user)
        payload = decode_token(token, verify_type="access")

        controller = AuthController()
        request = rf.post(
            "/auth/logout",
            data=json.dumps({}),
            content_type="application/json",
        )
        # Attach auth info to request as the jwt_required decorator would
        request.user = test_user
        request.token_payload = payload

        # Call the raw logout method (logout has no @jwt_required, so use unbound method)
        response = await AuthController.logout(controller, request)
        assert response.status_code == 200

        # Now the JTI should be blacklisted
        from django_matt.auth.blacklist.core import is_token_blacklisted

        assert is_token_blacklisted(payload.jti) is True

        reset_backend()


@pytest.mark.django_db
class TestChangePasswordRevokesOldTokens:
    """Test that change_password bulk-revokes user tokens."""

    @pytest.mark.asyncio
    async def test_change_password_calls_bulk_revoke(self, settings):
        """change_password calls abulk_revoke_tokens_for_user before issuing new tokens."""
        import json

        from asgiref.sync import sync_to_async

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        from django_matt.auth.blacklist.core import reset_backend

        reset_backend()

        user = await sync_to_async(User.objects.create_user)(
            username="pwchange",
            email="pwchange@test.com",
            password="OldPass123!",
        )

        from django.test import RequestFactory

        from django_matt.auth.controllers import AuthController

        factory = RequestFactory()
        request = factory.post(
            "/auth/change-password",
            data=json.dumps(
                {
                    "current_password": "OldPass123!",
                    "new_password": "NewPass456!",
                    "new_password_confirm": "NewPass456!",
                }
            ),
            content_type="application/json",
        )
        request.user = user

        revoke_called_with = []

        async def mock_bulk_revoke(user_id):
            revoke_called_with.append(user_id)

        from unittest.mock import patch

        with patch(
            "django_matt.auth.controllers.abulk_revoke_tokens_for_user",
            side_effect=mock_bulk_revoke,
        ):
            controller = AuthController()
            # Use __wrapped__ to bypass jwt_required decorator (we set request.user manually)
            response = await AuthController.change_password.__wrapped__(controller, request)

        assert response.status_code == 200
        assert len(revoke_called_with) == 1
        assert str(revoke_called_with[0]) == str(user.pk)

        reset_backend()


# =============================================================================
# CSRF exemption tests
# =============================================================================


class TestCSRFExemption:
    """Test that DjangoMattAPI sets _csrf_exempt on registered view functions."""

    def test_csrf_false_sets_exempt_on_view_funcs(self):
        """DjangoMattAPI(csrf=False) marks all view functions as _csrf_exempt."""
        from django_matt import DjangoMattAPI

        api = DjangoMattAPI(csrf=False)

        @api.get("/test-endpoint")
        def my_view(request):
            return {"ok": True}

        url_patterns = api.get_urls()
        # Find the view for our endpoint
        view_func = None
        for pattern in url_patterns:
            if hasattr(pattern, "pattern") and "test-endpoint" in str(pattern.pattern):
                view_func = pattern.callback
                break

        assert view_func is not None
        assert getattr(view_func, "_csrf_exempt", False) is True

    def test_csrf_true_does_not_set_exempt(self):
        """DjangoMattAPI(csrf=True) does NOT set _csrf_exempt on view functions."""
        from django_matt import DjangoMattAPI

        api = DjangoMattAPI(csrf=True)

        @api.get("/test-csrf-endpoint")
        def my_view(request):
            return {"ok": True}

        url_patterns = api.get_urls()
        view_func = None
        for pattern in url_patterns:
            if hasattr(pattern, "pattern") and "test-csrf-endpoint" in str(pattern.pattern):
                view_func = pattern.callback
                break

        assert view_func is not None
        assert getattr(view_func, "_csrf_exempt", False) is False

    def test_csrf_exempt_on_controller_view_funcs(self):
        """DjangoMattAPI(csrf=False) marks controller-registered views as _csrf_exempt."""
        from django_matt import DjangoMattAPI
        from django_matt.core.controller import APIController
        from django_matt.core.router import post

        api = DjangoMattAPI(csrf=False)

        class MyController(APIController):
            prefix = "myctrl"

            @post("action")
            async def action(self, request):
                return {"done": True}

        api.register_controller(MyController)
        url_patterns = api.get_urls()

        exempt_count = 0
        for pattern in url_patterns:
            cb = getattr(pattern, "callback", None)
            if cb and getattr(cb, "_csrf_exempt", False):
                exempt_count += 1

        assert exempt_count > 0, "Expected at least one view function to have _csrf_exempt=True"
