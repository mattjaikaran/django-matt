"""
Role-based decorators.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from django_matt.permissions.common import HasRole
from django_matt.permissions.decorators.base import create_permission_decorator

F = TypeVar("F", bound=Callable[..., Any])


def requires_role(*roles: str) -> Callable[[F], F]:
    """
    Decorator that requires specific role(s).

    Checks if the user belongs to any of the specified groups/roles.

    Example:
        @requires_role("manager", "admin")
        async def approve_request(self, request):
            ...

    Args:
        *roles: Role/group names (user needs any one)
    """
    role_instance = HasRole(roles=list(roles))
    base_decorator = create_permission_decorator([role_instance], "role_required")

    def decorator(func: F) -> F:
        wrapped = base_decorator(func)
        wrapped._required_roles = list(roles)  # type: ignore[attr-defined]
        return wrapped

    return decorator
