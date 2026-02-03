# Advanced Features

This guide covers advanced GraphQL features in Django Matt including persisted queries, custom scalars, schema federation, and performance optimization.

## Persisted Queries

Automatic Persisted Queries (APQ) improve performance by caching query strings and sending only hashes.

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "PERSISTED_QUERIES": True,
    "PERSISTED_QUERIES_CACHE_TTL": 86400,  # 24 hours
}
```

### How It Works

1. Client computes SHA256 hash of query
2. Sends only the hash (not the full query)
3. Server looks up query in cache
4. If not found, client resends with full query
5. Server caches query for future requests

### Client Implementation (Apollo)

```typescript
import { createPersistedQueryLink } from "@apollo/client/link/persisted-queries";
import { sha256 } from "crypto-hash";
import { HttpLink } from "@apollo/client";

const httpLink = new HttpLink({ uri: "/graphql" });

const persistedQueryLink = createPersistedQueryLink({
  sha256,
  useGETForHashedQueries: true, // Use GET for cache-friendly requests
});

const client = new ApolloClient({
  link: persistedQueryLink.concat(httpLink),
  cache: new InMemoryCache(),
});
```

### Pre-registered Queries

For production, you can pre-register queries:

```python
# queries.py
PERSISTED_QUERIES = {
    "abc123...": "query GetUser($id: ID!) { user(id: $id) { id name } }",
    "def456...": "query GetPosts { posts { id title } }",
}

# middleware.py
class PreregisteredQueryMiddleware(SchemaExtension):
    def on_request_start(self):
        extensions = self.execution_context.context.get("request_data", {}).get("extensions", {})
        persisted = extensions.get("persistedQuery", {})

        if persisted.get("sha256Hash") and not self.execution_context.query:
            query = PERSISTED_QUERIES.get(persisted["sha256Hash"])
            if query:
                self.execution_context.query = query
            else:
                raise Exception("PersistedQueryNotFound")
```

## Custom Scalars

Define custom scalar types for specialized data:

### Date/Time Scalars

```python
import strawberry
from datetime import datetime, date, time

@strawberry.scalar(
    description="Date in ISO format (YYYY-MM-DD)",
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: date.fromisoformat(v) if v else None,
)
class ISODate(date):
    pass

@strawberry.scalar(
    description="DateTime in ISO 8601 format",
    serialize=lambda v: v.isoformat() if v else None,
    parse_value=lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None,
)
class ISODateTime(datetime):
    pass
```

### Money Scalar

```python
from decimal import Decimal

@strawberry.scalar(
    description="Monetary value with 2 decimal places",
    serialize=lambda v: float(v) if v else None,
    parse_value=lambda v: Decimal(str(v)).quantize(Decimal("0.01")) if v else None,
)
class Money(Decimal):
    pass

@graphql_type
class ProductType:
    id: int
    name: str
    price: Money  # Stored as Decimal, serialized as float
```

### JSON Scalar

```python
import json

@strawberry.scalar(
    description="Arbitrary JSON data",
    serialize=lambda v: v,  # Already JSON-compatible
    parse_value=lambda v: v,
)
class JSONScalar:
    pass

# Or use built-in
from strawberry.scalars import JSON

@graphql_type
class SettingsType:
    id: int
    config: JSON  # Dict/list serialized as JSON
```

### Upload Scalar

```python
from strawberry.file_uploads import Upload

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def upload_file(self, file: Upload) -> str:
        content = await file.read()
        filename = file.filename
        # Save file...
        return f"Uploaded {filename}"
```

## Schema Federation

For microservices architecture, use Apollo Federation:

### Defining a Federated Service

```python
import strawberry
from strawberry.federation import FederationConfiguration

# Mark types as federated entities
@strawberry.federation.type(keys=["id"])
class UserType:
    id: strawberry.ID

    @classmethod
    def resolve_reference(cls, id: strawberry.ID) -> "UserType":
        """Resolve user from other services."""
        user = User.objects.get(id=id)
        return UserType.from_orm(user)

# Extend types from other services
@strawberry.federation.type(extend=True, keys=["id"])
class ProductType:
    id: strawberry.ID = strawberry.federation.field(external=True)

    @strawberry.field
    def reviews(self) -> list["ReviewType"]:
        """Reviews for this product (from this service)."""
        return Review.objects.filter(product_id=self.id)

# Create federated schema
schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    config=FederationConfiguration(
        enable_federation_2=True,
    ),
)
```

### Gateway Configuration

```yaml
# supergraph.yaml
federation_version: 2
subgraphs:
  users:
    routing_url: http://users-service/graphql
    schema:
      subgraph_url: http://users-service/graphql
  products:
    routing_url: http://products-service/graphql
    schema:
      subgraph_url: http://products-service/graphql
  reviews:
    routing_url: http://reviews-service/graphql
    schema:
      subgraph_url: http://reviews-service/graphql
```

## Query Optimization

### Automatic Query Optimization

```python
from django_matt.utils import optimize_queryset

@strawberry.field
def posts(self, info: Info) -> list[PostType]:
    queryset = Post.objects.all()
    # Automatically adds select_related/prefetch_related
    optimized = optimize_queryset(queryset)
    return optimized
```

### Info-Based Optimization

Optimize based on requested fields:

```python
def get_selections(info: Info, depth: int = 1) -> set[str]:
    """Get field names from GraphQL selection set."""
    selections = set()
    for selection in info.selected_fields:
        selections.add(selection.name)
        if depth > 0 and selection.selections:
            for sub in selection.selections:
                selections.add(f"{selection.name}.{sub.name}")
    return selections

@strawberry.field
def posts(self, info: Info) -> list[PostType]:
    selections = get_selections(info)
    queryset = Post.objects.all()

    # Only load author if requested
    if "author" in selections or any(s.startswith("author.") for s in selections):
        queryset = queryset.select_related("author")

    # Only load comments if requested
    if "comments" in selections:
        queryset = queryset.prefetch_related("comments")

    return queryset
```

### Batching with DataLoader

```python
from django_matt.graphql import DataLoaderRegistry, ModelDataLoader

def setup_loaders(info: Info) -> DataLoaderRegistry:
    """Setup optimized data loaders based on query."""
    registry = DataLoaderRegistry()

    # Pre-configure loaders with common optimizations
    registry.register_model(
        User,
        type_class=UserType,
        select_related=["profile", "organization"],
        prefetch_related=["groups"],
    )

    registry.register_model(
        Post,
        type_class=PostType,
        select_related=["author", "category"],
        prefetch_related=["tags"],
    )

    return registry
```

## Caching

### Response Caching

```python
from django.core.cache import cache
from functools import wraps

def cache_resolver(timeout: int = 300, key_prefix: str = ""):
    """Cache resolver results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from arguments
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(kwargs))}"
            result = cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator

@strawberry.type
class Query:
    @cache_resolver(timeout=60, key_prefix="posts")
    @strawberry.field
    def featured_posts(self) -> list[PostType]:
        return Post.objects.filter(
            is_featured=True,
            is_published=True,
        ).order_by("-published_at")[:10]
```

### Edge Caching with CDN

```python
class CacheControlMiddleware(SchemaExtension):
    """Add cache control headers for CDN caching."""

    def on_request_end(self):
        response = self.execution_context.context.get("response")
        if not response:
            return

        query = self.execution_context.query or ""

        # Only cache queries, not mutations
        if "mutation" in query.lower():
            response["Cache-Control"] = "no-store"
            return

        # Check for authenticated operations
        if self.execution_context.context.get("user"):
            response["Cache-Control"] = "private, max-age=60"
        else:
            response["Cache-Control"] = "public, max-age=300"
```

## Error Handling

### Custom Error Types

```python
@graphql_type
class FieldError:
    field: str
    message: str

@graphql_type
class ValidationErrors:
    errors: list[FieldError]

# Union for error handling
UserOrErrors = strawberry.union("UserOrErrors", types=[UserType, ValidationErrors])

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, input: CreateUserInput) -> UserOrErrors:
        errors = []

        # Validate
        if "@" not in input.email:
            errors.append(FieldError(field="email", message="Invalid email"))
        if len(input.password) < 8:
            errors.append(FieldError(field="password", message="Too short"))

        if errors:
            return ValidationErrors(errors=errors)

        user = User.objects.create_user(**vars(input))
        return UserType.from_orm(user)
```

### Error Extensions

```python
class CustomError(Exception):
    def __init__(self, message: str, code: str, details: dict = None):
        super().__init__(message)
        self.extensions = {
            "code": code,
            "details": details or {},
        }

@strawberry.type
class Mutation:
    @strawberry.mutation
    def delete_post(self, id: strawberry.ID) -> bool:
        post = Post.objects.filter(id=id).first()
        if not post:
            raise CustomError(
                "Post not found",
                code="POST_NOT_FOUND",
                details={"post_id": id},
            )
        post.delete()
        return True
```

## Introspection Control

### Disable in Production

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "INTROSPECTION_ENABLED": DEBUG,
    "INTROSPECTION_AUTH_REQUIRED": True,  # Require auth even if enabled
}
```

### Custom Introspection Middleware

```python
class IntrospectionGuard(SchemaExtension):
    def on_request_start(self):
        query = self.execution_context.query or ""

        if "__schema" in query or "__type" in query:
            # Check if allowed
            config = get_graphql_config()
            if not config.introspection_enabled:
                raise Exception("Introspection is disabled")

            if config.introspection_auth_required:
                user = self.execution_context.context.get("user")
                if not user or not user.is_staff:
                    raise Exception("Introspection requires admin access")
```

## Batching

### Query Batching

Accept multiple operations in a single request:

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "BATCHING_ENABLED": True,
    "MAX_BATCH_SIZE": 10,
}
```

### Client Usage

```typescript
// Send multiple queries in one request
const [usersResult, postsResult] = await Promise.all([
  client.query({ query: GET_USERS }),
  client.query({ query: GET_POSTS }),
]);

// With Apollo batching
const link = new BatchHttpLink({
  uri: "/graphql",
  batchMax: 5,
  batchInterval: 20,
});
```

## Directive Implementation

### @deprecated Directive

```python
@graphql_type
class UserType:
    id: int
    username: str

    @strawberry.field(deprecation_reason="Use fullName instead")
    def name(self) -> str:
        return self.username

    @strawberry.field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

### Custom Directives

```python
from strawberry.directive import DirectiveDefinition, DirectiveLocation

@strawberry.directive(
    locations=[DirectiveLocation.FIELD],
    description="Format a date field",
)
def date_format(value: str, format: str = "%Y-%m-%d") -> str:
    from datetime import datetime
    dt = datetime.fromisoformat(value)
    return dt.strftime(format)

# Usage in query
# query {
#   post {
#     publishedAt @dateFormat(format: "%B %d, %Y")
#   }
# }
```

## Testing

### Unit Testing Resolvers

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_info():
    info = MagicMock()
    info.context = {
        "user": UserFactory(is_staff=True),
        "dataloaders": DataLoaderRegistry(),
    }
    return info

def test_posts_query(mock_info):
    query = Query()
    posts = query.posts(mock_info)
    assert len(posts) > 0

def test_create_post_mutation(mock_info):
    mutation = Mutation()
    input = CreatePostInput(title="Test", content="Content")
    result = mutation.create_post(mock_info, input)
    assert result.title == "Test"
```

### Integration Testing

```python
from django.test import TestCase, AsyncClient
from django_matt.graphql import GraphQLView
from myapp.graphql import schema

class GraphQLTestCase(TestCase):
    def setUp(self):
        self.client = AsyncClient()
        self.user = UserFactory()

    async def test_query(self):
        response = await self.client.post(
            "/graphql/",
            {
                "query": "query { users { id email } }",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.user.token}",
        )
        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"]["users"], list)

    async def test_mutation(self):
        response = await self.client.post(
            "/graphql/",
            {
                "query": """
                    mutation CreatePost($input: CreatePostInput!) {
                        createPost(input: $input) {
                            id
                            title
                        }
                    }
                """,
                "variables": {
                    "input": {"title": "Test", "content": "Content"},
                },
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.user.token}",
        )
        data = response.json()
        self.assertIsNone(data.get("errors"))
        self.assertEqual(data["data"]["createPost"]["title"], "Test")
```

## Performance Monitoring

### Tracing Middleware

```python
import time
from dataclasses import dataclass

@dataclass
class ResolverTiming:
    path: str
    duration_ms: float

class TracingMiddleware(SchemaExtension):
    def __init__(self, execution_context=None):
        super().__init__(execution_context=execution_context)
        self.timings = []

    def resolve(self, next, root, info, **kwargs):
        start = time.perf_counter()
        result = next(root, info, **kwargs)
        duration = (time.perf_counter() - start) * 1000

        self.timings.append(ResolverTiming(
            path=".".join(str(p) for p in info.path),
            duration_ms=duration,
        ))

        return result

    def on_request_end(self):
        # Add timings to response extensions
        if self.timings:
            self.execution_context.result.extensions = {
                "tracing": {
                    "resolvers": [
                        {"path": t.path, "duration": t.duration_ms}
                        for t in self.timings
                    ],
                    "total": sum(t.duration_ms for t in self.timings),
                }
            }
```

### Query Complexity Tracking

```python
class ComplexityTrackingMiddleware(SchemaExtension):
    def on_request_start(self):
        complexity = calculate_complexity(self.execution_context.query)
        self.execution_context.context["complexity"] = complexity

    def on_request_end(self):
        complexity = self.execution_context.context.get("complexity", 0)

        # Log high-complexity queries
        if complexity > 50:
            logger.warning(
                "High complexity query",
                extra={
                    "complexity": complexity,
                    "query": self.execution_context.query[:500],
                    "user": self.execution_context.context.get("user"),
                }
            )

        # Add to response
        self.execution_context.result.extensions = {
            "complexity": complexity,
        }
```
