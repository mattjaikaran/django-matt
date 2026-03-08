"""Tests for token blacklisting system."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from django_matt.auth.blacklist.backends import (
    CacheBlacklistBackend,
    DatabaseBlacklistBackend,
    NullBlacklistBackend,
)
from django_matt.auth.blacklist.config import BlacklistConfig
from django_matt.auth.blacklist.core import (
    _get_backend,
    ablacklist_token,
    abulk_revoke_tokens_for_user,
    ais_user_tokens_revoked,
    blacklist_token,
    bulk_revoke_tokens_for_user,
    is_token_blacklisted,
    is_user_tokens_revoked,
    prune_expired_tokens,
    reset_backend,
)
from django_matt.auth.blacklist.models import BlacklistedToken


def _jti() -> str:
    """Generate a random JTI for tests."""
    return uuid.uuid4().hex


def _future(seconds: int = 3600) -> datetime:
    """Return a datetime in the future."""
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _past(seconds: int = 3600) -> datetime:
    """Return a datetime in the past."""
    return datetime.now(UTC) - timedelta(seconds=seconds)


# ============================================================================
# BlacklistConfig tests
# ============================================================================


class TestBlacklistConfig:
    def test_default_backend_is_cache(self, settings):
        settings.DJANGO_MATT_JWT = {}
        config = BlacklistConfig()
        assert config.backend == "cache"

    def test_null_backend_when_explicitly_set(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        config = BlacklistConfig()
        assert config.backend == "null"

    def test_enabled_true_for_default(self, settings):
        settings.DJANGO_MATT_JWT = {}
        config = BlacklistConfig()
        assert config.enabled is True

    def test_enabled_false_for_null(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        config = BlacklistConfig()
        assert config.enabled is False

    def test_enabled_true_for_cache(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        config = BlacklistConfig()
        assert config.enabled is True

    def test_enabled_true_for_database(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "database"}
        config = BlacklistConfig()
        assert config.enabled is True

    def test_cache_prefix_default(self, settings):
        settings.DJANGO_MATT_JWT = {}
        config = BlacklistConfig()
        assert config.cache_prefix == "jwt_blacklist:"

    def test_cache_prefix_custom(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_CACHE_PREFIX": "myapp:bl:"}
        config = BlacklistConfig()
        assert config.cache_prefix == "myapp:bl:"

    def test_blacklist_after_rotation_default(self, settings):
        settings.DJANGO_MATT_JWT = {}
        config = BlacklistConfig()
        assert config.blacklist_after_rotation is True

    def test_blacklist_after_rotation_false(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_AFTER_ROTATION": False}
        config = BlacklistConfig()
        assert config.blacklist_after_rotation is False

    def test_reads_from_settings(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "database"}
        config = BlacklistConfig()
        assert config.backend == "database"


# ============================================================================
# NullBlacklistBackend tests
# ============================================================================


class TestNullBlacklistBackend:
    def test_add_does_nothing(self):
        backend = NullBlacklistBackend()
        # Should not raise
        backend.add(_jti(), _future())

    def test_check_always_false(self):
        backend = NullBlacklistBackend()
        jti = _jti()
        backend.add(jti, _future())
        assert backend.check(jti) is False

    def test_prune_returns_zero(self):
        backend = NullBlacklistBackend()
        assert backend.prune() == 0

    @pytest.mark.asyncio
    async def test_async_add_does_nothing(self):
        backend = NullBlacklistBackend()
        await backend.aadd(_jti(), _future())

    @pytest.mark.asyncio
    async def test_async_check_always_false(self):
        backend = NullBlacklistBackend()
        jti = _jti()
        await backend.aadd(jti, _future())
        assert await backend.acheck(jti) is False

    @pytest.mark.asyncio
    async def test_async_prune_returns_zero(self):
        backend = NullBlacklistBackend()
        assert await backend.aprune() == 0


# ============================================================================
# CacheBlacklistBackend tests
# ============================================================================


class TestCacheBlacklistBackend:
    def test_add_and_check(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = CacheBlacklistBackend()
        jti = _jti()
        backend.add(jti, _future())
        assert backend.check(jti) is True

    def test_check_unknown_jti_returns_false(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = CacheBlacklistBackend()
        assert backend.check(_jti()) is False

    def test_expired_token_not_found(self, settings):
        """A token with expires_at in the past should not be stored (TTL <= 0)."""
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = CacheBlacklistBackend()
        jti = _jti()
        backend.add(jti, _past())
        assert backend.check(jti) is False

    def test_prune_returns_zero(self, settings):
        """Cache handles expiry automatically."""
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = CacheBlacklistBackend()
        assert backend.prune() == 0

    def test_custom_prefix(self, settings):
        settings.DJANGO_MATT_JWT = {
            "BLACKLIST_BACKEND": "cache",
            "BLACKLIST_CACHE_PREFIX": "custom:",
        }
        backend = CacheBlacklistBackend()
        assert backend._prefix == "custom:"
        jti = _jti()
        assert backend._key(jti) == f"custom:{jti}"

    @pytest.mark.asyncio
    async def test_async_add_and_check(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = CacheBlacklistBackend()
        jti = _jti()
        await backend.aadd(jti, _future())
        assert await backend.acheck(jti) is True

    @pytest.mark.asyncio
    async def test_async_check_unknown_jti(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = CacheBlacklistBackend()
        assert await backend.acheck(_jti()) is False


# ============================================================================
# DatabaseBlacklistBackend tests
# ============================================================================


@pytest.mark.django_db
class TestDatabaseBlacklistBackend:
    def test_add_and_check(self):
        backend = DatabaseBlacklistBackend()
        jti = _jti()
        backend.add(jti, _future())
        assert backend.check(jti) is True

    def test_check_unknown_jti_returns_false(self):
        backend = DatabaseBlacklistBackend()
        assert backend.check(_jti()) is False

    def test_expired_token_not_found(self):
        """check() should return False for tokens that have expired."""
        backend = DatabaseBlacklistBackend()
        jti = _jti()
        backend.add(jti, _past())
        assert backend.check(jti) is False

    def test_prune_removes_expired(self):
        backend = DatabaseBlacklistBackend()
        expired_jti = _jti()
        active_jti = _jti()
        backend.add(expired_jti, _past())
        backend.add(active_jti, _future())

        count = backend.prune()
        assert count == 1
        assert not BlacklistedToken.objects.filter(jti=expired_jti).exists()
        assert BlacklistedToken.objects.filter(jti=active_jti).exists()

    def test_prune_returns_zero_when_none_expired(self):
        backend = DatabaseBlacklistBackend()
        backend.add(_jti(), _future())
        assert backend.prune() == 0

    def test_add_idempotent(self):
        """Adding the same JTI twice should not raise, uses update_or_create."""
        backend = DatabaseBlacklistBackend()
        jti = _jti()
        backend.add(jti, _future())
        backend.add(jti, _future(seconds=7200))
        assert BlacklistedToken.objects.filter(jti=jti).count() == 1

    def test_model_str(self):
        backend = DatabaseBlacklistBackend()
        jti = _jti()
        backend.add(jti, _future())
        token = BlacklistedToken.objects.get(jti=jti)
        assert str(token) == f"BlacklistedToken({jti})"

    @pytest.mark.asyncio
    async def test_async_add_and_check(self):
        backend = DatabaseBlacklistBackend()
        jti = _jti()
        await backend.aadd(jti, _future())
        assert await backend.acheck(jti) is True

    @pytest.mark.asyncio
    async def test_async_check_unknown_jti(self):
        backend = DatabaseBlacklistBackend()
        assert await backend.acheck(_jti()) is False

    @pytest.mark.asyncio
    async def test_async_prune(self):
        backend = DatabaseBlacklistBackend()
        expired_jti = _jti()
        active_jti = _jti()
        await backend.aadd(expired_jti, _past())
        await backend.aadd(active_jti, _future())

        count = await backend.aprune()
        assert count == 1


# ============================================================================
# Core API tests
# ============================================================================


class TestCoreAPI:
    def setup_method(self):
        reset_backend()

    def test_default_backend_is_cache(self, settings):
        settings.DJANGO_MATT_JWT = {}
        backend = _get_backend()
        assert isinstance(backend, CacheBlacklistBackend)

    def test_null_backend_when_explicitly_set(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        backend = _get_backend()
        assert isinstance(backend, NullBlacklistBackend)

    def test_cache_backend_selection(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        backend = _get_backend()
        assert isinstance(backend, CacheBlacklistBackend)

    def test_database_backend_selection(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "database"}
        backend = _get_backend()
        assert isinstance(backend, DatabaseBlacklistBackend)

    def test_reset_backend_clears_cache(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        b1 = _get_backend()
        reset_backend()
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "database"}
        b2 = _get_backend()
        assert type(b1) is not type(b2)

    def test_blacklist_token_with_null_backend(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        # Should not raise
        blacklist_token(_jti(), _future())

    def test_is_token_blacklisted_with_null_backend(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        jti = _jti()
        blacklist_token(jti, _future())
        assert is_token_blacklisted(jti) is False

    def test_prune_with_null_backend(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        assert prune_expired_tokens() == 0

    def test_blacklist_and_check_with_cache(self, settings):
        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        jti = _jti()
        blacklist_token(jti, _future())
        assert is_token_blacklisted(jti) is True

    def teardown_method(self):
        reset_backend()


# ============================================================================
# JWT integration tests (verify_access_token / verify_refresh_token)
# ============================================================================


class TestJWTBlacklistIntegration:
    def setup_method(self):
        reset_backend()

    def test_verify_access_token_rejects_blacklisted(self, settings):
        """verify_access_token should raise InvalidTokenError for blacklisted JTI."""
        from django_matt.auth.jwt import InvalidTokenError, verify_access_token

        fake_payload = MagicMock()
        fake_payload.jti = "revoked-jti-123"
        # Set sub=None so per-user sentinel check is skipped in this test
        fake_payload.sub = None

        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload) as mock_decode,
            patch("django_matt.auth.blacklist.core.is_token_blacklisted", return_value=True),
        ):
            with pytest.raises(InvalidTokenError, match="Token has been revoked"):
                verify_access_token("fake.token.here")
            mock_decode.assert_called_once_with("fake.token.here", verify_type="access")

    def test_verify_access_token_allows_non_blacklisted(self, settings):
        """verify_access_token should return payload for non-blacklisted JTI."""
        from django_matt.auth.jwt import verify_access_token

        fake_payload = MagicMock()
        fake_payload.jti = "valid-jti-456"
        # Set sub=None so per-user sentinel check is skipped in this test
        fake_payload.sub = None

        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload),
            patch("django_matt.auth.blacklist.core.is_token_blacklisted", return_value=False),
        ):
            result = verify_access_token("fake.token.here")
            assert result is fake_payload

    def test_verify_access_token_no_jti_skips_check(self, settings):
        """verify_access_token should skip blacklist check if JTI is None."""
        from django_matt.auth.jwt import verify_access_token

        fake_payload = MagicMock()
        fake_payload.jti = None
        # Set sub=None so per-user sentinel check is also skipped
        fake_payload.sub = None

        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload),
            patch("django_matt.auth.blacklist.core.is_token_blacklisted") as mock_check,
        ):
            result = verify_access_token("fake.token.here")
            assert result is fake_payload
            mock_check.assert_not_called()

    def test_verify_refresh_token_rejects_blacklisted(self, settings):
        """verify_refresh_token should raise InvalidTokenError for blacklisted JTI."""
        from django_matt.auth.jwt import InvalidTokenError, verify_refresh_token

        fake_payload = MagicMock()
        fake_payload.jti = "revoked-refresh-jti"

        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload),
            patch("django_matt.auth.blacklist.core.is_token_blacklisted", return_value=True),
            pytest.raises(InvalidTokenError, match="Token has been revoked"),
        ):
            verify_refresh_token("fake.refresh.token")

    def test_verify_refresh_token_allows_non_blacklisted(self, settings):
        """verify_refresh_token should return payload for non-blacklisted JTI."""
        from django_matt.auth.jwt import verify_refresh_token

        fake_payload = MagicMock()
        fake_payload.jti = "valid-refresh-jti"

        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload),
            patch("django_matt.auth.blacklist.core.is_token_blacklisted", return_value=False),
        ):
            result = verify_refresh_token("fake.refresh.token")
            assert result is fake_payload

    def teardown_method(self):
        reset_backend()


# ============================================================================
# refresh_tokens blacklist integration
# ============================================================================


class TestRefreshTokensBlacklist:
    def setup_method(self):
        reset_backend()

    @pytest.mark.django_db
    def test_refresh_tokens_blacklists_old_token(self, settings):
        """refresh_tokens should blacklist old refresh token when configured."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.jwt import refresh_tokens

        User = get_user_model()
        user = User.objects.create_user(
            username="refreshtest",
            email="refresh@test.com",
            password="testpass123",
        )

        fake_payload = MagicMock()
        fake_payload.jti = "old-refresh-jti"
        fake_payload.sub = str(user.pk)
        fake_payload.exp = _future()

        settings.DJANGO_MATT_JWT = {"BLACKLIST_AFTER_ROTATION": True}

        with (
            patch("django_matt.auth.jwt.verify_refresh_token", return_value=fake_payload),
            patch("django_matt.auth.blacklist.core.blacklist_token") as mock_bl,
            patch("django_matt.auth.jwt.create_token_pair") as mock_create,
        ):
            mock_create.return_value = MagicMock()
            refresh_tokens("fake.refresh.token")
            mock_bl.assert_called_once_with(fake_payload.jti, fake_payload.exp)

    @pytest.mark.django_db
    def test_refresh_tokens_skips_blacklist_when_disabled(self, settings):
        """refresh_tokens should not blacklist when BLACKLIST_AFTER_ROTATION is False."""
        from django.contrib.auth import get_user_model

        from django_matt.auth.jwt import refresh_tokens

        User = get_user_model()
        user = User.objects.create_user(
            username="refreshtest2",
            email="refresh2@test.com",
            password="testpass123",
        )

        fake_payload = MagicMock()
        fake_payload.jti = "old-refresh-jti"
        fake_payload.sub = str(user.pk)

        with (
            patch("django_matt.auth.jwt.verify_refresh_token", return_value=fake_payload),
            patch("django_matt.auth.jwt.jwt_config") as mock_config,
            patch("django_matt.auth.blacklist.core.blacklist_token") as mock_bl,
            patch("django_matt.auth.jwt.create_token_pair") as mock_create,
        ):
            mock_config.blacklist_after_rotation = False
            mock_config.user_id_field = "id"
            mock_create.return_value = MagicMock()
            refresh_tokens("fake.refresh.token")
            mock_bl.assert_not_called()

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_async_refresh_tokens_blacklists_old_token(self, settings):
        """async_refresh_tokens should blacklist old refresh token when configured."""
        from django.contrib.auth import get_user_model

        from asgiref.sync import sync_to_async

        from django_matt.auth.jwt import async_refresh_tokens

        User = get_user_model()
        user = await sync_to_async(User.objects.create_user)(
            username="asyncrefresh",
            email="asyncrefresh@test.com",
            password="testpass123",
        )

        fake_payload = MagicMock()
        fake_payload.jti = "old-async-refresh-jti"
        fake_payload.sub = str(user.pk)
        fake_payload.exp = _future()

        settings.DJANGO_MATT_JWT = {"BLACKLIST_AFTER_ROTATION": True}

        async def _mock_averify(*args, **kwargs):
            return fake_payload

        async def _mock_ablacklist(*args, **kwargs):
            return None

        async def _mock_acreate_pair(*args, **kwargs):
            return MagicMock()

        with (
            patch("django_matt.auth.jwt.averify_refresh_token", side_effect=_mock_averify),
            patch("django_matt.auth.blacklist.core.ablacklist_token") as mock_abl,
            patch("django_matt.auth.jwt.acreate_token_pair", side_effect=_mock_acreate_pair),
        ):
            mock_abl.side_effect = _mock_ablacklist
            await async_refresh_tokens("fake.refresh.token")
            mock_abl.assert_called_once_with(fake_payload.jti, fake_payload.exp)

    def teardown_method(self):
        reset_backend()


# ============================================================================
# Bulk revocation tests
# ============================================================================


class TestBulkRevocation:
    def setup_method(self):
        reset_backend()

    def test_bulk_revoke_stores_sentinel(self, settings):
        """bulk_revoke_tokens_for_user stores a per-user sentinel in cache."""
        import time

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()
        user_id = 42
        bulk_revoke_tokens_for_user(user_id)
        old_iat = time.time() - 10  # issued 10 seconds ago
        assert is_user_tokens_revoked(user_id, old_iat) is True

    def test_bulk_revoke_null_backend_is_noop(self, settings):
        """bulk_revoke_tokens_for_user with null backend does nothing."""
        import time

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "null"}
        reset_backend()
        user_id = 99
        bulk_revoke_tokens_for_user(user_id)
        assert is_user_tokens_revoked(user_id, time.time() - 10) is False

    def test_is_user_tokens_revoked_false_for_new_token(self, settings):
        """Tokens issued AFTER the sentinel are NOT revoked."""
        import time

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()
        user_id = 55
        bulk_revoke_tokens_for_user(user_id)
        new_iat = time.time() + 5  # issued after revocation
        assert is_user_tokens_revoked(user_id, new_iat) is False

    def test_is_user_tokens_revoked_false_when_no_sentinel(self, settings):
        """is_user_tokens_revoked returns False when no sentinel exists."""
        import time

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()
        user_id = 77
        assert is_user_tokens_revoked(user_id, time.time() - 10) is False

    @pytest.mark.asyncio
    async def test_abulk_revoke_stores_sentinel(self, settings):
        """abulk_revoke_tokens_for_user async stores sentinel."""
        import time

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()
        user_id = 88
        await abulk_revoke_tokens_for_user(user_id)
        old_iat = time.time() - 5
        assert await ais_user_tokens_revoked(user_id, old_iat) is True

    @pytest.mark.asyncio
    async def test_ais_user_tokens_revoked_false_when_no_sentinel(self, settings):
        """ais_user_tokens_revoked returns False when no sentinel exists."""
        import time

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()
        user_id = 100
        assert await ais_user_tokens_revoked(user_id, time.time() - 10) is False

    def teardown_method(self):
        reset_backend()


# ============================================================================
# averify_access_token user-revocation sentinel tests
# ============================================================================


class TestAverifyAccessTokenBulkRevocation:
    def setup_method(self):
        reset_backend()

    @pytest.mark.asyncio
    async def test_averify_access_token_rejects_user_revoked_token(self, settings):
        """averify_access_token rejects a token issued before user's revocation sentinel."""
        from django_matt.auth.jwt import InvalidTokenError, averify_access_token

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()

        fake_payload = MagicMock()
        fake_payload.jti = "user-revoked-jti"
        fake_payload.sub = "123"
        fake_payload.iat = datetime(2020, 1, 1, tzinfo=UTC)

        async def _mock_ais_revoked(user_id, iat):
            return True

        # Patch at the source module since jwt.py imports inline
        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload),
            patch(
                "django_matt.auth.blacklist.core.ais_token_blacklisted",
                return_value=False,
            ),
            patch(
                "django_matt.auth.blacklist.core.ais_user_tokens_revoked",
                side_effect=_mock_ais_revoked,
            ),
        ):
            with pytest.raises(InvalidTokenError, match="revoked"):
                await averify_access_token("fake.token.here")

    @pytest.mark.asyncio
    async def test_averify_access_token_allows_post_revocation_token(self, settings):
        """averify_access_token allows a token issued after user's revocation sentinel."""
        from django_matt.auth.jwt import averify_access_token

        settings.DJANGO_MATT_JWT = {"BLACKLIST_BACKEND": "cache"}
        reset_backend()

        fake_payload = MagicMock()
        fake_payload.jti = "post-revoke-jti"
        fake_payload.sub = "123"
        fake_payload.iat = datetime(2030, 1, 1, tzinfo=UTC)

        async def _mock_ais_revoked(user_id, iat):
            return False

        # Patch at the source module since jwt.py imports inline
        with (
            patch("django_matt.auth.jwt.decode_token", return_value=fake_payload),
            patch(
                "django_matt.auth.blacklist.core.ais_token_blacklisted",
                return_value=False,
            ),
            patch(
                "django_matt.auth.blacklist.core.ais_user_tokens_revoked",
                side_effect=_mock_ais_revoked,
            ),
        ):
            result = await averify_access_token("fake.token.here")
            assert result is fake_payload

    def teardown_method(self):
        reset_backend()
