import inspect
import logging
from collections.abc import Callable
from typing import get_type_hints

import django
from django.http import HttpResponse, JsonResponse
from django.urls import path

import orjson
from pydantic import BaseModel, ValidationError

from django_matt._accel import HAS_RUST, RadixRouter

logger = logging.getLogger("django_matt.router")

# Django version detection for LoginRequiredMiddleware compatibility
_DJANGO_VERSION = tuple(int(x) for x in django.__version__.split(".")[:2])

_login_not_required: Callable | None = None
if _DJANGO_VERSION >= (5, 1):
    try:
        from django.contrib.auth.decorators import (
            login_not_required as _login_not_required,  # type: ignore[assignment]
        )
    except ImportError:
        pass

# Cache type hints per function to avoid repeated introspection
_hints_cache: dict[int, dict] = {}

from django_matt.conf import get_matt_setting
from django_matt.conf import reset_cache as _reset_di_config  # noqa: F401 — backward compat


def _get_di_config() -> bool:
    """Check if DI auto-wire is enabled."""
    return get_matt_setting("DI_AUTO_WIRE", False)


def _analyze_di_params(endpoint: Callable) -> dict | None:
    """
    Analyze endpoint for DI parameters. Returns dict of params needing resolution,
    or None if no DI params found. Called once at registration, not per-request.
    """
    if not _get_di_config():
        return None

    from django_matt.di.depends import DependencyMarker

    sig = inspect.signature(endpoint)
    di_params = {}

    for param_name, param in sig.parameters.items():
        # Skip self, cls, request, body, *args, **kwargs
        if param_name in ("self", "cls", "request", "body"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        # Check for Depends() marker in default value
        if isinstance(param.default, DependencyMarker):
            di_params[param_name] = param.default

    return di_params if di_params else None


def get_body_schema(endpoint: Callable) -> type[BaseModel] | None:
    """
    Get the Pydantic model type for the 'body' parameter of an endpoint.

    Results are cached per-function to avoid repeated get_type_hints() calls.
    """
    key = id(endpoint)
    if key not in _hints_cache:
        try:
            _hints_cache[key] = get_type_hints(endpoint)
        except Exception:
            _hints_cache[key] = {}

    hints = _hints_cache[key]
    body_type = hints.get("body")
    if body_type is not None and isinstance(body_type, type) and issubclass(body_type, BaseModel):
        return body_type
    return None


def parse_body(body_data: dict, schema: type[BaseModel] | None) -> BaseModel | dict:
    """
    Parse body data into a Pydantic model if schema is provided.

    Returns the original dict if no schema or parsing fails.
    """
    if schema is not None:
        try:
            return schema(**body_data)
        except ValidationError:
            raise  # Re-raise to be handled by the view function
    return body_data


class APIRouter:
    """
    Main router class for Django Matt framework.

    This router handles the registration of API endpoints and provides
    a way to include other routers.
    """

    def __init__(self, prefix: str = "", tags: list[str] = None):
        self.prefix = prefix
        self.tags = tags or []
        self.routes = []
        self.controllers = []
        # Rust-accelerated radix tree router (built lazily in get_urls)
        self._radix_router: RadixRouter | None = None
        self._radix_endpoints: dict[str, Callable] = {}

    def add_route(
        self,
        path_pattern: str,
        endpoint: Callable,
        methods: list[str],
        name: str | None = None,
        response_model: type[BaseModel] | None = None,
        status_code: int = 200,
        tags: list[str] = None,
        responses: dict[int, type[BaseModel]] | None = None,
    ):
        """Add a route to the router."""
        route = {
            "path": path_pattern,
            "endpoint": endpoint,
            "methods": methods,
            "name": name or endpoint.__name__,
            "response_model": response_model,
            "status_code": status_code,
            "tags": tags or [],
            "responses": responses or {},
        }
        self.routes.append(route)
        return endpoint

    def get(
        self,
        path_pattern: str,
        *,
        response_model: type[BaseModel] | None = None,
        status_code: int = 200,
        name: str | None = None,
        tags: list[str] = None,
        responses: dict[int, type[BaseModel]] | None = None,
    ):
        """Register a GET endpoint."""

        def decorator(endpoint):
            return self.add_route(
                path_pattern=path_pattern,
                endpoint=endpoint,
                methods=["GET"],
                name=name,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                responses=responses,
            )

        return decorator

    def post(
        self,
        path_pattern: str,
        *,
        response_model: type[BaseModel] | None = None,
        status_code: int = 201,
        name: str | None = None,
        tags: list[str] = None,
        responses: dict[int, type[BaseModel]] | None = None,
    ):
        """Register a POST endpoint."""

        def decorator(endpoint):
            return self.add_route(
                path_pattern=path_pattern,
                endpoint=endpoint,
                methods=["POST"],
                name=name,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                responses=responses,
            )

        return decorator

    def put(
        self,
        path_pattern: str,
        *,
        response_model: type[BaseModel] | None = None,
        status_code: int = 200,
        name: str | None = None,
        tags: list[str] = None,
        responses: dict[int, type[BaseModel]] | None = None,
    ):
        """Register a PUT endpoint."""

        def decorator(endpoint):
            return self.add_route(
                path_pattern=path_pattern,
                endpoint=endpoint,
                methods=["PUT"],
                name=name,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                responses=responses,
            )

        return decorator

    def patch(
        self,
        path_pattern: str,
        *,
        response_model: type[BaseModel] | None = None,
        status_code: int = 200,
        name: str | None = None,
        tags: list[str] = None,
        responses: dict[int, type[BaseModel]] | None = None,
    ):
        """Register a PATCH endpoint."""

        def decorator(endpoint):
            return self.add_route(
                path_pattern=path_pattern,
                endpoint=endpoint,
                methods=["PATCH"],
                name=name,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                responses=responses,
            )

        return decorator

    def delete(
        self,
        path_pattern: str,
        *,
        response_model: type[BaseModel] | None = None,
        status_code: int = 204,
        name: str | None = None,
        tags: list[str] = None,
        responses: dict[int, type[BaseModel]] | None = None,
    ):
        """Register a DELETE endpoint."""

        def decorator(endpoint):
            return self.add_route(
                path_pattern=path_pattern,
                endpoint=endpoint,
                methods=["DELETE"],
                name=name,
                response_model=response_model,
                status_code=status_code,
                tags=tags,
                responses=responses,
            )

        return decorator

    def include_router(self, router: "APIRouter", prefix: str = ""):
        """Include another router in this router."""
        combined_prefix = self.prefix + prefix
        for route in router.routes:
            route_copy = route.copy()
            route_copy["path"] = combined_prefix + route["path"]
            route_copy["tags"] = route["tags"] + self.tags
            self.routes.append(route_copy)

        for controller in router.controllers:
            self.controllers.append(controller)

    def register_controller(self, controller_class: type):
        """Register a controller class with the router."""
        self.controllers.append(controller_class)
        return controller_class

    @staticmethod
    def _create_view_func(endpoint, response_model, status_code, methods=None):
        """Create an async view function that handles parsing and serialization."""
        body_schema = get_body_schema(endpoint)
        is_coro = inspect.iscoroutinefunction(endpoint)
        # Pre-compute allowed methods set for O(1) lookup
        allowed_methods = frozenset(m.upper() for m in methods) if methods else None
        # Analyze DI params once at registration — not per-request
        di_params = _analyze_di_params(endpoint)

        async def view_func(request, *args, _di_params=di_params, **kwargs):
            # Enforce HTTP method
            if allowed_methods and request.method not in allowed_methods:
                response = JsonResponse(
                    {"detail": "Method not allowed"}, status=405
                )
                response["Allow"] = ", ".join(sorted(allowed_methods))
                return response

            # Parse request body with orjson (single parse)
            if request.body and request.content_type == "application/json":
                try:
                    body_data = orjson.loads(request.body)
                    kwargs["body"] = parse_body(body_data, body_schema)
                except ValidationError as e:
                    return JsonResponse(
                        {"detail": "Validation error", "errors": e.errors()},
                        status=422,
                    )
                except ValueError:
                    return JsonResponse({"detail": "Invalid JSON"}, status=400)

            # Call the endpoint (with DI resolution if needed)
            if _di_params is not None:
                from django_matt.di.container import _scoped_instances
                from django_matt.di.depends import aresolve_dependencies

                # Create per-request scope if not already set
                scope_token = None
                if _scoped_instances.get() is None:
                    scope_token = _scoped_instances.set({})

                try:
                    # Resolve DI dependencies
                    deps = await aresolve_dependencies(
                        endpoint,
                        request=request,
                        **kwargs,
                    )
                    kwargs.update(deps)

                    # Call the endpoint
                    if is_coro:
                        result = await endpoint(request, *args, **kwargs)
                    else:
                        result = endpoint(request, *args, **kwargs)
                finally:
                    if scope_token is not None:
                        _scoped_instances.reset(scope_token)
            # Original non-DI path
            elif is_coro:
                result = await endpoint(request, *args, **kwargs)
            else:
                result = endpoint(request, *args, **kwargs)

            # Early return for HttpResponse
            if isinstance(result, HttpResponse):
                return result

            # Serialize the response (use aliases for camelCase when enabled)
            from django_matt.core.schema import _get_camel_case_config

            _by_alias = _get_camel_case_config()
            if isinstance(result, BaseModel):
                result = result.model_dump(by_alias=_by_alias)
            elif response_model and isinstance(result, dict):
                try:
                    result = response_model(**result).model_dump(by_alias=_by_alias)
                except ValidationError as e:
                    return JsonResponse(
                        {"detail": "Response validation error", "errors": e.errors()},
                        status=500,
                    )
            elif isinstance(result, list) and result and isinstance(result[0], BaseModel):
                result = [item.model_dump(by_alias=_by_alias) for item in result]

            return JsonResponse(result, status=status_code, safe=False)

        return view_func

    @staticmethod
    def _is_parameterized_path(url_pattern) -> bool:
        """Return True if the Django URLPattern contains a path converter (e.g. <str:id>)."""
        # RoutePattern exposes _route; check for '<' which signals a converter.
        route = getattr(url_pattern.pattern, "_route", None)
        if route is None:
            # Fallback: inspect the string representation of the pattern.
            route = str(url_pattern.pattern)
        return "<" in route

    def get_urls(self, csrf_exempt: bool = False):
        """Get Django URL patterns for all registered routes.

        Routes with the same URL path pattern are merged into a single Django
        URL pattern that dispatches by HTTP method. This prevents Django from
        matching the first registered pattern and returning 405 for other
        methods on the same path.

        Static (non-parameterized) patterns are always placed before
        parameterized ones so that, e.g., ``/users/me`` is matched before
        ``/users/<str:id>``.  Within each group declaration order is preserved.

        Args:
            csrf_exempt: When True, set ``_csrf_exempt = True`` on every view
                         function so that CSRF middleware skips those endpoints.
                         This is set automatically by ``MattAPI`` when
                         ``csrf=False`` (the default).
        """
        # Collect all (path_pattern, view_func, name, methods) entries first,
        # then merge entries that share the same path_pattern.
        # Use a list to preserve registration order.
        path_entries: list[tuple[str, Callable, str, list[str]]] = []

        # Add routes from decorators
        for route in self.routes:
            view_func = self._create_view_func(
                endpoint=route["endpoint"],
                response_model=route["response_model"],
                status_code=route["status_code"],
                methods=route["methods"],
            )
            if csrf_exempt:
                view_func._csrf_exempt = True
            if _login_not_required is not None:
                view_func = _login_not_required(view_func)
            path_entries.append(
                (route["path"], view_func, route["name"], route["methods"])
            )

        # Add routes from controllers
        for controller_class in self.controllers:
            controller = controller_class()
            controller_prefix = getattr(controller, "prefix", "")
            combined_prefix = self.prefix + controller_prefix

            for method_name in dir(controller):
                if method_name.startswith("_"):
                    continue

                method = getattr(controller, method_name)
                if not callable(method):
                    continue

                route_info = getattr(method, "_route_info", None)
                if not route_info:
                    continue

                view_func = self._create_view_func(
                    endpoint=method,
                    response_model=route_info.get("response_model"),
                    status_code=route_info.get("status_code", 200),
                    methods=route_info.get("methods"),
                )
                if csrf_exempt:
                    view_func._csrf_exempt = True
                if _login_not_required is not None:
                    view_func = _login_not_required(view_func)
                full_path = combined_prefix + route_info["path"]
                path_entries.append(
                    (
                        full_path,
                        view_func,
                        route_info.get("name", method_name),
                        route_info.get("methods", []),
                    )
                )

        # Merge entries with the same path into a single dispatch view.
        # Preserves first-seen order for each unique path.
        from collections import OrderedDict

        grouped: OrderedDict[str, list[tuple[Callable, str, list[str]]]] = (
            OrderedDict()
        )
        for url_path, vf, name, methods in path_entries:
            if url_path not in grouped:
                grouped[url_path] = []
            grouped[url_path].append((vf, name, methods))

        static_patterns = []
        param_patterns = []

        def _append(pattern):
            if self._is_parameterized_path(pattern):
                param_patterns.append(pattern)
            else:
                static_patterns.append(pattern)

        for url_path, entries in grouped.items():
            if len(entries) == 1:
                # Single method — use the view directly
                vf, name, _methods = entries[0]
                _append(path(url_path, vf, name=name))
            else:
                # Multiple methods on the same path — create a dispatch view
                method_map: dict[str, Callable] = {}
                first_name = entries[0][1]
                for vf, _name, methods in entries:
                    for m in methods:
                        method_map[m.upper()] = vf

                async def _dispatch_view(
                    request,
                    *args,
                    _method_map=method_map,
                    **kwargs,
                ):
                    handler = _method_map.get(request.method)
                    if handler is None:
                        response = JsonResponse(
                            {"detail": "Method not allowed"}, status=405
                        )
                        response["Allow"] = ", ".join(
                            sorted(_method_map.keys())
                        )
                        return response
                    return await handler(request, *args, **kwargs)

                if csrf_exempt:
                    _dispatch_view._csrf_exempt = True
                if _login_not_required is not None:
                    _dispatch_view = _login_not_required(_dispatch_view)
                _append(path(url_path, _dispatch_view, name=first_name))

        # Static patterns first, then parameterized — preserves ordering within each group.
        django_patterns = static_patterns + param_patterns

        # Build Rust radix tree alongside Django patterns for fast dispatch
        if HAS_RUST and RadixRouter is not None:
            self._build_radix_router(path_entries, csrf_exempt)

        return django_patterns

    def _build_radix_router(
        self,
        path_entries: list[tuple[str, Callable, str, list[str]]],
        csrf_exempt: bool,
    ) -> None:
        """Build the Rust radix tree from collected path entries.

        Populates ``self._radix_router`` and ``self._radix_endpoints`` so that
        ``radix_dispatch`` can look up the correct view function in O(path) time.
        """
        self._radix_router = RadixRouter()
        self._radix_endpoints = {}

        for url_path, view_func, name, methods in path_entries:
            # Convert Django path syntax (<str:id>) to radix syntax ({id})
            radix_path = self._django_to_radix_pattern(url_path)
            for method in methods:
                endpoint_key = f"{method.upper()}:{radix_path}"
                self._radix_endpoints[endpoint_key] = view_func
                self._radix_router.add_route(method.upper(), radix_path, endpoint_key)

        logger.debug(
            "Rust radix router built: %d routes", self._radix_router.route_count
        )

    @staticmethod
    def _django_to_radix_pattern(django_path: str) -> str:
        """Convert Django URL pattern to radix tree pattern.

        ``users/<str:id>/posts`` → ``/users/{id}/posts``
        ``users/<int:pk>``       → ``/users/{pk}``
        """
        import re as _re

        # Ensure leading slash
        p = "/" + django_path.lstrip("/")
        # <type:name> → {name}
        p = _re.sub(r"<\w+:(\w+)>", r"{\1}", p)
        # <name> (no type) → {name}
        p = _re.sub(r"<(\w+)>", r"{\1}", p)
        # Strip trailing slash for consistent matching
        return p.rstrip("/") or "/"

    def radix_dispatch(self, request_method: str, request_path: str):
        """Fast route lookup using the Rust radix tree.

        Returns ``(view_func, kwargs)`` or ``None`` if no match.
        Used by ``MattAPI`` middleware or ASGI handler to bypass Django's
        URL resolver for registered API routes.
        """
        if self._radix_router is None:
            return None

        result = self._radix_router.match_route(request_method, request_path)
        if result is None:
            return None

        endpoint_key, params = result
        view_func = self._radix_endpoints.get(endpoint_key)
        if view_func is None:
            return None

        return view_func, dict(params)


# Route decorators for controller methods
def get(
    path: str,
    *,
    response_model: type[BaseModel] | None = None,
    status_code: int = 200,
    name: str | None = None,
    tags: list[str] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
):
    """Decorator to mark a controller method as a GET endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["GET"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
            "responses": responses or {},
        }
        return func

    return decorator


def post(
    path: str,
    *,
    response_model: type[BaseModel] | None = None,
    status_code: int = 201,
    name: str | None = None,
    tags: list[str] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
):
    """Decorator to mark a controller method as a POST endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["POST"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
            "responses": responses or {},
        }
        return func

    return decorator


def put(
    path: str,
    *,
    response_model: type[BaseModel] | None = None,
    status_code: int = 200,
    name: str | None = None,
    tags: list[str] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
):
    """Decorator to mark a controller method as a PUT endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["PUT"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
            "responses": responses or {},
        }
        return func

    return decorator


def patch(
    path: str,
    *,
    response_model: type[BaseModel] | None = None,
    status_code: int = 200,
    name: str | None = None,
    tags: list[str] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
):
    """Decorator to mark a controller method as a PATCH endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["PATCH"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
            "responses": responses or {},
        }
        return func

    return decorator


def delete(
    path: str,
    *,
    response_model: type[BaseModel] | None = None,
    status_code: int = 204,
    name: str | None = None,
    tags: list[str] | None = None,
    responses: dict[int, type[BaseModel]] | None = None,
):
    """Decorator to mark a controller method as a DELETE endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["DELETE"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
            "responses": responses or {},
        }
        return func

    return decorator
