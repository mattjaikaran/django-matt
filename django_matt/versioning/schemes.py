# file-length-max: 450
"""
Concrete versioning scheme implementations for django-matt.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from django_matt.versioning.base import BaseVersioning

if TYPE_CHECKING:
    from django.http import HttpRequest


class URLPathVersioning(BaseVersioning):
    """
    Version specified in the URL path.

    Example URLs:
        /api/v1/users/
        /api/v2/users/
        /v1/items/
        /v2.1/items/

    Configure the version regex pattern to match your URL structure:
        versioning = URLPathVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            version_param="version",  # URL parameter name
        )

    In your urls.py:
        path('api/<str:version>/users/', views.users),
        # or with regex:
        re_path(r'^api/v(?P<version>[0-9]+)/users/$', views.users),
    """

    # URL parameter name containing the version
    version_param: str = "version"

    # Regex pattern to extract version from URL
    # Matches: v1, v2, v1.0, v2.1, 1, 2, 1.0, 2.1
    version_regex: str = r"v?(?P<version>[0-9]+(?:\.[0-9]+)*)"

    def __init__(
        self,
        default_version: str | None = None,
        allowed_versions: list[str] | None = None,
        version_param: str | None = None,
        version_regex: str | None = None,
    ) -> None:
        super().__init__(default_version, allowed_versions)
        if version_param is not None:
            self.version_param = version_param
        if version_regex is not None:
            self.version_regex = version_regex

    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Extract version from URL path.

        Args:
            request: The Django HTTP request
            **kwargs: May contain resolver_match with URL parameters

        Returns:
            Version string or None
        """
        # Try to get version from URL kwargs (passed from URL resolver)
        if self.version_param in kwargs:
            version = kwargs[self.version_param]
            # Remove 'v' prefix if present
            if version and version.lower().startswith("v"):
                version = version[1:]
            return self.validate_version(version)

        # Try to get from resolver_match
        if hasattr(request, "resolver_match") and request.resolver_match:
            url_kwargs = request.resolver_match.kwargs
            if self.version_param in url_kwargs:
                version = url_kwargs[self.version_param]
                if version and version.lower().startswith("v"):
                    version = version[1:]
                return self.validate_version(version)

        # Try to extract from path using regex
        match = re.search(self.version_regex, request.path)
        if match:
            version = match.group("version")
            return self.validate_version(version)

        return self.validate_version(None)

    def reverse(
        self,
        viewname: str,
        version: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Reverse URL with version in path.

        Args:
            viewname: The name of the view
            version: The version to include
            **kwargs: URL parameters

        Returns:
            URL string with version
        """
        from django.urls import reverse

        version = version or self.default_version
        if version:
            kwargs[self.version_param] = f"v{version}"

        return reverse(viewname, kwargs=kwargs)


class HeaderVersioning(BaseVersioning):
    """
    Version specified in a custom HTTP header.

    Example:
        GET /api/users/
        X-API-Version: 2.0

    Configure:
        versioning = HeaderVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            header_name="X-API-Version",
        )
    """

    # HTTP header name (will be converted to HTTP_X_API_VERSION format)
    header_name: str = "X-API-Version"

    def __init__(
        self,
        default_version: str | None = None,
        allowed_versions: list[str] | None = None,
        header_name: str | None = None,
    ) -> None:
        super().__init__(default_version, allowed_versions)
        if header_name is not None:
            self.header_name = header_name

    def _get_meta_key(self) -> str:
        """Convert header name to Django META key format."""
        # X-API-Version -> HTTP_X_API_VERSION
        return "HTTP_" + self.header_name.upper().replace("-", "_")

    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Extract version from HTTP header.

        Args:
            request: The Django HTTP request
            **kwargs: Additional arguments (unused)

        Returns:
            Version string or None
        """
        meta_key = self._get_meta_key()
        version = request.META.get(meta_key)

        if version and version.lower().startswith("v"):
            version = version[1:]

        return self.validate_version(version)


class AcceptHeaderVersioning(BaseVersioning):
    """
    Version specified in the Accept header using media type parameters.

    Example:
        GET /api/users/
        Accept: application/json; version=2.0

    Or using vendor media type:
        Accept: application/vnd.myapi.v2+json

    Configure:
        versioning = AcceptHeaderVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            media_type="application/json",
        )
    """

    # Expected media type base
    media_type: str = "application/json"

    # Regex to extract version from Accept header
    # Matches: version=2, version=2.0, v2, vnd.api.v2+json
    version_regex: str = r"(?:version=|\.v)([0-9]+(?:\.[0-9]+)*)"

    def __init__(
        self,
        default_version: str | None = None,
        allowed_versions: list[str] | None = None,
        media_type: str | None = None,
        version_regex: str | None = None,
    ) -> None:
        super().__init__(default_version, allowed_versions)
        if media_type is not None:
            self.media_type = media_type
        if version_regex is not None:
            self.version_regex = version_regex

    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Extract version from Accept header.

        Args:
            request: The Django HTTP request
            **kwargs: Additional arguments (unused)

        Returns:
            Version string or None
        """
        accept = request.META.get("HTTP_ACCEPT", "")

        # Try to extract version from Accept header
        match = re.search(self.version_regex, accept)
        if match:
            version = match.group(1)
            return self.validate_version(version)

        return self.validate_version(None)


class QueryParameterVersioning(BaseVersioning):
    """
    Version specified in URL query parameters.

    Example:
        GET /api/users/?version=2
        GET /api/users/?v=2

    Configure:
        versioning = QueryParameterVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
            query_param="version",
        )
    """

    # Query parameter name
    query_param: str = "version"

    def __init__(
        self,
        default_version: str | None = None,
        allowed_versions: list[str] | None = None,
        query_param: str | None = None,
    ) -> None:
        super().__init__(default_version, allowed_versions)
        if query_param is not None:
            self.query_param = query_param

    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Extract version from query parameter.

        Args:
            request: The Django HTTP request
            **kwargs: Additional arguments (unused)

        Returns:
            Version string or None
        """
        version = request.GET.get(self.query_param)

        if version and version.lower().startswith("v"):
            version = version[1:]

        return self.validate_version(version)

    def reverse(
        self,
        viewname: str,
        version: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Reverse URL with version in query string.

        Args:
            viewname: The name of the view
            version: The version to include
            **kwargs: URL parameters

        Returns:
            URL string with version query param
        """

        from django.urls import reverse

        url = reverse(viewname, kwargs=kwargs)
        version = version or self.default_version
        if version:
            url = f"{url}?{self.query_param}={version}"

        return url


class HostNameVersioning(BaseVersioning):
    """
    Version specified in the hostname/subdomain.

    Example:
        GET https://v1.api.example.com/users/
        GET https://v2.api.example.com/users/

    Configure:
        versioning = HostNameVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
        )
    """

    # Regex to extract version from hostname
    # Matches: v1.api.example.com, api-v2.example.com
    version_regex: str = r"v([0-9]+(?:\.[0-9]+)*)"

    def __init__(
        self,
        default_version: str | None = None,
        allowed_versions: list[str] | None = None,
        version_regex: str | None = None,
    ) -> None:
        super().__init__(default_version, allowed_versions)
        if version_regex is not None:
            self.version_regex = version_regex

    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Extract version from hostname.

        Args:
            request: The Django HTTP request
            **kwargs: Additional arguments (unused)

        Returns:
            Version string or None
        """
        host = request.get_host()

        # Try to extract version from hostname
        match = re.search(self.version_regex, host)
        if match:
            version = match.group(1)
            return self.validate_version(version)

        return self.validate_version(None)


class NamespaceVersioning(BaseVersioning):
    """
    Version determined by the URL namespace.

    Useful when you have separate URL configurations for each version:
        urlpatterns = [
            path('v1/', include('myapi.v1.urls', namespace='v1')),
            path('v2/', include('myapi.v2.urls', namespace='v2')),
        ]

    Configure:
        versioning = NamespaceVersioning(
            default_version="1",
            allowed_versions=["1", "2"],
        )
    """

    def determine_version(self, request: HttpRequest, **kwargs: Any) -> str | None:
        """
        Extract version from URL namespace.

        Args:
            request: The Django HTTP request
            **kwargs: Additional arguments (unused)

        Returns:
            Version string or None
        """
        if not hasattr(request, "resolver_match") or not request.resolver_match:
            return self.validate_version(None)

        namespace = request.resolver_match.namespace
        if not namespace:
            return self.validate_version(None)

        # Extract version from namespace (e.g., "v1" -> "1", "api-v2" -> "2")
        match = re.search(r"v([0-9]+(?:\.[0-9]+)*)", namespace)
        if match:
            version = match.group(1)
            return self.validate_version(version)

        return self.validate_version(None)
