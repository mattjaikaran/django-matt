"""
Base permission classes for Django Matt.

Provides the foundational Permission class that all permission classes inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from django.http import HttpRequest


class BasePermission(ABC):
    """
    Base class for all permission classes.
    
    Override the `has_permission` method to implement custom permission logic.
    Optionally override `has_object_permission` for object-level permissions.
    
    Example:
        class IsProjectMember(BasePermission):
            message = "You must be a member of this project."
            
            def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
                return request.user.is_authenticated
            
            def has_object_permission(
                self, request: HttpRequest, view: Any, obj: Any
            ) -> bool:
                return obj.project.members.filter(id=request.user.id).exists()
    """
    
    # Error message shown when permission is denied
    message: ClassVar[str] = "Permission denied."
    
    # HTTP status code when permission is denied (default: 403 Forbidden)
    status_code: ClassVar[int] = 403
    
    @abstractmethod
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """
        Check if the request has permission to access the view.
        
        Called for all requests before any view logic.
        
        Args:
            request: The HTTP request
            view: The view or controller being accessed
            
        Returns:
            True if permission is granted, False otherwise
        """
        pass
    
    def has_object_permission(
        self, request: HttpRequest, view: Any, obj: Any
    ) -> bool:
        """
        Check if the request has permission to access the specific object.
        
        Called after `has_permission` when accessing a specific object.
        Default implementation returns True (no object-level restrictions).
        
        Args:
            request: The HTTP request
            view: The view or controller being accessed
            obj: The object being accessed
            
        Returns:
            True if permission is granted, False otherwise
        """
        return True
    
    def get_message(self) -> str:
        """Get the error message for permission denied."""
        return self.message
    
    def get_status_code(self) -> int:
        """Get the HTTP status code for permission denied."""
        return self.status_code


class Permission(BasePermission):
    """
    Convenience base class for simple permissions.
    
    Same as BasePermission but with a default implementation
    that returns False (deny by default).
    """
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Default implementation denies access."""
        return False


class OperationPermission(BasePermission):
    """
    Permission class that checks for specific operation permissions.
    
    Useful for CRUD operations where different operations require
    different permissions.
    
    Example:
        class TaskOperations(OperationPermission):
            read_permission = "tasks.view"
            create_permission = "tasks.create"
            update_permission = "tasks.update"
            delete_permission = "tasks.delete"
    """
    
    # Permission strings for each operation
    read_permission: ClassVar[str | None] = None
    create_permission: ClassVar[str | None] = None
    update_permission: ClassVar[str | None] = None
    delete_permission: ClassVar[str | None] = None
    list_permission: ClassVar[str | None] = None
    
    def has_permission(self, request: HttpRequest, view: Any = None) -> bool:
        """Check permission based on the HTTP method."""
        method = request.method.upper()
        
        # Get the required permission for this operation
        if method == "GET":
            # Could be list or read - check both
            required = self.read_permission or self.list_permission
        elif method == "POST":
            required = self.create_permission
        elif method in ("PUT", "PATCH"):
            required = self.update_permission
        elif method == "DELETE":
            required = self.delete_permission
        else:
            required = None
        
        if required is None:
            return True  # No permission required for this operation
        
        return self._check_permission(request, required)
    
    def _check_permission(self, request: HttpRequest, permission: str) -> bool:
        """
        Check if the user has the specified permission.
        
        Override to customize permission checking logic.
        """
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        
        return user.has_perm(permission)


class PermissionDenied(Exception):
    """
    Exception raised when permission is denied.
    
    Attributes:
        message: Error message
        status_code: HTTP status code (default: 403)
        permission: The permission that was denied (optional)
    """
    
    def __init__(
        self,
        message: str = "Permission denied.",
        status_code: int = 403,
        permission: str | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.permission = permission
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.permission:
            return f"{self.message} (required: {self.permission})"
        return self.message
