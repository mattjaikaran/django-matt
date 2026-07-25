"""
Django Matt GraphQL - GraphQL API integration with Strawberry.

Provides:
- Auto-generate GraphQL schema from Django models
- Strawberry integration (primary) with fallback to graphene
- Automatic CRUD mutations
- Filtering, pagination, ordering
- DataLoader for N+1 prevention
- JWT authentication integration
- Permission checking per field
- Subscription support via WebSockets
- Query complexity analysis and limiting
- Persisted queries support
- TypeScript client codegen

Requires: uv add strawberry-graphql

Configuration in settings.py:

    DJANGO_MATT_GRAPHQL = {
        "ENABLED": True,
        "DEBUG": True,
        "MAX_DEPTH": 10,
        "MAX_COMPLEXITY": 100,
        "PERSISTED_QUERIES": True,
        "SUBSCRIPTIONS_ENABLED": True,
        "AUTH_REQUIRED": False,
        "RATE_LIMIT": {
            "ENABLED": True,
            "QUERIES_PER_MINUTE": 100,
        },
    }

Example usage:

    from django_matt.graphql import GraphQLAPI, graphql_type
    from django_matt.graphql.schema import generate_schema

    # Auto-generate from models
    schema = generate_schema(models=[User, Post, Comment])

    # Or manual definition
    @graphql_type
    class UserType:
        id: int
        email: str
        posts: list["PostType"]

    # Add to API
    api = DjangoMattAPI()
    api.add_graphql("/graphql", schema=schema)
"""

from django_matt.graphql.config import (
    GraphQLConfig,
    RateLimitConfig,
    get_graphql_config,
    graphql_config,
)

# Check if strawberry is available
try:
    import strawberry

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False

# Decorators (always available)
from django_matt.graphql.decorators import (
    authenticated_field,
    complexity,
    field,
    graphql_enum,
    graphql_input,
    graphql_interface,
    graphql_type,
    mutation,
    permission_field,
    rate_limited,
    resolver,
    subscription,
)

# Core functionality (conditionally available)
if STRAWBERRY_AVAILABLE:
    from django_matt.graphql.codegen import (
        TypeScriptGenerator,
        generate_graphql_operations,
        generate_typescript_client,
        generate_typescript_types,
    )
    from django_matt.graphql.dataloaders import (
        DataLoaderRegistry,
        ModelDataLoader,
        RelatedDataLoader,
        create_dataloaders,
        get_loader,
    )
    from django_matt.graphql.middleware import (
        AuthMiddleware,
        ComplexityMiddleware,
        DepthLimitMiddleware,
        LoggingMiddleware,
        PersistedQueryMiddleware,
        RateLimitMiddleware,
    )
    from django_matt.graphql.mutations import (
        MutationGenerator,
        generate_bulk_create_mutation,
        generate_bulk_delete_mutation,
        generate_bulk_update_mutation,
        generate_create_mutation,
        generate_delete_mutation,
        generate_update_mutation,
    )
    from django_matt.graphql.queries import (
        QueryGenerator,
        generate_connection_query,
        generate_detail_query,
        generate_list_query,
    )
    from django_matt.graphql.schema import (
        GraphQLSchema,
        generate_mutations,
        generate_queries,
        generate_schema,
    )
    from django_matt.graphql.subscriptions import (
        SubscriptionGenerator,
        SubscriptionManager,
        generate_subscription,
        subscribe_to_model,
    )
    from django_matt.graphql.types import (
        ConnectionType,
        DjangoModelType,
        EdgeType,
        NodeInterface,
        PageInfoType,
        create_type_from_model,
    )
    from django_matt.graphql.views import (
        AsyncGraphQLView,
        GraphQLAPI,
        GraphQLView,
    )

    __all__ = [
        # Config
        "GraphQLConfig",
        "RateLimitConfig",
        "get_graphql_config",
        "graphql_config",
        # Decorators
        "graphql_type",
        "graphql_input",
        "graphql_interface",
        "graphql_enum",
        "resolver",
        "mutation",
        "subscription",
        "field",
        "permission_field",
        "authenticated_field",
        "rate_limited",
        "complexity",
        # Types
        "DjangoModelType",
        "ConnectionType",
        "EdgeType",
        "PageInfoType",
        "NodeInterface",
        "create_type_from_model",
        # Schema
        "GraphQLSchema",
        "generate_schema",
        "generate_queries",
        "generate_mutations",
        # Queries
        "QueryGenerator",
        "generate_list_query",
        "generate_detail_query",
        "generate_connection_query",
        # Mutations
        "MutationGenerator",
        "generate_create_mutation",
        "generate_update_mutation",
        "generate_delete_mutation",
        "generate_bulk_create_mutation",
        "generate_bulk_update_mutation",
        "generate_bulk_delete_mutation",
        # Subscriptions
        "SubscriptionManager",
        "SubscriptionGenerator",
        "generate_subscription",
        "subscribe_to_model",
        # DataLoaders
        "DataLoaderRegistry",
        "ModelDataLoader",
        "RelatedDataLoader",
        "get_loader",
        "create_dataloaders",
        # Middleware
        "AuthMiddleware",
        "RateLimitMiddleware",
        "ComplexityMiddleware",
        "DepthLimitMiddleware",
        "PersistedQueryMiddleware",
        "LoggingMiddleware",
        # Views
        "GraphQLView",
        "AsyncGraphQLView",
        "GraphQLAPI",
        # Codegen
        "TypeScriptGenerator",
        "generate_typescript_types",
        "generate_typescript_client",
        "generate_graphql_operations",
        # Availability flag
        "STRAWBERRY_AVAILABLE",
    ]
else:
    # Limited exports when strawberry is not available
    __all__ = [
        # Config
        "GraphQLConfig",
        "RateLimitConfig",
        "get_graphql_config",
        "graphql_config",
        # Decorators (stubs that raise errors)
        "graphql_type",
        "graphql_input",
        "graphql_interface",
        "graphql_enum",
        "resolver",
        "mutation",
        "subscription",
        "field",
        "permission_field",
        "authenticated_field",
        "rate_limited",
        "complexity",
        # Availability flag
        "STRAWBERRY_AVAILABLE",
    ]


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL support. "
            'Install it with: uv add "strawberry-graphql[django]"'
        )


# Convenience function to check availability
def check_strawberry_available():
    """Check if strawberry is available and raise a helpful error if not."""
    _require_strawberry()
    return True
