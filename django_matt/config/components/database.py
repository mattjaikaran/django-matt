"""
Database settings for Django Matt applications.

This module contains settings for configuring the database connection.
Django Matt provides first-class support for PostgreSQL, including pgvector,
while also supporting MySQL and SQLite with easy configuration.

Supports Django 5.2+ and 6.0+ with modern connection pooling options.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import django

import orjson

from django_matt.config.utils import get_env_bool, get_env_dict, get_env_int

# Django version detection
DJANGO_VERSION = tuple(map(int, django.__version__.split(".")[:2]))
DJANGO_5_1_PLUS = DJANGO_VERSION >= (5, 1)
DJANGO_5_2_PLUS = DJANGO_VERSION >= (5, 2)
DJANGO_6_0_PLUS = DJANGO_VERSION >= (6, 0)

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Detect database type from environment
DB_TYPE = os.environ.get("DB_TYPE", "postgres").lower()


def get_connection_pool_config() -> dict[str, Any]:
    """
    Get connection pooling configuration based on Django version and settings.

    Django 5.1+ supports:
    - CONN_HEALTH_CHECKS: Enable connection health checks before use
    - CONN_MAX_AGE: Maximum age of connections (None for persistent)

    Django 6.0+ will support:
    - Native psycopg3 connection pooling via OPTIONS

    Returns:
        Dict with connection pooling settings
    """
    config = {}

    # Basic connection persistence (Django 4.0+)
    # 0 = close connection after each request (required for ASGI, Django #33497)
    # None = persistent connections (unsafe under ASGI)
    # N = keep connection for N seconds
    conn_max_age = os.environ.get("DB_CONN_MAX_AGE")
    if conn_max_age is not None:
        if conn_max_age.lower() == "none":
            config["CONN_MAX_AGE"] = None  # Persistent connections
        else:
            config["CONN_MAX_AGE"] = int(conn_max_age)
    else:
        # Default: always 0 for ASGI safety
        config["CONN_MAX_AGE"] = 0  # ASGI requires 0 (Django #33497)

    # Connection health checks (Django 5.1+)
    if DJANGO_5_1_PLUS:
        config["CONN_HEALTH_CHECKS"] = get_env_bool("DB_CONN_HEALTH_CHECKS", True)

    return config


def get_postgres_pool_options() -> dict[str, Any]:
    """
    Get PostgreSQL-specific connection pool options.

    For psycopg3 (Django 5.2+), pooling can be configured via OPTIONS.

    Returns:
        Dict with pool options for PostgreSQL
    """
    # Connection pooling is enabled by default on Django 5.2+ (psycopg3)
    # Set DB_POOL_ENABLED=false to disable
    env = os.environ.get("DJANGO_ENV", "development")
    pool_default = DJANGO_5_2_PLUS and env == "production"
    pool_enabled = get_env_bool("DB_POOL_ENABLED", pool_default)

    if not pool_enabled:
        return {}

    # psycopg3 pool options (Django 5.2+ with psycopg3)
    use_psycopg3 = get_env_bool("DB_USE_PSYCOPG3", DJANGO_5_2_PLUS)

    if use_psycopg3 and DJANGO_5_2_PLUS:
        return {
            "pool": {
                "min_size": get_env_int("DB_POOL_MIN_SIZE", 5),
                "max_size": get_env_int("DB_POOL_MAX_SIZE", 20),
                "max_idle": get_env_int("DB_POOL_MAX_IDLE", 300),
                "max_lifetime": get_env_int("DB_POOL_MAX_LIFETIME", 3600),
                "timeout": get_env_int("DB_POOL_TIMEOUT", 30),
            }
        }

    return {}


def get_postgres_config() -> dict[str, Any]:
    """Get PostgreSQL database configuration."""
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "django_matt"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "ATOMIC_REQUESTS": get_env_bool("DB_ATOMIC_REQUESTS", False),
        "AUTOCOMMIT": get_env_bool("DB_AUTOCOMMIT", True),
        "OPTIONS": get_env_dict("DB_OPTIONS", {}),
        "TEST": {
            "NAME": os.environ.get("DB_TEST_NAME"),
        },
    }

    # Add connection pooling settings
    config.update(get_connection_pool_config())

    # Add psycopg3 pool options if enabled
    pool_options = get_postgres_pool_options()
    if pool_options:
        config["OPTIONS"].update(pool_options)

    # pgvector support
    if get_env_bool("DB_PGVECTOR_ENABLED", False):
        if "options" not in config["OPTIONS"]:
            config["OPTIONS"]["options"] = "-c search_path=public"

    # Timezone
    db_timezone = os.environ.get("DB_TIME_ZONE")
    if db_timezone:
        config["TIME_ZONE"] = db_timezone

    return config


def get_mysql_config() -> dict[str, Any]:
    """Get MySQL database configuration."""
    config = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "django_matt"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "ATOMIC_REQUESTS": get_env_bool("DB_ATOMIC_REQUESTS", False),
        "AUTOCOMMIT": get_env_bool("DB_AUTOCOMMIT", True),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            **get_env_dict("DB_OPTIONS", {}),
        },
        "TEST": {
            "NAME": os.environ.get("DB_TEST_NAME"),
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }

    # Add connection pooling settings
    config.update(get_connection_pool_config())

    # Timezone
    db_timezone = os.environ.get("DB_TIME_ZONE")
    if db_timezone:
        config["TIME_ZONE"] = db_timezone

    return config


def get_sqlite_config() -> dict[str, Any]:
    """Get SQLite database configuration."""
    db_name = os.environ.get("DB_NAME")
    if db_name is None:
        db_name = str(BASE_DIR / "db.sqlite3")

    config = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": db_name,
        "ATOMIC_REQUESTS": get_env_bool("DB_ATOMIC_REQUESTS", False),
        "AUTOCOMMIT": get_env_bool("DB_AUTOCOMMIT", True),
        "OPTIONS": get_env_dict("DB_OPTIONS", {}),
        "TEST": {
            "NAME": os.environ.get("DB_TEST_NAME"),
        },
    }

    # Add connection pooling settings
    config.update(get_connection_pool_config())

    # Timezone
    db_timezone = os.environ.get("DB_TIME_ZONE")
    if db_timezone:
        config["TIME_ZONE"] = db_timezone

    return config


# Database configuration factory
DB_CONFIG_FACTORIES = {
    "postgres": get_postgres_config,
    "postgresql": get_postgres_config,
    "mysql": get_mysql_config,
    "sqlite": get_sqlite_config,
    "sqlite3": get_sqlite_config,
}


def get_database_config(db_type: str | None = None) -> dict[str, Any]:
    """
    Get database configuration for the specified type.

    Args:
        db_type: Database type (postgres, mysql, sqlite). Defaults to DB_TYPE env var.

    Returns:
        Database configuration dictionary
    """
    db_type = (db_type or DB_TYPE).lower()
    factory = DB_CONFIG_FACTORIES.get(db_type, get_postgres_config)
    return factory()


# Build the main database config
db_config = get_database_config()

# Override engine if explicitly set
if os.environ.get("DB_ENGINE"):
    db_config["ENGINE"] = os.environ.get("DB_ENGINE")


# Database settings to export
settings: dict[str, Any] = {
    "DATABASES": {"default": db_config},
    # Django Matt specific settings
    "DJANGO_MATT_DB_TYPE": DB_TYPE,
    "DJANGO_MATT_DB_POOL_ENABLED": get_env_bool("DB_POOL_ENABLED", False),
    "DJANGO_MATT_DB_PGVECTOR_ENABLED": get_env_bool("DB_PGVECTOR_ENABLED", False),
}

# Add multiple databases if configured
if os.environ.get("DB_MULTIPLE"):
    try:
        multiple_dbs = orjson.loads(os.environ.get("DB_MULTIPLE", "{}"))
        for db_name, db_settings in multiple_dbs.items():
            db_type = db_settings.get("type", "postgres").lower()
            # Set env vars temporarily to build config
            original_env = {}
            for key, value in db_settings.items():
                if key != "type":
                    env_key = f"DB_{key.upper()}"
                    original_env[env_key] = os.environ.get(env_key)
                    os.environ[env_key] = str(value)

            # Build config
            settings["DATABASES"][db_name] = get_database_config(db_type)

            # Restore env vars
            for env_key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(env_key, None)
                else:
                    os.environ[env_key] = original_value
    except orjson.JSONDecodeError:
        pass  # Ignore invalid JSON

# Add database routers if configured
db_routers = os.environ.get("DB_ROUTERS")
if db_routers:
    settings["DATABASE_ROUTERS"] = [r.strip() for r in db_routers.split(",") if r.strip()]


# Convenience functions for users
def configure_database(
    db_type: str = "postgres",
    name: str = "django_matt",
    user: str = "postgres",
    password: str = "",
    host: str = "localhost",
    port: str = "5432",
    conn_max_age: int | None = None,
    conn_health_checks: bool = True,
    pool_enabled: bool = True,
    pool_min_size: int = 5,
    pool_max_size: int = 20,
    **extra_options: Any,
) -> dict[str, Any]:
    """
    Configure database settings programmatically.

    This is a convenience function for users who prefer to configure
    the database in Python code rather than environment variables.

    Args:
        db_type: Database type (postgres, mysql, sqlite)
        name: Database name
        user: Database user
        password: Database password
        host: Database host
        port: Database port
        conn_max_age: Connection max age (None for persistent)
        conn_health_checks: Enable connection health checks (Django 5.1+)
        pool_enabled: Enable connection pooling (Django 5.2+ with psycopg3)
        pool_min_size: Minimum pool size
        pool_max_size: Maximum pool size
        **extra_options: Additional database options

    Returns:
        Database configuration dictionary

    Example:
        from django_matt.config.components.database import configure_database

        DATABASES = {
            "default": configure_database(
                db_type="postgres",
                name="mydb",
                user="myuser",
                password="mypassword",
                host="localhost",
                port="5432",
                pool_enabled=True,
                pool_max_size=30,
            )
        }
    """
    config = {
        "ENGINE": {
            "postgres": "django.db.backends.postgresql",
            "postgresql": "django.db.backends.postgresql",
            "mysql": "django.db.backends.mysql",
            "sqlite": "django.db.backends.sqlite3",
            "sqlite3": "django.db.backends.sqlite3",
        }.get(db_type.lower(), "django.db.backends.postgresql"),
        "NAME": name,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": conn_max_age,
        "OPTIONS": extra_options.get("options", {}),
    }

    # Add health checks for Django 5.1+
    if DJANGO_5_1_PLUS:
        config["CONN_HEALTH_CHECKS"] = conn_health_checks

    # Add pool options for PostgreSQL with Django 5.2+
    if pool_enabled and db_type.lower() in ("postgres", "postgresql") and DJANGO_5_2_PLUS:
        config["OPTIONS"]["pool"] = {
            "min_size": pool_min_size,
            "max_size": pool_max_size,
            "max_idle": extra_options.get("pool_max_idle", 300),
            "max_lifetime": extra_options.get("pool_max_lifetime", 3600),
            "timeout": extra_options.get("pool_timeout", 30),
        }

    # Remove None values
    return {k: v for k, v in config.items() if v is not None}


__all__ = [
    "settings",
    "get_database_config",
    "configure_database",
    "DJANGO_VERSION",
    "DJANGO_5_1_PLUS",
    "DJANGO_5_2_PLUS",
    "DJANGO_6_0_PLUS",
]
