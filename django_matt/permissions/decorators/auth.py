"""
Authentication-related permission decorators.
"""

from typing import Any, Callable, TypeVar

from django_matt.permissions.common import IsAuthenticated
from django_matt.permissions.decorators.base import create_permission_decorator


F = TypeVar("F", bound=Callable[..., Any])


def authenticated(func: F) -> F:
    """
    Decorator that requires authentication.
    
    Shorthand for requiring the IsAuthenticated permission.
    
    Example:
        @authenticated
        async def protected_action(self, request):
            ...
    """
    auth_instance = IsAuthenticated()
    decorator = create_permission_decorator([auth_instance], "authentication_required")
    return decorator(func)


def allow_any(func: F) -> F:
    """
    Decorator that explicitly marks a method as publicly accessible.
    
    Useful when a controller has default permissions but some
    methods should be public.
    
    Example:
        class UserController(APIController):
            permission_classes = [IsAuthenticated]
            
            @get("public")
            @allow_any
            async def public_info(self, request):
                return {"status": "ok"}
    """
    # Mark the function as allowing any access
    func._allow_any = True  # type: ignore
    return func
