import inspect
from collections.abc import Callable
from typing import get_type_hints

from django.http import HttpResponse, JsonResponse
from django.urls import path

import orjson
from pydantic import BaseModel, ValidationError

# Cache type hints per function to avoid repeated introspection
_hints_cache: dict[int, dict] = {}

# --- DI auto-wire config (cached at module level) ---
_di_config: bool | None = None


def _get_di_config() -> bool:
    """Check if DI auto-wire is enabled. Cached after first call."""
    global _di_config
    if _di_config is None:
        from django.conf import settings

        matt_config = getattr(settings, "DJANGO_MATT", {})
        _di_config = matt_config.get("DI_AUTO_WIRE", False)
    return _di_config


def _reset_di_config() -> None:
    """Reset the cached DI config. Used in tests."""
    global _di_config
    _di_config = None


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

    def add_route(
        self,
        path_pattern: str,
        endpoint: Callable,
        methods: list[str],
        name: str | None = None,
        response_model: type[BaseModel] | None = None,
        status_code: int = 200,
        tags: list[str] = None,
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
                except (ValueError, orjson.JSONDecodeError):
                    return JsonResponse({"detail": "Invalid JSON"}, status=400)
                except ValidationError as e:
                    return JsonResponse(
                        {"detail": "Validation error", "errors": e.errors()},
                        status=422,
                    )

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

            # Serialize the response
            if isinstance(result, BaseModel):
                result = result.model_dump()
            elif response_model and isinstance(result, dict):
                try:
                    result = response_model(**result).model_dump()
                except ValidationError as e:
                    return JsonResponse(
                        {"detail": "Response validation error", "errors": e.errors()},
                        status=500,
                    )
            elif isinstance(result, list) and result and isinstance(result[0], BaseModel):
                result = [item.model_dump() for item in result]

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

    def get_urls(self):
        """Get Django URL patterns for all registered routes.

        Static (non-parameterized) patterns are always placed before
        parameterized ones so that, e.g., ``/users/me`` is matched before
        ``/users/<str:id>``.  Within each group declaration order is preserved.
        """
        static_patterns = []
        param_patterns = []

        def _append(pattern):
            if self._is_parameterized_path(pattern):
                param_patterns.append(pattern)
            else:
                static_patterns.append(pattern)

        # Add routes from decorators
        for route in self.routes:
            view_func = self._create_view_func(
                endpoint=route["endpoint"],
                response_model=route["response_model"],
                status_code=route["status_code"],
                methods=route["methods"],
            )
            _append(path(route["path"], view_func, name=route["name"]))

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
                _append(
                    path(
                        combined_prefix + route_info["path"],
                        view_func,
                        name=route_info.get("name", method_name),
                    )
                )

        # Static patterns first, then parameterized — preserves ordering within each group.
        return static_patterns + param_patterns


# Route decorators for controller methods
def get(path: str, *, response_model=None, status_code=200, name=None, tags=None):
    """Decorator to mark a controller method as a GET endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["GET"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
        }
        return func

    return decorator


def post(path: str, *, response_model=None, status_code=201, name=None, tags=None):
    """Decorator to mark a controller method as a POST endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["POST"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
        }
        return func

    return decorator


def put(path: str, *, response_model=None, status_code=200, name=None, tags=None):
    """Decorator to mark a controller method as a PUT endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["PUT"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
        }
        return func

    return decorator


def patch(path: str, *, response_model=None, status_code=200, name=None, tags=None):
    """Decorator to mark a controller method as a PATCH endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["PATCH"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
        }
        return func

    return decorator


def delete(path: str, *, response_model=None, status_code=204, name=None, tags=None):
    """Decorator to mark a controller method as a DELETE endpoint."""

    def decorator(func):
        func._route_info = {
            "path": path,
            "methods": ["DELETE"],
            "response_model": response_model,
            "status_code": status_code,
            "name": name,
            "tags": tags or [],
        }
        return func

    return decorator
