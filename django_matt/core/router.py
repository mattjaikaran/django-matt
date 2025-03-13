import inspect
import json
from collections.abc import Callable

from django.http import HttpResponse, JsonResponse
from django.urls import path
from pydantic import BaseModel, ValidationError


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

    def get_urls(self):
        """Get Django URL patterns for all registered routes."""
        url_patterns = []

        # Add routes from decorators
        for route in self.routes:
            endpoint = route["endpoint"]
            path_pattern = route["path"]
            name = route["name"]

            # Create a wrapper function that handles request parsing and response serialization
            def create_view_func(endpoint, response_model, status_code):
                async def view_func(request, *args, **kwargs):
                    # Parse request body if it exists
                    if request.body and request.content_type == "application/json":
                        try:
                            body_data = json.loads(request.body)
                            kwargs["body"] = body_data
                        except json.JSONDecodeError:
                            return JsonResponse({"detail": "Invalid JSON"}, status=400)

                    # Call the endpoint
                    if inspect.iscoroutinefunction(endpoint):
                        result = await endpoint(request, *args, **kwargs)
                    else:
                        result = endpoint(request, *args, **kwargs)

                    # Serialize the response if needed
                    if response_model and isinstance(result, dict):
                        try:
                            result = response_model(**result).model_dump()
                        except ValidationError as e:
                            return JsonResponse(
                                {
                                    "detail": "Response validation error",
                                    "errors": e.errors(),
                                },
                                status=500,
                            )

                    # Return the response
                    if isinstance(result, HttpResponse):
                        return result
                    else:
                        return JsonResponse(result, status=status_code, safe=False)

                return view_func

            view_func = create_view_func(
                endpoint=endpoint,
                response_model=route["response_model"],
                status_code=route["status_code"],
            )

            url_patterns.append(path(path_pattern, view_func, name=name))

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

                # Check if the method has route metadata
                route_info = getattr(method, "_route_info", None)
                if not route_info:
                    continue

                path_pattern = combined_prefix + route_info["path"]
                name = route_info.get("name", method_name)
                response_model = route_info.get("response_model")
                status_code = route_info.get("status_code", 200)

                # Create a wrapper function that handles request parsing and response serialization
                def create_view_func(method, response_model, status_code):
                    async def view_func(request, *args, **kwargs):
                        # Parse request body if it exists
                        if request.body and request.content_type == "application/json":
                            try:
                                body_data = json.loads(request.body)
                                kwargs["body"] = body_data
                            except json.JSONDecodeError:
                                return JsonResponse(
                                    {"detail": "Invalid JSON"}, status=400
                                )

                        # Call the method
                        if inspect.iscoroutinefunction(method):
                            result = await method(request, *args, **kwargs)
                        else:
                            result = method(request, *args, **kwargs)

                        # Serialize the response if needed
                        if response_model and isinstance(result, dict):
                            try:
                                result = response_model(**result).model_dump()
                            except ValidationError as e:
                                return JsonResponse(
                                    {
                                        "detail": "Response validation error",
                                        "errors": e.errors(),
                                    },
                                    status=500,
                                )

                        # Return the response
                        if isinstance(result, HttpResponse):
                            return result
                        else:
                            return JsonResponse(result, status=status_code, safe=False)

                    return view_func

                view_func = create_view_func(
                    method=method,
                    response_model=response_model,
                    status_code=status_code,
                )

                url_patterns.append(path(path_pattern, view_func, name=name))

        return url_patterns


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
