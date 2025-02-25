"""
Database settings for Django Matt applications.

This module contains settings for configuring the database connection.
"""

import os
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Database settings
settings = {
    "DATABASES": {
        "default": {
            "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.environ.get("DB_NAME", os.path.join(BASE_DIR, "db.sqlite3")),
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", ""),
            "PORT": os.environ.get("DB_PORT", ""),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", 600)),
            "OPTIONS": {},
        }
    },
    # Database connection pooling (if using PostgreSQL)
    "DB_POOL_OPTIONS": {
        "MAX_CONNS": int(os.environ.get("DB_POOL_MAX_CONNS", 20)),
        "MIN_CONNS": int(os.environ.get("DB_POOL_MIN_CONNS", 5)),
        "MAX_IDLE": int(os.environ.get("DB_POOL_MAX_IDLE", 300)),  # seconds
    },
}
