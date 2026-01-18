"""
Middleware for Livewire request handling.

Provides request detection, CSRF handling, and component context.
"""

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse


class LivewireMiddleware:
    """
    Middleware for handling Livewire requests.

    - Detects Livewire requests via headers
    - Provides request.livewire attribute
    - Handles CSRF token injection

    Usage:
        # settings.py
        MIDDLEWARE = [
            ...
            'django_matt.livewire.LivewireMiddleware',
        ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Add livewire context to request
        request.livewire = LivewireRequest(request)

        response = self.get_response(request)

        # Add Livewire-specific headers if needed
        if request.livewire.is_livewire:
            response["X-Livewire"] = "true"

        return response


class AsyncLivewireMiddleware:
    """Async version of LivewireMiddleware."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        request.livewire = LivewireRequest(request)

        response = await self.get_response(request)

        if request.livewire.is_livewire:
            response["X-Livewire"] = "true"

        return response


class LivewireRequest:
    """
    Livewire request context.

    Provides information about the current Livewire request.
    """

    def __init__(self, request: HttpRequest):
        self._request = request

    @property
    def is_livewire(self) -> bool:
        """Check if this is a Livewire request."""
        return (
            self._request.headers.get("X-Livewire") == "true"
            or self._request.POST.get("_livewire") == "true"
        )

    @property
    def is_initial(self) -> bool:
        """Check if this is an initial page load (not an update)."""
        return not self.is_livewire

    @property
    def component_id(self) -> str | None:
        """Get the component ID from the request."""
        return self._request.headers.get("X-Livewire-Component-Id") or self._request.POST.get(
            "_component_id"
        )

    @property
    def component_name(self) -> str | None:
        """Get the component name from the request."""
        return self._request.headers.get("X-Livewire-Component-Name") or self._request.POST.get(
            "_component_name"
        )

    @property
    def action(self) -> str | None:
        """Get the action being called."""
        return self._request.POST.get("_action")

    @property
    def action_params(self) -> list:
        """Get action parameters."""
        import json

        params = self._request.POST.get("_params", "[]")
        try:
            return json.loads(params)
        except json.JSONDecodeError:
            return []

    @property
    def updates(self) -> dict:
        """Get state updates from the request."""
        import json

        updates = self._request.POST.get("_updates", "{}")
        try:
            return json.loads(updates)
        except json.JSONDecodeError:
            return {}

    @property
    def snapshot(self) -> str | None:
        """Get the component snapshot token."""
        return self._request.POST.get("_snapshot")

    def get_header(self, name: str, default: Any = None) -> Any:
        """Get a Livewire-specific header."""
        return self._request.headers.get(f"X-Livewire-{name}", default)


__all__ = [
    "AsyncLivewireMiddleware",
    "LivewireMiddleware",
    "LivewireRequest",
]
