"""
Versioning middleware for django-matt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from django.http import JsonResponse

from django_matt.versioning.base import BaseVersioning, VersioningError
from django_matt.versioning.schemes import (
    AcceptHeaderVersioning,
    HeaderVersioning,
    QueryParameterVersioning,
    URLPathVersioning,
)

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


class VersioningMiddleware:
    """
    Middleware to detect and set API version on requests.

    Configure in settings:
        MIDDLEWARE = [
            ...
            'django_matt.versioning.middleware.VersioningMiddleware',
            ...
        ]

        # Versioning configuration
        API_VERSIONING = {
            'scheme': 'url',  # 'url', 'header', 'accept', 'query'
            'default_version': '1',
            'allowed_versions': ['1', '2'],
            # Optional scheme-specific settings
            'header_name': 'X-API-Version',
            'query_param': 'version',
            'version_param': 'version',
        }

    The middleware sets `request.version` with the detected API version.
    """

    # Mapping of scheme names to classes
    SCHEME_MAP: dict[str, type[BaseVersioning]] = {
        "url": URLPathVersioning,
        "path": URLPathVersioning,
        "header": HeaderVersioning,
        "accept": AcceptHeaderVersioning,
        "query": QueryParameterVersioning,
    }

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._versioning: BaseVersioning | None = None
        self._config: dict[str, Any] | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Get versioning configuration from Django settings."""
        if self._config is None:
            try:
                from django.conf import settings

                self._config = getattr(settings, "API_VERSIONING", {})
            except Exception:
                self._config = {}
        return self._config

    @property
    def versioning(self) -> BaseVersioning | None:
        """Get the configured versioning scheme."""
        if self._versioning is not None:
            return self._versioning

        scheme_name = self.config.get("scheme", "url")
        scheme_class = self.SCHEME_MAP.get(scheme_name)

        if scheme_class is None:
            return None

        # Build kwargs for the scheme
        kwargs: dict[str, Any] = {
            "default_version": self.config.get("default_version"),
            "allowed_versions": self.config.get("allowed_versions"),
        }

        # Add scheme-specific settings
        if scheme_name in ("url", "path"):
            if "version_param" in self.config:
                kwargs["version_param"] = self.config["version_param"]
            if "version_regex" in self.config:
                kwargs["version_regex"] = self.config["version_regex"]
        elif scheme_name == "header":
            if "header_name" in self.config:
                kwargs["header_name"] = self.config["header_name"]
        elif scheme_name == "accept":
            if "media_type" in self.config:
                kwargs["media_type"] = self.config["media_type"]
        elif scheme_name == "query":
            if "query_param" in self.config:
                kwargs["query_param"] = self.config["query_param"]

        # Remove None values
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        self._versioning = scheme_class(**kwargs)
        return self._versioning

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and set version attribute.

        Args:
            request: The Django HTTP request

        Returns:
            HttpResponse from the view or error response
        """
        # Default version to None
        request.version = None  # type: ignore

        if self.versioning is not None:
            try:
                request.version = self.versioning.determine_version(request)  # type: ignore
            except VersioningError as exc:
                return self.version_error_response(request, exc)

        response = self.get_response(request)

        # Add version header to response
        if request.version:  # type: ignore
            response["X-API-Version"] = request.version  # type: ignore

        return response

    def version_error_response(self, request: HttpRequest, exc: VersioningError) -> JsonResponse:
        """
        Create an error response for invalid version.

        Args:
            request: The Django HTTP request
            exc: The versioning error

        Returns:
            JsonResponse with 400 status
        """
        return JsonResponse(
            {
                "error": "invalid_version",
                "message": exc.message,
                "version": exc.version,
                "allowed_versions": exc.allowed_versions,
            },
            status=400,
        )


class MultiSchemeVersioningMiddleware:
    """
    Middleware that tries multiple versioning schemes in order.

    Useful when you want to support multiple versioning methods.

    Configure in settings:
        API_VERSIONING = {
            'schemes': ['url', 'header', 'query'],
            'default_version': '1',
            'allowed_versions': ['1', '2'],
        }

    The middleware tries each scheme in order until one returns a version.
    """

    SCHEME_MAP = VersioningMiddleware.SCHEME_MAP

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self._schemes: list[BaseVersioning] | None = None
        self._config: dict[str, Any] | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Get versioning configuration from Django settings."""
        if self._config is None:
            try:
                from django.conf import settings

                self._config = getattr(settings, "API_VERSIONING", {})
            except Exception:
                self._config = {}
        return self._config

    @property
    def schemes(self) -> list[BaseVersioning]:
        """Get configured versioning schemes."""
        if self._schemes is not None:
            return self._schemes

        self._schemes = []
        scheme_names = self.config.get("schemes", ["url"])

        default_version = self.config.get("default_version")
        allowed_versions = self.config.get("allowed_versions")

        for name in scheme_names:
            scheme_class = self.SCHEME_MAP.get(name)
            if scheme_class:
                # Create scheme without default (we'll apply default at the end)
                scheme = scheme_class(
                    default_version=None,
                    allowed_versions=allowed_versions,
                )
                self._schemes.append(scheme)

        # Store default for fallback
        self._default_version = default_version

        return self._schemes

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process the request and set version attribute.

        Args:
            request: The Django HTTP request

        Returns:
            HttpResponse from the view or error response
        """
        request.version = None  # type: ignore

        # Try each scheme in order
        for scheme in self.schemes:
            try:
                version = scheme.determine_version(request)
                if version is not None:
                    request.version = version  # type: ignore
                    break
            except VersioningError:
                # Try next scheme
                continue

        # Apply default if no version found
        if request.version is None:  # type: ignore
            request.version = getattr(self, "_default_version", None)  # type: ignore

        response = self.get_response(request)

        # Add version header to response
        if request.version:  # type: ignore
            response["X-API-Version"] = request.version  # type: ignore

        return response


def versioning_exception_handler(exc: Exception, context: Any = None) -> JsonResponse | None:
    """
    Exception handler for VersioningError.

    Use with django-matt's exception handling:
        from django_matt.versioning import versioning_exception_handler

        api = API(
            exception_handlers={
                VersioningError: versioning_exception_handler,
            }
        )

    Args:
        exc: The exception
        context: Optional context dict

    Returns:
        JsonResponse with error details or None if not a VersioningError
    """
    if not isinstance(exc, VersioningError):
        return None

    return JsonResponse(
        {
            "error": "invalid_version",
            "message": exc.message,
            "version": exc.version,
            "allowed_versions": exc.allowed_versions,
        },
        status=400,
    )
