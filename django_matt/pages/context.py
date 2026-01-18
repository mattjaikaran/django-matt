"""
Shared data and flash message management for pages.

Provides mechanisms for:
- Shared data that's available on every page (auth state, etc.)
- Flash messages that persist across redirects
- Request-scoped data
"""

import json
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest

# Request attribute names
SHARED_DATA_ATTR = "_page_shared_data"
FLASH_MESSAGES_ATTR = "_page_flash_messages"


# Global shared data providers
_shared_data_providers: list[Callable[[HttpRequest], dict[str, Any]]] = []


def register_shared_data(provider: Callable[[HttpRequest], dict[str, Any]]) -> Callable:
    """
    Register a function that provides shared data for all pages.

    The function receives the request and returns a dict of data
    that will be merged into every page's shared data.

    Usage:
        @register_shared_data
        def auth_data(request):
            if request.user.is_authenticated:
                return {
                    "user": {
                        "id": request.user.id,
                        "email": request.user.email,
                        "name": request.user.get_full_name(),
                    }
                }
            return {"user": None}

        @register_shared_data
        def app_data(request):
            return {
                "app_name": "My App",
                "version": "1.0.0",
            }
    """
    _shared_data_providers.append(provider)
    return provider


def get_shared_data(request: HttpRequest) -> dict[str, Any]:
    """
    Get all shared data for a request.

    This merges data from all registered providers and any
    request-specific shared data.
    """
    # Check cache
    if hasattr(request, SHARED_DATA_ATTR):
        return getattr(request, SHARED_DATA_ATTR)

    shared = {}

    # Collect from all providers
    for provider in _shared_data_providers:
        try:
            data = provider(request)
            if data:
                shared.update(data)
        except Exception:
            # Don't let a failing provider break the page
            pass

    # Add default shared data
    shared.update(_get_default_shared_data(request))

    # Cache on request
    setattr(request, SHARED_DATA_ATTR, shared)

    return shared


def _get_default_shared_data(request: HttpRequest) -> dict[str, Any]:
    """Get default shared data that's always included."""
    shared = {}

    # CSRF token (for forms)
    from django.middleware.csrf import get_token

    shared["csrfToken"] = get_token(request)

    # Authenticated user (basic info)
    if hasattr(request, "user") and request.user.is_authenticated:
        shared["auth"] = {
            "user": {
                "id": request.user.pk,
                "email": getattr(request.user, "email", None),
            },
            "isAuthenticated": True,
        }
    else:
        shared["auth"] = {
            "user": None,
            "isAuthenticated": False,
        }

    return shared


def set_shared_data(request: HttpRequest, key: str, value: Any) -> None:
    """
    Set shared data for the current request.

    This is useful for setting request-specific shared data
    that should be available to the page.

    Usage:
        set_shared_data(request, "permissions", user_permissions)
    """
    if not hasattr(request, SHARED_DATA_ATTR):
        setattr(request, SHARED_DATA_ATTR, {})

    shared = getattr(request, SHARED_DATA_ATTR)
    shared[key] = value


# Flash messages


def add_flash_message(
    request: HttpRequest,
    message: str,
    type: str = "success",
    **extra: Any,
) -> None:
    """
    Add a flash message to be shown on the next page.

    Usage:
        add_flash_message(request, "User created successfully")
        add_flash_message(request, "Error occurred", type="error")
        add_flash_message(request, "Check your email", type="info", action="resend")
    """
    if not hasattr(request, FLASH_MESSAGES_ATTR):
        setattr(request, FLASH_MESSAGES_ATTR, [])

    messages = getattr(request, FLASH_MESSAGES_ATTR)
    messages.append(
        {
            "message": message,
            "type": type,
            **extra,
        }
    )


def get_flash_messages(request: HttpRequest) -> list[dict[str, Any]]:
    """
    Get all flash messages for the current request.

    This includes:
    - Messages added during this request
    - Messages from the previous request (via cookie)
    """
    messages = []

    # Get messages from cookie (from previous request/redirect)
    cookie_flash = request.COOKIES.get("_page_flash")
    if cookie_flash:
        try:
            flash_data = json.loads(cookie_flash)
            if isinstance(flash_data, dict):
                messages.append(flash_data)
            elif isinstance(flash_data, list):
                messages.extend(flash_data)
        except (json.JSONDecodeError, TypeError):
            pass

    # Get messages added during this request
    if hasattr(request, FLASH_MESSAGES_ATTR):
        messages.extend(getattr(request, FLASH_MESSAGES_ATTR))

    return messages


def flash(message: str, type: str = "success") -> Callable:
    """
    Decorator to add a flash message after a view returns successfully.

    Usage:
        @page("UserCreate")
        @flash("User created successfully")
        def create_user(request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            result = func(request, *args, **kwargs)
            add_flash_message(request, message, type)
            return result

        return wrapper

    return decorator


# Shared data context manager


class SharedDataContext:
    """
    Context manager for temporarily adding shared data.

    Usage:
        with SharedDataContext(request, permissions=user_perms):
            return PageResponse("Dashboard", {"stats": stats})
    """

    def __init__(self, request: HttpRequest, **data: Any):
        self.request = request
        self.data = data
        self._original: dict[str, Any] = {}

    def __enter__(self):
        # Store original values
        if hasattr(self.request, SHARED_DATA_ATTR):
            shared = getattr(self.request, SHARED_DATA_ATTR)
            for key in self.data:
                if key in shared:
                    self._original[key] = shared[key]

        # Set new values
        for key, value in self.data.items():
            set_shared_data(self.request, key, value)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original values
        if hasattr(self.request, SHARED_DATA_ATTR):
            shared = getattr(self.request, SHARED_DATA_ATTR)
            for key in self.data:
                if key in self._original:
                    shared[key] = self._original[key]
                elif key in shared:
                    del shared[key]

        return False


__all__ = [
    "SharedDataContext",
    "add_flash_message",
    "flash",
    "get_flash_messages",
    "get_shared_data",
    "register_shared_data",
    "set_shared_data",
]
