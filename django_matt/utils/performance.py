"""
Performance utilities for Django Matt framework.

This module provides tools for optimizing performance, including faster JSON
rendering, MessagePack serialization, caching mechanisms, and benchmarking utilities.
"""

import functools
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.cache import cache as django_cache
from django.http import HttpResponse, JsonResponse

# Try to import faster JSON libraries
try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

try:
    import ujson

    HAS_UJSON = True
except ImportError:
    HAS_UJSON = False

# Try to import MessagePack
try:
    import msgpack

    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False


class FastJSONRenderer:
    """
    A faster JSON renderer that uses orjson or ujson if available.

    This class provides methods to serialize Python objects to JSON using
    the fastest available JSON library.
    """

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
        if HAS_ORJSON:
            # orjson is the fastest JSON library
            orjson_options = kwargs.pop("orjson_options", None)
            if orjson_options is not None:
                return orjson.dumps(obj, option=orjson_options)
            return orjson.dumps(obj)
        elif HAS_UJSON:
            # ujson is faster than the standard json library
            return ujson.dumps(obj, **kwargs).encode("utf-8")
        else:
            # Fall back to the standard json library
            return json.dumps(obj, **kwargs).encode("utf-8")

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
        if HAS_ORJSON:
            return orjson.loads(s)
        elif HAS_UJSON:
            if isinstance(s, bytes):
                s = s.decode("utf-8")
            return ujson.loads(s, **kwargs)
        else:
            if isinstance(s, bytes):
                s = s.decode("utf-8")
            return json.loads(s, **kwargs)


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
                "MessagePack is not installed. Install it with 'pip install msgpack'."
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
                "MessagePack is not installed. Install it with 'pip install msgpack'."
            )

        return msgpack.unpackb(s, **kwargs)


class FastJsonResponse(JsonResponse):
    """
    A JsonResponse that uses the fastest available JSON library.

    This class extends Django's JsonResponse to use orjson or ujson
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

        # Use the fastest available JSON library
        if not safe and encoder:
            # If not safe and a custom encoder is provided, fall back to Django's JsonResponse
            super().__init__(data, encoder, safe, json_dumps_params, **kwargs)
            return

        kwargs.setdefault("content_type", "application/json")
        data = FastJSONRenderer.dumps(data, **json_dumps_params)
        super(HttpResponse, self).__init__(content=data, **kwargs)


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
                "MessagePack is not installed. Install it with 'pip install msgpack'."
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
        self.default_timeout = getattr(
            settings, "DJANGO_MATT_CACHE_TIMEOUT", 300
        )  # 5 minutes

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
            else:
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
            else:
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


class APIBenchmark:
    """
    A utility for benchmarking API endpoints.

    This class provides methods to measure the performance of API endpoints
    and generate reports.
    """

    def __init__(self):
        self.measurements = {}
        self.enabled = getattr(settings, "DJANGO_MATT_BENCHMARK_ENABLED", False)

    def measure(self, name: str | None = None) -> Callable:
        """
        Decorator to measure the execution time of a function.

        Args:
            name: The name of the measurement (defaults to the function name)

        Returns:
            The decorated function
        """

        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)

                measurement_name = name or func.__name__
                start_time = time.time()
                result = await func(*args, **kwargs)
                end_time = time.time()

                # Record the measurement
                duration = (end_time - start_time) * 1000  # Convert to milliseconds
                self._record_measurement(measurement_name, duration)

                # Add timing information to the response headers if it's an HTTP response
                if isinstance(result, HttpResponse):
                    result["X-Django-Matt-Timing"] = f"{duration:.2f}ms"

                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                measurement_name = name or func.__name__
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()

                # Record the measurement
                duration = (end_time - start_time) * 1000  # Convert to milliseconds
                self._record_measurement(measurement_name, duration)

                # Add timing information to the response headers if it's an HTTP response
                if isinstance(result, HttpResponse):
                    result["X-Django-Matt-Timing"] = f"{duration:.2f}ms"

                return result

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

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
        self.measurements[name]["min_time"] = min(
            self.measurements[name]["min_time"], duration
        )
        self.measurements[name]["max_time"] = max(
            self.measurements[name]["max_time"], duration
        )
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


class StreamingJsonResponse(HttpResponse):
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
            **kwargs: Additional keyword arguments to pass to the HttpResponse
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
        if HAS_ORJSON:
            buffer.append(orjson.dumps(item).decode("utf-8"))
        else:
            buffer.append(json.dumps(item))

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
        response["X-Django-Matt-Request-Time"] = f"{duration:.2f}ms"

        return response


# Import asyncio at the end to avoid circular imports
import asyncio
