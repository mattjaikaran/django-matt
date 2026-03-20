"""
Common settings for Django Matt applications.

These settings are shared across all environments (dev, staging, prod).
Environment-specific settings should override these in their respective files.

Usage:
    # In your project's settings.py
    from django_matt.config.settings.common import *

    # Or import the settings dict
    from django_matt.config.settings.common import settings
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Django version detection
import django

DJANGO_VERSION = tuple(map(int, django.__version__.split(".")[:2]))
DJANGO_5_2_PLUS = DJANGO_VERSION >= (5, 2)
DJANGO_6_0_PLUS = DJANGO_VERSION >= (6, 0)

# Build paths inside the project
# This will be overridden by the user's project
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


# Common settings dictionary
settings: dict[str, Any] = {
    # ==========================================================================
    # Core Django Settings
    # ==========================================================================
    "DEBUG": False,  # Always False by default, override in dev.py
    "SECRET_KEY": os.environ.get("DJANGO_SECRET_KEY"),  # Must be set
    "ALLOWED_HOSTS": [],
    "ROOT_URLCONF": None,  # Must be set in project
    "WSGI_APPLICATION": None,  # Must be set in project
    "ASGI_APPLICATION": None,  # For async support
    # ==========================================================================
    # Application Definition
    # ==========================================================================
    "INSTALLED_APPS": [
        # Django core apps
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        # Django Matt is added automatically when using configure()
    ],
    # ==========================================================================
    # Middleware
    # ==========================================================================
    "MIDDLEWARE": [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ],
    # ==========================================================================
    # Templates
    # ==========================================================================
    "TEMPLATES": [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
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
    ],
    # ==========================================================================
    # Internationalization
    # ==========================================================================
    "LANGUAGE_CODE": "en-us",
    "TIME_ZONE": "UTC",
    "USE_I18N": True,
    "USE_TZ": True,
    # ==========================================================================
    # Static & Media Files
    # ==========================================================================
    "STATIC_URL": "static/",
    "STATIC_ROOT": str(BASE_DIR / "staticfiles"),
    "STATICFILES_DIRS": [],
    "MEDIA_URL": "media/",
    "MEDIA_ROOT": str(BASE_DIR / "media"),
    # ==========================================================================
    # Database
    # ==========================================================================
    # Default to SQLite for simplicity - override in environment files
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    },
    # ==========================================================================
    # Authentication & Authorization
    # ==========================================================================
    "AUTH_PASSWORD_VALIDATORS": [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ],
    # ==========================================================================
    # Default Primary Key
    # ==========================================================================
    "DEFAULT_AUTO_FIELD": "django.db.models.BigAutoField",
    # ==========================================================================
    # Django Matt Settings
    # ==========================================================================
    "DJANGO_MATT": {
        "VERSION": "0.1.0",
        # Performance settings
        "BENCHMARK_ENABLED": False,
        "BENCHMARK_HEADER": "X-Django-Matt-Timing",
        # Caching
        "CACHE_ENABLED": False,
        "CACHE_TIMEOUT": 300,  # 5 minutes
        "CACHE_KEY_PREFIX": "django_matt:",
        # Database
        "DB_TYPE": os.environ.get("DB_TYPE", "postgres"),
        "DB_POOL_ENABLED": False,
        # Query optimization
        "QUERY_OPTIMIZATION_ENABLED": True,
        "N1_DETECTION_ENABLED": True,
        # API serialization
        "CAMEL_CASE_API": False,  # When True, API responses use camelCase field names
    },
}


# ==========================================================================
# Export individual settings for `from common import *` usage
# ==========================================================================
DEBUG = settings["DEBUG"]
SECRET_KEY = settings["SECRET_KEY"]
ALLOWED_HOSTS = settings["ALLOWED_HOSTS"]
INSTALLED_APPS = settings["INSTALLED_APPS"]
MIDDLEWARE = settings["MIDDLEWARE"]
ROOT_URLCONF = settings["ROOT_URLCONF"]
TEMPLATES = settings["TEMPLATES"]
WSGI_APPLICATION = settings["WSGI_APPLICATION"]
DATABASES = settings["DATABASES"]
AUTH_PASSWORD_VALIDATORS = settings["AUTH_PASSWORD_VALIDATORS"]
LANGUAGE_CODE = settings["LANGUAGE_CODE"]
TIME_ZONE = settings["TIME_ZONE"]
USE_I18N = settings["USE_I18N"]
USE_TZ = settings["USE_TZ"]
STATIC_URL = settings["STATIC_URL"]
STATIC_ROOT = settings["STATIC_ROOT"]
STATICFILES_DIRS = settings["STATICFILES_DIRS"]
MEDIA_URL = settings["MEDIA_URL"]
MEDIA_ROOT = settings["MEDIA_ROOT"]
DEFAULT_AUTO_FIELD = settings["DEFAULT_AUTO_FIELD"]
DJANGO_MATT = settings["DJANGO_MATT"]


__all__ = [
    "settings",
    "BASE_DIR",
    "DJANGO_VERSION",
    "DJANGO_5_2_PLUS",
    "DJANGO_6_0_PLUS",
    # Individual settings
    "DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "INSTALLED_APPS",
    "MIDDLEWARE",
    "ROOT_URLCONF",
    "TEMPLATES",
    "WSGI_APPLICATION",
    "DATABASES",
    "AUTH_PASSWORD_VALIDATORS",
    "LANGUAGE_CODE",
    "TIME_ZONE",
    "USE_I18N",
    "USE_TZ",
    "STATIC_URL",
    "STATIC_ROOT",
    "STATICFILES_DIRS",
    "MEDIA_URL",
    "MEDIA_ROOT",
    "DEFAULT_AUTO_FIELD",
    "DJANGO_MATT",
]
