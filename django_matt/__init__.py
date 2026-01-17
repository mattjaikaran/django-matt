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

# Import auth module (lazy import to handle optional PyJWT dependency)
# Users should import from django_matt.auth for full auth functionality
# Core decorators are re-exported here for convenience
try:
    from django_matt.auth import (
        jwt_required,
        jwt_optional,
        requires_auth,
        admin_required,
        superuser_required,
        with_roles,
        with_permission,
        create_token_pair,
        JWTAuthenticationMiddleware,
    )
    _auth_available = True
except ImportError:
    _auth_available = False
    # Define placeholder functions that raise helpful errors
    def _auth_not_available(*args, **kwargs):
        raise ImportError(
            "Auth features require PyJWT. Install with: pip install 'django-matt[auth]'"
        )
    jwt_required = jwt_optional = requires_auth = _auth_not_available
    admin_required = superuser_required = with_roles = _auth_not_available
    with_permission = create_token_pair = _auth_not_available
    JWTAuthenticationMiddleware = None

# Import billing module (lazy import to handle optional dependencies)
# Users should import from django_matt.billing for full billing functionality
try:
    from django_matt.billing import (
        BillingController,
        WebhookController,
        get_provider,
        get_billing_config,
    )
    _billing_available = True
except ImportError:
    _billing_available = False
    BillingController = WebhookController = None
    get_provider = get_billing_config = None

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
    # Auth (requires PyJWT - install with django-matt[auth])
    "jwt_required",
    "jwt_optional",
    "requires_auth",
    "admin_required",
    "superuser_required",
    "with_roles",
    "with_permission",
    "create_token_pair",
    "JWTAuthenticationMiddleware",
    # Billing (requires stripe/httpx - install with django-matt[billing])
    "BillingController",
    "WebhookController",
    "get_provider",
    "get_billing_config",
]
