"""
Content negotiation decorators for views.

Decorators for customizing content negotiation on a per-view basis.
"""

import functools
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_matt.negotiation.config import FormatType
from django_matt.negotiation.negotiator import (
    NotAcceptable,
    get_negotiator,
    render_format,
)


def renders(*formats: FormatType) -> Callable:
    """
    Decorator to specify which formats a view supports.

    If the client requests a format not in the list, returns 406.

    Usage:
        @renders("json", "xml")
        def my_view(request):
            return {"data": "value"}

        @api.get("/users")
        @renders("json", "csv")
        async def list_users(request):
            return users
    """

    def decorator[F: Callable[..., Any]](func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Check if requested format is supported
            negotiator = get_negotiator()
            try:
                negotiated = negotiator.negotiate(request)
            except NotAcceptable as e:
                return HttpResponse(
                    content=f'{{"error": "{e}"}}',
                    status=406,
                    content_type="application/json",
                )

            if negotiated.format not in formats:
                available = ", ".join(formats)
                return HttpResponse(
                    content=f'{{"error": "Format \'{negotiated.format}\' not supported. Available: {available}"}}',
                    status=406,
                    content_type="application/json",
                )

            # Store on request for later use
            request.negotiated_format = negotiated

            # Call the view
            result = func(request, *args, **kwargs)

            # If result is already a response, return it
            if isinstance(result, HttpResponse):
                return result

            # Otherwise, render to the negotiated format
            return negotiated.renderer.to_response(result)

        @functools.wraps(func)
        async def async_wrapper(request: HttpRequest, *args, **kwargs):
            negotiator = get_negotiator()
            try:
                negotiated = negotiator.negotiate(request)
            except NotAcceptable as e:
                return HttpResponse(
                    content=f'{{"error": "{e}"}}',
                    status=406,
                    content_type="application/json",
                )

            if negotiated.format not in formats:
                available = ", ".join(formats)
                return HttpResponse(
                    content=f'{{"error": "Format \'{negotiated.format}\' not supported. Available: {available}"}}',
                    status=406,
                    content_type="application/json",
                )

            request.negotiated_format = negotiated
            result = await func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            return negotiated.renderer.to_response(result)

        # Check if function is async
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


def render_as(format_name: FormatType) -> Callable:
    """
    Decorator to force a specific output format.

    Ignores content negotiation and always renders in the specified format.

    Usage:
        @render_as("csv")
        def export_users(request):
            return users

        @api.get("/export.xml")
        @render_as("xml")
        async def export_data(request):
            return data
    """

    def decorator[F: Callable[..., Any]](func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            result = func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            return render_format(result, format_name)

        @functools.wraps(func)
        async def async_wrapper(request: HttpRequest, *args, **kwargs):
            result = await func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            return render_format(result, format_name)

        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


def content_negotiated[F: Callable[..., Any]](func: F) -> F:
    """
    Decorator to enable content negotiation for a view.

    Automatically renders the return value based on Accept header.

    Usage:
        @content_negotiated
        def my_view(request):
            return {"data": "value"}

        @api.get("/data")
        @content_negotiated
        async def get_data(request):
            return data
    """

    @functools.wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        negotiator = get_negotiator()
        try:
            negotiated = negotiator.negotiate(request)
        except NotAcceptable as e:
            return HttpResponse(
                content=f'{{"error": "{e}"}}',
                status=406,
                content_type="application/json",
            )

        request.negotiated_format = negotiated
        result = func(request, *args, **kwargs)

        if isinstance(result, HttpResponse):
            return result

        return negotiated.renderer.to_response(result)

    @functools.wraps(func)
    async def async_wrapper(request: HttpRequest, *args, **kwargs):
        negotiator = get_negotiator()
        try:
            negotiated = negotiator.negotiate(request)
        except NotAcceptable as e:
            return HttpResponse(
                content=f'{{"error": "{e}"}}',
                status=406,
                content_type="application/json",
            )

        request.negotiated_format = negotiated
        result = await func(request, *args, **kwargs)

        if isinstance(result, HttpResponse):
            return result

        return negotiated.renderer.to_response(result)

    if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
        return async_wrapper  # type: ignore
    return wrapper  # type: ignore


def with_template(template_name: str) -> Callable:
    """
    Decorator to specify HTML template for HTML responses.

    When client requests HTML, renders using the specified template.
    Other formats work normally.

    Usage:
        @with_template("users/list.html")
        def list_users(request):
            return {"users": users}

        @api.get("/users")
        @with_template("users/list.html")
        async def get_users(request):
            return {"users": users}
    """

    def decorator[F: Callable[..., Any]](func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            negotiator = get_negotiator()
            try:
                negotiated = negotiator.negotiate(request)
            except NotAcceptable as e:
                return HttpResponse(
                    content=f'{{"error": "{e}"}}',
                    status=406,
                    content_type="application/json",
                )

            request.negotiated_format = negotiated
            result = func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            # If HTML format, use template
            if negotiated.format == "html":
                return negotiated.renderer.to_response(
                    result,
                    template_name=template_name,
                )

            return negotiated.renderer.to_response(result)

        @functools.wraps(func)
        async def async_wrapper(request: HttpRequest, *args, **kwargs):
            negotiator = get_negotiator()
            try:
                negotiated = negotiator.negotiate(request)
            except NotAcceptable as e:
                return HttpResponse(
                    content=f'{{"error": "{e}"}}',
                    status=406,
                    content_type="application/json",
                )

            request.negotiated_format = negotiated
            result = await func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            if negotiated.format == "html":
                return negotiated.renderer.to_response(
                    result,
                    template_name=template_name,
                )

            return negotiated.renderer.to_response(result)

        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


class NegotiatedResponse:
    """
    Helper class for building negotiated responses.

    Usage:
        def my_view(request):
            data = {"users": users}
            return NegotiatedResponse(data).with_status(201).render(request)

        # Or with specific format
        return NegotiatedResponse(data).as_format("csv").render()
    """

    def __init__(self, data: Any):
        self.data = data
        self.status_code = 200
        self._format: FormatType | None = None
        self._kwargs: dict[str, Any] = {}

    def with_status(self, status: int) -> "NegotiatedResponse":
        """Set response status code."""
        self.status_code = status
        return self

    def as_format(self, format_name: FormatType) -> "NegotiatedResponse":
        """Force a specific format (bypass negotiation)."""
        self._format = format_name
        return self

    def with_template(self, template_name: str) -> "NegotiatedResponse":
        """Set template for HTML rendering."""
        self._kwargs["template_name"] = template_name
        return self

    def with_options(self, **kwargs) -> "NegotiatedResponse":
        """Set additional renderer options."""
        self._kwargs.update(kwargs)
        return self

    def render(self, request: HttpRequest | None = None) -> HttpResponse:
        """Render the response."""
        if self._format:
            # Use specific format
            return render_format(
                self.data,
                self._format,
                status=self.status_code,
                **self._kwargs,
            )

        if request is None:
            # No request, default to JSON
            return render_format(
                self.data,
                "json",
                status=self.status_code,
                **self._kwargs,
            )

        # Use content negotiation
        negotiator = get_negotiator()
        try:
            negotiated = negotiator.negotiate(request)
        except NotAcceptable:
            # Fall back to default
            return render_format(
                self.data,
                "json",
                status=self.status_code,
                **self._kwargs,
            )

        return negotiated.renderer.to_response(
            self.data,
            status=self.status_code,
            **self._kwargs,
        )
