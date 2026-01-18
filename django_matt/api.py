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


class MattAPI(APIRouter):
    """
    Main API class for Django Matt.

    Extends APIRouter with OpenAPI documentation and additional configuration.

    Usage:
        from django_matt import MattAPI

        api = MattAPI(
            title="My API",
            version="1.0.0",
            description="My awesome API",
        )

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
    ):
        super().__init__(prefix=prefix, tags=tags)

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

        self._openapi_schema: dict | None = None

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

    def get_urls(self) -> list:
        """Get Django URL patterns including documentation endpoints."""
        url_patterns = super().get_urls()

        # Add OpenAPI JSON endpoint
        if self.openapi_url:

            def openapi_view(request: HttpRequest) -> HttpResponse:
                return get_openapi_json(self.openapi_schema)

            url_patterns.append(
                path(self.openapi_url.lstrip("/"), openapi_view, name="openapi-schema")
            )

        # Add Swagger UI endpoint
        if self.docs_url:

            def docs_view(request: HttpRequest) -> HttpResponse:
                openapi_path = self.prefix + (self.openapi_url or "/openapi.json")
                return get_swagger_ui(
                    openapi_url=openapi_path,
                    title=f"{self.title} - Docs",
                )

            url_patterns.append(path(self.docs_url.lstrip("/"), docs_view, name="swagger-ui"))

        # Add ReDoc endpoint
        if self.redoc_url:

            def redoc_view(request: HttpRequest) -> HttpResponse:
                openapi_path = self.prefix + (self.openapi_url or "/openapi.json")
                return get_redoc(
                    openapi_url=openapi_path,
                    title=f"{self.title} - ReDoc",
                )

            url_patterns.append(path(self.redoc_url.lstrip("/"), redoc_view, name="redoc"))

        return url_patterns

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
