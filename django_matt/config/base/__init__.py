"""
Base settings for Django Matt applications.

This module contains settings that are common to all environments.
"""

import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Default settings dictionary
settings = {
    # Core Django settings
    "DEBUG": False,
    "SECRET_KEY": None,  # Must be set in environment settings
    "ALLOWED_HOSTS": [],
    "ROOT_URLCONF": None,  # Must be set in project settings
    "WSGI_APPLICATION": None,  # Must be set in project settings
    # Application definition
    "INSTALLED_APPS": [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ],
    # Middleware
    "MIDDLEWARE": [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ],
    # Templates
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
    # Internationalization
    "LANGUAGE_CODE": "en-us",
    "TIME_ZONE": "UTC",
    "USE_I18N": True,
    "USE_TZ": True,
    # Static files (CSS, JavaScript, Images)
    "STATIC_URL": "static/",
    "STATIC_ROOT": os.path.join(BASE_DIR, "staticfiles"),
    "STATICFILES_DIRS": [
        os.path.join(BASE_DIR, "static"),
    ],
    # Media files
    "MEDIA_URL": "media/",
    "MEDIA_ROOT": os.path.join(BASE_DIR, "media"),
    # Default primary key field type
    "DEFAULT_AUTO_FIELD": "django.db.models.BigAutoField",
    # Django Matt specific settings
    "DJANGO_MATT": {
        "VERSION": "0.1.0",
        "BENCHMARK_ENABLED": False,
        "BENCHMARK_HEADER": "X-Django-Matt-Timing",
        "CACHE_ENABLED": False,
        "CACHE_TIMEOUT": 300,  # 5 minutes
        "CACHE_KEY_PREFIX": "django_matt:",
    },
}
