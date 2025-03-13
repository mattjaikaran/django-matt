"""
Security settings for Django Matt applications.

This module contains settings for enhancing security.
"""

import os

# Security settings
settings = {
    # CSRF settings
    "CSRF_COOKIE_SECURE": os.environ.get("CSRF_COOKIE_SECURE", "False").lower()
    == "true",
    "CSRF_COOKIE_HTTPONLY": True,
    "CSRF_COOKIE_SAMESITE": "Lax",
    "CSRF_TRUSTED_ORIGINS": os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(","),
    # Session settings
    "SESSION_COOKIE_SECURE": os.environ.get("SESSION_COOKIE_SECURE", "False").lower()
    == "true",
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": "Lax",
    "SESSION_ENGINE": os.environ.get(
        "SESSION_ENGINE", "django.contrib.sessions.backends.db"
    ),
    "SESSION_COOKIE_AGE": int(os.environ.get("SESSION_COOKIE_AGE", 1209600)),  # 2 weeks
    # Security middleware settings
    "SECURE_BROWSER_XSS_FILTER": True,
    "SECURE_CONTENT_TYPE_NOSNIFF": True,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": os.environ.get(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", "False"
    ).lower()
    == "true",
    "SECURE_HSTS_PRELOAD": os.environ.get("SECURE_HSTS_PRELOAD", "False").lower()
    == "true",
    "SECURE_HSTS_SECONDS": int(os.environ.get("SECURE_HSTS_SECONDS", 0)),
    "SECURE_SSL_REDIRECT": os.environ.get("SECURE_SSL_REDIRECT", "False").lower()
    == "true",
    "SECURE_PROXY_SSL_HEADER": (
        ("HTTP_X_FORWARDED_PROTO", "https")
        if os.environ.get("SECURE_PROXY_SSL_HEADER", "False").lower() == "true"
        else None
    ),
    # Content Security Policy
    "CSP_DEFAULT_SRC": ("'self'",),
    "CSP_STYLE_SRC": ("'self'", "'unsafe-inline'"),
    "CSP_SCRIPT_SRC": ("'self'", "'unsafe-inline'", "'unsafe-eval'"),
    "CSP_IMG_SRC": ("'self'", "data:", "*.googleapis.com", "*.gstatic.com"),
    "CSP_FONT_SRC": ("'self'", "data:", "*.googleapis.com", "*.gstatic.com"),
    "CSP_CONNECT_SRC": ("'self'",),
    "CSP_FRAME_SRC": ("'self'",),
    # Password validation
    "AUTH_PASSWORD_VALIDATORS": [
        {
            "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {
                "min_length": int(os.environ.get("PASSWORD_MIN_LENGTH", 8)),
            },
        },
        {
            "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
        },
    ],
    # Rate limiting
    "RATELIMIT_ENABLE": os.environ.get("RATELIMIT_ENABLE", "True").lower() == "true",
    "RATELIMIT_USE_CACHE": os.environ.get("RATELIMIT_USE_CACHE", "default"),
    "RATELIMIT_VIEW": os.environ.get("RATELIMIT_VIEW", "django_matt.views.ratelimited"),
    "RATELIMIT_FAIL_OPEN": os.environ.get("RATELIMIT_FAIL_OPEN", "False").lower()
    == "true",
}
