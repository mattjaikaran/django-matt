# file-length-max: 500
"""
GraphQL middleware for Django Matt.

Provides authentication, rate limiting, complexity analysis, and logging.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache

try:
    import strawberry
    from strawberry.extensions import SchemaExtension
    from strawberry.types import ExecutionContext, Info

    STRAWBERRY_AVAILABLE = True
except ImportError:
    STRAWBERRY_AVAILABLE = False
    SchemaExtension = object
    ExecutionContext = Any
    Info = Any


logger = logging.getLogger("django_matt.graphql")


def _require_strawberry():
    """Raise an error if strawberry is not installed."""
    if not STRAWBERRY_AVAILABLE:
        raise ImportError(
            "strawberry-graphql is required for GraphQL middleware. "
            'Install it with: uv add "strawberry-graphql[django]"'
        )


class AuthMiddleware(SchemaExtension if STRAWBERRY_AVAILABLE else object):
    """
    Authentication middleware for GraphQL.

    Validates JWT tokens and sets the user on the context.

    Usage:
        schema = strawberry.Schema(
            query=Query,
            extensions=[AuthMiddleware],
        )
    """

    def on_request_start(self):
        """Called when a request starts."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        request = self.execution_context.context.get("request")

        if not request:
            return

        # Try to get user from JWT
        try:
            from django_matt.auth.jwt import get_token_from_request, get_user_from_token

            token = get_token_from_request(request)
            if token:
                user = get_user_from_token(token)
                if user:
                    request.user = user
                    self.execution_context.context["user"] = user
        except ImportError:
            pass

        # Check if auth is required
        if config.auth_required:
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                raise PermissionError("Authentication required")

    def on_request_end(self):
        """Called when a request ends."""


class RateLimitMiddleware(SchemaExtension if STRAWBERRY_AVAILABLE else object):
    """
    Rate limiting middleware for GraphQL.

    Limits the number of requests per user/IP.

    Usage:
        schema = strawberry.Schema(
            query=Query,
            extensions=[RateLimitMiddleware],
        )
    """

    def __init__(self, execution_context: ExecutionContext = None):
        if STRAWBERRY_AVAILABLE and execution_context:
            super().__init__(execution_context=execution_context)
        self._request_counts: dict[str, list[float]] = defaultdict(list)

    def _get_rate_limit_key(self, request: Any) -> str:
        """Get the rate limit key for a request."""
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        parts = []

        if config.rate_limit.by_user and hasattr(request, "user") and request.user.is_authenticated:
            parts.append(f"user:{request.user.id}")

        if config.rate_limit.by_ip:
            ip = request.META.get(
                "HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "unknown")
            )
            if "," in ip:
                ip = ip.split(",")[0].strip()
            parts.append(f"ip:{ip}")

        return ":".join(parts) if parts else "anonymous"

    def on_request_start(self):
        """Check rate limits before processing."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        if not config.rate_limit.enabled:
            return

        request = self.execution_context.context.get("request")
        if not request:
            return

        key = self._get_rate_limit_key(request)
        cache_key = f"graphql_rate_limit:{key}"

        # Get current window
        now = time.time()
        window_start = now - 60  # 1 minute window

        # Get and filter old entries
        timestamps = cache.get(cache_key, [])
        timestamps = [t for t in timestamps if t > window_start]

        # Check limit
        if len(timestamps) >= config.rate_limit.queries_per_minute:
            raise Exception(
                f"Rate limit exceeded. Max {config.rate_limit.queries_per_minute} requests per minute."
            )

        # Add new timestamp
        timestamps.append(now)
        cache.set(cache_key, timestamps, 120)  # 2 minute TTL

    def on_request_end(self):
        """Called when request ends."""


@dataclass
class ComplexityInfo:
    """Information about query complexity."""

    total: int
    max_depth: int
    fields: dict[str, int]


class ComplexityMiddleware(SchemaExtension if STRAWBERRY_AVAILABLE else object):
    """
    Query complexity analysis middleware.

    Calculates and limits query complexity to prevent expensive queries.

    Usage:
        schema = strawberry.Schema(
            query=Query,
            extensions=[ComplexityMiddleware],
        )
    """

    def on_request_start(self):
        """Analyze query complexity before execution."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        query = self.execution_context.query

        if not query:
            return

        # Simple complexity calculation
        # Count fields and depth
        complexity = self._calculate_complexity(query)

        if complexity.total > config.max_complexity:
            raise Exception(
                f"Query too complex. Complexity: {complexity.total}, max: {config.max_complexity}"
            )

        if complexity.max_depth > config.max_depth:
            raise Exception(
                f"Query too deep. Depth: {complexity.max_depth}, max: {config.max_depth}"
            )

        # Store complexity info in context
        self.execution_context.context["complexity"] = complexity

    def _calculate_complexity(self, query: str) -> ComplexityInfo:
        """Calculate query complexity (simplified)."""
        # This is a simplified implementation
        # A full implementation would parse the AST

        # Count field occurrences (rough estimate)
        field_count = query.count("{") + query.count("}")

        # Calculate depth by counting nested braces
        max_depth = 0
        current_depth = 0
        for char in query:
            if char == "{":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == "}":
                current_depth -= 1

        # Estimate total complexity
        total = field_count * (max_depth + 1)

        return ComplexityInfo(
            total=total,
            max_depth=max_depth,
            fields={},
        )

    def on_request_end(self):
        """Called when request ends."""


class DepthLimitMiddleware(SchemaExtension if STRAWBERRY_AVAILABLE else object):
    """
    Query depth limiting middleware.

    Prevents deeply nested queries.

    Usage:
        schema = strawberry.Schema(
            query=Query,
            extensions=[DepthLimitMiddleware],
        )
    """

    def on_request_start(self):
        """Check query depth."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        query = self.execution_context.query

        if not query:
            return

        # Calculate depth
        max_depth = 0
        current_depth = 0
        for char in query:
            if char == "{":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == "}":
                current_depth -= 1

        if max_depth > config.max_depth:
            raise Exception(
                f"Query exceeds maximum depth. Depth: {max_depth}, max: {config.max_depth}"
            )

    def on_request_end(self):
        """Called when request ends."""


class PersistedQueryMiddleware(SchemaExtension if STRAWBERRY_AVAILABLE else object):
    """
    Automatic Persisted Queries (APQ) middleware.

    Caches query strings by hash for performance.

    Usage:
        schema = strawberry.Schema(
            query=Query,
            extensions=[PersistedQueryMiddleware],
        )
    """

    CACHE_PREFIX = "graphql_persisted_query:"

    def on_request_start(self):
        """Handle persisted query lookup."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        if not config.persisted_queries_enabled:
            return

        context = self.execution_context.context
        request_data = context.get("request_data", {})

        # Check for persisted query extension
        extensions = request_data.get("extensions", {})
        persisted_query = extensions.get("persistedQuery", {})

        if not persisted_query:
            return

        sha256_hash = persisted_query.get("sha256Hash")
        if not sha256_hash:
            return

        query = self.execution_context.query
        cache_key = f"{self.CACHE_PREFIX}{sha256_hash}"

        if query:
            # Client sent query, cache it
            computed_hash = hashlib.sha256(query.encode()).hexdigest()
            if computed_hash != sha256_hash:
                raise Exception("Provided sha256Hash does not match query")

            cache.set(cache_key, query, config.persisted_queries_cache_ttl)
        else:
            # Client sent only hash, lookup query
            cached_query = cache.get(cache_key)
            if cached_query:
                self.execution_context.query = cached_query
            else:
                raise Exception("PersistedQueryNotFound")

    def on_request_end(self):
        """Called when request ends."""


class LoggingMiddleware(SchemaExtension if STRAWBERRY_AVAILABLE else object):
    """
    Logging middleware for GraphQL operations.

    Logs queries, mutations, and errors.

    Usage:
        schema = strawberry.Schema(
            query=Query,
            extensions=[LoggingMiddleware],
        )
    """

    def __init__(self, execution_context: ExecutionContext = None):
        if STRAWBERRY_AVAILABLE and execution_context:
            super().__init__(execution_context=execution_context)
        self._start_time: float | None = None

    def on_request_start(self):
        """Log request start."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        self._start_time = time.time()

        query = self.execution_context.query
        operation_name = self.execution_context.operation_name

        # Determine operation type
        is_mutation = query and "mutation" in query.lower()

        if is_mutation and config.log_mutations:
            logger.info(
                "GraphQL mutation started",
                extra={
                    "operation_name": operation_name,
                    "query": query[:500] if query else None,  # Truncate for logging
                },
            )
        elif config.log_queries:
            logger.debug(
                "GraphQL query started",
                extra={
                    "operation_name": operation_name,
                    "query": query[:500] if query else None,
                },
            )

    def on_request_end(self):
        """Log request end."""
        _require_strawberry()
        from django_matt.graphql.config import get_graphql_config

        config = get_graphql_config()
        duration = time.time() - self._start_time if self._start_time else 0
        result = self.execution_context.result

        # Check for errors
        if result and result.errors:
            if config.log_errors:
                for error in result.errors:
                    logger.error(
                        "GraphQL error",
                        extra={
                            "error": str(error),
                            "operation_name": self.execution_context.operation_name,
                            "duration": duration,
                        },
                    )
        else:
            query = self.execution_context.query
            is_mutation = query and "mutation" in query.lower()

            if is_mutation and config.log_mutations:
                logger.info(
                    "GraphQL mutation completed",
                    extra={
                        "operation_name": self.execution_context.operation_name,
                        "duration": duration,
                    },
                )
            elif config.log_queries:
                logger.debug(
                    "GraphQL query completed",
                    extra={
                        "operation_name": self.execution_context.operation_name,
                        "duration": duration,
                    },
                )


def get_default_extensions() -> list[type]:
    """
    Get the default list of middleware extensions.

    Returns:
        List of extension classes
    """
    _require_strawberry()
    from django_matt.graphql.config import get_graphql_config

    config = get_graphql_config()
    extensions = []

    # Always add auth middleware
    extensions.append(AuthMiddleware)

    # Add rate limiting if enabled
    if config.rate_limit.enabled:
        extensions.append(RateLimitMiddleware)

    # Add complexity/depth checking
    extensions.append(ComplexityMiddleware)
    extensions.append(DepthLimitMiddleware)

    # Add persisted queries if enabled
    if config.persisted_queries_enabled:
        extensions.append(PersistedQueryMiddleware)

    # Add logging
    extensions.append(LoggingMiddleware)

    return extensions


__all__ = [
    "AuthMiddleware",
    "RateLimitMiddleware",
    "ComplexityMiddleware",
    "DepthLimitMiddleware",
    "PersistedQueryMiddleware",
    "LoggingMiddleware",
    "ComplexityInfo",
    "get_default_extensions",
]
