"""
Configuration sections for the interactive editor.

Each section handles a specific category of configuration settings.
"""

from abc import ABC, abstractmethod
from typing import Any

from django_matt.cli.prompts import confirm, select, text


class ConfigSection(ABC):
    """Base class for configuration sections."""

    name: str = "base"
    title: str = "Base Section"
    description: str = "Base configuration section"

    @abstractmethod
    def get_prompts(self) -> dict[str, Any]:
        """Get prompts for this section and return values."""

    @abstractmethod
    def get_env_vars(self, values: dict[str, Any]) -> dict[str, str]:
        """Convert values to environment variables."""

    @abstractmethod
    def validate(self, values: dict[str, Any]) -> list[str]:
        """Validate values, return list of error messages."""


class GeneralSection(ConfigSection):
    """General project configuration."""

    name = "general"
    title = "General Settings"
    description = "Basic project configuration"

    def get_prompts(self) -> dict[str, Any]:
        """Get general configuration values."""
        environment = select(
            "Select environment:",
            choices=[
                {"name": "Development", "value": "development"},
                {"name": "Staging", "value": "staging"},
                {"name": "Production", "value": "production"},
            ],
            default="development",
        )

        debug = confirm(
            "Enable debug mode?",
            default=environment == "development",
        )

        allowed_hosts = text(
            "Allowed hosts (comma-separated):",
            default="localhost,127.0.0.1" if environment == "development" else "",
        )

        return {
            "environment": environment,
            "debug": debug,
            "allowed_hosts": allowed_hosts,
        }

    def get_env_vars(self, values: dict[str, Any]) -> dict[str, str]:
        """Convert to environment variables."""
        return {
            "DJANGO_ENV": values["environment"],
            "DJANGO_DEBUG": str(values["debug"]).lower(),
            "ALLOWED_HOSTS": values["allowed_hosts"],
        }

    def validate(self, values: dict[str, Any]) -> list[str]:
        """Validate general settings."""
        errors = []

        if values.get("environment") == "production" and values.get("debug"):
            errors.append("Debug mode should be disabled in production")

        if not values.get("allowed_hosts"):
            errors.append("Allowed hosts cannot be empty")

        return errors


class DatabaseSection(ConfigSection):
    """Database configuration."""

    name = "database"
    title = "Database Settings"
    description = "Configure your database connection"

    def get_prompts(self) -> dict[str, Any]:
        """Get database configuration values."""
        db_type = select(
            "Select database type:",
            choices=[
                {"name": "PostgreSQL (Recommended)", "value": "postgres"},
                {"name": "MySQL", "value": "mysql"},
                {"name": "SQLite (Development only)", "value": "sqlite"},
            ],
            default="postgres",
        )

        if db_type == "sqlite":
            db_name = text(
                "Database file name:",
                default="db.sqlite3",
            )
            return {
                "db_type": db_type,
                "db_name": db_name,
            }

        db_name = text("Database name:", default="django_matt_db")
        db_user = text("Database user:", default="postgres" if db_type == "postgres" else "root")
        db_password = text("Database password:", default="")
        db_host = text("Database host:", default="localhost")
        db_port = text(
            "Database port:",
            default="5432" if db_type == "postgres" else "3306",
        )

        # PostgreSQL specific options
        pgvector_enabled = False
        pool_enabled = False

        if db_type == "postgres":
            pgvector_enabled = confirm(
                "Enable pgvector extension (for AI/ML embeddings)?",
                default=False,
            )
            pool_enabled = confirm(
                "Enable connection pooling?",
                default=False,
            )

        return {
            "db_type": db_type,
            "db_name": db_name,
            "db_user": db_user,
            "db_password": db_password,
            "db_host": db_host,
            "db_port": db_port,
            "pgvector_enabled": pgvector_enabled,
            "pool_enabled": pool_enabled,
        }

    def get_env_vars(self, values: dict[str, Any]) -> dict[str, str]:
        """Convert to environment variables."""
        db_type = values["db_type"]

        engines = {
            "postgres": "django.db.backends.postgresql",
            "mysql": "django.db.backends.mysql",
            "sqlite": "django.db.backends.sqlite3",
        }

        env_vars = {
            "DB_TYPE": db_type,
            "DB_ENGINE": engines.get(db_type, engines["postgres"]),
            "DB_NAME": values["db_name"],
        }

        if db_type != "sqlite":
            env_vars.update(
                {
                    "DB_USER": values.get("db_user", ""),
                    "DB_PASSWORD": values.get("db_password", ""),
                    "DB_HOST": values.get("db_host", "localhost"),
                    "DB_PORT": values.get("db_port", "5432"),
                }
            )

        if db_type == "postgres":
            env_vars.update(
                {
                    "DB_PGVECTOR_ENABLED": str(values.get("pgvector_enabled", False)).lower(),
                    "DB_POOL_ENABLED": str(values.get("pool_enabled", False)).lower(),
                }
            )

        return env_vars

    def validate(self, values: dict[str, Any]) -> list[str]:
        """Validate database settings."""
        errors = []

        if not values.get("db_name"):
            errors.append("Database name is required")

        if values.get("db_type") != "sqlite":
            if not values.get("db_user"):
                errors.append("Database user is required for PostgreSQL/MySQL")

        return errors


class CacheSection(ConfigSection):
    """Cache configuration."""

    name = "cache"
    title = "Cache Settings"
    description = "Configure caching for better performance"

    def get_prompts(self) -> dict[str, Any]:
        """Get cache configuration values."""
        cache_backend = select(
            "Select cache backend:",
            choices=[
                {"name": "Local Memory (Development)", "value": "locmem"},
                {"name": "Redis (Recommended for production)", "value": "redis"},
                {"name": "Memcached", "value": "memcached"},
                {"name": "Database", "value": "database"},
                {"name": "File-based", "value": "file"},
                {"name": "Dummy (No caching)", "value": "dummy"},
            ],
            default="locmem",
        )

        cache_location = ""
        cache_timeout = 300

        if cache_backend == "redis":
            cache_location = text(
                "Redis URL:",
                default="redis://localhost:6379/1",
            )
        elif cache_backend == "memcached":
            cache_location = text(
                "Memcached location:",
                default="127.0.0.1:11211",
            )
        elif cache_backend == "file":
            cache_location = text(
                "Cache directory:",
                default=".cache/django",
            )
        elif cache_backend == "database":
            cache_location = text(
                "Cache table name:",
                default="django_cache",
            )
        elif cache_backend == "locmem":
            cache_location = text(
                "Cache name:",
                default="django_matt",
            )

        cache_timeout = text(
            "Default cache timeout (seconds):",
            default="300",
        )

        return {
            "cache_backend": cache_backend,
            "cache_location": cache_location,
            "cache_timeout": cache_timeout,
        }

    def get_env_vars(self, values: dict[str, Any]) -> dict[str, str]:
        """Convert to environment variables."""
        backends = {
            "locmem": "django.core.cache.backends.locmem.LocMemCache",
            "redis": "django.core.cache.backends.redis.RedisCache",
            "memcached": "django.core.cache.backends.memcached.PyMemcacheCache",
            "database": "django.core.cache.backends.db.DatabaseCache",
            "file": "django.core.cache.backends.filebased.FileBasedCache",
            "dummy": "django.core.cache.backends.dummy.DummyCache",
        }

        backend = values.get("cache_backend", "locmem")

        env_vars = {
            "CACHE_BACKEND": backends.get(backend, backends["locmem"]),
            "CACHE_LOCATION": values.get("cache_location", ""),
            "CACHE_TIMEOUT": str(values.get("cache_timeout", "300")),
        }

        if backend == "redis":
            env_vars["REDIS_URL"] = values.get("cache_location", "").replace("/1", "/0")

        return env_vars

    def validate(self, values: dict[str, Any]) -> list[str]:
        """Validate cache settings."""
        errors = []

        backend = values.get("cache_backend")
        location = values.get("cache_location")

        if backend in ("redis", "memcached", "file", "database") and not location:
            errors.append(f"Cache location is required for {backend}")

        try:
            timeout = int(values.get("cache_timeout", 300))
            if timeout < 0:
                errors.append("Cache timeout must be a positive number")
        except ValueError:
            errors.append("Cache timeout must be a number")

        return errors


class SecuritySection(ConfigSection):
    """Security configuration."""

    name = "security"
    title = "Security Settings"
    description = "Configure security options"

    def get_prompts(self) -> dict[str, Any]:
        """Get security configuration values."""
        import secrets

        secret_key = text(
            "Secret key (leave blank to generate):",
            default="",
        )

        if not secret_key:
            secret_key = secrets.token_hex(32)

        https_enabled = confirm(
            "Enable HTTPS-related security settings?",
            default=False,
        )

        csrf_trusted_origins = ""
        cors_enabled = False
        cors_origins = ""

        if https_enabled:
            csrf_trusted_origins = text(
                "CSRF trusted origins (comma-separated):",
                default="https://localhost",
            )

        cors_enabled = confirm(
            "Enable CORS?",
            default=False,
        )

        if cors_enabled:
            cors_origins = text(
                "CORS allowed origins (comma-separated, or * for all):",
                default="http://localhost:3000",
            )

        return {
            "secret_key": secret_key,
            "https_enabled": https_enabled,
            "csrf_trusted_origins": csrf_trusted_origins,
            "cors_enabled": cors_enabled,
            "cors_origins": cors_origins,
        }

    def get_env_vars(self, values: dict[str, Any]) -> dict[str, str]:
        """Convert to environment variables."""
        env_vars = {
            "DJANGO_SECRET_KEY": values["secret_key"],
        }

        if values.get("https_enabled"):
            env_vars.update(
                {
                    "CSRF_COOKIE_SECURE": "true",
                    "SESSION_COOKIE_SECURE": "true",
                    "SECURE_SSL_REDIRECT": "true",
                    "SECURE_HSTS_SECONDS": "31536000",
                }
            )

        if values.get("csrf_trusted_origins"):
            env_vars["CSRF_TRUSTED_ORIGINS"] = values["csrf_trusted_origins"]

        if values.get("cors_enabled"):
            env_vars["CORS_ALLOWED_ORIGINS"] = values.get("cors_origins", "")

        return env_vars

    def validate(self, values: dict[str, Any]) -> list[str]:
        """Validate security settings."""
        errors = []

        if not values.get("secret_key"):
            errors.append("Secret key is required")
        elif len(values["secret_key"]) < 32:
            errors.append("Secret key should be at least 32 characters")

        return errors
