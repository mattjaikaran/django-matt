"""
Permission decorators for Django Matt.

Provides decorators for applying permissions to controller methods and views.
"""

import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from django.http import HttpRequest, JsonResponse

from django_matt.permissions.base import BasePermission, PermissionDenied
from django_matt.permissions.common import (
    AllowAny,
    HasPermission,
    HasRole,
    IsAuthenticated,
)


F = TypeVar("F", bound=Callable[..., Any])


def _check_permissions(
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


def requires_permission(*permissions: str) -> Callable[[F], F]:
    """
    Decorator that requires specific Django permissions.
    
    Uses Django's built-in permission system to check if the user
    has the required permissions.
    
    Example:
        class TaskController(APIController):
            @delete("{id}")
            @requires_permission("tasks.delete_task")
            async def delete_task(self, request, id: str):
                return await self.delete(request, id)
            
            @post("")
            @requires_permission("tasks.add_task", "tasks.change_task")
            async def create_task(self, request, data: TaskCreate):
                return await self.create(request, data)
    
    Args:
        *permissions: Permission strings (user must have at least one)
    """
    perm_instance = HasPermission(permissions=list(permissions))
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            # Handle both controller methods and standalone views
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                # It's a controller method, request is first arg
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, [perm_instance]
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "permission_denied"},
                    status=status_code,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, [perm_instance]
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "permission_denied"},
                    status=status_code,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


def requires_permissions(
    *permissions: str, require_all: bool = True
) -> Callable[[F], F]:
    """
    Decorator that requires multiple Django permissions.
    
    Similar to requires_permission but with control over whether
    all permissions are required or just one.
    
    Example:
        @requires_permissions("tasks.view", "tasks.change", require_all=True)
        async def sensitive_action(self, request):
            ...
    
    Args:
        *permissions: Permission strings
        require_all: If True, user must have all permissions.
                    If False, user needs any one.
    """
    perm_instance = HasPermission(permissions=list(permissions), require_all=require_all)
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, [perm_instance]
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "permission_denied"},
                    status=status_code,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, [perm_instance]
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "permission_denied"},
                    status=status_code,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


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
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, [role_instance]
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "role_required"},
                    status=status_code,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, [role_instance]
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "role_required"},
                    status=status_code,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


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
    
    @wraps(func)
    async def async_wrapper(self_or_request, *args, **kwargs):
        if hasattr(self_or_request, "request"):
            request = self_or_request.request
        elif isinstance(self_or_request, HttpRequest):
            request = self_or_request
        else:
            request = args[0] if args else kwargs.get("request")
        
        allowed, message, status_code = _check_permissions(
            request, [auth_instance]
        )
        
        if not allowed:
            return JsonResponse(
                {"detail": message, "code": "authentication_required"},
                status=status_code,
            )
        
        if inspect.iscoroutinefunction(func):
            return await func(self_or_request, *args, **kwargs)
        return func(self_or_request, *args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(self_or_request, *args, **kwargs):
        if hasattr(self_or_request, "request"):
            request = self_or_request.request
        elif isinstance(self_or_request, HttpRequest):
            request = self_or_request
        else:
            request = args[0] if args else kwargs.get("request")
        
        allowed, message, status_code = _check_permissions(
            request, [auth_instance]
        )
        
        if not allowed:
            return JsonResponse(
                {"detail": message, "code": "authentication_required"},
                status=status_code,
            )
        
        return func(self_or_request, *args, **kwargs)
    
    if inspect.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore


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


def with_permissions(*permission_classes: type[BasePermission]) -> Callable[[F], F]:
    """
    Decorator that applies multiple permission classes.
    
    All permissions must pass for access to be granted.
    
    Example:
        @with_permissions(IsAuthenticated, IsProjectMember)
        async def project_action(self, request):
            ...
    
    Args:
        *permission_classes: Permission classes (not instances)
    """
    instances = [cls() for cls in permission_classes]
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, instances
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "permission_denied"},
                    status=status_code,
                )
            
            if inspect.iscoroutinefunction(func):
                return await func(self_or_request, *args, **kwargs)
            return func(self_or_request, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            if hasattr(self_or_request, "request"):
                request = self_or_request.request
            elif isinstance(self_or_request, HttpRequest):
                request = self_or_request
            else:
                request = args[0] if args else kwargs.get("request")
            
            allowed, message, status_code = _check_permissions(
                request, instances
            )
            
            if not allowed:
                return JsonResponse(
                    {"detail": message, "code": "permission_denied"},
                    status=status_code,
                )
            
            return func(self_or_request, *args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator
