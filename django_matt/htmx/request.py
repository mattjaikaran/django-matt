"""
HTMX request detection and information.

Provides utilities for detecting HTMX requests and accessing
HTMX-specific request headers.
"""

from dataclasses import dataclass
from typing import Optional

from django.http import HttpRequest


@dataclass
class HtmxDetails:
    """
    HTMX request details extracted from headers.

    All HTMX requests include an HX-Request header. Additional headers
    provide context about the triggering element and current state.

    Attributes:
        boosted: True if request is via hx-boost
        current_url: Current URL of the browser (HX-Current-URL)
        history_restore_request: True if this is a history restoration request
        prompt: User response to hx-prompt
        request: True if this is an HTMX request
        target: ID of the target element (HX-Target)
        trigger: ID of the triggered element (HX-Trigger)
        trigger_name: Name of the triggered element (HX-Trigger-Name)

    Usage:
        from django_matt.htmx import HtmxDetails

        def my_view(request):
            htmx = HtmxDetails.from_request(request)
            if htmx:
                # This is an HTMX request
                return render(request, "partials/content.html")
            return render(request, "full_page.html")
    """

    boosted: bool = False
    current_url: str | None = None
    history_restore_request: bool = False
    prompt: str | None = None
    request: bool = False
    target: str | None = None
    trigger: str | None = None
    trigger_name: str | None = None

    @classmethod
    def from_request(cls, request: HttpRequest) -> Optional["HtmxDetails"]:
        """
        Extract HTMX details from a Django request.

        Returns None if this is not an HTMX request.
        """
        if request.headers.get("HX-Request") != "true":
            return None

        return cls(
            boosted=request.headers.get("HX-Boosted") == "true",
            current_url=request.headers.get("HX-Current-URL"),
            history_restore_request=request.headers.get("HX-History-Restore-Request") == "true",
            prompt=request.headers.get("HX-Prompt"),
            request=True,
            target=request.headers.get("HX-Target"),
            trigger=request.headers.get("HX-Trigger"),
            trigger_name=request.headers.get("HX-Trigger-Name"),
        )

    def __bool__(self) -> bool:
        """Allow using HtmxDetails in boolean context."""
        return self.request


def is_htmx_request(request: HttpRequest) -> bool:
    """
    Check if a request is an HTMX request.

    Usage:
        if is_htmx_request(request):
            return render(request, "partials/content.html")
    """
    return request.headers.get("HX-Request") == "true"


def is_htmx_boosted(request: HttpRequest) -> bool:
    """Check if request is boosted via hx-boost."""
    return request.headers.get("HX-Boosted") == "true"


def is_htmx_history_restore(request: HttpRequest) -> bool:
    """Check if this is a history restoration request."""
    return request.headers.get("HX-History-Restore-Request") == "true"


def get_htmx_target(request: HttpRequest) -> str | None:
    """Get the target element ID from an HTMX request."""
    return request.headers.get("HX-Target")


def get_htmx_trigger(request: HttpRequest) -> str | None:
    """Get the trigger element ID from an HTMX request."""
    return request.headers.get("HX-Trigger")


def get_htmx_trigger_name(request: HttpRequest) -> str | None:
    """Get the trigger element name from an HTMX request."""
    return request.headers.get("HX-Trigger-Name")


def get_htmx_prompt(request: HttpRequest) -> str | None:
    """Get the user's response to hx-prompt."""
    return request.headers.get("HX-Prompt")


def get_htmx_current_url(request: HttpRequest) -> str | None:
    """Get the current URL of the browser."""
    return request.headers.get("HX-Current-URL")


__all__ = [
    "HtmxDetails",
    "get_htmx_current_url",
    "get_htmx_prompt",
    "get_htmx_target",
    "get_htmx_trigger",
    "get_htmx_trigger_name",
    "is_htmx_boosted",
    "is_htmx_history_restore",
    "is_htmx_request",
]
