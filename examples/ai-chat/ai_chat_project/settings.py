"""
AI Chat Example — Django settings.

Demonstrates: SSE streaming, CQRS command/query buses, event bus, AI/LLM integration.
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
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "ai_chat_project.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# django-matt configuration
MATT_API = {
    "TITLE": "AI Chat API",
    "VERSION": "1.0.0",
    "DESCRIPTION": "AI-powered chat with SSE streaming and CQRS",
}

# LLM configuration — set your provider API key
MATT_AI = {
    "DEFAULT_PROVIDER": os.environ.get("AI_PROVIDER", "openai"),
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
    "DEFAULT_MODEL": os.environ.get("AI_MODEL", "gpt-4o-mini"),
}
