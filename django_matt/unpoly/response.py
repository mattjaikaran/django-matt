"""
Unpoly response utilities.

Provides response classes and helpers for Unpoly-specific response headers
like X-Up-Target, X-Up-Events, X-Up-Accept-Layer, etc.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse, HttpResponseRedirect

import orjson


class UnpolyResponse(HttpResponse):
    """
    HTTP response with Unpoly header support.

    Provides methods to set Unpoly-specific response headers for
    client-side behavior control.

    Usage:
        from django_matt.unpoly import UnpolyResponse

        def my_view(request):
            return (
                UnpolyResponse("<div>Updated</div>")
                .set_target(".content")
                .emit_event("user:updated", id=123)
            )
    """

    def set_target(self, selector: str) -> UnpolyResponse:
        """Set the X-Up-Target header (CSS selector for fragment update)."""
        self["X-Up-Target"] = selector
        return self

    def emit_event(self, name: str, **data: Any) -> UnpolyResponse:
        """
        Append an event to the X-Up-Events JSON array.

        Args:
            name: Event type name
            **data: Additional event data fields
        """
        events = self._get_events()
        event: dict[str, Any] = {"type": name}
        if data:
            event.update(data)
        events.append(event)
        self["X-Up-Events"] = orjson.dumps(events).decode()
        return self

    def clear_cache(self, *patterns: str) -> UnpolyResponse:
        """
        Set X-Up-Clear-Cache header.

        Args:
            *patterns: URL patterns to clear from cache.
                       Empty means clear all.
        """
        if patterns:
            self["X-Up-Clear-Cache"] = " ".join(patterns)
        else:
            self["X-Up-Clear-Cache"] = "*"
        return self

    def accept_layer(self, **value: Any) -> UnpolyResponse:
        """
        Accept the current layer (close overlay with a value).

        Sets X-Up-Accept-Layer header with JSON-encoded value.
        """
        self["X-Up-Accept-Layer"] = orjson.dumps(value).decode() if value else "true"
        return self

    def dismiss_layer(self, **value: Any) -> UnpolyResponse:
        """
        Dismiss the current layer (close overlay with a value).

        Sets X-Up-Dismiss-Layer header with JSON-encoded value.
        """
        self["X-Up-Dismiss-Layer"] = orjson.dumps(value).decode() if value else "true"
        return self

    def set_context(self, **data: Any) -> UnpolyResponse:
        """
        Set X-Up-Context header (layer context update).

        Args:
            **data: Context key-value pairs to set/update.
        """
        self["X-Up-Context"] = orjson.dumps(data).decode()
        return self

    def _get_events(self) -> list[dict[str, Any]]:
        """Get existing events from X-Up-Events header."""
        raw = self.get("X-Up-Events")
        if not raw:
            return []
        try:
            return orjson.loads(raw)
        except (orjson.JSONDecodeError, TypeError):
            return []


def up_redirect(url: str, **kwargs: Any) -> HttpResponse:
    """
    Redirect with Unpoly headers preserved.

    For Unpoly requests, uses X-Up-Location instead of a 302 so the
    client can handle the navigation within the current layer.

    Args:
        url: Target URL
        **kwargs: Additional keyword arguments passed to HttpResponseRedirect
    """
    response = HttpResponseRedirect(url, **kwargs)
    response["X-Up-Location"] = url
    return response


__all__ = [
    "UnpolyResponse",
    "up_redirect",
]
