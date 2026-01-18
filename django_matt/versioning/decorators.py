"""
Version decorators for django-matt.
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from datetime import date
from typing import TYPE_CHECKING, Any, TypeVar

from django_matt.versioning.base import BaseVersioning, VersioningError

if TYPE_CHECKING:
    from django.http import HttpRequest

F = TypeVar("F", bound=Callable[..., Any])


def version(
    *versions: str,
    deprecated_in: str | None = None,
    removed_in: str | None = None,
) -> Callable[[F], F]:
    """
    Decorator to specify which API versions a view supports.

    Example:
        @api.get("/users")
        @version("1", "2")
        def get_users(request):
            if request.version == "2":
                return {"users": [...], "meta": {...}}
            return {"users": [...]}

        @api.get("/legacy")
        @version("1", deprecated_in="2", removed_in="3")
        def legacy_endpoint(request):
            return {"data": [...]}

    Args:
        *versions: Supported version strings
        deprecated_in: Version where this endpoint becomes deprecated
        removed_in: Version where this endpoint will be removed

    Returns:
        Decorated function with version checking
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            # Get request version (set by middleware or extracted here)
            request_version = getattr(request, "version", None)

            if request_version is not None and versions:
                # Check if version is supported
                if request_version not in versions:
                    raise VersioningError(
                        message=f"This endpoint does not support version '{request_version}'. "
                        f"Supported versions: {list(versions)}",
                        version=request_version,
                        allowed_versions=list(versions),
                    )

                # Check deprecation
                if (
                    deprecated_in
                    and BaseVersioning.compare_versions(request_version, deprecated_in) >= 0
                ):
                    warnings.warn(
                        f"This endpoint is deprecated as of version {deprecated_in}. "
                        f"It will be removed in version {removed_in or 'a future version'}.",
                        DeprecationWarning,
                        stacklevel=2,
                    )

            return func(request, *args, **kwargs)

        # Store version info for introspection
        wrapper._versions = versions  # type: ignore
        wrapper._deprecated_in = deprecated_in  # type: ignore
        wrapper._removed_in = removed_in  # type: ignore

        return wrapper  # type: ignore

    return decorator


def deprecated(
    since: str | None = None,
    removed_in: str | None = None,
    message: str | None = None,
    sunset_date: date | str | None = None,
) -> Callable[[F], F]:
    """
    Mark an endpoint as deprecated.

    Adds deprecation warnings and headers to responses.

    Example:
        @api.get("/old-endpoint")
        @deprecated(since="2.0", removed_in="3.0", message="Use /new-endpoint instead")
        def old_endpoint(request):
            return {"data": [...]}

        @api.get("/legacy")
        @deprecated(sunset_date="2025-06-01")
        def legacy_endpoint(request):
            return {"data": [...]}

    Args:
        since: Version when this endpoint was deprecated
        removed_in: Version when this endpoint will be removed
        message: Custom deprecation message
        sunset_date: Date when the endpoint will be removed (for Sunset header)

    Returns:
        Decorated function with deprecation handling
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            # Generate deprecation message
            deprecation_msg = message
            if not deprecation_msg:
                parts = ["This endpoint is deprecated"]
                if since:
                    parts.append(f" since version {since}")
                if removed_in:
                    parts.append(f" and will be removed in version {removed_in}")
                deprecation_msg = "".join(parts) + "."

            # Issue warning
            warnings.warn(deprecation_msg, DeprecationWarning, stacklevel=2)

            # Execute the view
            response = func(request, *args, **kwargs)

            # Add deprecation headers if response supports it
            if hasattr(response, "__setitem__"):
                response["Deprecation"] = "true"
                if deprecation_msg:
                    response["X-Deprecation-Message"] = deprecation_msg

                # Add Sunset header if date provided
                if sunset_date:
                    if isinstance(sunset_date, date):
                        sunset_str = sunset_date.strftime("%a, %d %b %Y 00:00:00 GMT")
                    else:
                        # Assume ISO format string, convert to HTTP date
                        from datetime import datetime

                        dt = datetime.fromisoformat(sunset_date)
                        sunset_str = dt.strftime("%a, %d %b %Y 00:00:00 GMT")
                    response["Sunset"] = sunset_str

            return response

        # Store deprecation info for introspection
        wrapper._deprecated = True  # type: ignore
        wrapper._deprecated_since = since  # type: ignore
        wrapper._deprecated_removed_in = removed_in  # type: ignore
        wrapper._deprecation_message = message  # type: ignore
        wrapper._sunset_date = sunset_date  # type: ignore

        return wrapper  # type: ignore

    return decorator


def min_version(minimum: str) -> Callable[[F], F]:
    """
    Require a minimum API version to access this endpoint.

    Example:
        @api.get("/new-feature")
        @min_version("2.0")
        def new_feature(request):
            return {"feature": "new"}

    Args:
        minimum: Minimum required version

    Returns:
        Decorated function with version checking
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            request_version = getattr(request, "version", None)

            if request_version is not None:
                if BaseVersioning.compare_versions(request_version, minimum) < 0:
                    raise VersioningError(
                        message=f"This endpoint requires API version {minimum} or higher. "
                        f"You are using version {request_version}.",
                        version=request_version,
                        allowed_versions=[f">={minimum}"],
                    )

            return func(request, *args, **kwargs)

        wrapper._min_version = minimum  # type: ignore
        return wrapper  # type: ignore

    return decorator


def max_version(maximum: str) -> Callable[[F], F]:
    """
    Set a maximum API version for this endpoint.

    Useful for endpoints that are removed in newer versions.

    Example:
        @api.get("/old-feature")
        @max_version("1.9")
        def old_feature(request):
            return {"feature": "old"}

    Args:
        maximum: Maximum supported version

    Returns:
        Decorated function with version checking
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            request_version = getattr(request, "version", None)

            if request_version is not None:
                if BaseVersioning.compare_versions(request_version, maximum) > 0:
                    raise VersioningError(
                        message=f"This endpoint is not available in API version {request_version}. "
                        f"Maximum supported version is {maximum}.",
                        version=request_version,
                        allowed_versions=[f"<={maximum}"],
                    )

            return func(request, *args, **kwargs)

        wrapper._max_version = maximum  # type: ignore
        return wrapper  # type: ignore

    return decorator


def version_range(min_ver: str, max_ver: str) -> Callable[[F], F]:
    """
    Require an API version within a specific range.

    Example:
        @api.get("/feature")
        @version_range("1.5", "2.5")
        def feature(request):
            return {"feature": "data"}

    Args:
        min_ver: Minimum required version (inclusive)
        max_ver: Maximum supported version (inclusive)

    Returns:
        Decorated function with version checking
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
            request_version = getattr(request, "version", None)

            if request_version is not None:
                if BaseVersioning.compare_versions(request_version, min_ver) < 0:
                    raise VersioningError(
                        message=f"This endpoint requires API version {min_ver} or higher. "
                        f"You are using version {request_version}.",
                        version=request_version,
                        allowed_versions=[f"{min_ver}-{max_ver}"],
                    )
                if BaseVersioning.compare_versions(request_version, max_ver) > 0:
                    raise VersioningError(
                        message=f"This endpoint is not available in API version {request_version}. "
                        f"Maximum supported version is {max_ver}.",
                        version=request_version,
                        allowed_versions=[f"{min_ver}-{max_ver}"],
                    )

            return func(request, *args, **kwargs)

        wrapper._min_version = min_ver  # type: ignore
        wrapper._max_version = max_ver  # type: ignore
        return wrapper  # type: ignore

    return decorator


class VersionedMixin:
    """
    Mixin for class-based views to handle versioning.

    Example:
        class MyController(Controller, VersionedMixin):
            supported_versions = ["1", "2"]

            @route.get("/items")
            def list_items(self, request):
                if request.version == "2":
                    return {"items": [...], "meta": {...}}
                return {"items": [...]}
    """

    supported_versions: list[str] = []
    deprecated_versions: list[str] = []

    def check_version(self, request: HttpRequest) -> None:
        """
        Check if the request version is supported.

        Args:
            request: The Django HTTP request

        Raises:
            VersioningError: If version is not supported
        """
        request_version = getattr(request, "version", None)

        if request_version is None:
            return

        if self.supported_versions and request_version not in self.supported_versions:
            raise VersioningError(
                message=f"This endpoint does not support version '{request_version}'. "
                f"Supported versions: {self.supported_versions}",
                version=request_version,
                allowed_versions=self.supported_versions,
            )

        if request_version in self.deprecated_versions:
            warnings.warn(
                f"API version {request_version} is deprecated.",
                DeprecationWarning,
                stacklevel=2,
            )
