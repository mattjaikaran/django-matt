"""
Page middleware for request mode detection and response handling.

Detects whether a request is:
- Full HTML (initial browser visit)
- Page XHR (SPA navigation with X-Page header)
- API (Accept: application/json)
"""

from collections.abc import Callable
from enum import Enum

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class RequestMode(Enum):
    """The mode of the current request."""

    FULL_HTML = "full_html"  # Initial browser visit
    PAGE_XHR = "page_xhr"  # SPA navigation (X-Page header)
    API = "api"  # JSON API (Accept: application/json)
    SSR = "ssr"  # Server-side rendering request


# Request attribute name for storing mode
REQUEST_MODE_ATTR = "_page_mode"


def get_request_mode(request: HttpRequest) -> RequestMode:
    """
    Determine the request mode based on headers.

    Priority:
    1. X-Page header → PAGE_XHR
    2. X-SSR header → SSR
    3. Accept: application/json (without text/html) → API
    4. Default → FULL_HTML
    """
    # Check if already computed
    if hasattr(request, REQUEST_MODE_ATTR):
        return getattr(request, REQUEST_MODE_ATTR)

    mode = _detect_request_mode(request)
    setattr(request, REQUEST_MODE_ATTR, mode)
    return mode


def _detect_request_mode(request: HttpRequest) -> RequestMode:
    """Detect the request mode from headers."""

    # Check for page XHR (SPA navigation)
    # Support both X-Page and legacy X-Inertia headers
    if request.headers.get("X-Page") == "true":
        return RequestMode.PAGE_XHR

    # Legacy Inertia compatibility (if enabled)
    pages_settings = getattr(settings, "PAGES", {})
    if pages_settings.get("legacy_headers", False):
        if request.headers.get("X-Inertia") == "true":
            return RequestMode.PAGE_XHR

    # Check for SSR request (from Node.js SSR server)
    if request.headers.get("X-SSR") == "true":
        return RequestMode.SSR

    # Check for explicit API request
    accept = request.headers.get("Accept", "")

    # If Accept header explicitly requests JSON and NOT HTML, it's an API request
    if "application/json" in accept and "text/html" not in accept:
        return RequestMode.API

    # Check for XMLHttpRequest that's not a page request
    # This catches AJAX calls that don't want page responses
    if (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        and "X-Page" not in request.headers
    ):
        # Could be API or could be a legacy AJAX call
        # Default to API if Accept is JSON
        if "application/json" in accept:
            return RequestMode.API

    # Default: full HTML
    return RequestMode.FULL_HTML


def is_page_request(request: HttpRequest) -> bool:
    """Check if this is a page XHR request (SPA navigation)."""
    return get_request_mode(request) == RequestMode.PAGE_XHR


def is_api_request(request: HttpRequest) -> bool:
    """Check if this is an API request."""
    return get_request_mode(request) == RequestMode.API


def is_initial_request(request: HttpRequest) -> bool:
    """Check if this is an initial HTML request."""
    return get_request_mode(request) == RequestMode.FULL_HTML


class PageMiddleware:
    """
    Middleware for handling page requests.

    Responsibilities:
    - Detect request mode and attach to request
    - Handle PageResponse objects
    - Manage asset versioning (409 on mismatch)
    - Process redirects for SPA
    - Handle flash messages

    Add to MIDDLEWARE:
        'django_matt.pages.middleware.PageMiddleware',
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Detect and cache request mode
        mode = get_request_mode(request)

        # Check asset version for page requests
        if mode == RequestMode.PAGE_XHR:
            version_mismatch = self._check_version_mismatch(request)
            if version_mismatch:
                return version_mismatch

        # Process the request
        response = self.get_response(request)

        # Handle PageResponse objects
        from django_matt.pages.response import PageResponse

        if isinstance(response, PageResponse):
            response = response.render(request)

        # Handle redirects for page requests
        if mode == RequestMode.PAGE_XHR:
            response = self._handle_page_redirect(request, response)

        return response

    def _check_version_mismatch(self, request: HttpRequest) -> HttpResponse | None:
        """
        Check if the client's asset version matches the server's.

        If there's a mismatch, return a 409 Conflict response telling
        the client to do a full page reload.
        """
        from django_matt.pages.assets import get_asset_version

        client_version = request.headers.get("X-Page-Version", "")
        server_version = get_asset_version()

        # Skip check if no version configured
        if not server_version:
            return None

        # Skip check if client didn't send version
        if not client_version:
            return None

        # Check for mismatch
        if client_version != server_version:
            response = HttpResponse(status=409)
            response["X-Page-Location"] = request.get_full_path()
            return response

        return None

    def _handle_page_redirect(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Handle redirects for page requests.

        For page XHR requests, we need to convert redirects to 303
        and set the X-Page-Location header.
        """
        # Check if this is a redirect
        if response.status_code in (301, 302, 307, 308):
            location = response.get("Location", "")

            if location:
                # Convert to 303 See Other for page requests
                # This ensures the browser does a GET request
                response.status_code = 303
                response["X-Page-Location"] = location

        return response


class AsyncPageMiddleware:
    """
    Async version of PageMiddleware.

    Add to MIDDLEWARE:
        'django_matt.pages.middleware.AsyncPageMiddleware',
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self._sync_middleware = PageMiddleware(get_response)

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        # For now, delegate to sync version
        # TODO: Implement full async support
        return self._sync_middleware(request)


__all__ = [
    "AsyncPageMiddleware",
    "PageMiddleware",
    "RequestMode",
    "get_request_mode",
    "is_api_request",
    "is_initial_request",
    "is_page_request",
]
