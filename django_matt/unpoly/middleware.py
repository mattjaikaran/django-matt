"""
Unpoly middleware.

Provides middleware for automatic Unpoly request detection, response
header management, version mismatch handling, and redirect preservation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

import orjson

from django_matt.unpoly.config import get_unpoly_config
from django_matt.unpoly.request import UnpolyDetails


class UnpolyMiddleware:
    """
    Middleware that adds Unpoly details to requests and manages response headers.

    Adds `request.up` attribute with UnpolyDetails instance.

    Handles:
    - Parsing X-Up-* request headers into request.up
    - Setting X-Up-Location and X-Up-Method on responses
    - Version mismatch detection (sends up:fragment:expired event)
    - Preserving Unpoly headers through redirect chains
    - Adding Vary: X-Up-Target for proper caching

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.unpoly.UnpolyMiddleware',
        ]

        # views.py
        def my_view(request):
            if request.up:
                # Render only the targeted fragment
                return render(request, "partials/content.html", context)
            return render(request, "full.html", context)
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.up = UnpolyDetails.from_request(request)

        response = self.get_response(request)

        if request.up:
            self._process_response(request, response)

        return response

    def _process_response(self, request: HttpRequest, response: HttpResponse) -> None:
        """Add Unpoly response headers and handle version mismatch."""
        config = get_unpoly_config()

        # Always echo location and method so Unpoly can track navigation
        response["X-Up-Location"] = request.get_full_path()
        response["X-Up-Method"] = request.method

        # Add Vary header for proper caching
        _add_vary_header(response, "X-Up-Target")

        # Version mismatch: signal client to reload
        if config.version and request.up.version and request.up.version != config.version:
            _append_event(response, "up:fragment:expired")

        # Preserve Unpoly headers through redirects
        if 300 <= response.status_code < 400:
            self._preserve_redirect_headers(request, response)

    def _preserve_redirect_headers(self, request: HttpRequest, response: HttpResponse) -> None:
        """Carry Unpoly context headers through redirect responses."""
        if request.up.target:
            response["X-Up-Target"] = request.up.target
        if request.up.context:
            response["X-Up-Context"] = orjson.dumps(request.up.context).decode()


class AsyncUnpolyMiddleware:
    """
    Async version of UnpolyMiddleware.

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.unpoly.AsyncUnpolyMiddleware',
        ]
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        request.up = UnpolyDetails.from_request(request)

        response = await self.get_response(request)

        if request.up:
            config = get_unpoly_config()

            response["X-Up-Location"] = request.get_full_path()
            response["X-Up-Method"] = request.method

            _add_vary_header(response, "X-Up-Target")

            if config.version and request.up.version and request.up.version != config.version:
                _append_event(response, "up:fragment:expired")

            if 300 <= response.status_code < 400:
                if request.up.target:
                    response["X-Up-Target"] = request.up.target
                if request.up.context:
                    response["X-Up-Context"] = orjson.dumps(request.up.context).decode()

        return response


def _add_vary_header(response: HttpResponse, header: str) -> None:
    """Add a header name to the Vary response header."""
    existing = response.get("Vary", "")
    if header not in existing:
        if existing:
            response["Vary"] = f"{existing}, {header}"
        else:
            response["Vary"] = header


def _append_event(
    response: HttpResponse, event_name: str, data: dict[str, Any] | None = None
) -> None:
    """Append an event to the X-Up-Events header (JSON array)."""
    existing_raw = response.get("X-Up-Events")
    events: list[dict[str, Any]] = []
    if existing_raw:
        try:
            events = orjson.loads(existing_raw)
        except (orjson.JSONDecodeError, TypeError):
            events = []

    event: dict[str, Any] = {"type": event_name}
    if data:
        event.update(data)
    events.append(event)

    response["X-Up-Events"] = orjson.dumps(events).decode()


def unpoly_context_processor(request: HttpRequest) -> dict[str, Any]:
    """
    Context processor that adds Unpoly details to template context.

    Usage:
        # settings.py
        TEMPLATES = [{
            'OPTIONS': {
                'context_processors': [
                    'django_matt.unpoly.unpoly_context_processor',
                ],
            },
        }]

        # template.html
        {% if up %}Unpoly request targeting {{ up.target }}{% endif %}
    """
    up = getattr(request, "up", None)
    if up is None:
        up = UnpolyDetails.from_request(request)
    return {"up": up}


__all__ = [
    "AsyncUnpolyMiddleware",
    "UnpolyMiddleware",
    "unpoly_context_processor",
]
