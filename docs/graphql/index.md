# GraphQL Integration

Django Matt provides a first-class GraphQL integration built on [Strawberry](https://strawberry.rocks/), offering automatic schema generation from Django models, type-safe resolvers, and seamless integration with the rest of the framework.

## Why GraphQL?

GraphQL offers several advantages over traditional REST APIs:

| Feature | REST | GraphQL |
|---------|------|---------|
| Data fetching | Multiple endpoints, over-fetching | Single endpoint, precise data |
| Type safety | Manual documentation | Built-in schema types |
| Versioning | URL versioning (/v1, /v2) | Schema evolution |
| Documentation | OpenAPI/Swagger | Introspection |
| Real-time | Polling or WebSockets | Native subscriptions |
| N+1 Problem | Requires careful API design | DataLoaders |

## GraphQL vs REST in Django Matt

=== "GraphQL"

    ```python
    from django_matt.graphql import generate_schema, GraphQLAPI

    # Auto-generate schema from Django models
    schema = generate_schema(models=[User, Post, Comment])

    # Add to your API
    graphql = GraphQLAPI(schema=schema)

    # Single endpoint handles all queries
    # POST /graphql
    ```

=== "REST"

    ```python
    from django_matt import DjangoMattAPI
    from django_matt.views import APIViewSet, ListView, ReadView

    api = DjangoMattAPI()

    # Multiple endpoints for each resource
    class UserViewSet(APIViewSet):
        api = api
        model = User
        list = ListView()
        read = ReadView()

    class PostViewSet(APIViewSet):
        api = api
        model = Post
        list = ListView()
        read = ReadView()

    # GET /users, GET /users/{id}
    # GET /posts, GET /posts/{id}
    ```

## Quick Example

```python
from django_matt.graphql import (
    generate_schema,
    GraphQLAPI,
    graphql_type,
    create_type_from_model,
)

# Option 1: Auto-generate everything
schema = generate_schema(
    models=[User, Post, Comment],
    auto_mutations=True,
)

# Option 2: Manual type definitions
@graphql_type
class UserType:
    id: int
    email: str
    username: str
    posts: list["PostType"]

@graphql_type
class PostType:
    id: int
    title: str
    content: str
    author: UserType

# Add to Django URLs
graphql = GraphQLAPI(schema=schema, graphiql=True)
urlpatterns = graphql.urls
```

## Key Features

### Automatic Schema Generation

Generate GraphQL types directly from Django models without writing boilerplate:

```python
from django_matt.graphql import create_type_from_model

# Auto-generate type with all fields
UserType = create_type_from_model(User)

# Control which fields are exposed
UserType = create_type_from_model(
    User,
    fields=["id", "email", "username"],
    exclude=["password", "last_login"],
)
```

### CRUD Mutations

Automatic create, update, delete mutations with validation:

```python
from django_matt.graphql import generate_schema

schema = generate_schema(
    models=[User, Post],
    auto_mutations=True,  # Generates createUser, updateUser, deleteUser, etc.
)
```

### Real-time Subscriptions

WebSocket-based subscriptions for real-time updates:

```python
from django_matt.graphql import SubscriptionGenerator

generator = SubscriptionGenerator(Post, PostType)

@strawberry.type
class Subscription:
    post_created = generator.created_subscription()
    post_updated = generator.updated_subscription()
```

### N+1 Prevention

Built-in DataLoader support to prevent N+1 query problems:

```python
from django_matt.graphql import ModelDataLoader, get_loader

# Automatically batches database queries
loader = ModelDataLoader(User)
users = await loader.load_many([1, 2, 3])  # Single query
```

### Security Built-in

Authentication, rate limiting, and query complexity limits:

```python
from django_matt.graphql import (
    AuthMiddleware,
    RateLimitMiddleware,
    ComplexityMiddleware,
)

# All enabled by default through configuration
DJANGO_MATT_GRAPHQL = {
    "AUTH_REQUIRED": True,
    "MAX_COMPLEXITY": 100,
    "MAX_DEPTH": 10,
    "RATE_LIMIT": {"ENABLED": True, "QUERIES_PER_MINUTE": 100},
}
```

## Installation

GraphQL support requires the `strawberry-graphql` package:

```bash
uv add strawberry-graphql[django]
```

## Configuration

Configure GraphQL in your Django settings:

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "ENABLED": True,
    "DEBUG": DEBUG,

    # Query limits
    "MAX_DEPTH": 10,
    "MAX_COMPLEXITY": 100,
    "MAX_ALIASES": 10,

    # Persisted queries (APQ)
    "PERSISTED_QUERIES": True,
    "PERSISTED_QUERIES_CACHE_TTL": 86400,

    # Subscriptions
    "SUBSCRIPTIONS_ENABLED": True,
    "SUBSCRIPTION_KEEPALIVE": 30,

    # Authentication
    "AUTH_REQUIRED": False,
    "AUTH_HEADER_NAME": "Authorization",

    # Introspection (disable in production)
    "INTROSPECTION_ENABLED": True,
    "INTROSPECTION_AUTH_REQUIRED": False,

    # GraphiQL playground
    "GRAPHIQL_ENABLED": True,

    # Rate limiting
    "RATE_LIMIT": {
        "ENABLED": True,
        "QUERIES_PER_MINUTE": 100,
        "MUTATIONS_PER_MINUTE": 50,
        "SUBSCRIPTIONS_PER_MINUTE": 20,
        "BURST_LIMIT": 10,
        "BY_IP": True,
        "BY_USER": True,
    },

    # Batching
    "BATCHING_ENABLED": True,
    "MAX_BATCH_SIZE": 10,

    # Logging
    "LOG_QUERIES": False,
    "LOG_MUTATIONS": True,
    "LOG_ERRORS": True,
}
```

## Module Overview

| Module | Description |
|--------|-------------|
| `types` | Type generation from Django models |
| `schema` | Schema building and auto-generation |
| `queries` | Query resolvers with filtering/pagination |
| `mutations` | CRUD mutations with hooks |
| `subscriptions` | WebSocket subscriptions |
| `dataloaders` | N+1 prevention with DataLoaders |
| `middleware` | Auth, rate limiting, complexity |
| `codegen` | TypeScript client generation |
| `decorators` | Convenience decorators |
| `views` | Django views for GraphQL endpoint |

## When to Use GraphQL

**Choose GraphQL when:**

- Mobile apps need efficient data fetching
- Frontend needs to request specific fields
- Multiple clients need different data shapes
- Real-time updates are required
- You want strong type contracts

**Choose REST when:**

- Simple CRUD operations
- File uploads are common
- Caching is critical (HTTP caching)
- Team is more familiar with REST
- Third-party API consumers expect REST

## Integration with DjangoMattAPI

GraphQL can be added alongside REST endpoints:

```python
from django_matt import DjangoMattAPI
from django_matt.graphql import GraphQLAPI, generate_schema

# REST API
api = DjangoMattAPI()

@api.get("/health")
def health_check(request):
    return {"status": "ok"}

# GraphQL API
schema = generate_schema(models=[User, Post])
graphql = GraphQLAPI(schema=schema)

# Both available
urlpatterns = [
    path("api/", api.urls),
    path("graphql/", graphql.urls),
]
```

## Next Steps

- [Quickstart](quickstart.md) - Get started in 5 minutes
- [Schema](schema.md) - Schema generation and customization
- [Types](types.md) - Type definitions and inputs
- [Queries](queries.md) - Query resolvers and filtering
- [Mutations](mutations.md) - CRUD operations
- [Subscriptions](subscriptions.md) - Real-time updates
- [DataLoaders](dataloaders.md) - N+1 prevention
- [Authentication](authentication.md) - JWT and permissions
- [Middleware](middleware.md) - Rate limiting and security
- [Code Generation](codegen.md) - TypeScript client generation
- [Advanced](advanced.md) - Persisted queries, federation
