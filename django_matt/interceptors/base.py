from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse


class Interceptor:
    """Base class for request/response interceptors."""

    order: int = 0

    def enabled(self, request: HttpRequest) -> bool:
        return True

    async def before_request(
        self, request: HttpRequest, **kwargs: Any
    ) -> HttpRequest | HttpResponse | None:
        return None

    async def after_response(
        self, request: HttpRequest, response: HttpResponse, **kwargs: Any
    ) -> HttpResponse:
        return response

    async def on_error(
        self, request: HttpRequest, exc: Exception, **kwargs: Any
    ) -> HttpResponse | None:
        return None
