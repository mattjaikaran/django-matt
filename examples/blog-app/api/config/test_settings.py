from config.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable GinIndex on SQLite (postgres-only)
# Tests that use postgres-specific features should be skipped in CI without postgres
