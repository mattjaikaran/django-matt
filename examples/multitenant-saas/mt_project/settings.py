"""
Multi-tenant SaaS Example — Django settings.

Demonstrates: multi-tenancy, feature flags, event bus, interceptors.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "example-secret-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "tenants",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "mt_project.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MATT_API = {
    "TITLE": "Multi-tenant SaaS API",
    "VERSION": "1.0.0",
}

# Feature flags config — using DB backend for this example
MATT_FLAGS = {
    "BACKEND": "database",
}
