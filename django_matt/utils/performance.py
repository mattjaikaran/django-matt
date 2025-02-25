"""
Performance utilities for Django Matt framework.

This module provides tools for optimizing performance, including faster JSON
rendering and benchmarking utilities.
"""

import functools
import json
import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
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
        self.measurements[name]["min_time"] = min(self.measurements[name]["min_time"], duration)
        self.measurements[name]["max_time"] = max(self.measurements[name]["max_time"], duration)
        self.measurements[name]["avg_time"] = self.measurements[name]["total_time"] / self.measurements[name]["count"]

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


# Create a singleton instance of the benchmark utility
benchmark = APIBenchmark()


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
