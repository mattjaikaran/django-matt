"""
Inertia.js view helpers.

Provides a class-based view mixin and a function-view decorator.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.views import View

from django_matt.inertia.response import inertia


class InertiaView(View):
    """Class-based view mixin for Inertia responses.

    Subclass and set ``component`` to the frontend component path.
    Override ``get_props()`` to provide data.

    Usage::

        class DashboardView(InertiaView):
            component = "Dashboard/Index"

            def get_props(self, request, **kwargs):
                return {"stats": get_stats()}
    """

    component: str = ""

    def get_props(self, request: HttpRequest, **kwargs: Any) -> dict[str, Any]:
        """Return props dict for the Inertia response. Override in subclass."""
        return {}

    def get_component(self) -> str:
        """Return the frontend component name."""
        if not self.component:
            raise ValueError(f"{self.__class__.__name__} must define a 'component' attribute")
        return self.component

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return inertia(request, self.get_component(), self.get_props(request, **kwargs))

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return inertia(request, self.get_component(), self.get_props(request, **kwargs))

    def put(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return inertia(request, self.get_component(), self.get_props(request, **kwargs))

    def patch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return inertia(request, self.get_component(), self.get_props(request, **kwargs))

    def delete(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return inertia(request, self.get_component(), self.get_props(request, **kwargs))


def inertia_view(component: str) -> Callable:
    """Decorator that wraps a function view into an Inertia response.

    The decorated function should return a props dict (or ``None``).

    Usage::

        @inertia_view("Dashboard/Index")
        def dashboard(request):
            return {"stats": get_stats(), "user": request.user.email}


        # In urls.py
        (path("dashboard/", dashboard),)
    """

    def decorator(view_func: Callable[..., dict[str, Any] | None]) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            result = view_func(request, *args, **kwargs)

            # Allow returning HttpResponse directly (redirects, etc.)
            if isinstance(result, HttpResponse):
                return result

            props = result if isinstance(result, dict) else {}
            return inertia(request, component, props)

        # Store metadata for introspection
        wrapper.inertia_component = component
        return wrapper

    return decorator


__all__ = [
    "InertiaView",
    "inertia_view",
]
