"""
Inertia.js middleware.

Handles the Inertia protocol: version checking, redirect conversion,
and partial reload headers.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from django_matt.inertia.config import get_inertia_config


def _resolve_version() -> str:
    """Return the current asset version string."""
    config = get_inertia_config()
    version = config.version
    if version is None:
        return ""
    if callable(version):
        return str(version())
    return str(version)


class InertiaMiddleware:
    """Synchronous Inertia middleware.

    Responsibilities:
    - Detect ``X-Inertia`` header and annotate the request.
    - On version mismatch: respond with 409 + ``X-Inertia-Location``.
    - Convert 302 redirects to 303 for PUT/PATCH/DELETE (Inertia spec).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request._inertia = request.headers.get("X-Inertia") == "true"
        if not hasattr(request, "_inertia_shared"):
            request._inertia_shared = {}

        response = self.get_response(request)
        return self._process_response(request, response)

    def _process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        is_inertia = getattr(request, "_inertia", False)
        if not is_inertia:
            return response

        # Version conflict detection (GET only)
        if request.method == "GET":
            request_version = request.headers.get("X-Inertia-Version", "")
            current_version = _resolve_version()
            if current_version and request_version != current_version:
                conflict = HttpResponse(status=409)
                conflict["X-Inertia-Location"] = request.get_full_path()
                return conflict

        # Convert 302 to 303 for non-GET methods (Inertia spec)
        if response.status_code == 302 and request.method in ("PUT", "PATCH", "DELETE"):
            response.status_code = 303

        return response


class AsyncInertiaMiddleware:
    """Async-compatible Inertia middleware.

    Same behaviour as :class:`InertiaMiddleware` but works under ASGI.
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        request._inertia = request.headers.get("X-Inertia") == "true"
        if not hasattr(request, "_inertia_shared"):
            request._inertia_shared = {}

        response = await self.get_response(request)

        is_inertia = getattr(request, "_inertia", False)
        if not is_inertia:
            return response

        # Version conflict (GET only)
        if request.method == "GET":
            request_version = request.headers.get("X-Inertia-Version", "")
            current_version = _resolve_version()
            if current_version and request_version != current_version:
                conflict = HttpResponse(status=409)
                conflict["X-Inertia-Location"] = request.get_full_path()
                return conflict

        # 302 → 303 for PUT/PATCH/DELETE
        if response.status_code == 302 and request.method in ("PUT", "PATCH", "DELETE"):
            response.status_code = 303

        return response


__all__ = [
    "AsyncInertiaMiddleware",
    "InertiaMiddleware",
]
