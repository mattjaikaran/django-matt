"""
Django Matt - An internal standalone meta-framework for building modern Django APIs.

Django Matt is a complete API framework that replaces Django Ninja and its ecosystem.
It provides class-based controllers, Pydantic integration, OpenAPI documentation,
JWT authentication, and type synchronization - all in one package.

No need for django-ninja, django-ninja-extra, django-ninja-jwt, or ninja-schema.
"""

__version__ = "0.1.0"

# Import main API class
from django_matt.api import MattAPI

# Import core components for easy access
from django_matt.core.controller import APIController, Controller, CRUDController
from django_matt.core.router import APIRouter, delete, get, patch, post, put
from django_matt.core.schema import (
    ModelSchema,
    Schema,
    create_schema_from_model,
    create_model_from_schema,
    model_validator,
)

# Import OpenAPI components
from django_matt.openapi import OpenAPISchema, get_swagger_ui, get_redoc

# Import utility components
from django_matt.utils.errors import ErrorHandler, ErrorMiddleware, error_handler
from django_matt.utils.hot_reload import (
    HotReloadMiddleware,
    start_hot_reloading,
    stop_hot_reloading,
)
from django_matt.utils.performance import (
    BenchmarkMiddleware,
    FastJsonResponse,
    MessagePackResponse,
    StreamingJsonResponse,
    benchmark,
    cache_manager,
    stream_json_list,
)

# Import views module
from django_matt.views import (
    APIView,
    APIViewSet,
    ViewSet,
    ListView,
    CreateView,
    ReadView,
    RetrieveView,
    UpdateView,
    DeleteView,
    PatchView,
)

# Import permissions module
from django_matt.permissions import (
    BasePermission,
    Permission,
    AllowAny,
    IsAuthenticated,
    IsAdmin,
    IsStaff,
    IsSuperUser,
    IsOwner,
    HasRole,
    HasPermission,
    requires_permission,
    requires_permissions,
    requires_role,
    authenticated,
    allow_any,
)

# Create a default API instance
api = MattAPI()

# Export commonly used components
__all__ = [
    # Main API class
    "MattAPI",
    # Core components
    "APIRouter",
    "Controller",
    "APIController",
    "CRUDController",
    # Schema components
    "ModelSchema",
    "Schema",
    "create_schema_from_model",
    "create_model_from_schema",
    "model_validator",
    # Default API instance
    "api",
    # Route decorators
    "get",
    "post",
    "put",
    "patch",
    "delete",
    # OpenAPI
    "OpenAPISchema",
    "get_swagger_ui",
    "get_redoc",
    # Error handling
    "ErrorHandler",
    "ErrorMiddleware",
    "error_handler",
    # Hot reloading
    "HotReloadMiddleware",
    "start_hot_reloading",
    "stop_hot_reloading",
    # Performance
    "FastJsonResponse",
    "MessagePackResponse",
    "StreamingJsonResponse",
    "benchmark",
    "cache_manager",
    "BenchmarkMiddleware",
    "stream_json_list",
    # Views - Composable CRUD
    "APIView",
    "APIViewSet",
    "ViewSet",
    "ListView",
    "CreateView",
    "ReadView",
    "RetrieveView",
    "UpdateView",
    "DeleteView",
    "PatchView",
    # Permissions
    "BasePermission",
    "Permission",
    "AllowAny",
    "IsAuthenticated",
    "IsAdmin",
    "IsStaff",
    "IsSuperUser",
    "IsOwner",
    "HasRole",
    "HasPermission",
    "requires_permission",
    "requires_permissions",
    "requires_role",
    "authenticated",
    "allow_any",
]
