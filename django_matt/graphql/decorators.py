"""
GraphQL decorators for Django Matt.

Provides decorators for defining GraphQL types, resolvers, and mutations.
These work with Strawberry when available, or provide helpful error messages otherwise.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

# Check for strawberry availability
try:
    import strawberry
    from strawberry.permission import BasePermission
    from strawberry.types import Info

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    BasePermission = object
    Info = Any


T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def _require_strawberry(feature: str = "this feature"):
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            f"strawberry-graphql is required for {feature}. "
            "Install it with: uv add \"strawberry-graphql[django]\""
        )


def graphql_type(
    cls: type[T] | None = None, *, name: str | None = None, description: str | None = None
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator to mark a class as a GraphQL type.

    Usage:
        @graphql_type
        class UserType:
            id: int
            email: str

        @graphql_type(name="CustomUser", description="A user type")
        class UserType:
            id: int
            email: str
    """
    _require_strawberry("@graphql_type")

    def decorator(cls: type[T]) -> type[T]:
        return strawberry.type(cls, name=name, description=description)

    if cls is None:
        return decorator
    return decorator(cls)


def graphql_input(
    cls: type[T] | None = None, *, name: str | None = None, description: str | None = None
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator to mark a class as a GraphQL input type.

    Usage:
        @graphql_input
        class CreateUserInput:
            email: str
            password: str
    """
    _require_strawberry("@graphql_input")

    def decorator(cls: type[T]) -> type[T]:
        return strawberry.input(cls, name=name, description=description)

    if cls is None:
        return decorator
    return decorator(cls)


def graphql_interface(
    cls: type[T] | None = None, *, name: str | None = None, description: str | None = None
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator to mark a class as a GraphQL interface.

    Usage:
        @graphql_interface
        class Node:
            id: strawberry.ID
    """
    _require_strawberry("@graphql_interface")

    def decorator(cls: type[T]) -> type[T]:
        return strawberry.interface(cls, name=name, description=description)

    if cls is None:
        return decorator
    return decorator(cls)


def graphql_enum(
    cls: type[T] | None = None, *, name: str | None = None, description: str | None = None
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Decorator to mark an Enum as a GraphQL enum.

    Usage:
        @graphql_enum
        class Status(Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"
    """
    _require_strawberry("@graphql_enum")

    def decorator(cls: type[T]) -> type[T]:
        return strawberry.enum(cls, name=name, description=description)

    if cls is None:
        return decorator
    return decorator(cls)


def resolver(func: F | None = None, *, name: str | None = None) -> F | Callable[[F], F]:
    """
    Decorator to mark a function as a GraphQL resolver.

    This is a convenience wrapper that works with field definitions.

    Usage:
        @graphql_type
        class Query:
            @resolver
            def users(self) -> list[UserType]:
                return User.objects.all()
    """
    _require_strawberry("@resolver")

    def decorator(func: F) -> F:
        # Mark as a strawberry field
        return strawberry.field(resolver=func, name=name)

    if func is None:
        return decorator
    return decorator(func)


def mutation(
    func: F | None = None, *, name: str | None = None, description: str | None = None
) -> F | Callable[[F], F]:
    """
    Decorator to mark a method as a GraphQL mutation.

    Usage:
        @graphql_type
        class Mutation:
            @mutation
            def create_user(self, input: CreateUserInput) -> UserType:
                user = User.objects.create(**input.__dict__)
                return UserType.from_orm(user)
    """
    _require_strawberry("@mutation")

    def decorator(func: F) -> F:
        return strawberry.mutation(func, name=name, description=description)

    if func is None:
        return decorator
    return decorator(func)


def subscription(
    func: F | None = None, *, name: str | None = None, description: str | None = None
) -> F | Callable[[F], F]:
    """
    Decorator to mark a method as a GraphQL subscription.

    Usage:
        @graphql_type
        class Subscription:
            @subscription
            async def user_created(self) -> AsyncGenerator[UserType, None]:
                async for user in user_stream():
                    yield UserType.from_orm(user)
    """
    _require_strawberry("@subscription")

    def decorator(func: F) -> F:
        return strawberry.subscription(func, name=name, description=description)

    if func is None:
        return decorator
    return decorator(func)


def field(
    func: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    deprecation_reason: str | None = None,
    default: Any = strawberry.UNSET if STRAWBERRY_AVAILABLE else None,
) -> F | Callable[[F], F]:
    """
    Decorator to define a field with additional options.

    Usage:
        @graphql_type
        class UserType:
            id: int
            email: str

            @field(description="The user's full name")
            def full_name(self) -> str:
                return f"{self.first_name} {self.last_name}"
    """
    _require_strawberry("@field")

    def decorator(func: F) -> F:
        return strawberry.field(
            resolver=func,
            name=name,
            description=description,
            deprecation_reason=deprecation_reason,
            default=default,
        )

    if func is None:
        return decorator
    return decorator(func)


class IsAuthenticated(BasePermission if STRAWBERRY_AVAILABLE else object):
    """Permission class that requires authentication."""

    message = "User must be authenticated"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        if not STRAWBERRY_AVAILABLE:
            return False
        request = info.context.get("request") or info.context
        if hasattr(request, "user"):
            return request.user.is_authenticated
        return False


class IsAdmin(BasePermission if STRAWBERRY_AVAILABLE else object):
    """Permission class that requires admin status."""

    message = "User must be an admin"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        if not STRAWBERRY_AVAILABLE:
            return False
        request = info.context.get("request") or info.context
        if hasattr(request, "user"):
            return request.user.is_authenticated and (
                request.user.is_staff or request.user.is_superuser
            )
        return False


class HasPermission(BasePermission if STRAWBERRY_AVAILABLE else object):
    """Permission class that requires a specific Django permission."""

    message = "User does not have required permission"

    def __init__(self, permission: str):
        self.permission = permission

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        if not STRAWBERRY_AVAILABLE:
            return False
        request = info.context.get("request") or info.context
        if hasattr(request, "user"):
            return request.user.has_perm(self.permission)
        return False


class HasRole(BasePermission if STRAWBERRY_AVAILABLE else object):
    """Permission class that requires a specific role (group)."""

    message = "User does not have required role"

    def __init__(self, *roles: str):
        self.roles = set(roles)

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        if not STRAWBERRY_AVAILABLE:
            return False
        request = info.context.get("request") or info.context
        if hasattr(request, "user") and request.user.is_authenticated:
            user_groups = set(request.user.groups.values_list("name", flat=True))
            return bool(user_groups & self.roles)
        return False


def permission_field(
    *permissions: type,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[F], F]:
    """
    Decorator for fields that require specific permissions.

    Usage:
        @graphql_type
        class UserType:
            @permission_field(IsAuthenticated, IsAdmin)
            def secret_data(self) -> str:
                return "secret"
    """
    _require_strawberry("@permission_field")

    def decorator(func: F) -> F:
        return strawberry.field(
            resolver=func,
            name=name,
            description=description,
            permission_classes=list(permissions),
        )

    return decorator


def authenticated_field(
    name: str | None = None,
    description: str | None = None,
) -> Callable[[F], F]:
    """
    Decorator for fields that require authentication.

    Usage:
        @graphql_type
        class UserType:
            @authenticated_field
            def email(self) -> str:
                return self._email
    """
    return permission_field(IsAuthenticated, name=name, description=description)


# Complexity tracking
_complexity_registry: dict[Callable, int] = {}


def complexity(value: int) -> Callable[[F], F]:
    """
    Decorator to set query complexity for a field.

    Used for query complexity analysis and limiting.

    Usage:
        @graphql_type
        class Query:
            @complexity(10)
            def expensive_query(self) -> list[DataType]:
                return expensive_computation()
    """

    def decorator(func: F) -> F:
        _complexity_registry[func] = value
        return func

    return decorator


def get_field_complexity(func: Callable) -> int:
    """Get the complexity value for a field."""
    return _complexity_registry.get(func, 1)


# Rate limiting
_rate_limit_registry: dict[Callable, tuple[int, int]] = {}


def rate_limited(max_calls: int, period_seconds: int = 60) -> Callable[[F], F]:
    """
    Decorator to rate limit a field or mutation.

    Usage:
        @graphql_type
        class Mutation:
            @rate_limited(10, 60)  # 10 calls per minute
            def send_email(self, to: str, subject: str) -> bool:
                ...
    """

    def decorator(func: F) -> F:
        _rate_limit_registry[func] = (max_calls, period_seconds)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Rate limiting logic is handled by middleware
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_rate_limit(func: Callable) -> tuple[int, int] | None:
    """Get the rate limit for a function."""
    return _rate_limit_registry.get(func)
