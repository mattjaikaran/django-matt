"""
Comprehensive tests for the django_matt API Keys module.

Covers:
- Key generation (format, prefix, uniqueness, hashing)
- Key validation/verification (manager methods, valid/invalid/expired)
- Authentication middleware (header extraction, IP restrictions, usage tracking)
- Decorators (api_key_required, api_key_optional, requires_scope, requires_live_key, requires_plan)
- Key scoping and permissions (exact match, wildcard, partial wildcard)
- Key expiration
- Key revocation
- Rate limiting middleware
- Usage tracking middleware and model
- Live vs test keys
- Async variants (acreate_api_key, arotate_api_key, arecord_usage, arevoke)
- Schemas (create, update, response serialization)
- Edge cases (empty keys, malformed keys, concurrent usage)
"""

from __future__ import annotations

import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest
from pydantic import ValidationError

from django_matt.auth.api_keys.decorators import (
    api_key_optional,
    api_key_required,
    requires_live_key,
    requires_plan,
    requires_scope,
)
from django_matt.auth.api_keys.middleware import (
    APIKeyAuthenticationMiddleware,
    APIKeyRateLimitMiddleware,
    APIKeyUsageTrackingMiddleware,
)
from django_matt.auth.api_keys.models import (
    PLAN_RATE_LIMITS,
    APIKey,
    APIKeyUsage,
)
from django_matt.auth.api_keys.schemas import (
    APIKeyCreatedResponse,
    APIKeyCreateRequest,
    APIKeyListResponse,
    APIKeyResponse,
    APIKeyUpdateRequest,
    ExportRequest,
    ExportResponse,
    UsageRecord,
    UsageResponse,
    UsageSummary,
)
from django_matt.auth.api_keys.utils import (
    APIKeyConfig,
    acreate_api_key,
    api_key_config,
    arotate_api_key,
    create_api_key,
    generate_api_key,
    generate_webhook_secret,
    get_api_key_from_request,
    get_client_ip,
    get_key_prefix,
    hash_api_key,
    mask_api_key,
    rotate_api_key,
)

User = get_user_model()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
@pytest.mark.django_db
def user(db):
    return User.objects.create_user(
        username="apikey_user",
        email="apikey@example.com",
        password="TestPass123!",
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def user2(db):
    return User.objects.create_user(
        username="apikey_user2",
        email="apikey2@example.com",
        password="TestPass123!",
        is_active=True,
    )


@pytest.fixture
@pytest.mark.django_db
def live_key(user):
    """Create a live API key and return (APIKey, raw_key)."""
    return create_api_key(user, name="Live Key", is_test=False)


@pytest.fixture
@pytest.mark.django_db
def test_key(user):
    """Create a test API key and return (APIKey, raw_key)."""
    return create_api_key(user, name="Test Key", is_test=True)


@pytest.fixture
@pytest.mark.django_db
def scoped_key(user):
    """Create a scoped API key and return (APIKey, raw_key)."""
    return create_api_key(
        user,
        name="Scoped Key",
        scopes=["read:users", "write:posts", "read:*"],
    )


@pytest.fixture
@pytest.mark.django_db
def expired_key(user):
    """Create an expired API key and return (APIKey, raw_key)."""
    return create_api_key(
        user,
        name="Expired Key",
        expires_at=timezone.now() - timedelta(hours=1),
    )


@pytest.fixture
@pytest.mark.django_db
def ip_restricted_key(user):
    """Create an IP-restricted API key and return (APIKey, raw_key)."""
    return create_api_key(
        user,
        name="IP Restricted Key",
        allowed_ips=["10.0.0.1", "192.168.1.0"],
    )


@pytest.fixture
@pytest.mark.django_db
def pro_key(user):
    """Create a pro-plan API key and return (APIKey, raw_key)."""
    return create_api_key(user, name="Pro Key", plan="pro")


@pytest.fixture
@pytest.mark.django_db
def enterprise_key(user):
    """Create an enterprise-plan API key and return (APIKey, raw_key)."""
    return create_api_key(user, name="Enterprise Key", plan="enterprise")


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before each test."""
    cache.clear()
    yield
    cache.clear()


# =============================================================================
# Key Generation Tests
# =============================================================================


class TestKeyGeneration:
    """Test API key generation utilities."""

    def test_generate_live_key_prefix(self):
        """Live key should start with sk_live_ prefix."""
        key = generate_api_key(is_test=False)
        assert key.startswith("sk_live_")

    def test_generate_test_key_prefix(self):
        """Test key should start with sk_test_ prefix."""
        key = generate_api_key(is_test=True)
        assert key.startswith("sk_test_")

    def test_generate_key_length(self):
        """Generated key should have prefix + 43 chars (32 bytes base64)."""
        key = generate_api_key(is_test=False)
        random_part = key[len("sk_live_") :]
        # secrets.token_urlsafe(32) produces a 43-char string
        assert len(random_part) == 43

    def test_generate_keys_unique(self):
        """Each generated key should be unique."""
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_generate_key_default_is_live(self):
        """Default generation should produce a live key."""
        key = generate_api_key()
        assert key.startswith("sk_live_")

    def test_hash_api_key_deterministic(self):
        """Hashing the same key should produce the same hash."""
        key = "sk_live_testkey123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2

    def test_hash_api_key_different_keys(self):
        """Different keys should produce different hashes."""
        h1 = hash_api_key("sk_live_key1")
        h2 = hash_api_key("sk_live_key2")
        assert h1 != h2

    def test_hash_api_key_sha256_length(self):
        """SHA-256 hex digest should be 64 characters."""
        h = hash_api_key("sk_live_somekey")
        assert len(h) == 64

    def test_get_key_prefix_default(self):
        """Default prefix should be first 12 characters."""
        key = "sk_live_abcdefghijklmnop"
        prefix = get_key_prefix(key)
        assert prefix == "sk_live_abcd"
        assert len(prefix) == 12

    def test_get_key_prefix_custom_length(self):
        """Custom length prefix extraction."""
        key = "sk_live_abcdefghijklmnop"
        prefix = get_key_prefix(key, length=8)
        assert prefix == "sk_live_"

    def test_get_key_prefix_short_key(self):
        """Short key should return the full key."""
        key = "short"
        prefix = get_key_prefix(key, length=12)
        assert prefix == "short"

    def test_mask_api_key_long(self):
        """Long key should show first 12 and last 4 chars."""
        key = "sk_live_abcdefghijklmnopqrstuvwxyz"
        masked = mask_api_key(key)
        assert masked.startswith("sk_live_abcd")
        assert masked.endswith("wxyz")
        assert "..." in masked

    def test_mask_api_key_short(self):
        """Short key (<= 16 chars) should show first 4 and last 4."""
        key = "1234567890123456"
        masked = mask_api_key(key)
        assert masked == "1234...3456"

    def test_generate_webhook_secret(self):
        """Webhook secrets should start with whsec_ prefix."""
        secret = generate_webhook_secret()
        assert secret.startswith("whsec_")

    def test_generate_webhook_secret_unique(self):
        """Each webhook secret should be unique."""
        secrets = {generate_webhook_secret() for _ in range(50)}
        assert len(secrets) == 50


# =============================================================================
# APIKeyConfig Tests
# =============================================================================


class TestAPIKeyConfig:
    """Test APIKeyConfig defaults and customization."""

    def test_default_config(self):
        config = APIKeyConfig()
        assert config.prefix_live == "sk_live_"
        assert config.prefix_test == "sk_test_"
        assert config.key_length == 32
        assert config.hash_algorithm == "sha256"
        assert config.header_name == "X-API-Key"
        assert config.query_param == "api_key"
        assert config.track_usage is False
        assert config.rate_limiting is True
        assert config.allow_query_param is False

    @patch("django_matt.auth.api_keys.utils.settings")
    def test_custom_config(self, mock_settings):
        """Custom settings should override defaults."""
        mock_settings.DJANGO_MATT_API_KEYS = {
            "PREFIX_LIVE": "pk_live_",
            "PREFIX_TEST": "pk_test_",
            "KEY_LENGTH": 64,
            "HEADER_NAME": "Authorization-Key",
            "TRACK_USAGE": True,
            "RATE_LIMITING": False,
            "ALLOW_QUERY_PARAM": True,
        }
        config = APIKeyConfig()
        assert config.prefix_live == "pk_live_"
        assert config.prefix_test == "pk_test_"
        assert config.key_length == 64
        assert config.header_name == "Authorization-Key"
        assert config.track_usage is True
        assert config.rate_limiting is False
        assert config.allow_query_param is True


# =============================================================================
# Request Key Extraction Tests
# =============================================================================


class TestGetAPIKeyFromRequest:
    """Test extracting API keys from HTTP requests."""

    def test_extract_from_x_api_key_header(self, rf):
        """Should extract key from X-API-Key header."""
        request = rf.get("/", HTTP_X_API_KEY="sk_live_test123")
        key = get_api_key_from_request(request)
        assert key == "sk_live_test123"

    def test_extract_from_bearer_auth(self, rf):
        """Should extract key from Authorization: Bearer header."""
        request = rf.get("/", HTTP_AUTHORIZATION="Bearer sk_live_test123")
        key = get_api_key_from_request(request)
        assert key == "sk_live_test123"

    def test_extract_from_apikey_auth(self, rf):
        """Should extract key from Authorization: ApiKey header."""
        request = rf.get("/", HTTP_AUTHORIZATION="ApiKey sk_live_test123")
        key = get_api_key_from_request(request)
        assert key == "sk_live_test123"

    def test_no_key_present(self, rf):
        """Should return None when no key is present."""
        request = rf.get("/")
        key = get_api_key_from_request(request)
        assert key is None

    def test_bearer_strips_whitespace(self, rf):
        """Bearer token extraction should strip whitespace."""
        request = rf.get("/", HTTP_AUTHORIZATION="Bearer   sk_live_test123  ")
        key = get_api_key_from_request(request)
        assert key == "sk_live_test123"

    def test_x_api_key_priority_over_auth(self, rf):
        """X-API-Key header should take priority over Authorization."""
        request = rf.get(
            "/",
            HTTP_X_API_KEY="sk_live_primary",
            HTTP_AUTHORIZATION="Bearer sk_live_secondary",
        )
        key = get_api_key_from_request(request)
        assert key == "sk_live_primary"

    def test_unsupported_auth_scheme(self, rf):
        """Unsupported auth scheme should return None."""
        request = rf.get("/", HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz")
        key = get_api_key_from_request(request)
        assert key is None

    def test_empty_authorization_header(self, rf):
        """Empty Authorization header should return None."""
        request = rf.get("/", HTTP_AUTHORIZATION="")
        key = get_api_key_from_request(request)
        assert key is None


# =============================================================================
# Client IP Extraction Tests
# =============================================================================


class TestGetClientIP:
    """Test client IP extraction from requests."""

    def test_direct_ip(self, rf):
        """Should get IP from REMOTE_ADDR."""
        request = rf.get("/")
        request.META["REMOTE_ADDR"] = "1.2.3.4"
        ip = get_client_ip(request)
        assert ip == "1.2.3.4"

    def test_x_forwarded_for_single(self, rf):
        """Should get first IP from X-Forwarded-For."""
        request = rf.get("/", HTTP_X_FORWARDED_FOR="10.0.0.1")
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_x_forwarded_for_chain(self, rf):
        """Should get first IP from X-Forwarded-For chain."""
        request = rf.get("/", HTTP_X_FORWARDED_FOR="10.0.0.1, 10.0.0.2, 10.0.0.3")
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_x_real_ip(self, rf):
        """Should get IP from X-Real-IP if no X-Forwarded-For."""
        request = rf.get("/", HTTP_X_REAL_IP="10.0.0.5")
        ip = get_client_ip(request)
        assert ip == "10.0.0.5"

    def test_x_forwarded_for_priority(self, rf):
        """X-Forwarded-For should take priority over X-Real-IP."""
        request = rf.get(
            "/",
            HTTP_X_FORWARDED_FOR="10.0.0.1",
            HTTP_X_REAL_IP="10.0.0.5",
        )
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"


# =============================================================================
# APIKey Model Tests (sync)
# =============================================================================


class TestAPIKeyModel:
    """Test APIKey model creation, properties, and methods."""

    @pytest.mark.django_db
    def test_create_api_key_basic(self, user):
        """Should create a key with correct defaults."""
        api_key, raw_key = create_api_key(user, name="Basic Key")
        assert api_key.pk is not None
        assert api_key.user == user
        assert api_key.name == "Basic Key"
        assert api_key.is_active is True
        assert api_key.is_test is False
        assert api_key.plan == "free"
        assert api_key.scopes == []
        assert api_key.allowed_ips == []
        assert api_key.expires_at is None
        assert api_key.total_requests == 0
        assert raw_key.startswith("sk_live_")

    @pytest.mark.django_db
    def test_create_test_key(self, user):
        """Test key should have test prefix and is_test=True."""
        api_key, raw_key = create_api_key(user, name="Test Key", is_test=True)
        assert api_key.is_test is True
        assert raw_key.startswith("sk_test_")

    @pytest.mark.django_db
    def test_create_key_with_scopes(self, user):
        """Key should store scopes correctly."""
        scopes = ["read:users", "write:posts", "admin:*"]
        api_key, _ = create_api_key(user, name="Scoped", scopes=scopes)
        assert api_key.scopes == scopes

    @pytest.mark.django_db
    def test_create_key_with_expiration(self, user):
        """Key should store expiration correctly."""
        expires = timezone.now() + timedelta(days=30)
        api_key, _ = create_api_key(user, name="Expiring", expires_at=expires)
        assert api_key.expires_at is not None
        assert abs((api_key.expires_at - expires).total_seconds()) < 1

    @pytest.mark.django_db
    def test_create_key_with_plan(self, user):
        """Key should get rate limits from plan."""
        api_key, _ = create_api_key(user, name="Pro Plan", plan="pro")
        assert api_key.plan == "pro"
        assert api_key.rate_limit == PLAN_RATE_LIMITS["pro"]["rate_limit"]
        assert api_key.rate_limit_period == PLAN_RATE_LIMITS["pro"]["rate_limit_period"]

    @pytest.mark.django_db
    def test_create_key_with_allowed_ips(self, user):
        """Key should store allowed IPs correctly."""
        ips = ["10.0.0.1", "192.168.1.0"]
        api_key, _ = create_api_key(user, name="IP Key", allowed_ips=ips)
        assert api_key.allowed_ips == ips

    @pytest.mark.django_db
    def test_key_str_representation(self, live_key):
        """String representation should include name, prefix, and mode."""
        api_key, _ = live_key
        s = str(api_key)
        assert "Live Key" in s
        assert "[live]" in s
        assert api_key.prefix in s

    @pytest.mark.django_db
    def test_test_key_str_representation(self, test_key):
        """Test key string representation should show [test] mode."""
        api_key, _ = test_key
        s = str(api_key)
        assert "[test]" in s

    @pytest.mark.django_db
    def test_key_hash_stored(self, user):
        """Created key should have a stored hash."""
        api_key, raw_key = create_api_key(user, name="Hash Check")
        expected_hash = hash_api_key(raw_key)
        assert api_key.key_hash == expected_hash

    @pytest.mark.django_db
    def test_key_prefix_stored(self, user):
        """Created key should store the prefix."""
        api_key, raw_key = create_api_key(user, name="Prefix Check")
        expected_prefix = get_key_prefix(raw_key)
        assert api_key.prefix == expected_prefix


# =============================================================================
# Expiration Tests
# =============================================================================


class TestKeyExpiration:
    """Test API key expiration logic."""

    @pytest.mark.django_db
    def test_no_expiration_is_valid(self, user):
        """Key with no expiration should never be expired."""
        api_key, _ = create_api_key(user, name="No Expiry")
        assert api_key.is_expired is False
        assert api_key.is_valid is True

    @pytest.mark.django_db
    def test_future_expiration_is_valid(self, user):
        """Key with future expiration should be valid."""
        api_key, _ = create_api_key(
            user,
            name="Future Expiry",
            expires_at=timezone.now() + timedelta(days=30),
        )
        assert api_key.is_expired is False
        assert api_key.is_valid is True

    @pytest.mark.django_db
    def test_past_expiration_is_expired(self, expired_key):
        """Key with past expiration should be expired."""
        api_key, _ = expired_key
        assert api_key.is_expired is True
        assert api_key.is_valid is False

    @pytest.mark.django_db
    def test_just_expired_key(self, user):
        """Key that just expired should report expired."""
        api_key, _ = create_api_key(
            user,
            name="Just Expired",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        assert api_key.is_expired is True

    @pytest.mark.django_db
    def test_expired_key_not_returned_by_get_valid(self, user):
        """Manager.get_valid should return None for expired keys."""
        _, raw_key = create_api_key(
            user,
            name="Expired Lookup",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        found = APIKey.objects.get_valid(raw_key)
        assert found is None


# =============================================================================
# Revocation Tests
# =============================================================================


class TestKeyRevocation:
    """Test API key revocation."""

    @pytest.mark.django_db
    def test_revoke_key(self, live_key):
        """Revoking a key should set is_active=False."""
        api_key, _ = live_key
        assert api_key.is_active is True
        api_key.revoke()
        api_key.refresh_from_db()
        assert api_key.is_active is False
        assert api_key.is_valid is False

    @pytest.mark.django_db
    def test_revoked_key_not_returned_by_get_by_key(self, live_key):
        """Revoked key should not be returned by get_by_key."""
        api_key, raw_key = live_key
        api_key.revoke()
        found = APIKey.objects.get_by_key(raw_key)
        assert found is None

    @pytest.mark.django_db
    def test_revoked_key_not_returned_by_get_valid(self, live_key):
        """Revoked key should not be returned by get_valid."""
        api_key, raw_key = live_key
        api_key.revoke()
        found = APIKey.objects.get_valid(raw_key)
        assert found is None

    @pytest.mark.django_db(transaction=True)
    async def test_async_revoke(self):
        """Async revoke should deactivate the key."""
        user = await User.objects.acreate_user(
            username="async_revoke_user",
            email="async_revoke@example.com",
            password="TestPass123!",
        )
        api_key, raw_key = await acreate_api_key(user, name="Async Revoke")
        assert api_key.is_active is True
        await api_key.arevoke()
        await api_key.arefresh_from_db()
        assert api_key.is_active is False

    @pytest.mark.django_db
    def test_revoke_already_revoked(self, live_key):
        """Revoking an already revoked key should not raise."""
        api_key, _ = live_key
        api_key.revoke()
        api_key.revoke()  # Should not raise
        api_key.refresh_from_db()
        assert api_key.is_active is False


# =============================================================================
# Scope Tests
# =============================================================================


class TestKeyScopes:
    """Test API key scope checking."""

    @pytest.mark.django_db
    def test_exact_scope_match(self, user):
        """Exact scope should match."""
        api_key, _ = create_api_key(user, name="Exact Scope", scopes=["read:users", "write:posts"])
        assert api_key.has_scope("read:users") is True
        assert api_key.has_scope("write:posts") is True
        assert api_key.has_scope("delete:users") is False

    @pytest.mark.django_db
    def test_wildcard_all_scope(self, user):
        """Wildcard * should match everything."""
        api_key, _ = create_api_key(user, name="All Scopes", scopes=["*"])
        assert api_key.has_scope("read:users") is True
        assert api_key.has_scope("write:anything") is True
        assert api_key.has_scope("admin:delete") is True

    @pytest.mark.django_db
    def test_partial_wildcard_scope(self, user):
        """Partial wildcard (e.g., read:*) should match that action."""
        api_key, _ = create_api_key(user, name="Read All", scopes=["read:*"])
        assert api_key.has_scope("read:users") is True
        assert api_key.has_scope("read:posts") is True
        assert api_key.has_scope("read:anything") is True
        assert api_key.has_scope("write:posts") is False
        assert api_key.has_scope("delete:users") is False

    @pytest.mark.django_db
    def test_no_scopes_means_full_access(self, user):
        """Key with empty scopes should have full access."""
        api_key, _ = create_api_key(user, name="No Scopes", scopes=[])
        assert api_key.has_scope("anything") is True
        assert api_key.has_scope("read:users") is True

    @pytest.mark.django_db
    def test_multiple_partial_wildcards(self, user):
        """Multiple partial wildcards should each match their action."""
        api_key, _ = create_api_key(user, name="Multi Wildcard", scopes=["read:*", "write:*"])
        assert api_key.has_scope("read:users") is True
        assert api_key.has_scope("write:posts") is True
        assert api_key.has_scope("delete:users") is False

    @pytest.mark.django_db
    def test_scope_single_segment(self, user):
        """Single-segment scope should match exactly."""
        api_key, _ = create_api_key(user, name="Simple Scope", scopes=["admin"])
        assert api_key.has_scope("admin") is True
        assert api_key.has_scope("admin:dashboard") is False


# =============================================================================
# IP Restriction Tests
# =============================================================================


class TestIPRestrictions:
    """Test API key IP address restrictions."""

    @pytest.mark.django_db
    def test_allowed_ip(self, ip_restricted_key):
        """Allowed IP should pass."""
        api_key, _ = ip_restricted_key
        assert api_key.is_ip_allowed("10.0.0.1") is True
        assert api_key.is_ip_allowed("192.168.1.0") is True

    @pytest.mark.django_db
    def test_disallowed_ip(self, ip_restricted_key):
        """Disallowed IP should fail."""
        api_key, _ = ip_restricted_key
        assert api_key.is_ip_allowed("192.168.1.1") is False
        assert api_key.is_ip_allowed("0.0.0.0") is False

    @pytest.mark.django_db
    def test_no_ip_restriction(self, live_key):
        """Key with no IP restrictions should allow all IPs."""
        api_key, _ = live_key
        assert api_key.is_ip_allowed("10.0.0.1") is True
        assert api_key.is_ip_allowed("anything") is True


# =============================================================================
# Manager Methods Tests
# =============================================================================


class TestAPIKeyManager:
    """Test APIKeyManager query methods."""

    @pytest.mark.django_db
    def test_get_by_key_valid(self, live_key):
        """Should find active key by raw value."""
        api_key, raw_key = live_key
        found = APIKey.objects.get_by_key(raw_key)
        assert found is not None
        assert found.pk == api_key.pk

    @pytest.mark.django_db
    def test_get_by_key_nonexistent(self, db):
        """Should return None for nonexistent key."""
        found = APIKey.objects.get_by_key("sk_live_doesnotexist")
        assert found is None

    @pytest.mark.django_db
    def test_get_by_key_inactive(self, live_key):
        """Should return None for inactive key."""
        api_key, raw_key = live_key
        api_key.revoke()
        found = APIKey.objects.get_by_key(raw_key)
        assert found is None

    @pytest.mark.django_db
    def test_get_valid_active_non_expired(self, live_key):
        """Should return active, non-expired key."""
        api_key, raw_key = live_key
        found = APIKey.objects.get_valid(raw_key)
        assert found is not None
        assert found.pk == api_key.pk

    @pytest.mark.django_db
    def test_get_valid_expired(self, expired_key):
        """Should return None for expired key."""
        _, raw_key = expired_key
        found = APIKey.objects.get_valid(raw_key)
        assert found is None

    @pytest.mark.django_db
    def test_get_valid_revoked(self, live_key):
        """Should return None for revoked key."""
        api_key, raw_key = live_key
        api_key.revoke()
        found = APIKey.objects.get_valid(raw_key)
        assert found is None

    @pytest.mark.django_db
    def test_active_queryset(self, user):
        """active() should only return active keys."""
        k1, _ = create_api_key(user, name="Active1")
        k2, _ = create_api_key(user, name="Active2")
        k3, _ = create_api_key(user, name="Revoked")
        k3.revoke()

        active_pks = set(APIKey.objects.active().values_list("pk", flat=True))
        assert k1.pk in active_pks
        assert k2.pk in active_pks
        assert k3.pk not in active_pks

    @pytest.mark.django_db
    def test_live_queryset(self, user):
        """live() should only return active, non-test keys."""
        live, _ = create_api_key(user, name="Live", is_test=False)
        test, _ = create_api_key(user, name="Test", is_test=True)

        live_pks = set(APIKey.objects.live().values_list("pk", flat=True))
        assert live.pk in live_pks
        assert test.pk not in live_pks

    @pytest.mark.django_db
    def test_test_queryset(self, user):
        """test() should only return active test keys."""
        live, _ = create_api_key(user, name="Live", is_test=False)
        test, _ = create_api_key(user, name="Test", is_test=True)

        test_pks = set(APIKey.objects.test().values_list("pk", flat=True))
        assert test.pk in test_pks
        assert live.pk not in test_pks


# =============================================================================
# Usage Recording Tests
# =============================================================================


class TestUsageRecording:
    """Test APIKey usage recording."""

    @pytest.mark.django_db
    def test_record_usage(self, live_key):
        """record_usage should increment total_requests and update last_used_at."""
        api_key, _ = live_key
        assert api_key.total_requests == 0
        assert api_key.last_used_at is None

        api_key.record_usage()
        api_key.refresh_from_db()

        assert api_key.total_requests == 1
        assert api_key.last_used_at is not None

    @pytest.mark.django_db
    def test_record_usage_multiple(self, live_key):
        """Multiple usages should increment counter."""
        api_key, _ = live_key
        for _ in range(5):
            api_key.record_usage()
        api_key.refresh_from_db()
        assert api_key.total_requests == 5

    @pytest.mark.django_db(transaction=True)
    async def test_async_record_usage(self):
        """Async record_usage should work correctly."""
        user = await User.objects.acreate_user(
            username="async_usage_user",
            email="async_usage@example.com",
            password="TestPass123!",
        )
        api_key, _ = await acreate_api_key(user, name="Async Usage")
        await api_key.arecord_usage()
        await api_key.arefresh_from_db()
        assert api_key.total_requests == 1
        assert api_key.last_used_at is not None

    @pytest.mark.django_db
    def test_rate_limit_key(self, live_key):
        """Rate limit cache key should include PK."""
        api_key, _ = live_key
        cache_key = api_key.get_rate_limit_key()
        assert str(api_key.pk) in cache_key
        assert cache_key == f"api_key_rate_limit:{api_key.pk}"


# =============================================================================
# APIKeyUsage Model Tests
# =============================================================================


class TestAPIKeyUsageModel:
    """Test the APIKeyUsage tracking model."""

    @pytest.mark.django_db
    def test_record_creates_usage(self, live_key):
        """Recording should create a new usage record."""
        api_key, _ = live_key
        usage = APIKeyUsage.record(
            api_key=api_key,
            endpoint="/api/test",
            response_time_ms=50.0,
        )
        assert usage.request_count == 1
        assert usage.error_count == 0
        assert usage.endpoint_counts == {"/api/test": 1}
        assert usage.avg_response_time_ms == 50.0

    @pytest.mark.django_db
    def test_record_increments_existing(self, live_key):
        """Multiple records in same hour should increment existing."""
        api_key, _ = live_key
        APIKeyUsage.record(api_key=api_key, endpoint="/api/a", response_time_ms=10.0)
        usage = APIKeyUsage.record(api_key=api_key, endpoint="/api/b", response_time_ms=30.0)
        assert usage.request_count == 2
        assert "/api/a" in usage.endpoint_counts
        assert "/api/b" in usage.endpoint_counts

    @pytest.mark.django_db
    def test_record_error_count(self, live_key):
        """Errors should increment error_count."""
        api_key, _ = live_key
        usage = APIKeyUsage.record(api_key=api_key, endpoint="/api/fail", is_error=True)
        assert usage.error_count == 1

    @pytest.mark.django_db
    def test_record_bytes_tracking(self, live_key):
        """Should track bytes sent and received."""
        api_key, _ = live_key
        usage = APIKeyUsage.record(
            api_key=api_key,
            endpoint="/api/data",
            bytes_sent=1024,
            bytes_received=512,
        )
        assert usage.bytes_sent == 1024
        assert usage.bytes_received == 512

    @pytest.mark.django_db
    def test_record_max_response_time(self, live_key):
        """Should track maximum response time."""
        api_key, _ = live_key
        APIKeyUsage.record(api_key=api_key, endpoint="/api/a", response_time_ms=10.0)
        usage = APIKeyUsage.record(api_key=api_key, endpoint="/api/b", response_time_ms=100.0)
        assert usage.max_response_time_ms == 100.0

    @pytest.mark.django_db
    def test_usage_str_representation(self, live_key):
        """String representation should include key name and hour."""
        api_key, _ = live_key
        usage = APIKeyUsage.record(api_key=api_key, endpoint="/api/test")
        s = str(usage)
        assert api_key.name in s
        assert "requests" in s


# =============================================================================
# Key Rotation Tests
# =============================================================================


class TestKeyRotation:
    """Test API key rotation."""

    @pytest.mark.django_db
    def test_rotate_key(self, live_key):
        """Rotation should revoke old key and create new one with same settings."""
        old_key, old_raw = live_key
        new_key, new_raw = rotate_api_key(old_key)

        old_key.refresh_from_db()
        assert old_key.is_active is False
        assert new_key.is_active is True
        assert new_key.name == old_key.name
        assert new_raw != old_raw

    @pytest.mark.django_db
    def test_rotate_preserves_settings(self, user):
        """Rotation should preserve scopes, plan, IP restrictions."""
        old_key, _ = create_api_key(
            user,
            name="Rotate Me",
            is_test=True,
            scopes=["read:*", "write:posts"],
            plan="pro",
            allowed_ips=["10.0.0.1"],
        )
        new_key, _ = rotate_api_key(old_key)

        assert new_key.name == "Rotate Me"
        assert new_key.is_test is True
        assert new_key.scopes == ["read:*", "write:posts"]
        assert new_key.plan == "pro"
        assert new_key.allowed_ips == ["10.0.0.1"]

    @pytest.mark.django_db
    def test_old_key_invalid_after_rotation(self, live_key):
        """Old raw key should no longer validate after rotation."""
        _, old_raw = live_key
        rotate_api_key(live_key[0])
        found = APIKey.objects.get_valid(old_raw)
        assert found is None

    @pytest.mark.django_db
    def test_new_key_valid_after_rotation(self, live_key):
        """New raw key should validate after rotation."""
        _, new_raw = rotate_api_key(live_key[0])
        found = APIKey.objects.get_valid(new_raw)
        assert found is not None

    @pytest.mark.django_db(transaction=True)
    async def test_async_rotate_key(self):
        """Async rotation should work correctly."""
        user = await User.objects.acreate_user(
            username="async_rotate_user",
            email="async_rotate@example.com",
            password="TestPass123!",
        )
        old_key, old_raw = await acreate_api_key(user, name="Async Rotate")
        new_key, new_raw = await arotate_api_key(old_key)

        await old_key.arefresh_from_db()
        assert old_key.is_active is False
        assert new_key.is_active is True
        assert new_raw != old_raw


# =============================================================================
# Async Creation Tests
# =============================================================================


class TestAsyncCreation:
    """Test async API key creation."""

    @pytest.mark.django_db(transaction=True)
    async def test_acreate_api_key(self):
        """Async creation should produce a valid key."""
        user = await User.objects.acreate_user(
            username="acreate_user1",
            email="acreate1@example.com",
            password="TestPass123!",
        )
        api_key, raw_key = await acreate_api_key(user, name="Async Key")
        assert api_key.pk is not None
        assert api_key.name == "Async Key"
        assert raw_key.startswith("sk_live_")

    @pytest.mark.django_db(transaction=True)
    async def test_acreate_test_key(self):
        """Async creation of test key should work."""
        user = await User.objects.acreate_user(
            username="acreate_user2",
            email="acreate2@example.com",
            password="TestPass123!",
        )
        api_key, raw_key = await acreate_api_key(user, name="Async Test Key", is_test=True)
        assert api_key.is_test is True
        assert raw_key.startswith("sk_test_")

    @pytest.mark.django_db(transaction=True)
    async def test_acreate_with_all_options(self):
        """Async creation with all options should store correctly."""
        user = await User.objects.acreate_user(
            username="acreate_user3",
            email="acreate3@example.com",
            password="TestPass123!",
        )
        expires = timezone.now() + timedelta(days=90)
        api_key, _ = await acreate_api_key(
            user,
            name="Full Options",
            is_test=False,
            scopes=["read:*", "write:posts"],
            expires_at=expires,
            plan="enterprise",
            allowed_ips=["10.0.0.1"],
        )
        assert api_key.scopes == ["read:*", "write:posts"]
        assert api_key.plan == "enterprise"
        assert api_key.allowed_ips == ["10.0.0.1"]
        assert api_key.rate_limit == PLAN_RATE_LIMITS["enterprise"]["rate_limit"]


# =============================================================================
# Live vs Test Key Tests
# =============================================================================


class TestLiveVsTestKeys:
    """Test live and test key distinctions."""

    @pytest.mark.django_db
    def test_live_key_properties(self, live_key):
        """Live key should have correct properties."""
        api_key, raw_key = live_key
        assert api_key.is_test is False
        assert raw_key.startswith("sk_live_")

    @pytest.mark.django_db
    def test_test_key_properties(self, test_key):
        """Test key should have correct properties."""
        api_key, raw_key = test_key
        assert api_key.is_test is True
        assert raw_key.startswith("sk_test_")

    @pytest.mark.django_db
    def test_live_manager_excludes_test(self, user):
        """live() queryset should exclude test keys."""
        live, _ = create_api_key(user, name="Live", is_test=False)
        test, _ = create_api_key(user, name="Test", is_test=True)
        live_keys = list(APIKey.objects.live())
        live_pks = [k.pk for k in live_keys]
        assert live.pk in live_pks
        assert test.pk not in live_pks

    @pytest.mark.django_db
    def test_test_manager_excludes_live(self, user):
        """test() queryset should exclude live keys."""
        live, _ = create_api_key(user, name="Live", is_test=False)
        test, _ = create_api_key(user, name="Test", is_test=True)
        test_keys = list(APIKey.objects.test())
        test_pks = [k.pk for k in test_keys]
        assert test.pk in test_pks
        assert live.pk not in test_pks


# =============================================================================
# Authentication Middleware Tests
# =============================================================================


class TestAPIKeyAuthenticationMiddleware:
    """Test the APIKeyAuthenticationMiddleware."""

    def _make_middleware(self):
        """Create middleware with a simple pass-through response."""

        def get_response(request):
            return HttpResponse("OK")

        return APIKeyAuthenticationMiddleware(get_response)

    @pytest.mark.django_db
    def test_valid_key_authenticates(self, user, rf):
        """Valid key should set request.user and request.api_key."""
        _, raw_key = create_api_key(user, name="Middleware Test")
        middleware = self._make_middleware()
        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        middleware(request)
        assert request.user == user
        assert hasattr(request, "api_key")
        assert request.api_key.name == "Middleware Test"

    @pytest.mark.django_db
    def test_no_key_passes_through(self, rf):
        """Request without key should pass through without authentication."""
        middleware = self._make_middleware()
        request = rf.get("/")
        response = middleware(request)
        assert response.status_code == 200
        assert not hasattr(request, "api_key")

    @pytest.mark.django_db
    def test_invalid_key_passes_through(self, rf, db):
        """Invalid key should pass through without authentication."""
        middleware = self._make_middleware()
        request = rf.get("/", HTTP_X_API_KEY="sk_live_invalid_key_here")
        response = middleware(request)
        assert response.status_code == 200
        assert not hasattr(request, "api_key")

    @pytest.mark.django_db
    def test_expired_key_passes_through(self, expired_key, rf):
        """Expired key should pass through without authentication."""
        _, raw_key = expired_key
        middleware = self._make_middleware()
        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        middleware(request)
        assert not hasattr(request, "api_key")

    @pytest.mark.django_db
    def test_revoked_key_passes_through(self, live_key, rf):
        """Revoked key should pass through without authentication."""
        api_key, raw_key = live_key
        api_key.revoke()
        middleware = self._make_middleware()
        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        middleware(request)
        assert not hasattr(request, "api_key")

    @pytest.mark.django_db
    def test_ip_restricted_key_wrong_ip(self, ip_restricted_key, rf):
        """Key with IP restrictions should reject wrong IP."""
        _, raw_key = ip_restricted_key
        middleware = self._make_middleware()
        # Use a disallowed IP
        request = rf.get("/", HTTP_X_API_KEY=raw_key, REMOTE_ADDR="99.99.99.99")
        middleware(request)
        assert not hasattr(request, "api_key")

    @pytest.mark.django_db
    def test_ip_restricted_key_allowed_ip(self, ip_restricted_key, rf):
        """Key with IP restrictions should accept allowed IP."""
        _, raw_key = ip_restricted_key
        middleware = self._make_middleware()
        request = rf.get(
            "/",
            HTTP_X_API_KEY=raw_key,
            HTTP_X_FORWARDED_FOR="10.0.0.1",
        )
        middleware(request)
        assert hasattr(request, "api_key")


# =============================================================================
# Rate Limit Middleware Tests
# =============================================================================


class TestAPIKeyRateLimitMiddleware:
    """Test the APIKeyRateLimitMiddleware."""

    def _make_middleware(self):
        """Create rate limit middleware."""

        def get_response(request):
            return HttpResponse("OK")

        return APIKeyRateLimitMiddleware(get_response)

    @pytest.mark.django_db
    def test_no_api_key_passes_through(self, rf):
        """Request without api_key should pass through."""
        middleware = self._make_middleware()
        request = rf.get("/")
        response = middleware(request)
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response

    @pytest.mark.django_db
    def test_rate_limit_headers_present(self, live_key, rf):
        """Response should include rate limit headers."""
        api_key, _ = live_key
        middleware = self._make_middleware()
        request = rf.get("/")
        request.api_key = api_key
        response = middleware(request)
        assert "X-RateLimit-Limit" in response
        assert "X-RateLimit-Remaining" in response
        assert "X-RateLimit-Reset" in response

    @pytest.mark.django_db
    def test_rate_limit_decrement(self, live_key, rf):
        """Each request should decrement remaining count."""
        api_key, _ = live_key
        middleware = self._make_middleware()

        request1 = rf.get("/")
        request1.api_key = api_key
        response1 = middleware(request1)
        remaining1 = int(response1["X-RateLimit-Remaining"])

        request2 = rf.get("/")
        request2.api_key = api_key
        response2 = middleware(request2)
        remaining2 = int(response2["X-RateLimit-Remaining"])

        assert remaining2 < remaining1

    @pytest.mark.django_db
    def test_rate_limit_exceeded(self, user, rf):
        """Exceeding rate limit should return 429."""
        # Create a key with very low rate limit
        api_key, _ = create_api_key(user, name="Low Limit")
        api_key.rate_limit = 2
        api_key.rate_limit_period = 3600
        api_key.save()

        middleware = self._make_middleware()

        # Make requests up to the limit
        for _ in range(2):
            request = rf.get("/")
            request.api_key = api_key
            middleware(request)

        # This one should be rate limited
        request = rf.get("/")
        request.api_key = api_key
        response = middleware(request)
        assert response.status_code == 429
        assert "Retry-After" in response

    @pytest.mark.django_db
    def test_rate_limit_429_response_body(self, user, rf):
        """429 response should include rate limit details."""
        api_key, _ = create_api_key(user, name="Low Limit")
        api_key.rate_limit = 1
        api_key.rate_limit_period = 3600
        api_key.save()

        middleware = self._make_middleware()

        # Use the one allowed request
        request = rf.get("/")
        request.api_key = api_key
        middleware(request)

        # This should be rate limited
        request = rf.get("/")
        request.api_key = api_key
        response = middleware(request)

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "rate_limit_exceeded"
        assert body["limit"] == 1
        assert "retry_after" in body

    @pytest.mark.django_db
    @patch("django_matt.auth.api_keys.middleware.api_key_config")
    def test_rate_limiting_disabled(self, mock_config, live_key, rf):
        """When rate limiting is disabled, should pass through."""
        mock_config.rate_limiting = False
        api_key, _ = live_key
        middleware = self._make_middleware()
        request = rf.get("/")
        request.api_key = api_key
        response = middleware(request)
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response


# =============================================================================
# Usage Tracking Middleware Tests
# =============================================================================


class TestAPIKeyUsageTrackingMiddleware:
    """Test the APIKeyUsageTrackingMiddleware."""

    def _make_middleware(self):
        """Create usage tracking middleware."""

        def get_response(request):
            return HttpResponse("OK")

        return APIKeyUsageTrackingMiddleware(get_response)

    @pytest.mark.django_db
    def test_no_api_key_passes_through(self, rf):
        """Request without api_key should pass through without tracking."""
        middleware = self._make_middleware()
        request = rf.get("/api/test")
        response = middleware(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_tracks_usage(self, live_key, rf):
        """Should create usage record for API key requests."""
        api_key, _ = live_key
        middleware = self._make_middleware()
        request = rf.get("/api/tracked")
        request.api_key = api_key
        middleware(request)

        count = APIKeyUsage.objects.filter(api_key=api_key).count()
        assert count == 1

    @pytest.mark.django_db
    def test_tracks_endpoint(self, live_key, rf):
        """Should track the request endpoint path."""
        api_key, _ = live_key
        middleware = self._make_middleware()
        request = rf.get("/api/specific-endpoint")
        request.api_key = api_key
        middleware(request)

        usage = APIKeyUsage.objects.get(api_key=api_key)
        assert "/api/specific-endpoint" in usage.endpoint_counts

    @pytest.mark.django_db
    def test_tracks_error_response(self, live_key, rf):
        """Should track error responses."""
        api_key, _ = live_key

        def get_response(request):
            return HttpResponse("Error", status=500)

        middleware = APIKeyUsageTrackingMiddleware(get_response)
        request = rf.get("/api/fail")
        request.api_key = api_key
        middleware(request)

        usage = APIKeyUsage.objects.get(api_key=api_key)
        assert usage.error_count == 1

    @pytest.mark.django_db
    def test_tracking_failure_doesnt_break_request(self, live_key, rf):
        """If tracking fails, the request should still succeed."""
        api_key, _ = live_key
        middleware = self._make_middleware()
        request = rf.get("/api/test")
        request.api_key = api_key

        with patch.object(APIKeyUsage, "record", side_effect=Exception("DB error")):
            response = middleware(request)
        assert response.status_code == 200


# =============================================================================
# Decorator Tests — api_key_required (sync)
# =============================================================================


class TestAPIKeyRequiredDecoratorSync:
    """Test the @api_key_required decorator with sync views."""

    @pytest.mark.django_db
    def test_valid_key_authenticates(self, user, rf):
        """Valid key should authenticate and call the view."""
        _, raw_key = create_api_key(user, name="Decorator Test")

        @api_key_required
        def my_view(request):
            return JsonResponse({"user": request.user.pk})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_missing_key_returns_401(self, rf, db):
        """Missing key should return 401."""

        @api_key_required
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        response = my_view(request)
        assert response.status_code == 401

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "api_key_required"

    @pytest.mark.django_db
    def test_invalid_key_returns_401(self, rf, db):
        """Invalid key should return 401."""

        @api_key_required
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY="sk_live_totally_invalid")
        response = my_view(request)
        assert response.status_code == 401

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "invalid_api_key"

    @pytest.mark.django_db
    def test_expired_key_returns_401(self, expired_key, rf):
        """Expired key should return 401."""
        _, raw_key = expired_key

        @api_key_required
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_revoked_key_returns_401(self, live_key, rf):
        """Revoked key should return 401."""
        api_key, raw_key = live_key
        api_key.revoke()

        @api_key_required
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_ip_restriction_allowed(self, ip_restricted_key, rf):
        """Allowed IP should pass IP restriction check."""
        _, raw_key = ip_restricted_key

        @api_key_required
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key, HTTP_X_FORWARDED_FOR="10.0.0.1")
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_ip_restriction_denied(self, ip_restricted_key, rf):
        """Disallowed IP should return 403."""
        _, raw_key = ip_restricted_key

        @api_key_required
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key, REMOTE_ADDR="99.99.99.99")
        response = my_view(request)
        assert response.status_code == 403

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "ip_not_allowed"

    @pytest.mark.django_db
    def test_sets_request_api_key(self, user, rf):
        """Decorator should set request.api_key."""
        api_key, raw_key = create_api_key(user, name="Check Api Key Attr")

        @api_key_required
        def my_view(request):
            return JsonResponse({"key_name": request.api_key.name})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["key_name"] == "Check Api Key Attr"

    @pytest.mark.django_db
    def test_sets_request_user(self, user, rf):
        """Decorator should set request.user to key owner."""
        _, raw_key = create_api_key(user, name="User Check")

        @api_key_required
        def my_view(request):
            return JsonResponse({"user_pk": request.user.pk})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["user_pk"] == user.pk


# =============================================================================
# Decorator Tests — api_key_required (async)
# =============================================================================


class TestAPIKeyRequiredDecoratorAsync:
    """Test the @api_key_required decorator with async views."""

    @pytest.mark.django_db(transaction=True)
    async def test_valid_key_authenticates_async(self):
        """Valid key should authenticate async view."""
        rf = RequestFactory()
        user = await User.objects.acreate_user(
            username="async_req_user1",
            email="async_req1@example.com",
            password="TestPass123!",
        )
        api_key, raw_key = await acreate_api_key(user, name="Async Decorator")

        @api_key_required
        async def my_view(request):
            return JsonResponse({"user": request.user.pk})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = await my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db(transaction=True)
    async def test_missing_key_returns_401_async(self):
        """Missing key should return 401 in async view."""
        rf = RequestFactory()

        @api_key_required
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        response = await my_view(request)
        assert response.status_code == 401

    @pytest.mark.django_db(transaction=True)
    async def test_invalid_key_returns_401_async(self):
        """Invalid key should return 401 in async view."""
        rf = RequestFactory()

        @api_key_required
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY="sk_live_nonexistent")
        response = await my_view(request)
        assert response.status_code == 401


# =============================================================================
# Decorator Tests — api_key_optional
# =============================================================================


class TestAPIKeyOptionalDecorator:
    """Test the @api_key_optional decorator."""

    @pytest.mark.django_db
    def test_valid_key_attaches(self, user, rf):
        """Valid key should attach user and api_key."""
        _, raw_key = create_api_key(user, name="Optional Test")

        @api_key_optional
        def my_view(request):
            has_key = hasattr(request, "api_key")
            return JsonResponse({"has_key": has_key})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["has_key"] is True

    @pytest.mark.django_db
    def test_no_key_still_works(self, rf, db):
        """No key should still allow the view to run."""

        @api_key_optional
        def my_view(request):
            has_key = hasattr(request, "api_key")
            return JsonResponse({"has_key": has_key})

        request = rf.get("/")
        response = my_view(request)
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["has_key"] is False

    @pytest.mark.django_db
    def test_invalid_key_still_works(self, rf, db):
        """Invalid key should not block the view."""

        @api_key_optional
        def my_view(request):
            has_key = hasattr(request, "api_key")
            return JsonResponse({"has_key": has_key})

        request = rf.get("/", HTTP_X_API_KEY="sk_live_invalid")
        response = my_view(request)
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["has_key"] is False

    @pytest.mark.django_db
    def test_expired_key_not_attached(self, expired_key, rf):
        """Expired key should not be attached."""
        _, raw_key = expired_key

        @api_key_optional
        def my_view(request):
            has_key = hasattr(request, "api_key")
            return JsonResponse({"has_key": has_key})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["has_key"] is False

    @pytest.mark.django_db(transaction=True)
    async def test_async_optional_with_key(self):
        """Async view with valid key should work."""
        rf = RequestFactory()
        user = await User.objects.acreate_user(
            username="async_opt_user1",
            email="async_opt1@example.com",
            password="TestPass123!",
        )
        _, raw_key = await acreate_api_key(user, name="Async Optional")

        @api_key_optional
        async def my_view(request):
            has_key = hasattr(request, "api_key")
            return JsonResponse({"has_key": has_key})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = await my_view(request)
        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["has_key"] is True

    @pytest.mark.django_db(transaction=True)
    async def test_async_optional_without_key(self):
        """Async view without key should still work."""
        rf = RequestFactory()

        @api_key_optional
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        response = await my_view(request)
        assert response.status_code == 200


# =============================================================================
# Decorator Tests — requires_scope
# =============================================================================


class TestRequiresScopeDecorator:
    """Test the @requires_scope decorator."""

    @pytest.mark.django_db
    def test_has_required_scope(self, user, rf):
        """View should proceed if key has required scope."""
        _, raw_key = create_api_key(user, name="Scoped View", scopes=["read:users", "write:posts"])

        @api_key_required
        @requires_scope("read:users")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_missing_required_scope(self, user, rf):
        """View should return 403 if key lacks required scope."""
        _, raw_key = create_api_key(user, name="Limited", scopes=["read:users"])

        @api_key_required
        @requires_scope("write:posts")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 403

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "insufficient_scope"

    @pytest.mark.django_db
    def test_any_of_multiple_scopes(self, user, rf):
        """Should succeed if key has any of the required scopes."""
        _, raw_key = create_api_key(user, name="Multi Scope", scopes=["delete:posts"])

        @api_key_required
        @requires_scope("write:posts", "delete:posts")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_wildcard_scope_passes(self, user, rf):
        """Key with * scope should pass any scope check."""
        _, raw_key = create_api_key(user, name="Wildcard", scopes=["*"])

        @api_key_required
        @requires_scope("admin:nuke")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_no_api_key_returns_401(self, rf, db):
        """requires_scope without api_key should return 401."""

        @requires_scope("read:users")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        response = my_view(request)
        assert response.status_code == 401


# =============================================================================
# Decorator Tests — requires_live_key
# =============================================================================


class TestRequiresLiveKeyDecorator:
    """Test the @requires_live_key decorator."""

    @pytest.mark.django_db
    def test_live_key_passes(self, user, rf):
        """Live key should pass."""
        _, raw_key = create_api_key(user, name="Live Only", is_test=False)

        @api_key_required
        @requires_live_key
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_test_key_rejected(self, user, rf):
        """Test key should return 403."""
        _, raw_key = create_api_key(user, name="Test Only", is_test=True)

        @api_key_required
        @requires_live_key
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 403

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "live_key_required"

    @pytest.mark.django_db
    def test_no_api_key_returns_401(self, rf, db):
        """No api_key should return 401."""

        @requires_live_key
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        response = my_view(request)
        assert response.status_code == 401

    @pytest.mark.django_db(transaction=True)
    async def test_async_live_key_passes(self):
        """Async view with live key should pass."""
        rf = RequestFactory()
        user = await User.objects.acreate_user(
            username="async_live_user1",
            email="async_live1@example.com",
            password="TestPass123!",
        )
        _, raw_key = await acreate_api_key(user, name="Async Live", is_test=False)

        @api_key_required
        @requires_live_key
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = await my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db(transaction=True)
    async def test_async_test_key_rejected(self):
        """Async view with test key should return 403."""
        rf = RequestFactory()
        user = await User.objects.acreate_user(
            username="async_live_user2",
            email="async_live2@example.com",
            password="TestPass123!",
        )
        _, raw_key = await acreate_api_key(user, name="Async Test", is_test=True)

        @api_key_required
        @requires_live_key
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = await my_view(request)
        assert response.status_code == 403


# =============================================================================
# Decorator Tests — requires_plan
# =============================================================================


class TestRequiresPlanDecorator:
    """Test the @requires_plan decorator."""

    @pytest.mark.django_db
    def test_matching_plan_passes(self, pro_key, rf):
        """Key with matching plan should pass."""
        _, raw_key = pro_key

        @api_key_required
        @requires_plan("pro", "enterprise")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_wrong_plan_rejected(self, user, rf):
        """Key with wrong plan should return 403."""
        _, raw_key = create_api_key(user, name="Free Plan", plan="free")

        @api_key_required
        @requires_plan("pro", "enterprise")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = my_view(request)
        assert response.status_code == 403

        import json as stdlib_json

        body = stdlib_json.loads(response.content)
        assert body["code"] == "plan_required"
        assert body["current_plan"] == "free"
        assert "pro" in body["required_plans"]

    @pytest.mark.django_db
    def test_no_api_key_returns_401(self, rf, db):
        """No api_key should return 401."""

        @requires_plan("pro")
        def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/")
        response = my_view(request)
        assert response.status_code == 401

    @pytest.mark.django_db(transaction=True)
    async def test_async_matching_plan(self):
        """Async view with matching plan should pass."""
        rf = RequestFactory()
        user = await User.objects.acreate_user(
            username="async_plan_user1",
            email="async_plan1@example.com",
            password="TestPass123!",
        )
        _, raw_key = await acreate_api_key(user, name="Enterprise", plan="enterprise")

        @api_key_required
        @requires_plan("enterprise")
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = await my_view(request)
        assert response.status_code == 200

    @pytest.mark.django_db(transaction=True)
    async def test_async_wrong_plan(self):
        """Async view with wrong plan should return 403."""
        rf = RequestFactory()
        user = await User.objects.acreate_user(
            username="async_plan_user2",
            email="async_plan2@example.com",
            password="TestPass123!",
        )
        _, raw_key = await acreate_api_key(user, name="Starter", plan="starter")

        @api_key_required
        @requires_plan("enterprise")
        async def my_view(request):
            return JsonResponse({"ok": True})

        request = rf.get("/", HTTP_X_API_KEY=raw_key)
        response = await my_view(request)
        assert response.status_code == 403


# =============================================================================
# Plan Rate Limits Tests
# =============================================================================


class TestPlanRateLimits:
    """Test plan-based rate limits."""

    def test_all_plans_defined(self):
        """All plan tiers should have defined rate limits."""
        assert "free" in PLAN_RATE_LIMITS
        assert "starter" in PLAN_RATE_LIMITS
        assert "pro" in PLAN_RATE_LIMITS
        assert "enterprise" in PLAN_RATE_LIMITS

    def test_plan_limits_ascending(self):
        """Higher plans should have higher limits."""
        free = PLAN_RATE_LIMITS["free"]["rate_limit"]
        starter = PLAN_RATE_LIMITS["starter"]["rate_limit"]
        pro = PLAN_RATE_LIMITS["pro"]["rate_limit"]
        enterprise = PLAN_RATE_LIMITS["enterprise"]["rate_limit"]
        assert free < starter < pro < enterprise

    def test_plan_periods_set(self):
        """All plans should have rate_limit_period."""
        for plan_data in PLAN_RATE_LIMITS.values():
            assert "rate_limit" in plan_data
            assert "rate_limit_period" in plan_data
            assert plan_data["rate_limit_period"] > 0

    @pytest.mark.django_db
    def test_plan_sets_correct_limits(self, user):
        """Creating key with plan should set correct rate limits."""
        for plan_name, limits in PLAN_RATE_LIMITS.items():
            api_key, _ = create_api_key(user, name=f"{plan_name} Key", plan=plan_name)
            assert api_key.rate_limit == limits["rate_limit"]
            assert api_key.rate_limit_period == limits["rate_limit_period"]

    @pytest.mark.django_db
    def test_unknown_plan_uses_free_defaults(self, user):
        """Unknown plan should fall back to free tier limits."""
        api_key, _ = create_api_key(user, name="Unknown Plan", plan="nonexistent")
        free_limits = PLAN_RATE_LIMITS["free"]
        assert api_key.rate_limit == free_limits["rate_limit"]
        assert api_key.rate_limit_period == free_limits["rate_limit_period"]


# =============================================================================
# Schema Tests
# =============================================================================


class TestAPIKeySchemas:
    """Test Pydantic schemas for API key endpoints."""

    def test_create_request_validation(self):
        """APIKeyCreateRequest should validate correctly."""
        req = APIKeyCreateRequest(name="My Key")
        assert req.name == "My Key"
        assert req.is_test is False
        assert req.scopes == []
        assert req.expires_at is None

    def test_create_request_with_options(self):
        """APIKeyCreateRequest should accept all options."""
        req = APIKeyCreateRequest(
            name="Full Key",
            is_test=True,
            scopes=["read:*"],
            allowed_ips=["10.0.0.1"],
        )
        assert req.is_test is True
        assert req.scopes == ["read:*"]
        assert req.allowed_ips == ["10.0.0.1"]

    def test_create_request_empty_name_rejected(self):
        """Empty name should be rejected."""
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="")

    def test_create_request_long_name_rejected(self):
        """Name longer than 100 chars should be rejected."""
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="x" * 101)

    def test_update_request_all_optional(self):
        """APIKeyUpdateRequest should allow all fields as optional."""
        req = APIKeyUpdateRequest()
        assert req.name is None
        assert req.scopes is None
        assert req.expires_at is None
        assert req.allowed_ips is None
        assert req.is_active is None

    def test_update_request_partial(self):
        """APIKeyUpdateRequest should accept partial updates."""
        req = APIKeyUpdateRequest(name="Updated Name")
        assert req.name == "Updated Name"
        assert req.scopes is None

    def test_api_key_response_serialization(self):
        """APIKeyResponse should serialize correctly."""
        now = timezone.now()
        resp = APIKeyResponse(
            id=1,
            name="Test",
            prefix="sk_live_abcd",
            is_test=False,
            is_active=True,
            plan="free",
            scopes=["read:*"],
            rate_limit=100,
            rate_limit_period=3600,
            expires_at=None,
            created_at=now,
            last_used_at=None,
            total_requests=0,
            allowed_ips=[],
        )
        data = resp.model_dump(mode="json")
        assert data["id"] == 1
        assert data["name"] == "Test"
        assert data["scopes"] == ["read:*"]

    def test_api_key_created_response_includes_key(self):
        """APIKeyCreatedResponse should include the full key."""
        now = timezone.now()
        resp = APIKeyCreatedResponse(
            id=1,
            name="Test",
            prefix="sk_live_abcd",
            key="sk_live_full_secret_key",
            is_test=False,
            is_active=True,
            plan="free",
            scopes=[],
            rate_limit=100,
            rate_limit_period=3600,
            expires_at=None,
            created_at=now,
            last_used_at=None,
            total_requests=0,
            allowed_ips=[],
        )
        data = resp.model_dump(mode="json")
        assert "key" in data
        assert data["key"] == "sk_live_full_secret_key"

    def test_api_key_list_response(self):
        """APIKeyListResponse should hold items and total."""
        resp = APIKeyListResponse(items=[], total=0)
        assert resp.items == []
        assert resp.total == 0

    def test_export_request_defaults(self):
        """ExportRequest should have sensible defaults."""
        req = ExportRequest()
        assert req.format == "json"
        assert req.include_usage is True
        assert req.start_date is None
        assert req.end_date is None

    def test_usage_summary_schema(self):
        """UsageSummary should accept all required fields."""
        now = timezone.now()
        summary = UsageSummary(
            period_start=now - timedelta(days=30),
            period_end=now,
            total_requests=1000,
            total_errors=10,
            error_rate=0.01,
            avg_response_time_ms=50.0,
            total_bytes_sent=1024000,
            total_bytes_received=512000,
            top_endpoints=[{"endpoint": "/api/test", "count": 500}],
            requests_by_hour=[{"hour": now.isoformat(), "count": 100}],
        )
        assert summary.total_requests == 1000
        assert summary.error_rate == 0.01


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.django_db
    def test_empty_key_string(self, rf, db):
        """Empty key string should not crash."""
        request = rf.get("/", HTTP_X_API_KEY="")
        key = get_api_key_from_request(request)
        # Empty string from header is truthy-ish, but should not match
        if key:
            found = APIKey.objects.get_valid(key)
            assert found is None

    @pytest.mark.django_db
    def test_very_long_key_string(self, rf, db):
        """Very long key should not crash."""
        long_key = "sk_live_" + "a" * 10000
        request = rf.get("/", HTTP_X_API_KEY=long_key)
        key = get_api_key_from_request(request)
        assert key == long_key
        found = APIKey.objects.get_valid(long_key)
        assert found is None

    @pytest.mark.django_db
    def test_multiple_keys_for_same_user(self, user):
        """User should be able to have multiple keys."""
        k1, _ = create_api_key(user, name="Key 1")
        k2, _ = create_api_key(user, name="Key 2")
        k3, _ = create_api_key(user, name="Key 3")
        count = APIKey.objects.filter(user=user).count()
        assert count == 3

    @pytest.mark.django_db
    def test_different_users_separate_keys(self, user, user2):
        """Keys should be isolated per user."""
        k1, _ = create_api_key(user, name="User1 Key")
        k2, _ = create_api_key(user2, name="User2 Key")
        user1_keys = APIKey.objects.filter(user=user)
        user2_keys = APIKey.objects.filter(user=user2)
        assert user1_keys.count() == 1
        assert user2_keys.count() == 1
        assert user1_keys.first().pk != user2_keys.first().pk

    @pytest.mark.django_db
    def test_key_ordering_by_created_at(self, user):
        """Keys should be ordered by created_at descending (default)."""
        k1, _ = create_api_key(user, name="First")
        k2, _ = create_api_key(user, name="Second")
        k3, _ = create_api_key(user, name="Third")
        keys = list(APIKey.objects.filter(user=user))
        assert keys[0].name == "Third"
        assert keys[-1].name == "First"

    @pytest.mark.django_db
    def test_hash_collision_resistance(self, user):
        """Keys with similar prefixes should have different hashes."""
        keys = []
        for i in range(10):
            _, raw_key = create_api_key(user, name=f"Key {i}")
            keys.append(raw_key)

        hashes = [hash_api_key(k) for k in keys]
        assert len(set(hashes)) == 10

    @pytest.mark.django_db
    def test_meta_db_table(self):
        """Model Meta should set correct db_table."""
        assert APIKey._meta.db_table == "django_matt_api_keys"

    @pytest.mark.django_db
    def test_usage_meta_db_table(self):
        """APIKeyUsage Meta should set correct db_table."""
        assert APIKeyUsage._meta.db_table == "django_matt_api_key_usage"

    @pytest.mark.django_db
    def test_key_with_null_expiry_is_not_expired(self, user):
        """Key with null expires_at should not be expired."""
        api_key, _ = create_api_key(user, name="Null Expiry")
        assert api_key.expires_at is None
        assert api_key.is_expired is False
        assert api_key.is_valid is True

    def test_mask_very_short_key(self):
        """Very short key masking should not crash."""
        masked = mask_api_key("abc")
        # Less than 16 chars path
        assert "..." in masked

    def test_get_key_prefix_exact_length(self):
        """Key with exact length should return full key."""
        key = "exactly12345"  # 12 chars
        prefix = get_key_prefix(key, length=12)
        assert prefix == key

    @pytest.mark.django_db
    def test_bearer_with_extra_spaces(self, rf, db):
        """Bearer token with extra spaces should still extract."""
        request = rf.get("/", HTTP_AUTHORIZATION="Bearer   sk_live_spaced  ")
        key = get_api_key_from_request(request)
        assert key == "sk_live_spaced"
