"""Tests for django_matt.throttling.defaults and django_matt.auth.login_config."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from django_matt.auth.login_config import (
    EmailOrUsernameBackend,
    LoginConfig,
    get_login_config,
    reset_login_config,
)
from django_matt.throttling.defaults import (
    PRESETS,
    SCOPE_PATTERNS,
    get_rate_for_scope,
    get_scope_for_path,
    get_throttle_defaults,
    resolve_throttle_config,
)

# ---------------------------------------------------------------------------
# Throttle defaults
# ---------------------------------------------------------------------------


class TestPresets:
    def test_standard_preset_exists(self):
        assert "standard" in PRESETS

    def test_strict_preset_exists(self):
        assert "strict" in PRESETS

    def test_relaxed_preset_exists(self):
        assert "relaxed" in PRESETS

    def test_api_preset_exists(self):
        assert "api" in PRESETS

    @pytest.mark.parametrize("preset", ["standard", "strict", "relaxed", "api"])
    def test_preset_has_required_keys(self, preset):
        config = PRESETS[preset]
        assert "anon_rate" in config
        assert "user_rate" in config
        assert "login_rate" in config
        assert "burst_multiplier" in config
        assert "backend" in config

    def test_strict_rates_lower_than_standard(self):
        strict_anon = int(PRESETS["strict"]["anon_rate"].split("/")[0])
        standard_anon = int(PRESETS["standard"]["anon_rate"].split("/")[0])
        assert strict_anon < standard_anon

    def test_relaxed_rates_higher_than_standard(self):
        relaxed_anon = int(PRESETS["relaxed"]["anon_rate"].split("/")[0])
        standard_anon = int(PRESETS["standard"]["anon_rate"].split("/")[0])
        assert relaxed_anon > standard_anon


class TestResolveThrottleConfig:
    def test_none_returns_empty(self):
        assert resolve_throttle_config(None) == {}

    def test_standard_string(self):
        config = resolve_throttle_config("standard")
        assert config["anon_rate"] == "100/minute"
        assert config["backend"] == "memory"

    def test_strict_string(self):
        config = resolve_throttle_config("strict")
        assert config["anon_rate"] == "30/minute"

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown throttle preset"):
            resolve_throttle_config("nonexistent")

    def test_dict_merges_with_standard(self):
        config = resolve_throttle_config({"anon_rate": "50/minute"})
        assert config["anon_rate"] == "50/minute"
        # Other keys filled from standard defaults
        assert config["user_rate"] == PRESETS["standard"]["user_rate"]
        assert config["backend"] == "memory"

    def test_dict_full_override(self):
        custom = {
            "anon_rate": "10/minute",
            "user_rate": "100/minute",
            "login_rate": "3/minute",
            "register_rate": "2/minute",
            "password_reset_rate": "2/minute",
            "exclude_paths": [],
            "exclude_methods": [],
            "burst_multiplier": 1.0,
            "backend": "redis",
        }
        config = resolve_throttle_config(custom)
        assert config["backend"] == "redis"
        assert config["anon_rate"] == "10/minute"

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            resolve_throttle_config(42)

    def test_returns_copy_not_reference(self):
        config1 = resolve_throttle_config("standard")
        config2 = resolve_throttle_config("standard")
        config1["anon_rate"] = "modified"
        assert config2["anon_rate"] == "100/minute"


class TestGetThrottleDefaults:
    def test_no_setting_returns_empty(self, settings):
        if hasattr(settings, "MATT_THROTTLE"):
            delattr(settings, "MATT_THROTTLE")
        assert get_throttle_defaults() == {}

    def test_standard_setting(self, settings):
        settings.MATT_THROTTLE = "standard"
        config = get_throttle_defaults()
        assert config["anon_rate"] == "100/minute"

    def test_dict_setting(self, settings):
        settings.MATT_THROTTLE = {"anon_rate": "200/minute"}
        config = get_throttle_defaults()
        assert config["anon_rate"] == "200/minute"


class TestGetRateForScope:
    def test_anon_rate(self, settings):
        settings.MATT_THROTTLE = "standard"
        rate = get_rate_for_scope("anon")
        assert rate == "100/minute"

    def test_login_rate(self, settings):
        settings.MATT_THROTTLE = "standard"
        rate = get_rate_for_scope("login")
        assert rate == "10/minute"

    def test_unknown_scope_returns_none(self, settings):
        settings.MATT_THROTTLE = "standard"
        assert get_rate_for_scope("nonexistent") is None


class TestGetScopeForPath:
    def test_login_paths(self):
        assert get_scope_for_path("/auth/login") == "login"
        assert get_scope_for_path("/auth/login/") == "login"
        assert get_scope_for_path("/auth/token") == "login"

    def test_register_paths(self):
        assert get_scope_for_path("/auth/register") == "register"
        assert get_scope_for_path("/auth/signup") == "register"

    def test_password_reset_paths(self):
        assert get_scope_for_path("/auth/password-reset") == "password_reset"
        assert get_scope_for_path("/auth/forgot-password") == "password_reset"

    def test_unknown_path(self):
        assert get_scope_for_path("/api/users/") is None

    def test_case_insensitive(self):
        assert get_scope_for_path("/Auth/Login") == "login"


class TestScopePatterns:
    def test_login_patterns_exist(self):
        assert "login" in SCOPE_PATTERNS

    def test_register_patterns_exist(self):
        assert "register" in SCOPE_PATTERNS

    def test_password_reset_patterns_exist(self):
        assert "password_reset" in SCOPE_PATTERNS


# ---------------------------------------------------------------------------
# Login config
# ---------------------------------------------------------------------------


class TestLoginConfig:
    def test_defaults(self):
        config = LoginConfig()
        assert config.login_field == "email"
        assert config.case_insensitive is True
        assert config.strip_whitespace is True
        assert config.require_email_verified is False
        assert config.allow_inactive is False
        assert config.max_login_attempts == 0
        assert config.lockout_duration == 300

    def test_frozen(self):
        config = LoginConfig()
        with pytest.raises(AttributeError):
            config.login_field = "username"

    def test_custom_values(self):
        config = LoginConfig(
            login_field="username",
            case_insensitive=False,
            max_login_attempts=5,
        )
        assert config.login_field == "username"
        assert config.case_insensitive is False
        assert config.max_login_attempts == 5


class TestGetLoginConfig:
    def setup_method(self):
        reset_login_config()

    def teardown_method(self):
        reset_login_config()

    def test_default_config(self, settings):
        if hasattr(settings, "MATT_AUTH"):
            delattr(settings, "MATT_AUTH")
        config = get_login_config()
        assert config.login_field == "email"

    def test_reads_from_settings(self, settings):
        settings.MATT_AUTH = {"login_field": "username", "case_insensitive": False}
        config = get_login_config()
        assert config.login_field == "username"
        assert config.case_insensitive is False

    def test_caches_config(self, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        config1 = get_login_config()
        settings.MATT_AUTH = {"login_field": "username"}
        config2 = get_login_config()
        # Should return cached value
        assert config1 is config2
        assert config2.login_field == "email"


class TestResetLoginConfig:
    def test_reset_clears_cache(self, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        config1 = get_login_config()
        reset_login_config()
        settings.MATT_AUTH = {"login_field": "username"}
        config2 = get_login_config()
        assert config1.login_field == "email"
        assert config2.login_field == "username"
        reset_login_config()


# ---------------------------------------------------------------------------
# EmailOrUsernameBackend
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEmailOrUsernameBackend:
    @pytest.fixture(autouse=True)
    def _reset(self):
        reset_login_config()
        yield
        reset_login_config()

    @pytest.fixture
    def user(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="secret123",
        )
        return u

    def test_login_by_email(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="test@example.com", password="secret123")
        assert result is not None
        assert result.pk == user.pk

    def test_login_by_username(self, user, settings):
        settings.MATT_AUTH = {"login_field": "username"}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="testuser", password="secret123")
        assert result is not None
        assert result.pk == user.pk

    def test_wrong_password_returns_none(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="test@example.com", password="wrong")
        assert result is None

    def test_nonexistent_user_returns_none(self, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="nobody@example.com", password="secret123")
        assert result is None

    def test_email_fallback_to_username(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        backend = EmailOrUsernameBackend()
        # Login with username when login_field is email — should fall back
        result = backend.authenticate(None, username="testuser", password="secret123")
        assert result is not None
        assert result.pk == user.pk

    def test_username_fallback_to_email(self, user, settings):
        settings.MATT_AUTH = {"login_field": "username"}
        backend = EmailOrUsernameBackend()
        # Login with email when login_field is username — should fall back
        result = backend.authenticate(None, username="test@example.com", password="secret123")
        assert result is not None
        assert result.pk == user.pk

    def test_case_insensitive_email(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email", "case_insensitive": True}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="TEST@EXAMPLE.COM", password="secret123")
        assert result is not None

    def test_case_sensitive_email(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email", "case_insensitive": False}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="TEST@EXAMPLE.COM", password="secret123")
        # Exact match fails because DB has lowercase
        assert result is None

    def test_strip_whitespace(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email", "strip_whitespace": True}
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="  test@example.com  ", password="secret123")
        assert result is not None

    def test_inactive_user_rejected(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email", "allow_inactive": False}
        user.is_active = False
        user.save()
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="test@example.com", password="secret123")
        assert result is None

    def test_inactive_user_allowed(self, user, settings):
        settings.MATT_AUTH = {"login_field": "email", "allow_inactive": True}
        user.is_active = False
        user.save()
        backend = EmailOrUsernameBackend()
        result = backend.authenticate(None, username="test@example.com", password="secret123")
        assert result is not None

    def test_none_username_returns_none(self, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        backend = EmailOrUsernameBackend()
        assert backend.authenticate(None, username=None, password="secret") is None

    def test_none_password_returns_none(self, settings):
        settings.MATT_AUTH = {"login_field": "email"}
        backend = EmailOrUsernameBackend()
        assert backend.authenticate(None, username="test@example.com", password=None) is None
