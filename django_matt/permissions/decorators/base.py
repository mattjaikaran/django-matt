"""
Base utilities for permission decorators.
"""

import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from django.http import HttpRequest, JsonResponse

from django_matt.permissions.base import BasePermission


F = TypeVar("F", bound=Callable[..., Any])


def get_request(self_or_request, args, kwargs) -> HttpRequest | None:
    """Extract request from various call patterns."""
    if hasattr(self_or_request, "request"):
        return self_or_request.request
    elif isinstance(self_or_request, HttpRequest):
        return self_or_request
    elif args and isinstance(args[0], HttpRequest):
        return args[0]
    return kwargs.get("request")


def check_permissions(
    request: HttpRequest,
    permissions: list[BasePermission],
    view: Any = None,
    obj: Any = None,
) -> tuple[bool, str | None, int]:
    """
    Check a list of permissions.
    
    Returns:
        Tuple of (allowed, message, status_code)
    """
    for permission in permissions:
        if not permission.has_permission(request, view):
            return False, permission.get_message(), permission.get_status_code()
        
        if obj is not None and not permission.has_object_permission(request, view, obj):
            return False, permission.get_message(), permission.get_status_code()
    
    return True, None, 200


def create_permission_decorator(
    permission_instances: list[BasePermission],
    error_code: str = "permission_denied",
) -> Callable[[F], F]:
    """
    Factory function to create permission decorators.
    
    Reduces boilerplate by handling the async/sync wrapper pattern.
    
    Args:
        permission_instances: List of permission instances to check
        error_code: Error code to return on denial
        
    Returns:
        A decorator function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            request = get_request(self_or_request, args, kwargs)
            
            allowed, message, status_code = check_permissions(
                request, permission_instances
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": error_code},
                    status=status_code,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            request = get_request(self_or_request, args, kwargs)
            
            allowed, message, status_code = check_permissions(
                request, permission_instances
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": error_code},
                    status=status_code,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator
