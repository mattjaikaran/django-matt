# Middleware

Django Matt's GraphQL middleware provides security, performance, and observability features including rate limiting, complexity analysis, depth limiting, persisted queries, and logging.

## Overview

Middleware are implemented as Strawberry Schema Extensions that hook into the request lifecycle:

```python
from django_matt.graphql import (
    AuthMiddleware,
    RateLimitMiddleware,
    ComplexityMiddleware,
    DepthLimitMiddleware,
    PersistedQueryMiddleware,
    LoggingMiddleware,
)

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        AuthMiddleware,
        RateLimitMiddleware,
        ComplexityMiddleware,
        DepthLimitMiddleware,
        PersistedQueryMiddleware,
        LoggingMiddleware,
    ],
)
```

## Default Extensions

Use `get_default_extensions()` to get all recommended middleware:

```python
from django_matt.graphql import get_default_extensions

schema = strawberry.Schema(
    query=Query,
    extensions=get_default_extensions(),
)
```

This includes all middleware based on your configuration settings.

## Rate Limiting

The `RateLimitMiddleware` prevents API abuse by limiting request frequency:

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "RATE_LIMIT": {
        "ENABLED": True,
        "QUERIES_PER_MINUTE": 100,
        "MUTATIONS_PER_MINUTE": 50,
        "SUBSCRIPTIONS_PER_MINUTE": 20,
        "BURST_LIMIT": 10,
        "BY_IP": True,
        "BY_USER": True,
    },
}
```

### How It Works

1. Extracts identifier (user ID and/or IP address)
2. Checks request count in the current time window
3. Raises exception if limit exceeded
4. Stores request timestamp for tracking

### Per-Field Rate Limiting

Use the `@rate_limited` decorator for specific operations:

```python
from django_matt.graphql import rate_limited

@strawberry.type
class Mutation:
    @rate_limited(max_calls=5, period_seconds=60)
    @strawberry.mutation
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Limited to 5 emails per minute."""
        send_email(to, subject, body)
        return True

    @rate_limited(max_calls=3, period_seconds=3600)
    @strawberry.mutation
    def request_password_reset(self, email: str) -> bool:
        """Limited to 3 resets per hour."""
        send_password_reset(email)
        return True
```

## Complexity Analysis

The `ComplexityMiddleware` prevents expensive queries:

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "MAX_COMPLEXITY": 100,  # Maximum total complexity
    "MAX_ALIASES": 10,      # Maximum field aliases
}
```

### How Complexity Is Calculated

- Each field adds to total complexity
- Nested fields multiply complexity
- Lists multiply by expected size
- Custom complexity can be set per field

### Setting Field Complexity

```python
from django_matt.graphql import complexity

@strawberry.type
class Query:
    @complexity(1)
    @strawberry.field
    def simple_field(self) -> str:
        return "Simple"

    @complexity(10)
    @strawberry.field
    def expensive_query(self) -> list[DataType]:
        """This costs 10 complexity points."""
        return expensive_computation()

    @complexity(50)
    @strawberry.field
    def very_expensive_query(self) -> AnalyticsReport:
        """This costs 50 complexity points."""
        return generate_report()
```

### Query Examples

```graphql
# Low complexity (acceptable)
query {
  user(id: "1") {    # 1 point
    name             # 1 point
    email            # 1 point
  }
}
# Total: 3 points

# High complexity (may be rejected)
query {
  users {                    # 10 points (list)
    posts {                  # 10 x 10 = 100 points (nested list)
      comments {             # 100 x 10 = 1000 points (deeply nested)
        author {
          name
        }
      }
    }
  }
}
# Total: 1000+ points (REJECTED if max is 100)
```

## Depth Limiting

The `DepthLimitMiddleware` prevents deeply nested queries:

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "MAX_DEPTH": 10,  # Maximum query depth
}
```

### How Depth Is Calculated

```graphql
query {
  users {           # Depth 1
    posts {         # Depth 2
      comments {    # Depth 3
        author {    # Depth 4
          profile { # Depth 5
            avatar  # Depth 6
          }
        }
      }
    }
  }
}
```

### Error Response

```json
{
  "errors": [
    {
      "message": "Query exceeds maximum depth. Depth: 12, max: 10"
    }
  ]
}
```

## Persisted Queries

The `PersistedQueryMiddleware` implements Automatic Persisted Queries (APQ) for performance:

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "PERSISTED_QUERIES": True,
    "PERSISTED_QUERIES_CACHE_TTL": 86400,  # 24 hours
}
```

### How APQ Works

1. Client sends query with SHA256 hash
2. Server checks cache for the query
3. If found, executes cached query
4. If not found, client resends with full query
5. Server caches query for future requests

### Client Implementation

```typescript
import { createPersistedQueryLink } from "@apollo/client/link/persisted-queries";
import { sha256 } from "crypto-hash";

const link = createPersistedQueryLink({
  sha256,
  useGETForHashedQueries: true,
});
```

### First Request (Cache Miss)

```json
// Request
{
  "extensions": {
    "persistedQuery": {
      "version": 1,
      "sha256Hash": "abc123..."
    }
  }
}

// Response
{
  "errors": [
    { "message": "PersistedQueryNotFound" }
  ]
}
```

### Second Request (With Query)

```json
// Request
{
  "query": "query GetUser($id: ID!) { user(id: $id) { name } }",
  "extensions": {
    "persistedQuery": {
      "version": 1,
      "sha256Hash": "abc123..."
    }
  }
}

// Response (query is cached)
{
  "data": { "user": { "name": "John" } }
}
```

### Subsequent Requests (Cache Hit)

```json
// Request (no query needed)
{
  "extensions": {
    "persistedQuery": {
      "version": 1,
      "sha256Hash": "abc123..."
    }
  }
}

// Response (from cache)
{
  "data": { "user": { "name": "John" } }
}
```

## Logging

The `LoggingMiddleware` provides request logging and monitoring:

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "LOG_QUERIES": False,   # Log all queries
    "LOG_MUTATIONS": True,  # Log all mutations
    "LOG_ERRORS": True,     # Log errors
}

# Configure logging
LOGGING = {
    "version": 1,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django_matt.graphql": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
```

### Log Output

```
INFO django_matt.graphql: GraphQL mutation started
    operation_name=CreatePost
    query=mutation CreatePost($input: CreatePostInput!) { ...

INFO django_matt.graphql: GraphQL mutation completed
    operation_name=CreatePost
    duration=0.045

ERROR django_matt.graphql: GraphQL error
    error=Post not found
    operation_name=UpdatePost
    duration=0.012
```

## Authentication Middleware

The `AuthMiddleware` handles JWT token validation:

### How It Works

1. Extracts token from `Authorization: Bearer <token>` header
2. Validates token using Django Matt's JWT module
3. Sets `request.user` and `context["user"]`
4. Raises `PermissionError` if auth required but missing

### Configuration

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    "AUTH_REQUIRED": False,  # Require auth for all operations
    "AUTH_HEADER_NAME": "Authorization",
}
```

## Custom Middleware

Create your own middleware by extending `SchemaExtension`:

```python
from strawberry.extensions import SchemaExtension
from strawberry.types import ExecutionContext

class CustomMiddleware(SchemaExtension):
    def __init__(self, execution_context: ExecutionContext = None):
        if execution_context:
            super().__init__(execution_context=execution_context)

    def on_request_start(self):
        """Called when a request starts."""
        # Access request data
        query = self.execution_context.query
        operation_name = self.execution_context.operation_name
        context = self.execution_context.context

        # Add custom logic
        context["request_start_time"] = time.time()

    def on_request_end(self):
        """Called when a request ends."""
        context = self.execution_context.context
        result = self.execution_context.result

        # Log timing
        duration = time.time() - context.get("request_start_time", 0)
        print(f"Request took {duration:.3f}s")

        # Check for errors
        if result and result.errors:
            for error in result.errors:
                print(f"Error: {error}")
```

### Request Context Access

```python
class MyMiddleware(SchemaExtension):
    def on_request_start(self):
        # Get Django request
        request = self.execution_context.context.get("request")

        # Get query info
        query = self.execution_context.query
        operation_name = self.execution_context.operation_name
        variables = self.execution_context.variables

        # Get user
        user = self.execution_context.context.get("user")
```

### Modifying Context

```python
class EnrichContextMiddleware(SchemaExtension):
    def on_request_start(self):
        context = self.execution_context.context

        # Add feature flags
        context["features"] = get_user_features(context.get("user"))

        # Add request metadata
        context["request_id"] = str(uuid.uuid4())
        context["client_version"] = context["request"].META.get("HTTP_X_CLIENT_VERSION")
```

## Middleware Order

Middleware execute in order. The recommended order is:

```python
extensions = [
    # 1. Authentication first (sets user)
    AuthMiddleware,

    # 2. Rate limiting (early rejection)
    RateLimitMiddleware,

    # 3. Query validation
    ComplexityMiddleware,
    DepthLimitMiddleware,

    # 4. Performance optimization
    PersistedQueryMiddleware,

    # 5. Observability last
    LoggingMiddleware,
]
```

## Disabling Middleware

Disable specific middleware via configuration:

```python
# settings.py
DJANGO_MATT_GRAPHQL = {
    # Disable rate limiting
    "RATE_LIMIT": {"ENABLED": False},

    # Disable persisted queries
    "PERSISTED_QUERIES": False,
}
```

Or exclude from extensions list:

```python
from django_matt.graphql import (
    AuthMiddleware,
    ComplexityMiddleware,
    LoggingMiddleware,
)

# Only use specific middleware
schema = strawberry.Schema(
    query=Query,
    extensions=[
        AuthMiddleware,
        ComplexityMiddleware,
        LoggingMiddleware,
        # No rate limiting or persisted queries
    ],
)
```

## Complete Example

```python
# graphql/middleware.py
import time
import logging
from strawberry.extensions import SchemaExtension

logger = logging.getLogger(__name__)

class MetricsMiddleware(SchemaExtension):
    """Custom middleware for metrics collection."""

    def on_request_start(self):
        self.start_time = time.time()
        context = self.execution_context.context

        # Track operation
        context["metrics"] = {
            "operation": self.execution_context.operation_name,
            "query_size": len(self.execution_context.query or ""),
        }

    def on_request_end(self):
        duration = time.time() - self.start_time
        context = self.execution_context.context
        result = self.execution_context.result

        metrics = context.get("metrics", {})
        metrics["duration_ms"] = duration * 1000
        metrics["has_errors"] = bool(result and result.errors)

        # Send to metrics service
        send_metrics("graphql_request", metrics)

        # Log slow queries
        if duration > 1.0:
            logger.warning(
                "Slow GraphQL query",
                extra={
                    "operation": metrics["operation"],
                    "duration": duration,
                }
            )

class TracingMiddleware(SchemaExtension):
    """Add distributed tracing headers."""

    def on_request_start(self):
        context = self.execution_context.context
        request = context.get("request")

        if request:
            # Extract trace context
            trace_id = request.META.get("HTTP_X_TRACE_ID")
            span_id = request.META.get("HTTP_X_SPAN_ID")

            context["trace_id"] = trace_id or str(uuid.uuid4())
            context["span_id"] = str(uuid.uuid4())
            context["parent_span_id"] = span_id

class SecurityMiddleware(SchemaExtension):
    """Additional security checks."""

    BLOCKED_OPERATIONS = ["__schema", "__type"]

    def on_request_start(self):
        query = self.execution_context.query or ""

        # Block introspection in production
        if not settings.DEBUG:
            for op in self.BLOCKED_OPERATIONS:
                if op in query:
                    raise Exception("Introspection is disabled")

        # Check for injection attempts
        dangerous_patterns = ["__proto__", "constructor", "prototype"]
        for pattern in dangerous_patterns:
            if pattern in query:
                raise Exception("Invalid query")
```

```python
# graphql/schema.py
from django_matt.graphql import get_default_extensions
from .middleware import MetricsMiddleware, TracingMiddleware, SecurityMiddleware

# Combine default and custom middleware
extensions = [
    SecurityMiddleware,       # First: security checks
    *get_default_extensions(),  # Default middleware
    MetricsMiddleware,        # Additional metrics
    TracingMiddleware,        # Distributed tracing
]

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=extensions,
)
```

## Reference

### Configuration Options

```python
DJANGO_MATT_GRAPHQL = {
    # Rate Limiting
    "RATE_LIMIT": {
        "ENABLED": True,
        "QUERIES_PER_MINUTE": 100,
        "MUTATIONS_PER_MINUTE": 50,
        "SUBSCRIPTIONS_PER_MINUTE": 20,
        "BURST_LIMIT": 10,
        "BY_IP": True,
        "BY_USER": True,
    },

    # Complexity
    "MAX_COMPLEXITY": 100,
    "MAX_ALIASES": 10,

    # Depth
    "MAX_DEPTH": 10,

    # Persisted Queries
    "PERSISTED_QUERIES": True,
    "PERSISTED_QUERIES_CACHE_TTL": 86400,

    # Authentication
    "AUTH_REQUIRED": False,
    "AUTH_HEADER_NAME": "Authorization",

    # Logging
    "LOG_QUERIES": False,
    "LOG_MUTATIONS": True,
    "LOG_ERRORS": True,
}
```
