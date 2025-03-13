"""
Performance settings for Django Matt applications.

This module contains settings for optimizing performance.
"""

import os

# Performance settings
settings = {
    # Django Matt performance settings
    "DJANGO_MATT": {
        "BENCHMARK_ENABLED": os.environ.get(
            "DJANGO_MATT_BENCHMARK_ENABLED", "False"
        ).lower()
        == "true",
        "BENCHMARK_HEADER": os.environ.get(
            "DJANGO_MATT_BENCHMARK_HEADER", "X-Django-Matt-Timing"
        ),
    },
    # Django optimization settings
    "DATA_UPLOAD_MAX_MEMORY_SIZE": int(
        os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", 2621440)
    ),  # 2.5 MB
    "FILE_UPLOAD_MAX_MEMORY_SIZE": int(
        os.environ.get("FILE_UPLOAD_MAX_MEMORY_SIZE", 2621440)
    ),  # 2.5 MB
    "DATA_UPLOAD_MAX_NUMBER_FIELDS": int(
        os.environ.get("DATA_UPLOAD_MAX_NUMBER_FIELDS", 1000)
    ),
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
