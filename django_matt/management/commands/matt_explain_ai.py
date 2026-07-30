"""
AI-powered request lifecycle explanation command.

Usage:
    python manage.py matt_explain_ai <path> <method>
    python manage.py matt_explain_ai /api/orders/ POST
    python manage.py matt_explain_ai /api/users/ GET
"""

from __future__ import annotations

import logging
from typing import Any

from django.urls import URLPattern, URLResolver, get_resolver

from django_matt.ai.explain import trace_route
from django_matt.cli import MattCommand

logger = logging.getLogger(__name__)


class Command(MattCommand):
    """Explain the full request lifecycle for a route using AI-assisted tracing."""

    help = "Explain request lifecycle for a URL path with service-level tracing"

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "path",
            help="URL path to explain (e.g., /api/orders/)",
        )
        parser.add_argument(
            "method",
            nargs="?",
            default="GET",
            help="HTTP method (default: GET)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path: str = options["path"]
        method: str = (options.get("method") or "GET").upper()

        # Resolve the URL to find which app handles it, then find the API instance
        api_instance = self._find_api_instance(path)
        if api_instance is None:
            self.error(f"Could not resolve API instance for: {path}")
            return

        trace = trace_route(api_instance, path, method)
        output = trace.render()
        self.console.print(f"\n{output}\n")

    # ── API instance discovery ────────────────────────────────────

    def _find_api_instance(self, path: str) -> Any:
        """Locate the DjangoMattAPI instance that handles *path*."""
        # Strategy 1: Try to resolve the path to a view, then find its API
        try:
            from django.urls import resolve

            match = resolve(path)
            view_func = match.func

            # Check if view_func has __self__ that is a DjangoMattAPI
            api = self._api_from_view(view_func)
            if api is not None:
                return api
        except Exception:
            pass

        # Strategy 2: Scan all URL resolvers for DjangoMattAPI instances
        resolver = get_resolver()
        api_instances: list[Any] = []
        self._collect_apis(resolver, api_instances)

        for api in api_instances:
            # Check if this API has a matching route
            if self._api_handles_path(api, path):
                return api

        # Return the first API found as fallback
        if api_instances:
            return api_instances[0]

        return None

    def _api_from_view(self, view_func: Any) -> Any:
        """Extract API instance from a view function."""
        from django_matt.api import DjangoMattAPI

        # ViewSet dispatch
        if hasattr(view_func, "cls"):
            view_func = view_func.cls

        # Check view_class on the callback
        view_class = getattr(view_func, "view_class", None)
        if view_class is not None and hasattr(view_class, "__self__"):
            api = view_class.__self__
            if isinstance(api, DjangoMattAPI):
                return api

        # Check for __self__ directly
        if hasattr(view_func, "__self__"):
            api = view_func.__self__
            if isinstance(api, DjangoMattAPI):
                return api

        # Check for __wrapped__ (decorated views)
        if hasattr(view_func, "__wrapped__"):
            return self._api_from_view(view_func.__wrapped__)

        return None

    def _collect_apis(self, resolver: Any, apis: list[Any]) -> None:
        """Recursively collect DjangoMattAPI instances from URL patterns."""

        for pattern in resolver.url_patterns:
            if isinstance(pattern, URLResolver):
                self._collect_apis(pattern, apis)
            elif isinstance(pattern, URLPattern):
                callback = pattern.callback
                # Check if callback has an include-like URL list
                if hasattr(callback, "url_patterns"):
                    self._collect_apis_from_include(callback.url_patterns, apis)
                # Check for ViewSet-based patterns
                if hasattr(callback, "cls"):
                    callback = callback.cls
                api = self._api_from_view(callback)
                if api is not None and api not in apis:
                    apis.append(api)

    def _collect_apis_from_include(self, patterns: list[Any], apis: list[Any]) -> None:
        """Extract APIs from an included URL list."""

        for pattern in patterns:
            if hasattr(pattern, "callback"):
                api = self._api_from_view(pattern.callback)
                if api is not None and api not in apis:
                    apis.append(api)
            if hasattr(pattern, "url_patterns"):
                self._collect_apis_from_include(pattern.url_patterns, apis)

    def _api_handles_path(self, api_instance: Any, path: str) -> bool:
        """Check whether *api_instance* has a route matching *path*."""

        norm = path.rstrip("/") or "/"
        prefix = getattr(api_instance, "prefix", "")

        for route in getattr(api_instance, "routes", []):
            rpath = (prefix + route["path"]).rstrip("/") or "/"
            if _paths_match(rpath, norm):
                return True

        for ctrl_cls in getattr(api_instance, "controllers", []):
            ctrl_prefix = getattr(ctrl_cls, "prefix", "")
            full_prefix = prefix + ctrl_prefix
            for mname in dir(ctrl_cls):
                meth = getattr(ctrl_cls, mname, None)
                route_info = getattr(meth, "_route_info", None)
                if route_info is None:
                    continue
                rpath = (full_prefix + route_info["path"]).rstrip("/") or "/"
                if _paths_match(rpath, norm):
                    return True

        return False


def _paths_match(pattern: str, actual: str) -> bool:
    """Check if *actual* matches *pattern* accounting for Django path params."""
    import re

    if pattern == actual:
        return True
    pattern = pattern.rstrip("/") or "/"
    actual = actual.rstrip("/") or "/"

    regex_parts = []
    for segment in pattern.strip("/").split("/"):
        if segment.startswith("<") and segment.endswith(">"):
            inner = segment[1:-1]
            if ":" in inner:
                regex_parts.append(r"[^/]+")
            else:
                regex_parts.append(r"[^/]+")
        else:
            regex_parts.append(re.escape(segment))
    regex = "^/" + "/".join(regex_parts) + "$"
    return bool(re.match(regex, actual))
