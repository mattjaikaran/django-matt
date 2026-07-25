from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse


class RouteMiddleware:
    """Base class for route-scoped middleware.

    Lighter than Django middleware — no ASGI/WSGI lifecycle, just
    request/response/exception hooks that run around a single handler.
    """

    async def process_request(self, request: HttpRequest) -> HttpResponse | None:
        return None

    async def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        return response

    async def process_exception(self, request: HttpRequest, exc: Exception) -> HttpResponse | None:
        return None


class MiddlewareStack:
    """Ordered collection of RouteMiddleware instances.

    Resolved once at controller init time, executed per-request.
    Request hooks run top→bottom, response hooks run bottom→top (onion model).
    """

    __slots__ = ("_middlewares",)

    def __init__(self, middlewares: list[RouteMiddleware]) -> None:
        self._middlewares = middlewares

    async def execute(
        self, request: HttpRequest, handler: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> HttpResponse:
        # process_request — top to bottom
        for mw in self._middlewares:
            early_response = await mw.process_request(request)
            if early_response is not None:
                return early_response

        # call the actual handler
        try:
            response = await handler(request, *args, **kwargs)
        except Exception as exc:
            # process_exception — bottom to top
            for mw in reversed(self._middlewares):
                exc_response = await mw.process_exception(request, exc)
                if exc_response is not None:
                    return exc_response
            raise

        # process_response — bottom to top
        for mw in reversed(self._middlewares):
            response = await mw.process_response(request, response)

        return response


def _resolve_middleware_stack(
    controller_classes: list[type[RouteMiddleware]],
    method_add: list[type[RouteMiddleware]] | None,
    method_skip: list[type[RouteMiddleware]] | None,
) -> MiddlewareStack | None:
    """Build a MiddlewareStack for a single route method.

    Called once at init time per method, never per-request.
    """
    classes = list(controller_classes)

    if method_add:
        for cls in method_add:
            if cls not in classes:
                classes.append(cls)

    if method_skip:
        skip_set = set(method_skip)
        classes = [cls for cls in classes if cls not in skip_set]

    if not classes:
        return None

    return MiddlewareStack([cls() for cls in classes])


# --- Decorators ---


def use_middleware(*middleware_classes: type[RouteMiddleware]) -> Callable:
    """Add middleware to a specific route method."""

    def decorator(func: Callable) -> Callable:
        existing = getattr(func, "_use_middleware", [])
        func._use_middleware = existing + list(middleware_classes)
        return func

    return decorator


def skip_middleware(*middleware_classes: type[RouteMiddleware]) -> Callable:
    """Exclude specific middleware from a route method (overrides controller-level)."""

    def decorator(func: Callable) -> Callable:
        existing = getattr(func, "_skip_middleware", [])
        func._skip_middleware = existing + list(middleware_classes)
        return func

    return decorator
