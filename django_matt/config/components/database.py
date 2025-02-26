"""
Database settings for Django Matt applications.

This module contains settings for configuring the database connection.
Django Matt provides first-class support for PostgreSQL, including pgvector,
while also supporting MySQL and SQLite with easy configuration.
"""

import json
import os
from pathlib import Path

from django_matt.config.utils import get_env_bool, get_env_dict, get_env_int

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Detect database type from environment
DB_TYPE = os.environ.get("DB_TYPE", "postgres").lower()

# Default database configurations
DB_CONFIGS = {
    "postgres": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "django_matt"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": get_env_int("DB_CONN_MAX_AGE", 600),
        "OPTIONS": get_env_dict("DB_OPTIONS", {}),
        "ATOMIC_REQUESTS": get_env_bool("DB_ATOMIC_REQUESTS", False),
        "AUTOCOMMIT": get_env_bool("DB_AUTOCOMMIT", True),
        "TIME_ZONE": os.environ.get("DB_TIME_ZONE", None),
        "TEST": {
            "NAME": os.environ.get("DB_TEST_NAME", None),
        },
    },
    "mysql": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "django_matt"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "CONN_MAX_AGE": get_env_int("DB_CONN_MAX_AGE", 600),
        "OPTIONS": {
            "charset": "utf8mb4",
            **(get_env_dict("DB_OPTIONS", {})),
        },
        "ATOMIC_REQUESTS": get_env_bool("DB_ATOMIC_REQUESTS", False),
        "AUTOCOMMIT": get_env_bool("DB_AUTOCOMMIT", True),
        "TIME_ZONE": os.environ.get("DB_TIME_ZONE", None),
        "TEST": {
            "NAME": os.environ.get("DB_TEST_NAME", None),
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    },
    "sqlite": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DB_NAME", os.path.join(BASE_DIR, "db.sqlite3")),
        "CONN_MAX_AGE": get_env_int("DB_CONN_MAX_AGE", 600),
        "OPTIONS": get_env_dict("DB_OPTIONS", {}),
        "ATOMIC_REQUESTS": get_env_bool("DB_ATOMIC_REQUESTS", False),
        "AUTOCOMMIT": get_env_bool("DB_AUTOCOMMIT", True),
        "TIME_ZONE": os.environ.get("DB_TIME_ZONE", None),
        "TEST": {
            "NAME": os.environ.get("DB_TEST_NAME", None),
        },
    },
}

# Get the database configuration based on DB_TYPE
db_config = DB_CONFIGS.get(DB_TYPE, DB_CONFIGS["postgres"])

# Override with custom engine if provided
if os.environ.get("DB_ENGINE"):
    db_config["ENGINE"] = os.environ.get("DB_ENGINE")

# PostgreSQL specific settings
if DB_TYPE == "postgres":
    # Check if pgvector is enabled
    if get_env_bool("DB_PGVECTOR_ENABLED", False):
        # Add pgvector extension to PostgreSQL
        if "OPTIONS" not in db_config:
            db_config["OPTIONS"] = {}

        # Add the CREATE EXTENSION statement for pgvector
        if "options" not in db_config["OPTIONS"]:
            db_config["OPTIONS"]["options"] = "-c search_path=public"

        # Add pgvector to installed apps if not already there
        INSTALLED_APPS = ["pgvector"]

    # Connection pooling settings for PostgreSQL
    DB_POOL_ENABLED = get_env_bool("DB_POOL_ENABLED", False)
    if DB_POOL_ENABLED:
        db_config["ENGINE"] = "django_postgres_pooling.backends.postgresql"
        db_config["POOL_OPTIONS"] = {
            "MAX_CONNS": get_env_int("DB_POOL_MAX_CONNS", 20),
            "MIN_CONNS": get_env_int("DB_POOL_MIN_CONNS", 5),
            "MAX_IDLE": get_env_int("DB_POOL_MAX_IDLE", 300),  # seconds
        }

# Database settings
settings = {
    "DATABASES": {"default": db_config},
    # Database connection pooling (if using PostgreSQL)
    "DB_POOL_OPTIONS": {
        "MAX_CONNS": get_env_int("DB_POOL_MAX_CONNS", 20),
        "MIN_CONNS": get_env_int("DB_POOL_MIN_CONNS", 5),
        "MAX_IDLE": get_env_int("DB_POOL_MAX_IDLE", 300),  # seconds
    },
    # Database type
    "DB_TYPE": DB_TYPE,
    # pgvector support
    "DB_PGVECTOR_ENABLED": get_env_bool("DB_PGVECTOR_ENABLED", False),
}

# Add multiple databases if configured
if os.environ.get("DB_MULTIPLE"):
    try:
        multiple_dbs = json.loads(os.environ.get("DB_MULTIPLE", "{}"))
        for db_name, db_settings in multiple_dbs.items():
            db_type = db_settings.get("type", "postgres").lower()
            base_config = DB_CONFIGS.get(db_type, DB_CONFIGS["postgres"]).copy()

            # Override with provided settings
            for key, value in db_settings.items():
                if key != "type":
                    base_config[key.upper()] = value

            settings["DATABASES"][db_name] = base_config
    except json.JSONDecodeError:
        pass  # Ignore invalid JSON

# Add database routers if configured
if os.environ.get("DB_ROUTERS"):
    settings["DATABASE_ROUTERS"] = os.environ.get("DB_ROUTERS", "").split(",")
