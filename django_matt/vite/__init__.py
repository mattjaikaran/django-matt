"""
Django Matt Vite Integration.

First-class Vite support for Django, closing the #1 cited DX gap vs
Rails (Vite Ruby) and Laravel (Vite Plugin).

Quick Start:
    # settings.py
    MATT_VITE = {
        "DEV_SERVER_URL": "http://localhost:5173",
        "BUILD_DIR": "static/dist",
        "MANIFEST_PATH": "static/dist/.vite/manifest.json",
        "ENTRY_POINTS": ["src/main.js"],
        "HMR_ENABLED": True,
        "REACT_REFRESH": False,
    }

    MIDDLEWARE = [
        ...
        'django_matt.vite.ViteDevMiddleware',
    ]

    # templates/base.html
    {% load vite %}
    <html>
    <head>
        {% vite_hmr_client %}
        {% vite_react_refresh %}
        {% vite_asset "src/main.js" %}
    </head>
    <body>...</body>
    </html>

Management Commands:
    python manage.py vite_dev    # Start Vite + Django together
    python manage.py vite_build  # Production build
"""

from django_matt.vite.config import (
    ViteConfig,
    get_vite_config,
    reset_vite_config,
)
from django_matt.vite.manifest import (
    ManifestEntry,
    ViteManifest,
    get_manifest,
    reset_manifest,
)
from django_matt.vite.middleware import (
    AsyncViteDevMiddleware,
    ViteDevMiddleware,
)

__all__ = [
    # Config
    "ViteConfig",
    "get_vite_config",
    "reset_vite_config",
    # Manifest
    "ViteManifest",
    "ManifestEntry",
    "get_manifest",
    "reset_manifest",
    # Middleware
    "ViteDevMiddleware",
    "AsyncViteDevMiddleware",
]
