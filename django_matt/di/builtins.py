"""
Built-in dependency markers for common needs.

Provides pre-built dependencies for:
- CurrentUser: The authenticated user
- CurrentRequest: The current HTTP request
- CurrentOrg: The current organization (multi-tenant)
- DBSession: Database session/connection
- Settings: Django settings
- Cache: Cache backend
- Logger: Logging instance
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

from django.conf import settings as django_settings
from django.core.cache import cache as django_cache

from .depends import DependencyMarker
from .container import Container

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.contrib.auth.models import AbstractUser


class CurrentRequest(DependencyMarker):
    """
    Dependency that resolves to the current HTTP request.

    Usage:
        @get("info")
        async def get_info(
            self,
            request,
            req: HttpRequest = CurrentRequest(),
        ):
            return {"method": req.method, "path": req.path}
    """

    def resolve(self, request=None, container: Container = None) -> "HttpRequest":
        if request is None:
            raise RuntimeError("No request available in current context")
        return request

    def __repr__(self):
        return "CurrentRequest()"


class CurrentUser(DependencyMarker):
    """
    Dependency that resolves to the current authenticated user.

    Raises an error if the user is not authenticated (use optional=True
    to return None instead).

    Usage:
        @get("profile")
        @jwt_required
        async def get_profile(
            self,
            request,
            user: User = CurrentUser(),
        ):
            return {"email": user.email}

        # Optional (returns None if not authenticated)
        @get("maybe-profile")
        async def get_maybe_profile(
            self,
            request,
            user: User = CurrentUser(optional=True),
        ):
            if user:
                return {"email": user.email}
            return {"email": None}
    """

    def __init__(self, *, optional: bool = False):
        """
        Args:
            optional: If True, returns None for unauthenticated users.
                     If False (default), raises an error.
        """
        self.optional = optional

    def resolve(
        self, request=None, container: Container = None
    ) -> Optional["AbstractUser"]:
        if request is None:
            if self.optional:
                return None
            raise RuntimeError("No request available in current context")

        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            if self.optional:
                return None
            raise PermissionError("User is not authenticated")

        return user

    async def aresolve(
        self, request=None, container: Container = None
    ) -> Optional["AbstractUser"]:
        """Async version - same as sync since user is already on request."""
        return self.resolve(request=request, container=container)

    def __repr__(self):
        return f"CurrentUser(optional={self.optional})"


class CurrentOrg(DependencyMarker):
    """
    Dependency that resolves to the current organization (multi-tenant).

    Expects the organization to be set on request.org by middleware.

    Usage:
        @get("org-info")
        async def get_org_info(
            self,
            request,
            org: Organization = CurrentOrg(),
        ):
            return {"name": org.name, "slug": org.slug}
    """

    def __init__(self, *, optional: bool = False, attr_name: str = "org"):
        """
        Args:
            optional: If True, returns None if no org. If False, raises error.
            attr_name: The attribute name on request (default: "org")
        """
        self.optional = optional
        self.attr_name = attr_name

    def resolve(self, request=None, container: Container = None) -> Any:
        if request is None:
            if self.optional:
                return None
            raise RuntimeError("No request available in current context")

        org = getattr(request, self.attr_name, None)

        if org is None:
            if self.optional:
                return None
            raise RuntimeError(
                f"No organization found on request.{self.attr_name}. "
                "Ensure TenantMiddleware is enabled."
            )

        return org

    async def aresolve(self, request=None, container: Container = None) -> Any:
        """Async version - same as sync since org is already on request."""
        return self.resolve(request=request, container=container)

    def __repr__(self):
        return f"CurrentOrg(optional={self.optional})"


# Alias for CurrentOrg
CurrentTenant = CurrentOrg


class DBSession(DependencyMarker):
    """
    Dependency that resolves to a database connection/session.

    Usage:
        @get("raw-query")
        async def raw_query(
            self,
            request,
            db: DBSession = DBSession(),
        ):
            with db.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone()
    """

    def __init__(self, *, using: str = "default"):
        """
        Args:
            using: The database alias to use (default: "default")
        """
        self.using = using

    def resolve(self, request=None, container: Container = None):
        from django.db import connections

        return connections[self.using]

    def __repr__(self):
        return f"DBSession(using='{self.using}')"


class Settings(DependencyMarker):
    """
    Dependency that resolves to Django settings or a specific setting.

    Usage:
        # Get entire settings object
        @get("debug")
        async def is_debug(
            self,
            request,
            settings = Settings(),
        ):
            return {"debug": settings.DEBUG}

        # Get specific setting
        @get("secret")
        async def get_secret(
            self,
            request,
            secret: str = Settings("SECRET_KEY"),
        ):
            return {"has_secret": bool(secret)}
    """

    def __init__(self, key: str = None, *, default: Any = None):
        """
        Args:
            key: Specific setting key to retrieve (None = entire settings)
            default: Default value if setting doesn't exist
        """
        self.key = key
        self.default = default

    def resolve(self, request=None, container: Container = None) -> Any:
        if self.key is None:
            return django_settings

        return getattr(django_settings, self.key, self.default)

    def __repr__(self):
        if self.key:
            return f"Settings('{self.key}')"
        return "Settings()"


class Cache(DependencyMarker):
    """
    Dependency that resolves to the Django cache backend.

    Usage:
        @get("cached-data")
        async def get_cached(
            self,
            request,
            cache = Cache(),
        ):
            data = cache.get("my_key")
            if data is None:
                data = expensive_computation()
                cache.set("my_key", data, timeout=300)
            return data
    """

    def __init__(self, *, alias: str = "default"):
        """
        Args:
            alias: The cache alias to use (default: "default")
        """
        self.alias = alias

    def resolve(self, request=None, container: Container = None):
        if self.alias == "default":
            return django_cache

        from django.core.cache import caches

        return caches[self.alias]

    def __repr__(self):
        return f"Cache(alias='{self.alias}')"


class Logger(DependencyMarker):
    """
    Dependency that resolves to a logger instance.

    Usage:
        @post("action")
        async def do_action(
            self,
            request,
            logger = Logger("myapp.actions"),
        ):
            logger.info("Action performed", extra={"user": request.user.id})
            return {"status": "ok"}
    """

    def __init__(self, name: str = None, *, level: int = None):
        """
        Args:
            name: Logger name (default: uses module name)
            level: Optional logging level to set
        """
        self.name = name
        self.level = level

    def resolve(self, request=None, container: Container = None) -> logging.Logger:
        logger = logging.getLogger(self.name or __name__)

        if self.level is not None:
            logger.setLevel(self.level)

        return logger

    def __repr__(self):
        return f"Logger('{self.name}')" if self.name else "Logger()"


class Query(DependencyMarker):
    """
    Dependency that extracts a query parameter from the request.

    Usage:
        @get("search")
        async def search(
            self,
            request,
            q: str = Query("q"),
            page: int = Query("page", default=1),
            limit: int = Query("limit", default=10, le=100),
        ):
            return {"query": q, "page": page, "limit": limit}
    """

    def __init__(
        self,
        name: str,
        *,
        default: Any = ...,  # Ellipsis means required
        alias: str = None,
        ge: int = None,
        le: int = None,
        min_length: int = None,
        max_length: int = None,
    ):
        """
        Args:
            name: The query parameter name
            default: Default value (Ellipsis means required)
            alias: Alternative name to look for
            ge: Minimum value (for numbers)
            le: Maximum value (for numbers)
            min_length: Minimum string length
            max_length: Maximum string length
        """
        self.name = name
        self.default = default
        self.alias = alias
        self.ge = ge
        self.le = le
        self.min_length = min_length
        self.max_length = max_length
        self._param_type = None

    def resolve(self, request=None, container: Container = None) -> Any:
        if request is None:
            if self.default is ...:
                raise ValueError(f"Query parameter '{self.name}' is required")
            return self.default

        # Try name and alias
        value = request.GET.get(self.name)
        if value is None and self.alias:
            value = request.GET.get(self.alias)

        if value is None:
            if self.default is ...:
                raise ValueError(f"Query parameter '{self.name}' is required")
            return self.default

        # Type conversion
        if self._param_type is not None:
            try:
                if self._param_type == int:
                    value = int(value)
                elif self._param_type == float:
                    value = float(value)
                elif self._param_type == bool:
                    value = value.lower() in ("true", "1", "yes", "on")
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Query parameter '{self.name}' must be {self._param_type.__name__}"
                ) from e

        # Validation
        if isinstance(value, (int, float)):
            if self.ge is not None and value < self.ge:
                raise ValueError(
                    f"Query parameter '{self.name}' must be >= {self.ge}"
                )
            if self.le is not None and value > self.le:
                raise ValueError(
                    f"Query parameter '{self.name}' must be <= {self.le}"
                )

        if isinstance(value, str):
            if self.min_length is not None and len(value) < self.min_length:
                raise ValueError(
                    f"Query parameter '{self.name}' must be at least "
                    f"{self.min_length} characters"
                )
            if self.max_length is not None and len(value) > self.max_length:
                raise ValueError(
                    f"Query parameter '{self.name}' must be at most "
                    f"{self.max_length} characters"
                )

        return value

    def __repr__(self):
        return f"Query('{self.name}')"


class Header(DependencyMarker):
    """
    Dependency that extracts a header from the request.

    Usage:
        @get("info")
        async def get_info(
            self,
            request,
            user_agent: str = Header("User-Agent"),
            api_key: str = Header("X-API-Key", default=None),
        ):
            return {"user_agent": user_agent}
    """

    def __init__(
        self,
        name: str,
        *,
        default: Any = ...,
        convert_underscores: bool = True,
    ):
        """
        Args:
            name: The header name (case-insensitive)
            default: Default value (Ellipsis means required)
            convert_underscores: Convert underscores to hyphens for lookup
        """
        self.name = name
        self.default = default
        self.convert_underscores = convert_underscores

    def resolve(self, request=None, container: Container = None) -> Any:
        if request is None:
            if self.default is ...:
                raise ValueError(f"Header '{self.name}' is required")
            return self.default

        # Django stores headers as HTTP_X_HEADER_NAME
        header_name = self.name.upper().replace("-", "_")
        if not header_name.startswith("HTTP_") and header_name not in (
            "CONTENT_TYPE",
            "CONTENT_LENGTH",
        ):
            header_name = f"HTTP_{header_name}"

        value = request.META.get(header_name)

        if value is None:
            if self.default is ...:
                raise ValueError(f"Header '{self.name}' is required")
            return self.default

        return value

    def __repr__(self):
        return f"Header('{self.name}')"


class Path(DependencyMarker):
    """
    Dependency that extracts a path parameter.

    Note: Path parameters are typically handled by the router,
    but this can be useful for validation or type conversion.

    Usage:
        @get("users/{user_id}")
        async def get_user(
            self,
            request,
            user_id: int = Path("user_id", ge=1),
        ):
            return {"user_id": user_id}
    """

    def __init__(
        self,
        name: str,
        *,
        ge: int = None,
        le: int = None,
    ):
        self.name = name
        self.ge = ge
        self.le = le
        self._param_type = None

    def resolve(self, request=None, container: Container = None) -> Any:
        # Path params should come from router kwargs
        raise NotImplementedError(
            "Path parameters are resolved by the router. "
            "Use type hints in the function signature instead."
        )

    def __repr__(self):
        return f"Path('{self.name}')"
