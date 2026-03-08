"""
Performance utilities for Django Matt framework.

This module provides tools for optimizing performance, including faster JSON
rendering, MessagePack serialization, caching mechanisms, and benchmarking utilities.
"""

import functools
import hashlib
import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.cache import cache as django_cache
from django.http import HttpResponse, StreamingHttpResponse

import orjson

# Try to import MessagePack
try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False


class FastJSONRenderer:
    """
    A faster JSON renderer using orjson.

    This class provides methods to serialize Python objects to JSON using
    orjson for maximum performance.
    """

    def __init__(self):
        """Initialize the renderer."""
        self.library_name = "orjson"

    @staticmethod
    def dumps(obj: Any, **kwargs) -> bytes:
        """
        Serialize obj to JSON formatted bytes.

        Args:
            obj: The Python object to serialize
            **kwargs: Additional keyword arguments to pass to the JSON encoder

        Returns:
            JSON formatted bytes
        """
        orjson_options = kwargs.pop("orjson_options", None)
        if orjson_options is not None:
            return orjson.dumps(obj, option=orjson_options)
        return orjson.dumps(obj)

    @staticmethod
    def loads(s: str | bytes, **kwargs) -> Any:
        """
        Deserialize s (a str or bytes instance containing a JSON document) to a Python object.

        Args:
            s: The JSON string or bytes to deserialize
            **kwargs: Additional keyword arguments to pass to the JSON decoder

        Returns:
            A Python object
        """
        return orjson.loads(s)


class MessagePackRenderer:
    """
    A MessagePack renderer for efficient binary serialization.

    MessagePack is a binary serialization format that is more compact and faster
    than JSON for many use cases.
    """

    @staticmethod
    def dumps(obj: Any, **kwargs) -> bytes:
        """
        Serialize obj to MessagePack formatted bytes.

        Args:
            obj: The Python object to serialize
            **kwargs: Additional keyword arguments to pass to the MessagePack encoder

        Returns:
            MessagePack formatted bytes
        """
        if not HAS_MSGPACK:
            raise ImportError(
                "MessagePack is not installed. Install it with 'uv add msgpack'."
            )

        return msgpack.packb(obj, **kwargs)

    @staticmethod
    def loads(s: bytes, **kwargs) -> Any:
        """
        Deserialize s (a bytes instance containing a MessagePack document) to a Python object.

        Args:
            s: The MessagePack bytes to deserialize
            **kwargs: Additional keyword arguments to pass to the MessagePack decoder

        Returns:
            A Python object
        """
        if not HAS_MSGPACK:
            raise ImportError(
                "MessagePack is not installed. Install it with 'uv add msgpack'."
            )

        return msgpack.unpackb(s, **kwargs)


class FastJsonResponse(HttpResponse):
    """
    A JsonResponse that uses the fastest available JSON library.

    This class extends Django's HttpResponse to use orjson or ujson
    for faster JSON serialization.
    """

    def __init__(self, data, encoder=None, safe=True, json_dumps_params=None, **kwargs):
        """
        Initialize the response with the given data.

        Args:
            data: The data to serialize
            encoder: JSON encoder class (not used with orjson/ujson)
            safe: If False, any object can be passed for serialization
            json_dumps_params: Additional parameters to pass to the JSON encoder
            **kwargs: Additional keyword arguments to pass to the HttpResponse
        """
        if json_dumps_params is None:
            json_dumps_params = {}

        kwargs.setdefault("content_type", "application/json")
        content = FastJSONRenderer.dumps(data, **json_dumps_params)
        super().__init__(content=content, **kwargs)


class MessagePackResponse(HttpResponse):
    """
    An HttpResponse that renders its content as MessagePack.

    This class provides a response that serializes the data to MessagePack format,
    which is more compact and faster than JSON for many use cases.
    """

    def __init__(self, data, **kwargs):
        """
        Initialize the response with the given data.

        Args:
            data: The data to serialize
            **kwargs: Additional keyword arguments to pass to the HttpResponse
        """
        if not HAS_MSGPACK:
            raise ImportError(
                "MessagePack is not installed. Install it with 'uv add msgpack'."
            )

        kwargs.setdefault("content_type", "application/x-msgpack")
        content = MessagePackRenderer.dumps(data)
        super().__init__(content=content, **kwargs)


class CacheManager:
    """
    A utility for managing caching of API responses and other data.

    This class provides methods to cache data with various strategies,
    including time-based expiration, query-based invalidation, and more.
    """

    def __init__(self, cache=None):
        """
        Initialize the cache manager.

        Args:
            cache: The cache backend to use (defaults to Django's default cache)
        """
        self.cache = cache or django_cache
        self.enabled = getattr(settings, "DJANGO_MATT_CACHE_ENABLED", True)
        self.default_timeout = getattr(settings, "DJANGO_MATT_CACHE_TIMEOUT", 300)  # 5 minutes

    def _get_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a cache key from the prefix and arguments.

        Args:
            prefix: The prefix for the cache key
            *args: Positional arguments to include in the key
            **kwargs: Keyword arguments to include in the key

        Returns:
            A cache key string
        """
        # Create a string representation of the arguments
        args_str = str(args) if args else ""
        kwargs_str = str(sorted(kwargs.items())) if kwargs else ""

        # Create a hash of the arguments
        key_data = f"{prefix}:{args_str}:{kwargs_str}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()

        return f"django_matt:{prefix}:{key_hash}"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache.

        Args:
            key: The cache key
            default: Default value if key not found

        Returns:
            The cached value or default
        """
        if not self.enabled:
            return default
        return self.cache.get(key, default)

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        """
        Set a value in cache.

        Args:
            key: The cache key
            value: The value to cache
            timeout: Cache timeout in seconds (defaults to DJANGO_MATT_CACHE_TIMEOUT)
        """
        if not self.enabled:
            return
        cache_timeout = timeout or self.default_timeout
        self.cache.set(key, value, cache_timeout)

    def delete(self, key: str) -> None:
        """
        Delete a value from cache.

        Args:
            key: The cache key to delete
        """
        self.cache.delete(key)

    def cache_response(self, timeout: int | None = None, key_prefix: str | None = None):
        """
        Decorator to cache the response of a view function.

        Args:
            timeout: The cache timeout in seconds (defaults to DJANGO_MATT_CACHE_TIMEOUT)
            key_prefix: The prefix for the cache key (defaults to the function name)

        Returns:
            The decorated function
        """

        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(request, *args, **kwargs):
                if not self.enabled:
                    return await func(request, *args, **kwargs)

                # Generate a cache key
                prefix = key_prefix or func.__name__
                cache_key = self._get_cache_key(prefix, *args, **kwargs)

                # Try to get the response from the cache
                cached_response = self.cache.get(cache_key)
                if cached_response is not None:
                    return cached_response

                # Call the view function
                response = await func(request, *args, **kwargs)

                # Cache the response
                cache_timeout = timeout or self.default_timeout
                self.cache.set(cache_key, response, cache_timeout)

                return response

            @functools.wraps(func)
            def sync_wrapper(request, *args, **kwargs):
                if not self.enabled:
                    return func(request, *args, **kwargs)

                # Generate a cache key
                prefix = key_prefix or func.__name__
                cache_key = self._get_cache_key(prefix, *args, **kwargs)

                # Try to get the response from the cache
                cached_response = self.cache.get(cache_key)
                if cached_response is not None:
                    return cached_response

                # Call the view function
                response = func(request, *args, **kwargs)

                # Cache the response
                cache_timeout = timeout or self.default_timeout
                self.cache.set(cache_key, response, cache_timeout)

                return response

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def cache_result(self, timeout: int | None = None, key_prefix: str | None = None):
        """
        Decorator to cache the result of a function.

        Args:
            timeout: The cache timeout in seconds (defaults to DJANGO_MATT_CACHE_TIMEOUT)
            key_prefix: The prefix for the cache key (defaults to the function name)

        Returns:
            The decorated function
        """

        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)

                # Generate a cache key
                prefix = key_prefix or func.__name__
                cache_key = self._get_cache_key(prefix, *args, **kwargs)

                # Try to get the result from the cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Call the function
                result = await func(*args, **kwargs)

                # Cache the result
                cache_timeout = timeout or self.default_timeout
                self.cache.set(cache_key, result, cache_timeout)

                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                # Generate a cache key
                prefix = key_prefix or func.__name__
                cache_key = self._get_cache_key(prefix, *args, **kwargs)

                # Try to get the result from the cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Call the function
                result = func(*args, **kwargs)

                # Cache the result
                cache_timeout = timeout or self.default_timeout
                self.cache.set(cache_key, result, cache_timeout)

                return result

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def invalidate(self, key_prefix: str, *args, **kwargs):
        """
        Invalidate a cached item.

        Args:
            key_prefix: The prefix for the cache key
            *args: Positional arguments used to generate the key
            **kwargs: Keyword arguments used to generate the key
        """
        cache_key = self._get_cache_key(key_prefix, *args, **kwargs)
        self.cache.delete(cache_key)

    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all cached items matching a pattern.

        Args:
            pattern: The pattern to match against cache keys
        """
        # This is a simplified implementation that works with Django's cache
        # For more advanced pattern matching, a cache backend that supports it
        # (like Redis) would be needed
        if hasattr(self.cache, "delete_pattern"):
            self.cache.delete_pattern(f"django_matt:{pattern}:*")
        else:
            # Log a warning that pattern invalidation is not supported
            import logging

            logger = logging.getLogger("django_matt.cache")
            logger.warning(
                "Cache pattern invalidation is not supported by the current cache backend. "
                "Use Redis or another backend that supports pattern matching."
            )


def cache_response(timeout: int = 300, key_prefix: str = "matt_cache"):
    """Standalone decorator to cache a view or controller method response.

    Uses Django's default cache backend. The cache key is derived from the
    request path and query string, so different URLs produce different keys.

    Supports both sync and async view functions/methods.

    Usage:
        class MyController(APIController):
            @api.get("/items")
            @cache_response(timeout=300)
            async def list_items(self, request):
                return await self.get_queryset()

        # Or on a plain view function:
        @cache_response(timeout=60)
        def my_view(request):
            return HttpResponse("hello")

    Args:
        timeout: Cache lifetime in seconds (default: 300).
        key_prefix: Prefix for the cache key (default: "matt_cache").
    """

    def decorator(func):
        import asyncio as _asyncio

        @functools.wraps(func)
        async def async_wrapper(self_or_request, *args, **kwargs):
            # Resolve the request object: handle both plain-function and method calls.
            request = None
            if hasattr(self_or_request, "method"):
                # self_or_request IS the request (plain function)
                request = self_or_request
            elif args and hasattr(args[0], "method"):
                # self_or_request is `self`, first positional arg is the request
                request = args[0]

            if request is not None:
                raw_key = f"{key_prefix}:{request.path}:{request.GET.urlencode()}"
                cache_key = hashlib.md5(raw_key.encode()).hexdigest()
                cached = django_cache.get(cache_key)
                if cached is not None:
                    return cached

            result = await func(self_or_request, *args, **kwargs)

            if request is not None:
                django_cache.set(cache_key, result, timeout)
            return result

        @functools.wraps(func)
        def sync_wrapper(self_or_request, *args, **kwargs):
            request = None
            if hasattr(self_or_request, "method"):
                request = self_or_request
            elif args and hasattr(args[0], "method"):
                request = args[0]

            if request is not None:
                raw_key = f"{key_prefix}:{request.path}:{request.GET.urlencode()}"
                cache_key = hashlib.md5(raw_key.encode()).hexdigest()
                cached = django_cache.get(cache_key)
                if cached is not None:
                    return cached

            result = func(self_or_request, *args, **kwargs)

            if request is not None:
                django_cache.set(cache_key, result, timeout)
            return result

        if _asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class APIBenchmark:
    """
    A utility for benchmarking API endpoints.

    This class provides methods to measure the performance of API endpoints
    and generate reports.
    """

    def __init__(self):
        self.measurements = {}
        self.enabled = getattr(settings, "DJANGO_MATT_BENCHMARK_ENABLED", False)

    def measure(self, name: str | None = None):
        """
        Decorator or context manager to measure execution time.

        Can be used as a decorator:
            @benchmark.measure("my_operation")
            def my_function():
                pass

        Or as a context manager:
            with benchmark.measure("my_operation"):
                do_something()

        Args:
            name: The name of the measurement

        Returns:
            A MeasureContext that works as both decorator and context manager
        """
        return _MeasureContext(self, name)

    def _record_measurement(self, name: str, duration: float):
        """
        Record a measurement.

        Args:
            name: The name of the measurement
            duration: The duration of the measurement in milliseconds
        """
        if name not in self.measurements:
            self.measurements[name] = {
                "count": 0,
                "total_time": 0,
                "min_time": float("inf"),
                "max_time": 0,
                "avg_time": 0,
            }

        self.measurements[name]["count"] += 1
        self.measurements[name]["total_time"] += duration
        self.measurements[name]["min_time"] = min(self.measurements[name]["min_time"], duration)
        self.measurements[name]["max_time"] = max(self.measurements[name]["max_time"], duration)
        self.measurements[name]["avg_time"] = (
            self.measurements[name]["total_time"] / self.measurements[name]["count"]
        )

    def get_report(self) -> dict[str, Any]:
        """
        Get a report of all measurements.

        Returns:
            A dictionary containing the measurement reports
        """
        return self.measurements

    def reset(self):
        """Reset all measurements."""
        self.measurements = {}


class _MeasureContext:
    """Helper class that works as both a decorator and context manager."""

    def __init__(self, benchmark: "APIBenchmark", name: str | None = None):
        self.benchmark = benchmark
        self.name = name
        self.start_time: float | None = None

    def __call__(self, func):
        """Use as a decorator."""

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not self.benchmark.enabled:
                return await func(*args, **kwargs)

            measurement_name = self.name or func.__name__
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()

            duration = (end_time - start_time) * 1000
            self.benchmark._record_measurement(measurement_name, duration)

            if isinstance(result, HttpResponse):
                result["X-Django-Matt-Timing"] = f"{duration:.2f}ms"

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not self.benchmark.enabled:
                return func(*args, **kwargs)

            measurement_name = self.name or func.__name__
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()

            duration = (end_time - start_time) * 1000
            self.benchmark._record_measurement(measurement_name, duration)

            if isinstance(result, HttpResponse):
                result["X-Django-Matt-Timing"] = f"{duration:.2f}ms"

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    def __enter__(self):
        """Enter context manager."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and record measurement."""
        if self.start_time is not None and self.benchmark.enabled:
            end_time = time.time()
            duration = (end_time - self.start_time) * 1000
            measurement_name = self.name or "unnamed"
            self.benchmark._record_measurement(measurement_name, duration)
        return False


class StreamingJsonResponse(StreamingHttpResponse):
    """
    A streaming HTTP response that renders its content as JSON.

    This class is useful for large datasets that should be streamed to the client
    rather than loaded entirely into memory.
    """

    def __init__(self, streaming_content, **kwargs):
        """
        Initialize the response with the given streaming content.

        Args:
            streaming_content: An iterator that yields chunks of data
            **kwargs: Additional keyword arguments to pass to the StreamingHttpResponse
        """
        kwargs.setdefault("content_type", "application/json")
        super().__init__(streaming_content=streaming_content, **kwargs)


def stream_json_list(items_iterator, chunk_size=100):
    """
    Stream a list of items as JSON.

    Args:
        items_iterator: An iterator that yields items to be serialized
        chunk_size: The number of items to include in each chunk

    Yields:
        JSON chunks
    """
    # Start the JSON array
    yield "["

    # Keep track of whether we've yielded any items
    first_item = True

    # Buffer for collecting items
    buffer = []

    # Process items in chunks
    for item in items_iterator:
        if first_item:
            first_item = False
        else:
            buffer.append(",")

        # Add the serialized item to the buffer
        buffer.append(orjson.dumps(item).decode("utf-8"))

        # If the buffer is full, yield it
        if len(buffer) >= chunk_size:
            yield "".join(buffer)
            buffer = []

    # Yield any remaining items
    if buffer:
        yield "".join(buffer)

    # End the JSON array
    yield "]"


# Create singleton instances
benchmark = APIBenchmark()
cache_manager = CacheManager()


class BenchmarkMiddleware:
    """
    Middleware to benchmark request/response cycle.

    This middleware measures the time taken to process each request
    and adds timing information to the response headers.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "DJANGO_MATT_BENCHMARK_ENABLED", False)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        # Measure request processing time
        start_time = time.time()
        response = self.get_response(request)
        end_time = time.time()

        # Calculate duration in milliseconds
        duration = (end_time - start_time) * 1000

        # Add timing information to the response headers
        response["X-Django-Matt-Timing"] = f"{duration:.2f}ms"

        return response


# Import asyncio at the end to avoid circular imports
import asyncio

# =============================================================================
# Distributed Caching Support
# =============================================================================


class DistributedCacheManager(CacheManager):
    """
    A cache manager that supports distributed caching with Redis cluster.

    This class extends CacheManager to provide additional features for
    distributed caching scenarios, including key namespacing, cache stampede
    prevention, and cluster-aware operations.
    """

    def __init__(self, cache=None, namespace: str = "default"):
        """
        Initialize the distributed cache manager.

        Args:
            cache: The cache backend to use (defaults to Django's default cache)
            namespace: A namespace prefix for all cache keys (useful for multi-tenant)
        """
        super().__init__(cache)
        self.namespace = namespace
        self.lock_timeout = getattr(settings, "DJANGO_MATT_CACHE_LOCK_TIMEOUT", 10)

    def _get_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a namespaced cache key."""
        base_key = super()._get_cache_key(prefix, *args, **kwargs)
        return f"{self.namespace}:{base_key}"

    def get_or_set(
        self,
        key: str,
        default_func: Callable[[], Any],
        timeout: int | None = None,
        version: int | None = None,
    ) -> Any:
        """
        Get a value from cache, or set it if not present.

        This method provides cache stampede prevention by using a lock
        to ensure only one process computes the value.

        Args:
            key: The cache key
            default_func: A callable that returns the default value
            timeout: Cache timeout in seconds
            version: Optional cache version

        Returns:
            The cached or computed value
        """
        cache_key = f"{self.namespace}:{key}"
        lock_key = f"{cache_key}:lock"

        # Try to get from cache first
        value = self.cache.get(cache_key, version=version)
        if value is not None:
            return value

        # Try to acquire lock for computing value (stampede prevention)
        lock_acquired = self.cache.add(lock_key, "1", self.lock_timeout)

        if lock_acquired:
            try:
                # Double-check cache after acquiring lock
                value = self.cache.get(cache_key, version=version)
                if value is not None:
                    return value

                # Compute the value
                value = default_func()
                cache_timeout = timeout or self.default_timeout
                self.cache.set(cache_key, value, cache_timeout, version=version)
                return value
            finally:
                self.cache.delete(lock_key)
        else:
            # Another process is computing the value, wait and retry
            import time

            for _ in range(10):  # Max 10 retries
                time.sleep(0.1)
                value = self.cache.get(cache_key, version=version)
                if value is not None:
                    return value

            # Fallback: compute anyway if still not available
            return default_func()

    async def aget_or_set(
        self,
        key: str,
        default_func: Callable[[], Any],
        timeout: int | None = None,
        version: int | None = None,
    ) -> Any:
        """
        Async version of get_or_set.

        Args:
            key: The cache key
            default_func: An async callable that returns the default value
            timeout: Cache timeout in seconds
            version: Optional cache version

        Returns:
            The cached or computed value
        """
        cache_key = f"{self.namespace}:{key}"
        lock_key = f"{cache_key}:lock"

        # Try to get from cache first
        value = self.cache.get(cache_key, version=version)
        if value is not None:
            return value

        # Try to acquire lock
        lock_acquired = self.cache.add(lock_key, "1", self.lock_timeout)

        if lock_acquired:
            try:
                value = self.cache.get(cache_key, version=version)
                if value is not None:
                    return value

                # Compute the value (support both sync and async)
                if asyncio.iscoroutinefunction(default_func):
                    value = await default_func()
                else:
                    value = default_func()

                cache_timeout = timeout or self.default_timeout
                self.cache.set(cache_key, value, cache_timeout, version=version)
                return value
            finally:
                self.cache.delete(lock_key)
        else:
            for _ in range(10):
                await asyncio.sleep(0.1)
                value = self.cache.get(cache_key, version=version)
                if value is not None:
                    return value

            if asyncio.iscoroutinefunction(default_func):
                return await default_func()
            return default_func()

    def get_many(self, keys: list[str], version: int | None = None) -> dict[str, Any]:
        """
        Get multiple values from cache at once.

        Args:
            keys: List of cache keys
            version: Optional cache version

        Returns:
            Dictionary of key-value pairs
        """
        namespaced_keys = [f"{self.namespace}:{k}" for k in keys]
        result = self.cache.get_many(namespaced_keys, version=version)
        # Remove namespace from keys in result
        return {k.replace(f"{self.namespace}:", ""): v for k, v in result.items()}

    def set_many(
        self, mapping: dict[str, Any], timeout: int | None = None, version: int | None = None
    ):
        """
        Set multiple values in cache at once.

        Args:
            mapping: Dictionary of key-value pairs
            timeout: Cache timeout in seconds
            version: Optional cache version
        """
        namespaced_mapping = {f"{self.namespace}:{k}": v for k, v in mapping.items()}
        cache_timeout = timeout or self.default_timeout
        self.cache.set_many(namespaced_mapping, cache_timeout, version=version)

    def delete_many(self, keys: list[str], version: int | None = None):
        """
        Delete multiple values from cache at once.

        Args:
            keys: List of cache keys
            version: Optional cache version
        """
        namespaced_keys = [f"{self.namespace}:{k}" for k in keys]
        self.cache.delete_many(namespaced_keys, version=version)

    def incr(self, key: str, delta: int = 1, version: int | None = None) -> int:
        """
        Increment a value in cache.

        Args:
            key: The cache key
            delta: Amount to increment by
            version: Optional cache version

        Returns:
            The new value
        """
        cache_key = f"{self.namespace}:{key}"
        try:
            return self.cache.incr(cache_key, delta, version=version)
        except ValueError:
            # Key doesn't exist, initialize it
            self.cache.set(cache_key, delta, self.default_timeout, version=version)
            return delta

    def decr(self, key: str, delta: int = 1, version: int | None = None) -> int:
        """
        Decrement a value in cache.

        Args:
            key: The cache key
            delta: Amount to decrement by
            version: Optional cache version

        Returns:
            The new value
        """
        cache_key = f"{self.namespace}:{key}"
        try:
            return self.cache.decr(cache_key, delta, version=version)
        except ValueError:
            self.cache.set(cache_key, -delta, self.default_timeout, version=version)
            return -delta

    def touch(self, key: str, timeout: int | None = None, version: int | None = None) -> bool:
        """
        Update the timeout of a cached value without changing it.

        Args:
            key: The cache key
            timeout: New timeout in seconds
            version: Optional cache version

        Returns:
            True if successful, False otherwise
        """
        cache_key = f"{self.namespace}:{key}"
        cache_timeout = timeout or self.default_timeout
        return self.cache.touch(cache_key, cache_timeout, version=version)

    def clear_namespace(self):
        """
        Clear all cached items in this namespace.

        Note: This only works with cache backends that support pattern deletion.
        """
        self.invalidate_pattern(f"{self.namespace}:*")


# =============================================================================
# Query Optimization Utilities
# =============================================================================


class QueryAnalyzer:
    """
    Utilities for analyzing and optimizing Django ORM queries.

    This class provides tools to detect N+1 queries, suggest prefetch_related
    and select_related optimizations, and analyze query performance.
    """

    def __init__(self):
        self.query_log: list[dict[str, Any]] = []
        self.enabled = getattr(settings, "DJANGO_MATT_QUERY_ANALYSIS_ENABLED", False)

    def analyze_queryset(self, queryset) -> dict[str, Any]:
        """
        Analyze a queryset and provide optimization suggestions.

        Args:
            queryset: A Django QuerySet to analyze

        Returns:
            Dictionary containing analysis results and suggestions
        """
        from django.db.models import ForeignKey, ManyToManyField, ManyToOneRel

        model = queryset.model
        meta = model._meta

        # Get current optimizations
        current_select_related = (
            list(queryset.query.select_related.keys()) if queryset.query.select_related else []
        )
        current_prefetch_related = [
            p.prefetch_through if hasattr(p, "prefetch_through") else str(p)
            for p in queryset._prefetch_related_lookups
        ]

        # Find all relations
        foreign_keys = []
        many_to_many = []
        reverse_relations = []

        for field in meta.get_fields():
            if isinstance(field, ForeignKey):
                foreign_keys.append(field.name)
            elif isinstance(field, ManyToManyField):
                many_to_many.append(field.name)
            elif isinstance(field, ManyToOneRel):
                reverse_relations.append(field.get_accessor_name())

        # Generate suggestions
        suggestions = []

        # Suggest select_related for unoptimized foreign keys
        missing_select = [fk for fk in foreign_keys if fk not in current_select_related]
        if missing_select:
            suggestions.append(
                {
                    "type": "select_related",
                    "fields": missing_select,
                    "reason": "Foreign key fields not using select_related may cause N+1 queries",
                    "fix": f".select_related({', '.join(repr(f) for f in missing_select)})",
                }
            )

        # Suggest prefetch_related for many-to-many
        missing_prefetch_m2m = [m2m for m2m in many_to_many if m2m not in current_prefetch_related]
        if missing_prefetch_m2m:
            suggestions.append(
                {
                    "type": "prefetch_related",
                    "fields": missing_prefetch_m2m,
                    "reason": "Many-to-many fields should use prefetch_related",
                    "fix": f".prefetch_related({', '.join(repr(f) for f in missing_prefetch_m2m)})",
                }
            )

        # Suggest prefetch_related for reverse relations if commonly accessed
        if reverse_relations:
            suggestions.append(
                {
                    "type": "prefetch_related",
                    "fields": reverse_relations,
                    "reason": "Reverse relations may benefit from prefetch_related if accessed",
                    "fix": f".prefetch_related({', '.join(repr(f) for f in reverse_relations)})",
                    "conditional": True,
                }
            )

        return {
            "model": model.__name__,
            "current_optimizations": {
                "select_related": current_select_related,
                "prefetch_related": current_prefetch_related,
            },
            "relations": {
                "foreign_keys": foreign_keys,
                "many_to_many": many_to_many,
                "reverse_relations": reverse_relations,
            },
            "suggestions": suggestions,
            "query_count_estimate": self._estimate_query_count(
                queryset, missing_select, missing_prefetch_m2m
            ),
        }

    def _estimate_query_count(
        self, queryset, missing_select: list, missing_prefetch: list
    ) -> dict[str, int]:
        """Estimate query counts with and without optimization."""
        try:
            count = queryset.count()
        except Exception:
            count = 100  # Default estimate

        # Base query
        queries_without_opt = 1

        # Each missing select_related adds N queries (one per object)
        if missing_select:
            queries_without_opt += count * len(missing_select)

        # Each missing prefetch_related adds N queries
        if missing_prefetch:
            queries_without_opt += count * len(missing_prefetch)

        # With optimization: 1 base + 1 per prefetch
        queries_with_opt = 1 + len(missing_prefetch)

        return {
            "without_optimization": queries_without_opt,
            "with_optimization": queries_with_opt,
            "potential_savings": queries_without_opt - queries_with_opt,
        }

    def log_query(self, sql: str, duration: float, params: tuple | None = None):
        """
        Log a query for analysis.

        Args:
            sql: The SQL query string
            duration: Query execution time in seconds
            params: Query parameters
        """
        if not self.enabled:
            return

        self.query_log.append(
            {
                "sql": sql,
                "duration_ms": duration * 1000,
                "params": params,
                "timestamp": time.time(),
            }
        )

    def get_slow_queries(self, threshold_ms: float = 100) -> list[dict[str, Any]]:
        """
        Get queries that exceeded the threshold.

        Args:
            threshold_ms: Threshold in milliseconds

        Returns:
            List of slow queries
        """
        return [q for q in self.query_log if q["duration_ms"] > threshold_ms]

    def get_duplicate_queries(self) -> dict[str, int]:
        """
        Find duplicate queries (potential N+1 issues).

        Returns:
            Dictionary of query patterns and their counts
        """
        from collections import Counter

        # Normalize queries by removing specific values
        normalized = []
        for q in self.query_log:
            # Simple normalization - remove numbers and quoted strings
            import re

            sql = re.sub(r"\d+", "?", q["sql"])
            sql = re.sub(r"'[^']*'", "'?'", sql)
            normalized.append(sql)

        counts = Counter(normalized)
        return {sql: count for sql, count in counts.items() if count > 1}

    def clear_log(self):
        """Clear the query log."""
        self.query_log = []

    def get_report(self) -> dict[str, Any]:
        """
        Get a comprehensive query analysis report.

        Returns:
            Dictionary containing query analysis
        """
        if not self.query_log:
            return {"total_queries": 0, "message": "No queries logged"}

        durations = [q["duration_ms"] for q in self.query_log]
        duplicates = self.get_duplicate_queries()

        return {
            "total_queries": len(self.query_log),
            "total_time_ms": sum(durations),
            "avg_time_ms": sum(durations) / len(durations),
            "min_time_ms": min(durations),
            "max_time_ms": max(durations),
            "slow_queries": len(self.get_slow_queries()),
            "duplicate_patterns": len(duplicates),
            "potential_n_plus_1": sum(1 for count in duplicates.values() if count > 5),
            "duplicates": duplicates,
        }


def optimize_queryset(queryset, include_reverse: bool = False):
    """
    Automatically optimize a queryset with select_related and prefetch_related.

    Args:
        queryset: A Django QuerySet to optimize
        include_reverse: Whether to include reverse relations in prefetch

    Returns:
        The optimized queryset
    """
    from django.db.models import ForeignKey, ManyToManyField, ManyToOneRel

    model = queryset.model
    meta = model._meta

    select_fields = []
    prefetch_fields = []

    for field in meta.get_fields():
        if isinstance(field, ForeignKey):
            select_fields.append(field.name)
        elif isinstance(field, ManyToManyField):
            prefetch_fields.append(field.name)
        elif isinstance(field, ManyToOneRel) and include_reverse:
            prefetch_fields.append(field.get_accessor_name())

    if select_fields:
        queryset = queryset.select_related(*select_fields)
    if prefetch_fields:
        queryset = queryset.prefetch_related(*prefetch_fields)

    return queryset


# =============================================================================
# Performance Suggestions
# =============================================================================


class PerformanceSuggester:
    """
    Provides actionable performance suggestions based on runtime analysis.

    This class monitors application behavior and provides specific
    recommendations for improving performance.
    """

    def __init__(self):
        self.observations: list[dict[str, Any]] = []
        self.enabled = getattr(settings, "DJANGO_MATT_SUGGESTIONS_ENABLED", False)

    def observe(self, category: str, data: dict[str, Any]):
        """
        Record an observation for analysis.

        Args:
            category: The category of observation (e.g., 'serialization', 'query', 'cache')
            data: The observation data
        """
        if not self.enabled:
            return

        self.observations.append(
            {
                "category": category,
                "data": data,
                "timestamp": time.time(),
            }
        )

    def get_suggestions(self) -> list[dict[str, Any]]:
        """
        Analyze observations and generate suggestions.

        Returns:
            List of actionable suggestions
        """
        suggestions = []

        # Analyze serialization performance
        serialization_obs = [o for o in self.observations if o["category"] == "serialization"]
        if serialization_obs:
            avg_size = sum(o["data"].get("size", 0) for o in serialization_obs) / len(
                serialization_obs
            )
            avg_time = sum(o["data"].get("time_ms", 0) for o in serialization_obs) / len(
                serialization_obs
            )

            if avg_size > 100000:  # > 100KB average
                suggestions.append(
                    {
                        "category": "serialization",
                        "priority": "high",
                        "title": "Large response payloads detected",
                        "description": f"Average response size is {avg_size / 1000:.1f}KB",
                        "recommendations": [
                            "Use pagination to limit response size",
                            "Consider using StreamingJsonResponse for large datasets",
                            "Implement field selection to return only needed fields",
                            "Use MessagePack for binary data transfer",
                        ],
                    }
                )

            if avg_time > 50:  # > 50ms average
                suggestions.append(
                    {
                        "category": "serialization",
                        "priority": "high",
                        "title": "Slow JSON serialization",
                        "description": f"Average serialization time is {avg_time:.1f}ms",
                        "recommendations": [
                            "Check for complex nested objects slowing serialization",
                            "Consider using StreamingJsonResponse for large datasets",
                            "Profile serialization with APIBenchmark.measure()",
                        ],
                    }
                )

        # Analyze query performance
        query_obs = [o for o in self.observations if o["category"] == "query"]
        if query_obs:
            total_queries = sum(o["data"].get("count", 0) for o in query_obs)
            avg_queries_per_request = total_queries / len(query_obs) if query_obs else 0

            if avg_queries_per_request > 10:
                suggestions.append(
                    {
                        "category": "database",
                        "priority": "high",
                        "title": "High query count per request",
                        "description": f"Average of {avg_queries_per_request:.1f} queries per request",
                        "recommendations": [
                            "Use select_related() for foreign key relationships",
                            "Use prefetch_related() for many-to-many relationships",
                            "Consider using optimize_queryset() helper",
                            "Review for N+1 query patterns",
                        ],
                    }
                )

        # Analyze cache usage
        cache_obs = [o for o in self.observations if o["category"] == "cache"]
        if cache_obs:
            hits = sum(1 for o in cache_obs if o["data"].get("hit", False))
            hit_rate = hits / len(cache_obs) if cache_obs else 0

            if hit_rate < 0.5 and len(cache_obs) > 10:
                suggestions.append(
                    {
                        "category": "cache",
                        "priority": "medium",
                        "title": "Low cache hit rate",
                        "description": f"Cache hit rate is {hit_rate * 100:.1f}%",
                        "recommendations": [
                            "Review cache key generation for consistency",
                            "Consider increasing cache timeout",
                            "Implement cache warming for frequently accessed data",
                            "Use get_or_set() to prevent cache stampedes",
                        ],
                    }
                )

        if not HAS_MSGPACK:
            suggestions.append(
                {
                    "category": "dependencies",
                    "priority": "low",
                    "title": "MessagePack not available",
                    "description": "Binary serialization not available",
                    "recommendations": [
                        "Install msgpack for binary serialization: uv add msgpack",
                        "Useful for internal service communication",
                    ],
                }
            )

        return suggestions

    def clear(self):
        """Clear all observations."""
        self.observations = []

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of all observations and suggestions.

        Returns:
            Dictionary containing summary and suggestions
        """
        categories = {}
        for obs in self.observations:
            cat = obs["category"]
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        return {
            "total_observations": len(self.observations),
            "categories": categories,
            "suggestions": self.get_suggestions(),
            "libraries": {
                "orjson": True,
                "msgpack": HAS_MSGPACK,
            },
        }


# Create singleton instances
distributed_cache = DistributedCacheManager()
query_analyzer = QueryAnalyzer()
performance_suggester = PerformanceSuggester()


class QueryLoggingMiddleware:
    """
    Middleware to log database queries for analysis.

    This middleware captures all database queries made during a request
    and logs them for performance analysis.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "DJANGO_MATT_QUERY_ANALYSIS_ENABLED", False)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        from django.db import connection

        # Clear query log
        query_analyzer.clear_log()

        # Enable query logging
        initial_queries = len(connection.queries)

        response = self.get_response(request)

        # Log queries
        for query in connection.queries[initial_queries:]:
            query_analyzer.log_query(
                sql=query["sql"],
                duration=float(query["time"]),
            )

        # Add query count to response headers
        query_count = len(connection.queries) - initial_queries
        response["X-Django-Matt-Query-Count"] = str(query_count)

        # Log observation for suggestions
        performance_suggester.observe("query", {"count": query_count})

        return response
