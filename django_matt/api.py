"""
Django Matt API class.

The main entry point for creating APIs with Django Matt.
"""

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.urls import path

from django_matt.core.router import APIRouter
from django_matt.openapi.docs import get_openapi_json, get_redoc, get_swagger_ui
from django_matt.openapi.schema import OpenAPISchema
from django_matt.slim import Mode, ModuleRegistry


class MattAPI(APIRouter):
    """
    Main API class for Django Matt.

    Extends APIRouter with OpenAPI documentation and additional configuration.

    Supports Slim Mode via the ``mode`` parameter:
        - "full" (default): all middleware, URLs, and modules loaded
        - "minimal": only core + explicitly activated modules
        - "auto": detect from DJANGO_MATT settings which modules are in use

    Usage:
        from django_matt import MattAPI

        api = MattAPI(
            title="My API",
            version="1.0.0",
            description="My awesome API",
        )

        # Slim mode — only load what you use
        api = MattAPI(title="My API", mode="minimal")
        api.activate("auth", "cors")

        @api.get("/hello")
        def hello(request):
            return {"message": "Hello, World!"}

        # In urls.py
        urlpatterns = [
            path("api/", include(api.urls)),
        ]
    """

    def __init__(
        self,
        title: str = "Django Matt API",
        version: str = "1.0.0",
        description: str = "",
        prefix: str = "",
        tags: list[str] | None = None,
        # OpenAPI settings
        docs_url: str | None = "/docs",
        redoc_url: str | None = "/redoc",
        openapi_url: str | None = "/openapi.json",
        terms_of_service: str | None = None,
        contact: dict[str, str] | None = None,
        license_info: dict[str, str] | None = None,
        servers: list[dict[str, str]] | None = None,
        # Auth settings
        auth: Any = None,
        # CSRF settings
        csrf: bool = False,
        # Health check endpoint
        health_url: str | None = "/health",
        # Slim mode
        mode: Mode = "full",
    ):
        super().__init__(prefix=prefix, tags=tags)

        self._resource_viewsets: list[type] = []

        self.title = title
        self.version = version
        self.description = description
        self.docs_url = docs_url
        self.redoc_url = redoc_url
        self.openapi_url = openapi_url
        self.terms_of_service = terms_of_service
        self.contact = contact
        self.license_info = license_info
        self.servers = servers
        self.auth = auth
        self.csrf = csrf
        self.health_url = health_url

        self._openapi_schema: dict | None = None

        # Module registry for slim mode
        self._registry = ModuleRegistry(mode=mode)

        # Auto-activate auth module if auth is configured on the API
        if auth is not None:
            self._registry.activate("auth")

    # ------------------------------------------------------------------
    # Module registry API
    # ------------------------------------------------------------------

    @property
    def mode(self) -> Mode:
        """Return the current loading mode."""
        return self._registry.mode

    @property
    def modules(self) -> frozenset[str]:
        """Return the set of active module names."""
        return self._registry.active_modules

    @property
    def registry(self) -> ModuleRegistry:
        """Direct access to the module registry."""
        return self._registry

    def activate(self, *modules: str) -> "MattAPI":
        """
        Activate one or more modules.

        Returns self for chaining:
            api = MattAPI(mode="minimal").activate("auth", "cors")
        """
        self._registry.activate(*modules)
        return self

    def deactivate(self, *modules: str) -> "MattAPI":
        """Deactivate one or more non-core modules."""
        self._registry.deactivate(*modules)
        return self

    # ------------------------------------------------------------------
    # OpenAPI
    # ------------------------------------------------------------------

    @property
    def openapi_schema(self) -> dict:
        """Get or generate the OpenAPI schema."""
        if self._openapi_schema is None:
            self._openapi_schema = self._generate_openapi_schema()
        return self._openapi_schema

    def _generate_openapi_schema(self) -> dict:
        """Generate OpenAPI schema from registered routes."""
        schema = OpenAPISchema(
            title=self.title,
            version=self.version,
            description=self.description,
            terms_of_service=self.terms_of_service,
            contact=self.contact,
            license_info=self.license_info,
            servers=self.servers,
        )

        # Add routes from this router
        schema.add_routes(self.routes)

        # Add routes from registered controllers
        for controller_class in self.controllers:
            schema.add_controller(controller_class)

        return schema.build()

    @property
    def urls(self) -> list:
        """Return URL patterns for use in Django's urlpatterns."""
        return self.get_urls()

    def add_router(self, router: "APIRouter", prefix: str = "") -> None:
        """Add another router's routes to this API."""
        self.include_router(router, prefix=prefix)
        # Invalidate cached schema
        self._openapi_schema = None

    def register_controllers(self, *controller_classes: type) -> None:
        """Register multiple controllers at once."""
        for controller_class in controller_classes:
            self.register_controller(controller_class)
        # Invalidate cached schema
        self._openapi_schema = None

    def resource(self, model_or_none=None, prefix: str | None = None, **kwargs):
        """
        Register a model as a CRUD resource.

        Usage:
            api.resource(Product)
            api.resource(Product, prefix="/products", permissions={"delete": [IsAdmin]})

        Returns the generated APIViewSet subclass.
        """
        from django_matt.resources.resource import resource as _resource

        if model_or_none is not None:
            viewset_cls = _resource(model_or_none, prefix=prefix, **kwargs)
            self._resource_viewsets.append(viewset_cls)
            return viewset_cls

        # Called as @api.resource(prefix="/products") decorator
        def decorator(cls):
            viewset_cls = _resource(self, prefix=prefix, **kwargs)(cls)
            return viewset_cls

        return decorator

    def get_urls(self) -> list:
        """Get Django URL patterns including documentation and resource endpoints.

        When ``csrf=False`` (the default), all registered view functions will
        have ``_csrf_exempt = True`` set so that Django's CSRF middleware (and
        django_matt's own CSRFMiddleware) skips CSRF validation on API endpoints.
        JWT-authenticated APIs don't use cookies, so CSRF protection is not
        needed and would reject legitimate clients that don't send a CSRF token.
        """
        # csrf=False means "do not require CSRF", so we exempt all views
        csrf_exempt = not self.csrf
        url_patterns = super().get_urls(csrf_exempt=csrf_exempt)

        # Add resource ViewSet URLs
        for viewset_cls in self._resource_viewsets:
            url_patterns.extend(viewset_cls.as_urls())

        # Add health check endpoint (only if observability is active)
        if self.health_url and self._registry.is_active("observability"):
            from django_matt.observability.views import health_view

            url_patterns.append(
                path(self.health_url.lstrip("/"), health_view, name="health-check")
            )

        # Add OpenAPI JSON endpoint (always active — part of core)
        if self.openapi_url and self._registry.is_active("openapi"):

            def openapi_view(request: HttpRequest) -> HttpResponse:
                return get_openapi_json(self.openapi_schema)

            url_patterns.append(
                path(self.openapi_url.lstrip("/"), openapi_view, name="openapi-schema")
            )

        # Add Swagger UI endpoint
        if self.docs_url and self._registry.is_active("docs"):

            def docs_view(request: HttpRequest) -> HttpResponse:
                openapi_path = self.prefix + (self.openapi_url or "/openapi.json")
                return get_swagger_ui(
                    openapi_url=openapi_path,
                    title=f"{self.title} - Docs",
                )

            url_patterns.append(path(self.docs_url.lstrip("/"), docs_view, name="swagger-ui"))

        # Add ReDoc endpoint
        if self.redoc_url and self._registry.is_active("redoc"):

            def redoc_view(request: HttpRequest) -> HttpResponse:
                openapi_path = self.prefix + (self.openapi_url or "/openapi.json")
                return get_redoc(
                    openapi_url=openapi_path,
                    title=f"{self.title} - ReDoc",
                )

            url_patterns.append(path(self.redoc_url.lstrip("/"), redoc_view, name="redoc"))

        return url_patterns

    def exception_handler(self, exc_class: type[Exception]) -> Callable:
        """
        Decorator to register an exception handler.

        Usage:
            @api.exception_handler(ValueError)
            def handle_value_error(request, exc):
                return JsonResponse({"error": str(exc)}, status=400)
        """

        def decorator(handler: Callable) -> Callable:
            if not hasattr(self, "_exception_handlers"):
                self._exception_handlers = {}
            self._exception_handlers[exc_class] = handler
            return handler

        return decorator
