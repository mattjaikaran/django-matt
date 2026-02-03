"""
GraphQL configuration for Django Matt.
"""

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for GraphQL."""
    enabled: bool = True
    queries_per_minute: int = 100
    mutations_per_minute: int = 50
    subscriptions_per_minute: int = 20
    burst_limit: int = 10
    by_ip: bool = True
    by_user: bool = True


@dataclass
class GraphQLConfig:
    """
    GraphQL configuration with sensible defaults.

    Configure in Django settings:
        DJANGO_MATT_GRAPHQL = {
            "ENABLED": True,
            "DEBUG": True,
            "MAX_DEPTH": 10,
            "MAX_COMPLEXITY": 100,
            "PERSISTED_QUERIES": True,
            "SUBSCRIPTIONS_ENABLED": True,
            "AUTH_REQUIRED": False,
            "INTROSPECTION_ENABLED": True,
            "GRAPHIQL_ENABLED": True,
            "RATE_LIMIT": {
                "ENABLED": True,
                "QUERIES_PER_MINUTE": 100,
            },
        }
    """
    enabled: bool = True
    debug: bool = False

    # Query limits
    max_depth: int = 10
    max_complexity: int = 100
    max_aliases: int = 10

    # Persisted queries (APQ)
    persisted_queries_enabled: bool = True
    persisted_queries_cache_ttl: int = 86400  # 24 hours

    # Subscriptions
    subscriptions_enabled: bool = True
    subscription_keepalive: int = 30

    # Authentication
    auth_required: bool = False
    auth_header_name: str = "Authorization"

    # Introspection
    introspection_enabled: bool = True
    introspection_auth_required: bool = False

    # GraphiQL/Playground
    graphiql_enabled: bool = True

    # Rate limiting
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Batching
    batching_enabled: bool = True
    max_batch_size: int = 10

    # Logging
    log_queries: bool = False
    log_mutations: bool = True
    log_errors: bool = True

    @classmethod
    def from_settings(cls) -> "GraphQLConfig":
        """Create config from Django settings."""
        config_dict = getattr(settings, "DJANGO_MATT_GRAPHQL", {})

        # Handle rate limit config separately
        rate_limit_dict = config_dict.pop("RATE_LIMIT", {})
        rate_limit = RateLimitConfig(
            enabled=rate_limit_dict.get("ENABLED", True),
            queries_per_minute=rate_limit_dict.get("QUERIES_PER_MINUTE", 100),
            mutations_per_minute=rate_limit_dict.get("MUTATIONS_PER_MINUTE", 50),
            subscriptions_per_minute=rate_limit_dict.get("SUBSCRIPTIONS_PER_MINUTE", 20),
            burst_limit=rate_limit_dict.get("BURST_LIMIT", 10),
            by_ip=rate_limit_dict.get("BY_IP", True),
            by_user=rate_limit_dict.get("BY_USER", True),
        )

        return cls(
            enabled=config_dict.get("ENABLED", True),
            debug=config_dict.get("DEBUG", settings.DEBUG),
            max_depth=config_dict.get("MAX_DEPTH", 10),
            max_complexity=config_dict.get("MAX_COMPLEXITY", 100),
            max_aliases=config_dict.get("MAX_ALIASES", 10),
            persisted_queries_enabled=config_dict.get("PERSISTED_QUERIES", True),
            persisted_queries_cache_ttl=config_dict.get("PERSISTED_QUERIES_CACHE_TTL", 86400),
            subscriptions_enabled=config_dict.get("SUBSCRIPTIONS_ENABLED", True),
            subscription_keepalive=config_dict.get("SUBSCRIPTION_KEEPALIVE", 30),
            auth_required=config_dict.get("AUTH_REQUIRED", False),
            auth_header_name=config_dict.get("AUTH_HEADER_NAME", "Authorization"),
            introspection_enabled=config_dict.get("INTROSPECTION_ENABLED", True),
            introspection_auth_required=config_dict.get("INTROSPECTION_AUTH_REQUIRED", False),
            graphiql_enabled=config_dict.get("GRAPHIQL_ENABLED", True),
            rate_limit=rate_limit,
            batching_enabled=config_dict.get("BATCHING_ENABLED", True),
            max_batch_size=config_dict.get("MAX_BATCH_SIZE", 10),
            log_queries=config_dict.get("LOG_QUERIES", False),
            log_mutations=config_dict.get("LOG_MUTATIONS", True),
            log_errors=config_dict.get("LOG_ERRORS", True),
        )


# Global config instance (lazy loaded)
_graphql_config: GraphQLConfig | None = None


def get_graphql_config() -> GraphQLConfig:
    """Get the global GraphQL configuration."""
    global _graphql_config
    if _graphql_config is None:
        _graphql_config = GraphQLConfig.from_settings()
    return _graphql_config


def graphql_config() -> GraphQLConfig:
    """Alias for get_graphql_config()."""
    return get_graphql_config()


def reset_config():
    """Reset the configuration (for testing)."""
    global _graphql_config
    _graphql_config = None
