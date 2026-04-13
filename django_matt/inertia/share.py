"""
Inertia.js shared data utilities.

Provides ``share()`` for per-request shared data and
``SharedDataMiddleware`` for automatic injection of auth, flash
messages, and CSRF tokens.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse


def share(request: HttpRequest, key: str, value: Any) -> None:
    """Share a value with all subsequent Inertia responses for this request.

    Usage::

        share(request, "flash", {"success": "Item created"})
        share(request, "app_name", "My App")
    """
    if not hasattr(request, "_inertia_shared"):
        request._inertia_shared = {}
    request._inertia_shared[key] = value


class SharedDataMiddleware:
    """Inject common shared data into every Inertia response.

    Automatically shares:
    - ``auth.user`` — serialised authenticated user (with permissions)
    - ``flash`` — Django messages as flash data
    - ``csrf_token`` — CSRF token string

    Add **after** ``InertiaMiddleware`` and Django's ``MessageMiddleware``.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not hasattr(request, "_inertia_shared"):
            request._inertia_shared = {}

        self._share_auth(request)
        self._share_csrf(request)

        response = self.get_response(request)

        # Flash messages must be consumed after the view runs
        self._share_flash(request)

        return response

    # ------------------------------------------------------------------
    # Shared data helpers
    # ------------------------------------------------------------------

    def _share_auth(self, request: HttpRequest) -> None:
        """Share authenticated user data."""
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            auth_data: dict[str, Any] = {
                "user": {
                    "id": getattr(user, "pk", None),
                    "email": getattr(user, "email", ""),
                    "name": self._get_display_name(user),
                    "is_staff": getattr(user, "is_staff", False),
                    "is_superuser": getattr(user, "is_superuser", False),
                },
            }
            # Include permissions if available
            if hasattr(user, "get_all_permissions"):
                auth_data["user"]["permissions"] = sorted(user.get_all_permissions())
            # Include roles from django-matt RBAC if available
            if hasattr(user, "roles"):
                try:
                    roles = user.roles.values_list("name", flat=True)
                    auth_data["user"]["roles"] = list(roles)
                except Exception:
                    auth_data["user"]["roles"] = []

            request._inertia_shared["auth"] = auth_data
        else:
            request._inertia_shared["auth"] = {"user": None}

    def _share_csrf(self, request: HttpRequest) -> None:
        """Share CSRF token."""
        from django.middleware.csrf import get_token

        request._inertia_shared["csrf_token"] = get_token(request)

    def _share_flash(self, request: HttpRequest) -> None:
        """Share flash messages from Django's messages framework."""
        try:
            from django.contrib.messages import get_messages

            storage = get_messages(request)
            messages = [{"level": m.level_tag, "message": str(m)} for m in storage]
            if messages:
                request._inertia_shared["flash"] = messages
        except Exception:
            pass

    @staticmethod
    def _get_display_name(user: Any) -> str:
        """Best-effort display name."""
        if hasattr(user, "get_full_name"):
            name = user.get_full_name()
            if name and name.strip():
                return name
        return getattr(user, "email", "") or str(user)


class AsyncSharedDataMiddleware:
    """Async version of :class:`SharedDataMiddleware`."""

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        if not hasattr(request, "_inertia_shared"):
            request._inertia_shared = {}

        SharedDataMiddleware._share_auth(self, request)
        SharedDataMiddleware._share_csrf(self, request)

        response = await self.get_response(request)

        SharedDataMiddleware._share_flash(self, request)

        return response


__all__ = [
    "AsyncSharedDataMiddleware",
    "SharedDataMiddleware",
    "share",
]
