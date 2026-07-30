"""
Django Matt - An internal standalone meta-framework for building modern Django APIs.

Django Matt is a complete API framework that replaces Django Ninja and its ecosystem.
It provides class-based controllers, Pydantic integration, OpenAPI documentation,
JWT authentication, and type synchronization - all in one package.

No need for django-ninja, django-ninja-extra, django-ninja-jwt, or ninja-schema.

Usage:
    from django_matt import DjangoMattAPI, APIController, get, post

    api = DjangoMattAPI()

    class UserController(APIController):
        prefix = "/users"

        @get("/")
        async def list_users(self):
            return []

    api.register_controller(UserController)

For auth, billing, and other features with model dependencies, import from submodules:
    from django_matt.auth import jwt_required, AuthController
    from django_matt.billing import BillingController
"""

__version__ = "0.10.0"

# =============================================================================
# Lazy imports to avoid circular dependencies with Django models
# =============================================================================
# These are the public exports - actual imports happen on first access
# This allows Django to fully load apps before we import model-heavy modules

_LAZY_IMPORTS = {
    "DjangoMattAPI": "django_matt.api",
    # Core components
    "APIRouter": "django_matt.core.router",
    "Controller": "django_matt.core.controller",
    "APIController": "django_matt.core.controller",
    "CRUDController": "django_matt.core.controller",
    "get": "django_matt.core.router",
    "post": "django_matt.core.router",
    "put": "django_matt.core.router",
    "patch": "django_matt.core.router",
    "delete": "django_matt.core.router",
    # Schema
    "ModelSchema": "django_matt.core.schema",
    "Schema": "django_matt.core.schema",
    "create_schema_from_model": "django_matt.core.schema",
    "create_model_from_schema": "django_matt.core.schema",
    "model_validator": "django_matt.core.schema",
    # OpenAPI
    "OpenAPISchema": "django_matt.openapi",
    "get_swagger_ui": "django_matt.openapi",
    "get_redoc": "django_matt.openapi",
    # Errors
    "ErrorHandler": "django_matt.core.errors",
    "ErrorMiddleware": "django_matt.core.errors",
    "error_handler": "django_matt.core.errors",
    "ErrorEnhancementMiddleware": "django_matt.errors",
    "StructuredError": "django_matt.errors",
    "install_default_handlers": "django_matt.errors",
    "build_error_response": "django_matt.errors",
    # Hot reload
    "HotReloadMiddleware": "django_matt.utils.hot_reload",
    "start_hot_reloading": "django_matt.utils.hot_reload",
    "stop_hot_reloading": "django_matt.utils.hot_reload",
    # Performance
    "FastJsonResponse": "django_matt.utils.performance",
    "MessagePackResponse": "django_matt.utils.performance",
    "StreamingJsonResponse": "django_matt.utils.performance",
    "benchmark": "django_matt.utils.performance",
    "cache_manager": "django_matt.utils.performance",
    "BenchmarkMiddleware": "django_matt.utils.performance",
    "stream_json_list": "django_matt.utils.performance",
    # Views
    "APIView": "django_matt.views",
    "APIViewSet": "django_matt.views",
    "ViewSet": "django_matt.views",
    "ListView": "django_matt.views",
    "CreateView": "django_matt.views",
    "ReadView": "django_matt.views",
    "RetrieveView": "django_matt.views",
    "UpdateView": "django_matt.views",
    "DeleteView": "django_matt.views",
    "PatchView": "django_matt.views",
    # Permissions
    "BasePermission": "django_matt.permissions",
    "Permission": "django_matt.permissions",
    "AllowAny": "django_matt.permissions",
    "IsAuthenticated": "django_matt.permissions",
    "IsAdmin": "django_matt.permissions",
    "IsStaff": "django_matt.permissions",
    "IsSuperUser": "django_matt.permissions",
    "IsOwner": "django_matt.permissions",
    "HasRole": "django_matt.permissions",
    "HasPermission": "django_matt.permissions",
    "requires_permission": "django_matt.permissions",
    "requires_permissions": "django_matt.permissions",
    "requires_role": "django_matt.permissions",
    "authenticated": "django_matt.permissions",
    "allow_any": "django_matt.permissions",
    # Auth (lazy - has model dependencies)
    "jwt_required": "django_matt.auth",
    "jwt_optional": "django_matt.auth",
    "requires_auth": "django_matt.auth",
    "admin_required": "django_matt.auth",
    "superuser_required": "django_matt.auth",
    "with_roles": "django_matt.auth",
    "with_permission": "django_matt.auth",
    "create_token_pair": "django_matt.auth",
    "JWTAuthenticationMiddleware": "django_matt.auth",
    # Content negotiation
    "ContentNegotiationMiddleware": "django_matt.negotiation",
    "ContentNegotiator": "django_matt.negotiation",
    "renders": "django_matt.negotiation",
    "render_as": "django_matt.negotiation",
    "content_negotiated": "django_matt.negotiation",
    "render": "django_matt.negotiation",
    "render_format": "django_matt.negotiation",
    "negotiate": "django_matt.negotiation",
    # Pagination
    "BasePagination": "django_matt.pagination",
    "PageNumberPagination": "django_matt.pagination",
    "LimitOffsetPagination": "django_matt.pagination",
    "CursorPagination": "django_matt.pagination",
    # Filtering
    "BaseFilterBackend": "django_matt.filtering",
    "DjangoFilterBackend": "django_matt.filtering",
    "SearchBackend": "django_matt.filtering",
    "OrderingBackend": "django_matt.filtering",
    "FilterSet": "django_matt.filtering",
    "Filter": "django_matt.filtering",
    "CharFilter": "django_matt.filtering",
    "IntegerFilter": "django_matt.filtering",
    "BooleanFilter": "django_matt.filtering",
    "DateFilter": "django_matt.filtering",
    "DateTimeFilter": "django_matt.filtering",
    "InFilter": "django_matt.filtering",
    "PostgresSearchBackend": "django_matt.filtering",
    # Dependency Injection
    "Container": "django_matt.di",
    "container": "django_matt.di",
    "Singleton": "django_matt.di",
    "Scoped": "django_matt.di",
    "Transient": "django_matt.di",
    "Depends": "django_matt.di",
    "CurrentUser": "django_matt.di",
    "CurrentRequest": "django_matt.di",
    "CurrentOrg": "django_matt.di",
    "injectable": "django_matt.di",
    "inject": "django_matt.di",
    "DependencyInjectionMiddleware": "django_matt.di",
    # Billing (lazy - has model dependencies)
    "BillingController": "django_matt.billing",
    "WebhookController": "django_matt.billing",
    "get_provider": "django_matt.billing",
    "get_billing_config": "django_matt.billing",
    # WebSockets (lazy - optional dependency)
    "BaseConsumer": "django_matt.websockets",
    "JsonConsumer": "django_matt.websockets",
    "AuthenticatedConsumer": "django_matt.websockets",
    "RoomConsumer": "django_matt.websockets",
    "JWTAuthMiddleware": "django_matt.websockets",
    "SessionAuthMiddleware": "django_matt.websockets",
    "AuthMiddlewareStack": "django_matt.websockets",
    "WebSocketRouter": "django_matt.websockets",
    "create_asgi_application": "django_matt.websockets",
    "broadcast": "django_matt.websockets",
    "send_to_user": "django_matt.websockets",
    "PresenceManager": "django_matt.websockets",
    # Observability (lazy - optional dependencies)
    "setup_tracing": "django_matt.observability",
    "get_tracer": "django_matt.observability",
    "get_current_span": "django_matt.observability",
    "trace": "django_matt.observability",
    "metric": "django_matt.observability",
    "timed": "django_matt.observability",
    "counted": "django_matt.observability",
    "TracingMiddleware": "django_matt.observability",
    "MetricsMiddleware": "django_matt.observability",
    "LoggingMiddleware": "django_matt.observability",
    "ObservabilityMiddleware": "django_matt.observability",
    "metrics_view": "django_matt.observability",
    "health_view": "django_matt.observability",
    "ready_view": "django_matt.observability",
    "readiness_checker": "django_matt.observability",
    "get_logger": "django_matt.observability",
    "get_logging_config": "django_matt.observability",
    "observability_urlpatterns": "django_matt.observability",
    # Feature Flags (lazy - has model dependencies)
    "feature_enabled": "django_matt.flags",
    "get_variant": "django_matt.flags",
    "feature_flag": "django_matt.flags",
    "requires_flag": "django_matt.flags",
    "FlagMiddleware": "django_matt.flags",
    "FlagContext": "django_matt.flags",
    "FlagController": "django_matt.flags",
    # GraphQL (lazy - requires strawberry)
    "GraphQLAPI": "django_matt.graphql",
    "GraphQLView": "django_matt.graphql",
    "AsyncGraphQLView": "django_matt.graphql",
    "GraphQLSchema": "django_matt.graphql",
    "generate_schema": "django_matt.graphql",
    "graphql_type": "django_matt.graphql",
    "graphql_input": "django_matt.graphql",
    "graphql_enum": "django_matt.graphql",
    "resolver": "django_matt.graphql",
    "mutation": "django_matt.graphql",
    "subscription": "django_matt.graphql",
    "create_type_from_model": "django_matt.graphql",
    "DataLoaderRegistry": "django_matt.graphql",
    "generate_typescript_types": "django_matt.graphql",
    "generate_typescript_client": "django_matt.graphql",
    # Experiments / A/B Testing (lazy - has model dependencies)
    "get_experiment_variant": "django_matt.experiments",
    "track_experiment_conversion": "django_matt.experiments",
    "experiment": "django_matt.experiments",
    "requires_experiment": "django_matt.experiments",
    "ExperimentMiddleware": "django_matt.experiments",
    "ExperimentContext": "django_matt.experiments",
    "ExperimentController": "django_matt.experiments",
    "analyze_experiment": "django_matt.experiments",
    # Resources — zero-config CRUD
    "resource": "django_matt.resources",
    "build_viewset": "django_matt.resources",
    "ResourceConfig": "django_matt.resources",
    "action": "django_matt.resources",
    # Configuration shortcut
    "configure": "django_matt.config",
    # Middleware stack
    "SecurityHeadersMiddleware": "django_matt.middleware",
    "RequestIDMiddleware": "django_matt.middleware",
    "CORSMiddleware": "django_matt.middleware",
    "RequestLoggingMiddleware": "django_matt.middleware",
    "TimingMiddleware": "django_matt.middleware",
    "PRODUCTION_STACK": "django_matt.middleware",
    "DEVELOPMENT_STACK": "django_matt.middleware",
    # Request ID helper
    "get_request_id": "django_matt.middleware.request_id",
    # Slim mode
    "ModuleRegistry": "django_matt.slim",
    "SlimConfig": "django_matt.slim",
    "get_slim_config": "django_matt.slim",
    "is_module_enabled": "django_matt.slim",
    # Lazy loading
    "LazyModuleProxy": "django_matt.loader",
    "DeferredLoader": "django_matt.loader",
    "lazy_import": "django_matt.loader",
    # Startup profiling
    "StartupProfiler": "django_matt.startup",
    "profile_imports": "django_matt.startup",
}

# Cache for imported modules
_imported = {}


def __getattr__(name: str):
    """Lazy import handler for module attributes."""
    if name in _LAZY_IMPORTS:
        if name not in _imported:
            module_path = _LAZY_IMPORTS[name]
            from importlib import import_module

            module = import_module(module_path)

            # Special case for 'api' - it's an instance, not a class
            if name == "api":
                _imported[name] = getattr(module, "api", module.DjangoMattAPI())
            else:
                try:
                    _imported[name] = getattr(module, name)
                except AttributeError:
                    # Provide helpful error for optional deps (e.g., GraphQL needs strawberry)
                    optional_dep_hints = {
                        "django_matt.graphql": "strawberry-graphql (uv add strawberry-graphql)",
                    }
                    hint = optional_dep_hints.get(module_path, "")
                    if hint:
                        raise ImportError(f"{name!r} requires {hint} to be installed.") from None
                    raise

        return _imported[name]

    raise AttributeError(f"module 'django_matt' has no attribute {name!r}")


def __dir__():
    """List available attributes for autocompletion."""
    return list(_LAZY_IMPORTS.keys()) + ["__version__"]


# Export list for `from django_matt import *`
__all__ = [
    "__version__",
    # Main API class
    "DjangoMattAPI",
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
    "ErrorEnhancementMiddleware",
    "StructuredError",
    "install_default_handlers",
    "build_error_response",
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
    # Auth (lazy - import from django_matt.auth for models)
    "jwt_required",
    "jwt_optional",
    "requires_auth",
    "admin_required",
    "superuser_required",
    "with_roles",
    "with_permission",
    "create_token_pair",
    "JWTAuthenticationMiddleware",
    # Billing (lazy - import from django_matt.billing for models)
    "BillingController",
    "WebhookController",
    "get_provider",
    "get_billing_config",
    # Content negotiation
    "ContentNegotiationMiddleware",
    "ContentNegotiator",
    "renders",
    "render_as",
    "content_negotiated",
    "render",
    "render_format",
    "negotiate",
    # WebSockets (lazy - requires channels)
    "BaseConsumer",
    "JsonConsumer",
    "AuthenticatedConsumer",
    "RoomConsumer",
    "JWTAuthMiddleware",
    "SessionAuthMiddleware",
    "AuthMiddlewareStack",
    "WebSocketRouter",
    "create_asgi_application",
    "broadcast",
    "send_to_user",
    "PresenceManager",
    # Pagination
    "BasePagination",
    "PageNumberPagination",
    "LimitOffsetPagination",
    "CursorPagination",
    # Filtering
    "BaseFilterBackend",
    "DjangoFilterBackend",
    "SearchBackend",
    "OrderingBackend",
    "FilterSet",
    "Filter",
    "CharFilter",
    "IntegerFilter",
    "BooleanFilter",
    "DateFilter",
    "DateTimeFilter",
    "InFilter",
    "PostgresSearchBackend",
    # Dependency Injection
    "Container",
    "container",
    "Singleton",
    "Scoped",
    "Transient",
    "Depends",
    "CurrentUser",
    "CurrentRequest",
    "CurrentOrg",
    "injectable",
    "inject",
    "DependencyInjectionMiddleware",
    # Observability
    "setup_tracing",
    "get_tracer",
    "get_current_span",
    "trace",
    "metric",
    "timed",
    "counted",
    "TracingMiddleware",
    "MetricsMiddleware",
    "LoggingMiddleware",
    "ObservabilityMiddleware",
    "metrics_view",
    "health_view",
    "ready_view",
    "readiness_checker",
    "get_logger",
    "get_logging_config",
    "observability_urlpatterns",
    # Feature Flags
    "feature_enabled",
    "get_variant",
    "feature_flag",
    "requires_flag",
    "FlagMiddleware",
    "FlagContext",
    "FlagController",
    # GraphQL (requires strawberry)
    "GraphQLAPI",
    "GraphQLView",
    "AsyncGraphQLView",
    "GraphQLSchema",
    "generate_schema",
    "graphql_type",
    "graphql_input",
    "graphql_enum",
    "resolver",
    "mutation",
    "subscription",
    "create_type_from_model",
    "DataLoaderRegistry",
    "generate_typescript_types",
    "generate_typescript_client",
    # Experiments / A/B Testing
    "get_experiment_variant",
    "track_experiment_conversion",
    "experiment",
    "requires_experiment",
    "ExperimentMiddleware",
    "ExperimentContext",
    "ExperimentController",
    "analyze_experiment",
    # Resources — zero-config CRUD
    "resource",
    "build_viewset",
    "ResourceConfig",
    "action",
    # Configuration shortcut
    "configure",
    # Middleware stack
    "SecurityHeadersMiddleware",
    "RequestIDMiddleware",
    "CORSMiddleware",
    "RequestLoggingMiddleware",
    "TimingMiddleware",
    "PRODUCTION_STACK",
    "DEVELOPMENT_STACK",
    "get_request_id",
    # Slim mode
    "ModuleRegistry",
    "SlimConfig",
    "get_slim_config",
    "is_module_enabled",
    # Lazy loading
    "LazyModuleProxy",
    "DeferredLoader",
    "lazy_import",
    # Startup profiling
    "StartupProfiler",
    "profile_imports",
]
