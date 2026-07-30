"""
Rust Radix Router Middleware — primary dispatch for API routes.

Usage in settings.py:
    MIDDLEWARE = [
        "django_matt.core.radix_middleware.RadixRouterMiddleware",
        ...
    ]

The middleware is auto-registered when ``DjangoMattAPI.__init__`` is called
with ``use_radix=True`` (the default when HAS_RUST is True).

When the Rust wheel is unavailable, the middleware is a no-op.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import resolve

logger = logging.getLogger("django_matt.radix")

# Global registry of API routers that have radix trees built.
# Populated during DjangoMattAPI.get_urls() when HAS_RUST is True.
_radix_routers: list[object] = []


def register_radix_router(router: object) -> None:
    """Register an API router with a radix tree for fast dispatch."""
    if router not in _radix_routers:
        _radix_routers.append(router)
        logger.debug("Registered radix router: %s", type(router).__name__)


class RadixRouterMiddleware:
    """Middleware that tries Rust radix dispatch before Django URL resolver.

    On match: dispatches directly, bypassing Django resolver (2.3x faster).
    On miss: falls through to Django for non-API routes (admin, static, etc.).
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        result = self._try_dispatch(request)
        if result is not None:
            return result
        return self.get_response(request)

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        result = self._try_dispatch(request)
        if result is not None:
            return result
        return await self.get_response(request)

    def _try_dispatch(self, request: HttpRequest) -> HttpResponse | None:
        """Try all registered radix routers. Returns None if no match."""
        for router in _radix_routers:
            try:
                result = router.radix_dispatch(request.method, request.path)
            except Exception as e:
                logger.debug("Radix dispatch skip: %s", e)
                continue

            if result is None:
                continue

            view_func, kwargs = result

            # Populate resolver_match for Django internals
            try:
                request.resolver_match = resolve(request.path)
                if kwargs:
                    request.resolver_match.kwargs.update(kwargs)
            except Exception:
                pass

            try:
                return view_func(request, **kwargs)
            except Exception as e:
                logger.error("Radix view error: %s", e, exc_info=True)
                return None

        return None
