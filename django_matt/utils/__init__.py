"""
Utility modules for Django Matt framework.

This package contains utility modules for error handling, hot reloading,
and other framework features.
"""

from django_matt.utils.errors import ErrorHandler, ErrorMiddleware, ValidationErrorFormatter, error_handler
from django_matt.utils.hot_reload import HotReloader, HotReloadMiddleware, start_hot_reloading, stop_hot_reloading
from django_matt.utils.performance import (
    HAS_MSGPACK,
    HAS_ORJSON,
    HAS_UJSON,
    APIBenchmark,
    BenchmarkMiddleware,
    CacheManager,
    FastJSONRenderer,
    FastJsonResponse,
    MessagePackRenderer,
    MessagePackResponse,
    StreamingJsonResponse,
    benchmark,
    cache_manager,
    stream_json_list,
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
    # Performance
    "FastJSONRenderer",
    "FastJsonResponse",
    "MessagePackRenderer",
    "MessagePackResponse",
    "StreamingJsonResponse",
    "APIBenchmark",
    "BenchmarkMiddleware",
    "CacheManager",
    "benchmark",
    "cache_manager",
    "stream_json_list",
    "HAS_ORJSON",
    "HAS_UJSON",
    "HAS_MSGPACK",
]
