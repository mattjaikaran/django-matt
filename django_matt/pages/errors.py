"""
Error handling for pages.

Provides error page handlers and utilities for consistent
error responses across HTML and JSON modes.
"""

from typing import Any, Callable, Dict, Optional, Type

from django.http import HttpRequest, HttpResponse

from django_matt.pages.response import PageResponse
from django_matt.pages.middleware import get_request_mode, RequestMode


# Registry of error handlers
_error_handlers: Dict[int, Callable] = {}


def error_page(status_code: int) -> Callable:
    """
    Decorator to register an error page handler.

    Usage:
        @error_page(404)
        def not_found(request, exception=None):
            return {"message": "Page not found"}

        @error_page(500)
        def server_error(request):
            return {"message": "Something went wrong"}

        @error_page(403)
        def forbidden(request, exception=None):
            return {
                "message": "You don't have permission",
                "login_url": "/login",
            }

    The decorated function should return a dict of props that will
    be passed to an error component (Error404, Error500, etc.).
    """
    def decorator(func: Callable) -> Callable:
        _error_handlers[status_code] = func
        return func
    return decorator


def get_error_handler(status_code: int) -> Optional[Callable]:
    """Get the registered error handler for a status code."""
    return _error_handlers.get(status_code)


def render_error_page(
    request: HttpRequest,
    status_code: int,
    exception: Optional[Exception] = None,
    message: Optional[str] = None,
) -> HttpResponse:
    """
    Render an error page.

    Uses registered error handlers if available, otherwise
    returns a basic error response.
    """
    mode = get_request_mode(request)

    # Get custom handler
    handler = get_error_handler(status_code)

    if handler:
        # Call custom handler
        try:
            if exception:
                props = handler(request, exception)
            else:
                props = handler(request)
        except Exception:
            props = {"message": message or f"Error {status_code}"}
    else:
        # Default props
        props = {
            "message": message or _get_default_error_message(status_code),
            "status": status_code,
        }

    # Add exception details in debug mode
    from django.conf import settings
    if settings.DEBUG and exception:
        props["debug"] = {
            "exception": str(exception),
            "type": type(exception).__name__,
        }

    # Determine component name
    component = f"Error{status_code}"

    # For API mode, return JSON error
    if mode == RequestMode.API:
        from django.http import JsonResponse
        return JsonResponse(
            {"error": props.get("message", f"Error {status_code}"), **props},
            status=status_code,
        )

    # For page mode, return page JSON
    if mode == RequestMode.PAGE_XHR:
        response = PageResponse(
            component,
            props=props,
            status=status_code,
        )
        return response._render_page_json(request)

    # For full HTML, render error page
    response = PageResponse(
        component,
        props=props,
        title=f"Error {status_code}",
        status=status_code,
    )
    return response._render_full_html(request)


def _get_default_error_message(status_code: int) -> str:
    """Get default error message for status code."""
    messages = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Page Not Found",
        405: "Method Not Allowed",
        408: "Request Timeout",
        409: "Conflict",
        410: "Gone",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }
    return messages.get(status_code, f"Error {status_code}")


# Django error handler integration

def handler400(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Django 400 error handler."""
    return render_error_page(request, 400, exception)


def handler403(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Django 403 error handler."""
    return render_error_page(request, 403, exception)


def handler404(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Django 404 error handler."""
    return render_error_page(request, 404, exception)


def handler500(request: HttpRequest) -> HttpResponse:
    """Django 500 error handler."""
    return render_error_page(request, 500)


__all__ = [
    "error_page",
    "get_error_handler",
    "render_error_page",
    "handler400",
    "handler403",
    "handler404",
    "handler500",
]
