"""
Vite dev server middleware.

Injects the Vite HMR client into HTML responses during development,
enabling hot module replacement without manual script tags.
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Callable
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from django_matt.vite.config import ViteConfig, get_vite_config

logger = logging.getLogger("django_matt.vite")


def _is_vite_reachable(url: str, timeout: float = 0.3) -> bool:
    """Check if the Vite dev server is reachable."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5173
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ViteDevMiddleware:
    """
    Middleware that injects the Vite HMR client into HTML responses.

    Only active when DEBUG=True and the Vite dev server is reachable.
    Injects the HMR client script before </head> in HTML responses.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.vite.ViteDevMiddleware',
        ]

        MATT_VITE = {
            "DEV_SERVER_URL": "http://localhost:5173",
            "HMR_ENABLED": True,
            "REACT_REFRESH": False,
        }
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._vite_available: bool | None = None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        if not getattr(settings, "DEBUG", False):
            return response

        config = get_vite_config()
        if not config.hmr_enabled:
            return response

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        # Check Vite reachability (cache per-request cycle to avoid
        # hammering the socket on every middleware call)
        if self._vite_available is None:
            self._vite_available = _is_vite_reachable(config.dev_server_url)

        if not self._vite_available:
            return response

        _inject_hmr_into_response(response, config)
        return response


class AsyncViteDevMiddleware:
    """
    Async version of ViteDevMiddleware.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.vite.AsyncViteDevMiddleware',
        ]
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._vite_available: bool | None = None

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        response = await self.get_response(request)

        if not getattr(settings, "DEBUG", False):
            return response

        config = get_vite_config()
        if not config.hmr_enabled:
            return response

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        if self._vite_available is None:
            self._vite_available = _is_vite_reachable(config.dev_server_url)

        if not self._vite_available:
            return response

        _inject_hmr_into_response(response, config)
        return response


def _inject_hmr_into_response(response: HttpResponse, config: ViteConfig) -> None:
    """Shared injection logic for sync and async middleware."""
    content = response.content.decode(response.charset)
    dev_url = config.dev_server_url.rstrip("/")

    parts: list[str] = []
    if config.react_refresh:
        parts.append(
            f'<script type="module">\n'
            f'  import RefreshRuntime from "{dev_url}/@react-refresh";\n'
            f"  RefreshRuntime.injectIntoGlobalHook(window);\n"
            f"  window.$RefreshReg$ = () => {{}};\n"
            f"  window.$RefreshSig$ = () => (type) => type;\n"
            f"  window.__vite_plugin_react_preamble_installed__ = true;\n"
            f"</script>"
        )
    parts.append(f'<script type="module" src="{dev_url}/@vite/client"></script>')
    inject_scripts = "\n".join(parts)

    if "</head>" in content:
        content = content.replace("</head>", f"{inject_scripts}</head>")
    elif "<body" in content:
        idx = content.index("<body")
        end = content.index(">", idx)
        content = content[: end + 1] + inject_scripts + content[end + 1 :]
    else:
        return

    response.content = content.encode(response.charset)
    response["Content-Length"] = len(response.content)


__all__ = [
    "AsyncViteDevMiddleware",
    "ViteDevMiddleware",
]
