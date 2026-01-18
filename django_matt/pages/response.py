"""
Page response classes for server-driven SPA.

Provides PageData and PageResponse for rendering pages as HTML or JSON
based on request mode (initial visit, SPA navigation, or API).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union
import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.conf import settings

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


@dataclass
class PageData:
    """
    The page object sent to the client.

    This is the core data structure that represents a page render,
    containing the component name, props, and metadata.
    """

    component: str                                      # Component name (e.g., "UserList")
    props: Dict[str, Any]                              # Page props
    url: str                                           # Current URL
    version: str = ""                                  # Asset version hash
    shared: Dict[str, Any] = field(default_factory=dict)   # Shared data (auth, etc.)
    errors: Dict[str, List[str]] = field(default_factory=dict)  # Validation errors
    flash: List[Dict[str, str]] = field(default_factory=list)   # Flash messages

    # Metadata
    title: Optional[str] = None                        # Page title
    meta: Dict[str, str] = field(default_factory=dict) # Meta tags

    # Navigation options
    preserve_scroll: bool = False                      # Preserve scroll position
    clear_history: bool = False                        # Clear browser history
    replace_state: bool = False                        # Replace instead of push

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON response."""
        data = {
            "component": self.component,
            "props": self.props,
            "url": self.url,
            "version": self.version,
            "shared": self.shared,
        }

        # Only include non-empty optional fields
        if self.errors:
            data["errors"] = self.errors
        if self.flash:
            data["flash"] = self.flash
        if self.title:
            data["title"] = self.title
        if self.meta:
            data["meta"] = self.meta
        if self.preserve_scroll:
            data["preserveScroll"] = True
        if self.clear_history:
            data["clearHistory"] = True
        if self.replace_state:
            data["replaceState"] = True

        return data

    def to_json(self) -> str:
        """Serialize to JSON string."""
        if HAS_ORJSON:
            return orjson.dumps(self.to_dict()).decode("utf-8")
        return json.dumps(self.to_dict(), separators=(",", ":"))


class PageResponse:
    """
    Response that renders as HTML (initial) or JSON (XHR).

    Usage:
        # Simple usage
        return PageResponse("UserList", {"users": users})

        # With options
        return PageResponse(
            "UserDetail",
            props={"user": user},
            title=f"{user.name} - Profile",
            shared={"can_edit": request.user == user},
        )

        # With errors (form validation)
        return PageResponse(
            "UserCreate",
            props={"values": form.data},
            errors=form.errors,
            status=422,
        )
    """

    def __init__(
        self,
        component: str,
        props: Optional[Dict[str, Any]] = None,
        *,
        shared: Optional[Dict[str, Any]] = None,
        errors: Optional[Dict[str, List[str]]] = None,
        flash: Optional[List[Dict[str, str]]] = None,
        title: Optional[str] = None,
        meta: Optional[Dict[str, str]] = None,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        preserve_scroll: bool = False,
        clear_history: bool = False,
        replace_state: bool = False,
    ):
        self.component = component
        self.props = props or {}
        self.shared = shared or {}
        self.errors = errors or {}
        self.flash = flash or []
        self.title = title
        self.meta = meta or {}
        self.status = status
        self.headers = headers or {}
        self.preserve_scroll = preserve_scroll
        self.clear_history = clear_history
        self.replace_state = replace_state

        # Will be set by middleware/decorator
        self._request: Optional[HttpRequest] = None

    def get_page_data(self, request: HttpRequest) -> PageData:
        """Build the PageData object for this response."""
        from django_matt.pages.context import get_shared_data, get_flash_messages
        from django_matt.pages.assets import get_asset_version

        # Merge shared data from context
        shared = {**get_shared_data(request), **self.shared}

        # Get flash messages
        flash = get_flash_messages(request) + self.flash

        return PageData(
            component=self.component,
            props=self.props,
            url=request.get_full_path(),
            version=get_asset_version(),
            shared=shared,
            errors=self.errors,
            flash=flash,
            title=self.title,
            meta=self.meta,
            preserve_scroll=self.preserve_scroll,
            clear_history=self.clear_history,
            replace_state=self.replace_state,
        )

    def render(self, request: HttpRequest) -> HttpResponse:
        """Render based on request mode."""
        from django_matt.pages.middleware import get_request_mode, RequestMode

        mode = get_request_mode(request)

        if mode == RequestMode.PAGE_XHR:
            return self._render_page_json(request)
        elif mode == RequestMode.API:
            return self._render_api_json(request)
        else:
            return self._render_full_html(request)

    def _render_page_json(self, request: HttpRequest) -> JsonResponse:
        """Render as page JSON for SPA navigation."""
        page_data = self.get_page_data(request)

        response = JsonResponse(
            page_data.to_dict(),
            status=self.status,
            json_dumps_params={"separators": (",", ":")},
        )

        # Set page headers
        response["X-Page"] = "true"
        response["Vary"] = "X-Page, Accept"

        for key, value in self.headers.items():
            response[key] = value

        return response

    def _render_api_json(self, request: HttpRequest) -> JsonResponse:
        """Render as pure JSON API response (for mobile, etc.)."""
        # For API mode, just return the props directly
        response = JsonResponse(
            self.props,
            status=self.status,
            json_dumps_params={"separators": (",", ":")},
        )

        for key, value in self.headers.items():
            response[key] = value

        return response

    def _render_full_html(self, request: HttpRequest) -> HttpResponse:
        """Render as full HTML document for initial page load."""
        from django_matt.pages.rendering import render_page_html

        page_data = self.get_page_data(request)
        html = render_page_html(request, page_data)

        response = HttpResponse(
            html,
            status=self.status,
            content_type="text/html; charset=utf-8",
        )

        response["Vary"] = "X-Page, Accept"

        for key, value in self.headers.items():
            response[key] = value

        return response


def redirect_page(
    url: str,
    *,
    flash: Optional[str] = None,
    flash_type: str = "success",
    preserve_scroll: bool = False,
) -> HttpResponse:
    """
    Redirect to another page.

    For SPA navigation, this returns a 303 with X-Page-Location header.
    For initial requests, this returns a standard redirect.

    Usage:
        return redirect_page("/users", flash="User created successfully")
        return redirect_page(f"/users/{user.id}")
    """
    from django.shortcuts import redirect
    from django_matt.pages.context import add_flash_message

    # This will be handled by middleware to add flash message
    response = redirect(url)

    if flash:
        # Store flash message for next request
        response.set_cookie(
            "_page_flash",
            json.dumps({"message": flash, "type": flash_type}),
            max_age=60,  # 1 minute
            httponly=True,
            samesite="Lax",
        )

    # For SPA requests, we need special handling
    response["X-Page-Location"] = url

    if preserve_scroll:
        response["X-Page-Preserve-Scroll"] = "true"

    return response


__all__ = [
    "PageData",
    "PageResponse",
    "redirect_page",
]
