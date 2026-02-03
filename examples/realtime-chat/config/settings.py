"""
Django settings for realtime-chat example.

Demonstrates django-matt WebSocket configuration with Django Channels.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add django-matt to path for development
DJANGO_MATT_PATH = BASE_DIR.parent.parent
if DJANGO_MATT_PATH not in sys.path:
    sys.path.insert(0, str(DJANGO_MATT_PATH))

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv(
    "SECRET_KEY", "django-insecure-example-key-change-in-production"
)

DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


# Application definition
INSTALLED_APPS = [
    # Django apps
    "daphne",  # Must be before django.contrib.staticfiles for ASGI
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "channels",
    # Local apps
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # django-matt JWT middleware (optional - for REST API)
    "django_matt.auth.middleware.JWTAuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ASGI application (for WebSocket support)
ASGI_APPLICATION = "config.asgi.application"

# WSGI application (fallback for HTTP-only)
WSGI_APPLICATION = "config.wsgi.application"


# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")

if DATABASE_URL.startswith("postgres"):
    # Parse PostgreSQL URL
    import re

    match = re.match(
        r"postgres(?:ql)?://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)/(?P<name>.+)",
        DATABASE_URL,
    )
    if match:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": match.group("name"),
                "USER": match.group("user"),
                "PASSWORD": match.group("password"),
                "HOST": match.group("host"),
                "PORT": match.group("port"),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (uploads)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# Django Channels Configuration (WebSockets)
# =============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# Parse Redis URL
import re as re_module

redis_match = re_module.match(
    r"redis://(?:(?P<user>[^:]+):(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)(?:/(?P<db>\d+))?",
    REDIS_URL,
)

if redis_match:
    redis_host = redis_match.group("host")
    redis_port = int(redis_match.group("port"))
else:
    redis_host = "127.0.0.1"
    redis_port = 6379

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(redis_host, redis_port)],
            "capacity": 1500,  # Max number of messages to store
            "expiry": 10,  # Message expiry in seconds
        },
    },
}

# For development without Redis, use in-memory channel layer:
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels.layers.InMemoryChannelLayer"
#     }
# }


# =============================================================================
# django-matt WebSocket Configuration
# =============================================================================

DJANGO_MATT_WEBSOCKETS = {
    "ENABLED": True,
    "AUTH_REQUIRED": False,  # Allow anonymous connections, auth happens in consumer
    "HEARTBEAT_INTERVAL": int(os.getenv("WS_HEARTBEAT_INTERVAL", 30)),
    "GROUP_PREFIX": "chat_",  # Prefix for channel groups
    "MAX_GROUPS_PER_USER": 50,  # Max channels a user can join
    "RATE_LIMIT": {
        "ENABLED": True,
        "MESSAGES_PER_SECOND": int(
            os.getenv("WS_RATE_LIMIT_MESSAGES_PER_SECOND", 10)
        ),
        "BURST_SIZE": 20,
    },
}


# =============================================================================
# django-matt JWT Configuration
# =============================================================================

DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", 60))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_LIFETIME_DAYS", 7))
    ),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "sub",
}


# =============================================================================
# Cache Configuration (for presence tracking)
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# For development without Redis:
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
#     }
# }


# =============================================================================
# File Upload Settings
# =============================================================================

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", 10)) * 1024 * 1024  # 10MB default

ALLOWED_UPLOAD_TYPES = os.getenv(
    "ALLOWED_UPLOAD_TYPES",
    "image/png,image/jpeg,image/gif,application/pdf,text/plain",
).split(",")


# =============================================================================
# Logging Configuration
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "chat": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "django_matt.websockets": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
