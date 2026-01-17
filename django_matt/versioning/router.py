"""
Versioned router for django-matt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from django.http import HttpRequest

F = TypeVar("F", bound=Callable[..., Any])


class VersionedRouter:
    """
    A router that groups endpoints by API version.

    Example:
        from django_matt.versioning import VersionedRouter

        # Create versioned routers
        v1 = VersionedRouter(version="1")
        v2 = VersionedRouter(version="2")

        @v1.get("/users")
        def get_users_v1(request):
            return {"users": [...]}

        @v2.get("/users")
        def get_users_v2(request):
            return {"users": [...], "meta": {...}}

        # Include in main API with version prefix
        api.include_router(v1, prefix="/v1")
        api.include_router(v2, prefix="/v2")

    Or use with URL path versioning:
        # Single router with version-specific logic
        router = VersionedRouter()

        @router.get("/users")
        def get_users(request):
            if request.version == "2":
                return {"users": [...], "meta": {...}}
            return {"users": [...]}
    """

    def __init__(
        self,
        version: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Initialize the versioned router.

        Args:
            version: API version for this router
            tags: OpenAPI tags for endpoints in this router
        """
        self.version = version
        self.tags = tags or []
        if version:
            self.tags.append(f"v{version}")
        self._routes: list[dict[str, Any]] = []

    def route(
        self,
        path: str,
        methods: list[str] | None = None,
        **kwargs: Any,
    ) -> Callable[[F], F]:
        """
        Register a route on this versioned router.

        Args:
            path: URL path for the route
            methods: HTTP methods (default: ["GET"])
            **kwargs: Additional route options

        Returns:
            Decorator function
        """
        if methods is None:
            methods = ["GET"]

        def decorator(func: F) -> F:
            route_info = {
                "path": path,
                "methods": methods,
                "endpoint": func,
                "version": self.version,
                "tags": self.tags.copy(),
                **kwargs,
            }
            self._routes.append(route_info)
            return func

        return decorator

    def get(self, path: str, **kwargs: Any) -> Callable[[F], F]:
        """Register a GET route."""
        return self.route(path, methods=["GET"], **kwargs)

    def post(self, path: str, **kwargs: Any) -> Callable[[F], F]:
        """Register a POST route."""
        return self.route(path, methods=["POST"], **kwargs)

    def put(self, path: str, **kwargs: Any) -> Callable[[F], F]:
        """Register a PUT route."""
        return self.route(path, methods=["PUT"], **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Callable[[F], F]:
        """Register a PATCH route."""
        return self.route(path, methods=["PATCH"], **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Callable[[F], F]:
        """Register a DELETE route."""
        return self.route(path, methods=["DELETE"], **kwargs)

    @property
    def routes(self) -> list[dict[str, Any]]:
        """Get all registered routes."""
        return self._routes.copy()

    def get_urls(self) -> list[Any]:
        """
        Generate Django URL patterns for this router.

        Returns:
            List of Django URL patterns
        """
        from django.urls import path

        patterns = []
        for route in self._routes:
            # Create view function that handles the route
            endpoint = route["endpoint"]
            methods = route["methods"]

            def view_wrapper(request: HttpRequest, _endpoint: Callable = endpoint, _methods: list = methods) -> Any:
                if request.method not in _methods:
                    from django.http import HttpResponseNotAllowed
                    return HttpResponseNotAllowed(_methods)
                return _endpoint(request)

            # Clean path for Django (remove leading slash if present)
            url_path = route["path"].lstrip("/")
            patterns.append(path(url_path, view_wrapper))

        return patterns


class VersionedAPI:
    """
    Helper class to manage multiple API versions.

    Example:
        from django_matt.versioning import VersionedAPI

        api = VersionedAPI(
            versions=["1", "2"],
            default_version="1",
        )

        @api.version("1").get("/users")
        def get_users_v1(request):
            return {"users": [...]}

        @api.version("2").get("/users")
        def get_users_v2(request):
            return {"users": [...], "meta": {...}}

        # Include all versions
        api.include_in(main_api, prefix="/api")
    """

    def __init__(
        self,
        versions: list[str] | None = None,
        default_version: str | None = None,
    ) -> None:
        """
        Initialize the versioned API.

        Args:
            versions: List of supported versions
            default_version: Default version when none specified
        """
        self.versions = versions or []
        self.default_version = default_version
        self._routers: dict[str, VersionedRouter] = {}

        # Create routers for each version
        for version in self.versions:
            self._routers[version] = VersionedRouter(version=version)

    def version(self, version: str) -> VersionedRouter:
        """
        Get the router for a specific version.

        Args:
            version: The version string

        Returns:
            VersionedRouter for that version
        """
        if version not in self._routers:
            self._routers[version] = VersionedRouter(version=version)
            if version not in self.versions:
                self.versions.append(version)

        return self._routers[version]

    def include_in(self, api: Any, prefix: str = "") -> None:
        """
        Include all versioned routers in a main API.

        Args:
            api: The main API/router to include into
            prefix: URL prefix for versioned endpoints
        """
        for version, router in self._routers.items():
            version_prefix = f"{prefix}/v{version}".replace("//", "/")
            if hasattr(api, "include_router"):
                api.include_router(router, prefix=version_prefix)

    def get_all_urls(self) -> list[Any]:
        """
        Generate Django URL patterns for all versions.

        Returns:
            List of Django URL patterns with version prefixes
        """
        from django.urls import include, path

        patterns = []
        for version, router in self._routers.items():
            patterns.append(
                path(f"v{version}/", include(router.get_urls()))
            )

        return patterns

    @property
    def routers(self) -> dict[str, VersionedRouter]:
        """Get all versioned routers."""
        return self._routers.copy()
