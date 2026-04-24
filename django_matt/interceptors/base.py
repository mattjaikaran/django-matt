"""Base interceptor class defining the before/after/error lifecycle hooks."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse


class Interceptor:
    """Base class for request/response interceptors."""

    order: int = 0

    def enabled(self, request: HttpRequest) -> bool:
        """Return whether this interceptor should run for the given request."""
        return True

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        """Hook called before the request handler; return HttpResponse to short-circuit."""
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        """Hook called after the handler produces a response."""
        return response

    async def on_error(
        self, request: HttpRequest, exc: Exception, **kwargs: Any
    ) -> HttpResponse | None:
        """Hook called when the handler raises; return HttpResponse to handle the error."""
        return None
