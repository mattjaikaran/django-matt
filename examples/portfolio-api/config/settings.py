import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_matt",
    "apps.core",
    "apps.users",
    "apps.projects",
    "apps.skills",
    "apps.experience",
    "apps.contact",
    "apps.site_config",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_matt.core.errors.ErrorMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "frontend_dist"],
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

ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# Database — SQLite by default, PostgreSQL via DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": DATABASE_URL.split("/")[-1].split("?")[0],
            "USER": DATABASE_URL.split("://")[1].split(":")[0],
            "PASSWORD": DATABASE_URL.split(":")[2].split("@")[0],
            "HOST": DATABASE_URL.split("@")[1].split(":")[0],
            "PORT": DATABASE_URL.split(":")[-1].split("/")[0],
        }
    }
else:
    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "db.sqlite3"))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DB_PATH,
        }
    }

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files — Django admin CSS/JS
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# WhiteNoise serves the built frontend from root (/assets/..., /index.html, etc.)
WHITENOISE_ROOT = BASE_DIR / "frontend_dist"
WHITENOISE_INDEX_FILE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

APPEND_SLASH = False

# django-matt config
DJANGO_MATT = {
    "API_TITLE": "Portfolio API",
    "API_VERSION": "1.0.0",
    "API_DESCRIPTION": "Personal portfolio backend built with django-matt",
    "DOCS_URL": "/api/docs",
    "REDOC_URL": "/api/redoc",
    "OPENAPI_URL": "/api/openapi.json",
}

# Resend — contact form email notifications
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
CONTACT_TO_EMAIL = os.getenv("CONTACT_TO_EMAIL", "hello@example.dev")
CONTACT_FROM_EMAIL = os.getenv("CONTACT_FROM_EMAIL", "portfolio@example.dev")

DJANGO_MATT_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_NAME": "Authorization",
    "AUTH_HEADER_PREFIX": "Bearer",
}
