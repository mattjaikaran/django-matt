"""
Tests for the performance utilities in Django Matt.
"""

import ast
import json
import time
from pathlib import Path

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory, TestCase, override_settings

import pytest

from django_matt.utils.performance import (
    HAS_MSGPACK,
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


class TestFastJSONRenderer(TestCase):
    """Tests for the FastJSONRenderer class."""

    def test_dumps_and_loads(self):
        """Test that dumps and loads work correctly."""
        renderer = FastJSONRenderer()
        data = {"key": "value", "nested": {"list": [1, 2, 3]}}

        # Test dumps - returns bytes
        json_bytes = renderer.dumps(data)
        self.assertIsInstance(json_bytes, bytes)

        # Test loads
        loaded_data = renderer.loads(json_bytes)
        self.assertEqual(loaded_data, data)

    def test_renderer_selection(self):
        """Test that the renderer uses orjson (base dependency)."""
        renderer = FastJSONRenderer()
        self.assertEqual(renderer.library_name, "orjson")


class TestFastJsonResponse(TestCase):
    """Tests for the FastJsonResponse class."""

    def test_response_content(self):
        """Test that the response content is correctly serialized."""
        data = {"key": "value", "list": [1, 2, 3]}
        response = FastJsonResponse(data)

        # Check content type
        self.assertEqual(response["Content-Type"], "application/json")

        # Check content
        content = json.loads(response.content.decode())
        self.assertEqual(content, data)


@pytest.mark.skipif(not HAS_MSGPACK, reason="MessagePack is not installed")
class TestMessagePackRenderer(TestCase):
    """Tests for the MessagePackRenderer class."""

    def test_dumps_and_loads(self):
        """Test that dumps and loads work correctly."""
        renderer = MessagePackRenderer()
        data = {"key": "value", "nested": {"list": [1, 2, 3]}}

        # Test dumps
        msgpack_data = renderer.dumps(data)
        self.assertIsInstance(msgpack_data, bytes)

        # Test loads
        loaded_data = renderer.loads(msgpack_data)
        self.assertEqual(loaded_data, data)


@pytest.mark.skipif(not HAS_MSGPACK, reason="MessagePack is not installed")
class TestMessagePackResponse(TestCase):
    """Tests for the MessagePackResponse class."""

    def test_response_content(self):
        """Test that the response content is correctly serialized."""
        data = {"key": "value", "list": [1, 2, 3]}
        response = MessagePackResponse(data)

        # Check content type
        self.assertEqual(response["Content-Type"], "application/x-msgpack")

        # Check content
        renderer = MessagePackRenderer()
        content = renderer.loads(response.content)
        self.assertEqual(content, data)


class TestStreamingJsonResponse(TestCase):
    """Tests for the StreamingJsonResponse class."""

    def test_streaming_content(self):
        """Test that the streaming content is correctly generated."""

        def items_generator():
            for i in range(5):
                yield {"id": i, "name": f"Item {i}"}

        response = StreamingJsonResponse(streaming_content=stream_json_list(items_generator()))

        # Check content type
        self.assertEqual(response["Content-Type"], "application/json")

        # Check content
        content = b"".join(response.streaming_content)
        expected_data = [{"id": i, "name": f"Item {i}"} for i in range(5)]
        self.assertEqual(json.loads(content.decode()), expected_data)


class TestCacheManager(TestCase):
    """Tests for the CacheManager class."""

    def setUp(self):
        """Set up the test case."""
        self.cache_manager = CacheManager()

    def test_set_and_get(self):
        """Test that set and get work correctly."""
        key = "test_key"
        value = {"data": "test_value"}

        # Set the value
        self.cache_manager.set(key, value, timeout=10)

        # Get the value
        cached_value = self.cache_manager.get(key)
        self.assertEqual(cached_value, value)

    def test_delete(self):
        """Test that delete works correctly."""
        key = "test_key"
        value = {"data": "test_value"}

        # Set the value
        self.cache_manager.set(key, value)

        # Delete the value
        self.cache_manager.delete(key)

        # Get the value (should be None)
        cached_value = self.cache_manager.get(key)
        self.assertIsNone(cached_value)

    def test_cache_response(self):
        """Test that cache_response works correctly."""

        @self.cache_manager.cache_response(timeout=10)
        def test_view(request):
            return FastJsonResponse({"data": "test_value", "timestamp": time.time()})

        # Create a request
        request = RequestFactory().get("/test/")

        # Call the view twice
        response1 = test_view(request)
        time.sleep(0.1)  # Small delay to ensure timestamps would be different
        response2 = test_view(request)

        # Check that the responses are the same (cached)
        content1 = json.loads(response1.content.decode())
        content2 = json.loads(response2.content.decode())
        self.assertEqual(content1, content2)

    def test_cache_result(self):
        """Test that cache_result works correctly."""
        counter = [0]

        @self.cache_manager.cache_result(timeout=10)
        def expensive_function(param):
            counter[0] += 1
            return {"result": param, "count": counter[0]}

        # Call the function twice with the same parameter
        result1 = expensive_function("test")
        result2 = expensive_function("test")

        # Check that the function was only called once
        self.assertEqual(counter[0], 1)

        # Check that the results are the same
        self.assertEqual(result1, result2)

        # Call the function with a different parameter
        result3 = expensive_function("different")

        # Check that the function was called again
        self.assertEqual(counter[0], 2)

        # Check that the result is different
        self.assertNotEqual(result1, result3)


class TestAPIBenchmark(TestCase):
    """Tests for the APIBenchmark class."""

    def setUp(self):
        """Set up the test case."""
        self.benchmark = APIBenchmark()

    def test_measure_decorator(self):
        """Test that the measure decorator works correctly."""

        @self.benchmark.measure("test_operation")
        def test_function():
            time.sleep(0.01)
            return "result"

        # Call the function
        result = test_function()

        # Check that the function returned the correct result
        self.assertEqual(result, "result")

        # Check that the benchmark recorded the operation
        report = self.benchmark.get_report()
        self.assertIn("test_operation", report)
        self.assertEqual(report["test_operation"]["count"], 1)
        self.assertGreater(report["test_operation"]["avg_time"], 0)

    def test_measure_context_manager(self):
        """Test that the measure context manager works correctly."""
        with self.benchmark.measure("test_operation"):
            time.sleep(0.01)

        # Check that the benchmark recorded the operation
        report = self.benchmark.get_report()
        self.assertIn("test_operation", report)
        self.assertEqual(report["test_operation"]["count"], 1)
        self.assertGreater(report["test_operation"]["avg_time"], 0)


@override_settings(DJANGO_MATT_BENCHMARK_ENABLED=True)
class TestBenchmarkMiddleware(TestCase):
    """Tests for the BenchmarkMiddleware class."""

    def setUp(self):
        """Set up the test case."""
        self.middleware = BenchmarkMiddleware(
            get_response=lambda request: JsonResponse({"data": "test"})
        )

    def test_middleware_adds_timing_header(self):
        """Test that the middleware adds a timing header to the response."""
        request = HttpRequest()
        response = self.middleware(request)

        # Check that the timing header is present
        self.assertIn("X-Django-Matt-Timing", response)

        # Check that the timing value is a number followed by "ms"
        timing_value = response["X-Django-Matt-Timing"]
        self.assertRegex(timing_value, r"^\d+(\.\d+)?ms$")


class TestGlobalInstances(TestCase):
    """Tests for the global instances of the performance utilities."""

    def test_benchmark_instance(self):
        """Test that the global benchmark instance works correctly."""

        @benchmark.measure("test_operation")
        def test_function():
            time.sleep(0.01)
            return "result"

        # Call the function
        result = test_function()

        # Check that the function returned the correct result
        self.assertEqual(result, "result")

        # Check that the benchmark recorded the operation
        report = benchmark.get_report()
        self.assertIn("test_operation", report)

    def test_cache_manager_instance(self):
        """Test that the global cache_manager instance works correctly."""
        key = "test_key"
        value = {"data": "test_value"}

        # Set the value
        cache_manager.set(key, value)

        # Get the value
        cached_value = cache_manager.get(key)
        self.assertEqual(cached_value, value)


# ---------------------------------------------------------------------------
# MATT_API_MODE and hot-path introspection caching tests (CORE-12, CORE-09)
# ---------------------------------------------------------------------------

_FULL_MIDDLEWARE_STACK = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


class TestApiModeMiddlewareStripping(TestCase):
    """CORE-12: MATT_API_MODE=True strips browser-oriented middleware."""

    def test_api_mode_strips_middleware(self):
        """
        With MATT_API_MODE=True and a full middleware stack, apply_api_mode()
        must remove CSRF, Sessions, Messages, and Clickjacking middleware while
        keeping SecurityMiddleware and CommonMiddleware.
        """
        from django_matt.config.components.performance import apply_api_mode

        result = apply_api_mode(list(_FULL_MIDDLEWARE_STACK))

        # Stripped middleware must be absent
        self.assertNotIn("django.middleware.csrf.CsrfViewMiddleware", result)
        self.assertNotIn("django.contrib.sessions.middleware.SessionMiddleware", result)
        self.assertNotIn("django.contrib.messages.middleware.MessageMiddleware", result)
        self.assertNotIn("django.middleware.clickjacking.XFrameOptionsMiddleware", result)

        # Security and Common middleware must always remain
        self.assertIn("django.middleware.security.SecurityMiddleware", result)
        self.assertIn("django.middleware.common.CommonMiddleware", result)

    def test_api_mode_keeps_security_middleware(self):
        """SecurityMiddleware is never stripped even with MATT_API_MODE=True."""
        from django_matt.config.components.performance import (
            MIDDLEWARE_KEEP_LIST,
            MIDDLEWARE_STRIP_LIST,
            apply_api_mode,
        )

        # Confirm SecurityMiddleware is not accidentally in the strip list
        self.assertNotIn(
            "django.middleware.security.SecurityMiddleware",
            MIDDLEWARE_STRIP_LIST,
        )
        # And it IS in the keep list
        self.assertIn(
            "django.middleware.security.SecurityMiddleware",
            MIDDLEWARE_KEEP_LIST,
        )

        # Even if only SecurityMiddleware is present, apply_api_mode keeps it
        result = apply_api_mode(["django.middleware.security.SecurityMiddleware"])
        self.assertEqual(result, ["django.middleware.security.SecurityMiddleware"])

    def test_api_mode_disabled_by_default(self):
        """Without MATT_API_MODE setting in Django settings it defaults to False."""
        from django.conf import settings

        value = getattr(settings, "MATT_API_MODE", False)
        self.assertFalse(value)

    def test_api_mode_does_not_strip_unknown_middleware(self):
        """Third-party middleware not in the strip list is left untouched."""
        from django_matt.config.components.performance import apply_api_mode

        custom_mw = [
            "django.middleware.security.SecurityMiddleware",
            "myapp.middleware.CustomMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
        ]
        result = apply_api_mode(custom_mw)

        self.assertIn("myapp.middleware.CustomMiddleware", result)
        self.assertNotIn("django.middleware.csrf.CsrfViewMiddleware", result)


class TestNoGetTypeHintsPerRequest(TestCase):
    """CORE-09: Zero get_type_hints() calls after warmup."""

    def test_no_get_type_hints_per_request(self):
        """
        After warming up the router with N requests (populating the cache),
        subsequent calls to get_body_schema() must produce zero get_type_hints()
        invocations — verified via cProfile.
        """
        import cProfile
        import io
        import pstats
        from typing import get_type_hints

        from pydantic import BaseModel

        from django_matt.core.router import _hints_cache, get_body_schema

        class ItemSchema(BaseModel):
            name: str
            price: float

        def test_endpoint(request, body: ItemSchema) -> dict:
            return {"ok": True}

        # Ensure the endpoint is not in the cache at the start of this test
        endpoint_key = id(test_endpoint)
        _hints_cache.pop(endpoint_key, None)

        # --- WARMUP: populate the hints cache ---
        for _ in range(10):
            get_body_schema(test_endpoint)

        # The cache must be populated after warmup
        self.assertIn(endpoint_key, _hints_cache)

        # --- PROFILE: run 100 more calls and check for get_type_hints ---
        pr = cProfile.Profile()
        pr.enable()
        for _ in range(100):
            get_body_schema(test_endpoint)
        pr.disable()

        # Capture pstats output to a string
        buf = io.StringIO()
        stats = pstats.Stats(pr, stream=buf)
        stats.print_stats("get_type_hints")
        output = buf.getvalue()

        # If get_type_hints was called during the profiled 100 iterations, its
        # function name appears in the pstats output table. Assert it is absent.
        # pstats lists function entries only if they have at least one call, so
        # absence means zero calls during the profiled section.
        self.assertNotIn(
            "get_type_hints",
            output,
            msg=(
                "get_type_hints() was called during the profiled 100 requests — "
                "router-level caching in _hints_cache is broken.\n"
                f"pstats output:\n{output}"
            ),
        )

# ---------------------------------------------------------------------------
# CORE-10: Verify no stdlib json in hot-path files
# ---------------------------------------------------------------------------


def test_orjson_used_everywhere():
    """CORE-10: Verify no stdlib json.dumps or json.loads in hot-path files.

    The hot paths (core/router.py, core/controller.py, views/base.py) must
    use orjson — never stdlib json — for all JSON serialization/deserialization.
    """
    hot_path_files = [
        "django_matt/core/router.py",
        "django_matt/core/controller.py",
        "django_matt/views/base.py",
    ]

    for filepath in hot_path_files:
        source = Path(filepath).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "json" and node.attr in ("dumps", "loads"):
                    pytest.fail(
                        f"{filepath} uses json.{node.attr} — use orjson instead "
                        f"(line {node.lineno})"
                    )


# ---------------------------------------------------------------------------
# PERF-08: assert_query_count — context manager, decorator, error details
# ---------------------------------------------------------------------------


@override_settings(DEBUG=True)
class TestAssertQueryCount(TestCase):
    """PERF-08: assert_query_count raises AssertionError with SQL details on mismatch."""

    def test_context_manager_correct_count_passes(self):
        """Context manager with exactly the right number of queries does not raise."""
        from django.contrib.auth.models import User

        from django_matt.testing.assertions import assert_query_count

        with assert_query_count(1):
            list(User.objects.all())

    def test_context_manager_wrong_count_raises(self):
        """Context manager raises AssertionError when actual count != expected."""
        from django.contrib.auth.models import User

        from django_matt.testing.assertions import assert_query_count

        with self.assertRaises(AssertionError) as cm, assert_query_count(99):
            list(User.objects.all())

        # The error message must report the mismatch
        error_msg = str(cm.exception)
        self.assertIn("99", error_msg)
        self.assertIn("1", error_msg)

    def test_context_manager_shows_sql_on_failure(self):
        """AssertionError message includes actual SQL queries for debugging."""
        from django.contrib.auth.models import User

        from django_matt.testing.assertions import assert_query_count

        with self.assertRaises(AssertionError) as cm, assert_query_count(0):
            list(User.objects.all())

        error_msg = str(cm.exception)
        # The SQL text for a User query must appear in the error message
        self.assertIn("SELECT", error_msg.upper())

    def test_decorator_correct_count_passes(self):
        """Decorated test function with the right query count does not raise."""
        from django.contrib.auth.models import User

        from django_matt.testing.assertions import assert_query_count

        @assert_query_count(1)
        def run():
            list(User.objects.all())

        # Should not raise
        run()

    def test_decorator_wrong_count_raises(self):
        """Decorated function raises AssertionError when count mismatches."""
        from django.contrib.auth.models import User

        from django_matt.testing.assertions import assert_query_count

        @assert_query_count(99)
        def run():
            list(User.objects.all())

        with self.assertRaises(AssertionError):
            run()


# ---------------------------------------------------------------------------
# PERF-05: Streaming memory threshold — 10k records < 50 MB peak
# ---------------------------------------------------------------------------


class TestStreamingMemoryThreshold(TestCase):
    """PERF-05: Stream 10k dict records via stream_json_list with < 50MB peak memory."""

    def test_streaming_memory_threshold(self):
        """10k records via stream_json_list must use < 50 MB peak memory."""
        import tracemalloc

        from django_matt.utils.performance import StreamingJsonResponse, stream_json_list

        def generate_records():
            for i in range(10_000):
                yield {"id": i, "name": f"Item {i}", "value": i * 1.5}

        tracemalloc.start()
        response = StreamingJsonResponse(
            streaming_content=stream_json_list(generate_records())
        )
        # Consume the entire streaming response to measure actual peak memory
        content = b"".join(
            chunk.encode("utf-8") if isinstance(chunk, str) else chunk
            for chunk in response.streaming_content
        )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        self.assertGreater(len(content), 0, "Streaming response must produce content")
        self.assertLess(
            peak_mb,
            50,
            f"Peak memory {peak_mb:.2f} MB exceeded 50 MB threshold for 10k record stream",
        )


# ---------------------------------------------------------------------------
# PERF-06: cache_response decorator — caches result, returns on repeat call
# ---------------------------------------------------------------------------


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class TestCacheResponseDecorator(TestCase):
    """PERF-06: cache_response decorator must cache view responses."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_view_executed_only_once_for_same_url(self):
        """View body executes only once; second call returns cached result."""
        from django.core.cache import cache
        from django.http import HttpResponse

        from django_matt.utils.performance import cache_response

        call_counter = [0]

        @cache_response(timeout=300)
        def my_view(request):
            call_counter[0] += 1
            return HttpResponse(f"count={call_counter[0]}")

        request = RequestFactory().get("/test-cache/")

        response1 = my_view(request)
        response2 = my_view(request)

        # View body must have been called exactly once
        self.assertEqual(call_counter[0], 1, "View must execute only once when cached")

        # Both responses must return the same content (from cache)
        self.assertEqual(
            response1.content,
            response2.content,
            "Second call must return the same content as the cached response",
        )

    def test_different_urls_produce_different_cache_entries(self):
        """Requests to different paths are cached independently."""
        from django.http import HttpResponse

        from django_matt.utils.performance import cache_response

        call_counter = [0]

        @cache_response(timeout=300)
        def my_view(request):
            call_counter[0] += 1
            return HttpResponse(f"count={call_counter[0]}")

        request_a = RequestFactory().get("/path-a/")
        request_b = RequestFactory().get("/path-b/")

        my_view(request_a)
        my_view(request_b)

        # Both paths are different → view body must be called twice
        self.assertEqual(call_counter[0], 2, "Different paths must produce separate cache entries")
