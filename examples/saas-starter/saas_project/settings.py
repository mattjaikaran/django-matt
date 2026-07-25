"""
Django settings for SaaS Starter project.

A comprehensive example application showcasing django-matt features:
- Multi-tenancy with organizations
- JWT + OAuth authentication
- Stripe billing integration
- WebSocket for real-time updates
- Feature flags for gradual rollout
- Background tasks with Celery
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-saas-starter-example-change-in-production"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Application definition
INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "channels",
    # Django Matt modules — this example defines its own Organization/Membership
    # models in core.models, so we don't install django_matt.multitenancy.
    "django_matt",
    "django_matt.billing",
    "django_matt.flags",
    # Project apps
    "core.apps.CoreConfig",
    "projects.apps.ProjectsConfig",
    "billing.apps.BillingConfig",
    "notifications.apps.NotificationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Django Matt middleware
    "django_matt.flags.FlagMiddleware",
    "django_matt.negotiation.ContentNegotiationMiddleware",
]

ROOT_URLCONF = "saas_project.urls"

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

WSGI_APPLICATION = "saas_project.wsgi.application"
ASGI_APPLICATION = "saas_project.asgi.application"

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "saas_starter"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Use SQLite for local development if PostgreSQL is not available
if os.environ.get("USE_SQLITE", "False").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Custom User Model
AUTH_USER_MODEL = "core.User"

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
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Django Matt Configuration
# =============================================================================

# JWT Authentication
MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": 60 * 15,  # 15 minutes
    "REFRESH_TOKEN_LIFETIME": 60 * 60 * 24 * 7,  # 7 days
    "SECRET_KEY": os.environ.get("JWT_SECRET_KEY", SECRET_KEY),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_PREFIX": "Bearer",
}

# OAuth Providers
MATT_OAUTH = {
    "GOOGLE": {
        "CLIENT_ID": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "CLIENT_SECRET": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "REDIRECT_URI": os.environ.get(
            "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/oauth/google/callback"
        ),
    },
    "GITHUB": {
        "CLIENT_ID": os.environ.get("GITHUB_CLIENT_ID", ""),
        "CLIENT_SECRET": os.environ.get("GITHUB_CLIENT_SECRET", ""),
        "REDIRECT_URI": os.environ.get(
            "GITHUB_REDIRECT_URI", "http://localhost:8000/api/auth/oauth/github/callback"
        ),
    },
}

# Magic Link Authentication
MATT_MAGIC_LINK = {
    "TOKEN_LIFETIME": 60 * 15,  # 15 minutes
    "FROM_EMAIL": os.environ.get("FROM_EMAIL", "noreply@saas-starter.local"),
}

# Feature Flags
FEATURE_FLAG_BACKEND = os.environ.get("FEATURE_FLAG_BACKEND", "database")
FEATURE_FLAG_CACHE_TIMEOUT = 60  # seconds

# Multi-tenancy
MATT_MULTITENANCY = {
    "TENANT_MODEL": "multitenancy.Organization",
    "AUTO_CREATE_PERSONAL_ORG": True,
    "MAX_TEAMS_PER_ORG": 10,
    "MAX_MEMBERS_PER_TEAM": 50,
}

# =============================================================================
# Redis / Channels Configuration
# =============================================================================

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# =============================================================================
# Celery Configuration
# =============================================================================

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# =============================================================================
# Stripe Configuration
# =============================================================================

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Billing products (defined in Stripe)
BILLING_PRODUCTS = {
    "free": {
        "name": "Free",
        "price_id": os.environ.get("STRIPE_FREE_PRICE_ID", ""),
        "limits": {
            "projects": 3,
            "members_per_org": 5,
            "storage_gb": 1,
        },
    },
    "pro": {
        "name": "Pro",
        "price_id": os.environ.get("STRIPE_PRO_PRICE_ID", ""),
        "limits": {
            "projects": 50,
            "members_per_org": 25,
            "storage_gb": 50,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "price_id": os.environ.get("STRIPE_ENTERPRISE_PRICE_ID", ""),
        "limits": {
            "projects": -1,  # unlimited
            "members_per_org": -1,  # unlimited
            "storage_gb": 500,
        },
    },
}

# =============================================================================
# Email Configuration
# =============================================================================

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@saas-starter.local")

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
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django_matt": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# =============================================================================
# Security Settings (for production)
# =============================================================================

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# =============================================================================
# CORS Configuration (for frontend)
# =============================================================================

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

CORS_ALLOW_CREDENTIALS = True
