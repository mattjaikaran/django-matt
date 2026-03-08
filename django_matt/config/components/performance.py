"""
Performance settings for Django Matt applications.

This module contains settings for optimizing performance.
"""

import logging
import os

logger = logging.getLogger("django_matt")

# API mode settings
# Set MATT_API_MODE=True in your Django settings to strip browser-oriented
# middleware and optimize for pure API usage.
MATT_API_MODE: bool = False

# Middleware to remove when MATT_API_MODE is True.
# These are browser-oriented middleware not needed in API-only projects.
MIDDLEWARE_STRIP_LIST: list[str] = [
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Middleware that must always remain active even when MATT_API_MODE is True.
# These provide essential security and HTTP compliance for all projects.
MIDDLEWARE_KEEP_LIST: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]


def apply_api_mode(middleware_list: list[str]) -> list[str]:
    """
    Strip browser-oriented middleware from the given middleware list.

    Removes any middleware whose dotted path appears in MIDDLEWARE_STRIP_LIST.
    Never removes middleware in MIDDLEWARE_KEEP_LIST even if it were accidentally
    added to the strip list.

    Logs stripped and remaining middleware at INFO level via 'django_matt' logger.

    Args:
        middleware_list: The current MIDDLEWARE list to filter.

    Returns:
        A new list with browser-oriented middleware removed.
    """
    stripped = []
    kept = []

    for mw in middleware_list:
        # Never strip protected middleware
        if mw in MIDDLEWARE_KEEP_LIST:
            kept.append(mw)
        elif mw in MIDDLEWARE_STRIP_LIST:
            stripped.append(mw)
        else:
            kept.append(mw)

    if stripped:
        logger.info(
            "MATT_API_MODE: stripped %d browser-oriented middleware: %s",
            len(stripped),
            ", ".join(stripped),
        )
    else:
        logger.warning(
            "MATT_API_MODE is True but no strippable middleware found in MIDDLEWARE setting. "
            "Nothing was removed. Strippable list: %s",
            ", ".join(MIDDLEWARE_STRIP_LIST),
        )

    logger.info(
        "MATT_API_MODE: active middleware (%d): %s",
        len(kept),
        ", ".join(kept) if kept else "(none)",
    )

    return kept


# Performance settings
settings = {
    # Django Matt performance settings
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": os.environ.get("DJANGO_MATT_BENCHMARK_ENABLED", "False").lower()
        == "true",
        "BENCHMARK_HEADER": os.environ.get("DJANGO_MATT_BENCHMARK_HEADER", "X-Django-Matt-Timing"),
    },
    # Django optimization settings
    "DATA_UPLOAD_MAX_MEMORY_SIZE": int(
        os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", 2621440)
    ),  # 2.5 MB
    "FILE_UPLOAD_MAX_MEMORY_SIZE": int(
        os.environ.get("FILE_UPLOAD_MAX_MEMORY_SIZE", 2621440)
    ),  # 2.5 MB
    "DATA_UPLOAD_MAX_NUMBER_FIELDS": int(os.environ.get("DATA_UPLOAD_MAX_NUMBER_FIELDS", 1000)),
    # Template caching
    "TEMPLATES": [
        {
            "OPTIONS": {
                "loaders": [
                    (
                        "django.template.loaders.cached.Loader",
                        [
                            "django.template.loaders.filesystem.Loader",
                            "django.template.loaders.app_directories.Loader",
                        ],
                    ),
                ],
            },
        },
    ],
    # Static files settings
    "STATICFILES_STORAGE": os.environ.get(
        "STATICFILES_STORAGE",
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    ),
    # Middleware for performance
    "MIDDLEWARE": [
        "django.middleware.gzip.GZipMiddleware",
        "django.middleware.http.ConditionalGetMiddleware",
    ],
}
