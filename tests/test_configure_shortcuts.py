"""Tests for configure() shortcut params."""

from django_matt.config import _build_shortcut_settings


class TestBuildShortcutSettings:
    def test_no_params(self):
        result = _build_shortcut_settings()
        assert result == {}

    def test_auth_jwt(self):
        result = _build_shortcut_settings(auth="jwt")
        assert result["AUTH_BACKEND"] == "jwt"
        assert "JWT_AUTH" in result
        assert result["JWT_AUTH"]["ALGORITHM"] == "HS256"

    def test_auth_session(self):
        result = _build_shortcut_settings(auth="session")
        assert result["AUTH_BACKEND"] == "session"

    def test_database_postgresql(self):
        result = _build_shortcut_settings(database="postgresql")
        assert result["DATABASE_ENGINE"] == "django.db.backends.postgresql"
        assert result["CONNECTION_POOL"]["ENABLED"] is True

    def test_database_sqlite(self):
        result = _build_shortcut_settings(database="sqlite")
        assert result["DATABASE_ENGINE"] == "django.db.backends.sqlite3"

    def test_cache_redis(self):
        result = _build_shortcut_settings(cache="redis")
        assert "redis" in result["CACHE_BACKEND"].lower()

    def test_cache_memory(self):
        result = _build_shortcut_settings(cache="memory")
        assert "locmem" in result["CACHE_BACKEND"].lower()

    def test_middleware_production(self):
        result = _build_shortcut_settings(middleware="production")
        assert result["MIDDLEWARE_STACK"] == "production"

    def test_middleware_development(self):
        result = _build_shortcut_settings(middleware="development")
        assert result["MIDDLEWARE_STACK"] == "development"

    def test_throttle(self):
        result = _build_shortcut_settings(throttle="100/hour")
        assert result["THROTTLE"]["DEFAULT_RATE"] == "100/hour"

    def test_cors_true(self):
        result = _build_shortcut_settings(cors=True)
        assert result["CORS"]["ALLOWED_ORIGINS"] is True
        assert result["CORS"]["ENABLED"] is True

    def test_cors_list(self):
        result = _build_shortcut_settings(cors=["https://app.example.com"])
        assert "https://app.example.com" in result["CORS"]["ALLOWED_ORIGINS"]

    def test_cors_none(self):
        result = _build_shortcut_settings(cors=None)
        assert "CORS" not in result

    def test_multiple_params_combine(self):
        result = _build_shortcut_settings(
            auth="jwt",
            database="postgresql",
            cache="redis",
            middleware="production",
            throttle="50/minute",
            cors=True,
        )
        assert result["AUTH_BACKEND"] == "jwt"
        assert result["DATABASE_ENGINE"] == "django.db.backends.postgresql"
        assert "redis" in result["CACHE_BACKEND"].lower()
        assert result["MIDDLEWARE_STACK"] == "production"
        assert result["THROTTLE"]["DEFAULT_RATE"] == "50/minute"
        assert result["CORS"]["ENABLED"] is True

    def test_unknown_auth_ignored(self):
        result = _build_shortcut_settings(auth="unknown")
        assert "AUTH_BACKEND" not in result

    def test_unknown_database_ignored(self):
        result = _build_shortcut_settings(database="unknown")
        assert "DATABASE_ENGINE" not in result

    def test_unknown_cache_ignored(self):
        result = _build_shortcut_settings(cache="unknown")
        assert "CACHE_BACKEND" not in result
