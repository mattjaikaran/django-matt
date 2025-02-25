"""
Tests for the performance utilities in Django Matt.
"""

import json
import time

import pytest
from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory, TestCase, override_settings

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


class TestFastJSONRenderer(TestCase):
    """Tests for the FastJSONRenderer class."""

    def test_dumps_and_loads(self):
        """Test that dumps and loads work correctly."""
        renderer = FastJSONRenderer()
        data = {"key": "value", "nested": {"list": [1, 2, 3]}}

        # Test dumps
        json_str = renderer.dumps(data)
        self.assertIsInstance(json_str, str)

        # Test loads
        loaded_data = renderer.loads(json_str)
        self.assertEqual(loaded_data, data)

    def test_renderer_selection(self):
        """Test that the correct renderer is selected based on availability."""
        renderer = FastJSONRenderer()

        if HAS_ORJSON:
            self.assertEqual(renderer.library_name, "orjson")
        elif HAS_UJSON:
            self.assertEqual(renderer.library_name, "ujson")
        else:
            self.assertEqual(renderer.library_name, "json")


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
        self.middleware = BenchmarkMiddleware(get_response=lambda request: JsonResponse({"data": "test"}))

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
