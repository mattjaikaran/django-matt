"""
Utility modules for Django Matt framework.

This package contains utility modules for error handling, hot reloading,
and other framework features.
"""

from django_matt.utils.errors import (
    ErrorHandler,
    ErrorMiddleware,
    ValidationErrorFormatter,
    error_handler,
)
from django_matt.utils.hot_reload import (
    HotReloader,
    HotReloadMiddleware,
    start_hot_reloading,
    stop_hot_reloading,
)
from django_matt.utils.performance import (
    HAS_MSGPACK,
    HAS_ORJSON,
    HAS_UJSON,
    APIBenchmark,
    BenchmarkMiddleware,
    CacheManager,
    DistributedCacheManager,
    FastJSONRenderer,
    FastJsonResponse,
    MessagePackRenderer,
    MessagePackResponse,
    PerformanceSuggester,
    QueryAnalyzer,
    QueryLoggingMiddleware,
    StreamingJsonResponse,
    benchmark,
    cache_manager,
    distributed_cache,
    optimize_queryset,
    performance_suggester,
    query_analyzer,
    stream_json_list,
)
from django_matt.utils.cache_invalidation import (
    CacheInvalidationMixin,
    CacheInvalidator,
    cache_invalidator,
    cached_view,
    invalidate_cache_for_model,
    register_cache_invalidation,
)

__all__ = [
    # Error handling
    "ErrorHandler",
    "ErrorMiddleware",
    "error_handler",
    "ValidationErrorFormatter",
    # Hot reloading
    "HotReloader",
    "HotReloadMiddleware",
    "start_hot_reloading",
    "stop_hot_reloading",
    # Performance - Serialization
    "FastJSONRenderer",
    "FastJsonResponse",
    "MessagePackRenderer",
    "MessagePackResponse",
    "StreamingJsonResponse",
    "stream_json_list",
    # Performance - Benchmarking
    "APIBenchmark",
    "BenchmarkMiddleware",
    "benchmark",
    # Performance - Caching
    "CacheManager",
    "DistributedCacheManager",
    "cache_manager",
    "distributed_cache",
    # Cache Invalidation
    "CacheInvalidator",
    "CacheInvalidationMixin",
    "cache_invalidator",
    "register_cache_invalidation",
    "cached_view",
    "invalidate_cache_for_model",
    # Performance - Query Optimization
    "QueryAnalyzer",
    "QueryLoggingMiddleware",
    "query_analyzer",
    "optimize_queryset",
    # Performance - Suggestions
    "PerformanceSuggester",
    "performance_suggester",
    # Performance - Flags
    "HAS_ORJSON",
    "HAS_UJSON",
    "HAS_MSGPACK",
]
