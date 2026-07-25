"""
Tests for the Request Inspector module in Django Matt.
"""

import json
import time
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from django_matt.inspector.export import (
    export_as_curl,
    export_as_fetch,
    export_as_httpie,
    export_as_python,
    export_request,
)
from django_matt.inspector.middleware import RequestCaptureMiddleware
from django_matt.inspector.schemas import (
    CapturedRequestListSchema,
    CapturedRequestSchema,
    CaptureStatusSchema,
    InspectorStatsSchema,
)
from django_matt.inspector.storage import (
    CapturedRequest,
    MemoryStorage,
    get_storage,
    reset_storage,
)

# =============================================================================
# Storage Tests
# =============================================================================


class TestCapturedRequest(TestCase):
    """Tests for CapturedRequest dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        request = CapturedRequest()
        self.assertIsNotNone(request.id)
        self.assertIsNotNone(request.timestamp)
        self.assertEqual(request.method, "")
        self.assertEqual(request.path, "")
        self.assertEqual(request.response_status, 0)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        request = CapturedRequest(
            method="GET",
            path="/api/test",
            response_status=200,
        )
        data = request.to_dict()
        self.assertEqual(data["method"], "GET")
        self.assertEqual(data["path"], "/api/test")
        self.assertEqual(data["response_status"], 200)

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "id": "test-id",
            "timestamp": 1234567890.0,
            "method": "POST",
            "path": "/api/users",
            "full_url": "http://localhost/api/users",
            "query_string": "",
            "request_headers": {},
            "request_body": None,
            "request_content_type": None,
            "response_status": 201,
            "response_headers": {},
            "response_body": None,
            "response_content_type": None,
            "duration_ms": 50.0,
            "client_ip": "127.0.0.1",
            "user_id": None,
            "user_email": None,
            "exception": None,
            "traceback": None,
        }
        request = CapturedRequest.from_dict(data)
        self.assertEqual(request.id, "test-id")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.response_status, 201)

    def test_status_category_success(self):
        """Test status category for success responses."""
        request = CapturedRequest(response_status=200)
        self.assertEqual(request.status_category, "success")
        self.assertTrue(request.is_success)
        self.assertFalse(request.is_client_error)

    def test_status_category_redirect(self):
        """Test status category for redirect responses."""
        request = CapturedRequest(response_status=302)
        self.assertEqual(request.status_category, "redirect")
        self.assertTrue(request.is_redirect)

    def test_status_category_client_error(self):
        """Test status category for client error responses."""
        request = CapturedRequest(response_status=404)
        self.assertEqual(request.status_category, "client_error")
        self.assertTrue(request.is_client_error)

    def test_status_category_server_error(self):
        """Test status category for server error responses."""
        request = CapturedRequest(response_status=500)
        self.assertEqual(request.status_category, "server_error")
        self.assertTrue(request.is_server_error)


class TestMemoryStorage(TestCase):
    """Tests for MemoryStorage backend."""

    def setUp(self):
        self.storage = MemoryStorage(max_requests=10)

    def test_add_and_get(self):
        """Test adding and retrieving requests."""
        request = CapturedRequest(
            method="GET",
            path="/api/test",
            response_status=200,
        )
        self.storage.add(request)

        retrieved = self.storage.get(request.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.method, "GET")
        self.assertEqual(retrieved.path, "/api/test")

    def test_get_nonexistent(self):
        """Test retrieving non-existent request returns None."""
        retrieved = self.storage.get("nonexistent-id")
        self.assertIsNone(retrieved)

    def test_list_all(self):
        """Test listing all requests."""
        for i in range(5):
            request = CapturedRequest(
                method="GET",
                path=f"/api/test/{i}",
                response_status=200,
            )
            self.storage.add(request)

        requests = self.storage.list()
        self.assertEqual(len(requests), 5)

    def test_list_with_limit(self):
        """Test listing with limit."""
        for i in range(5):
            self.storage.add(CapturedRequest(path=f"/api/test/{i}"))

        requests = self.storage.list(limit=3)
        self.assertEqual(len(requests), 3)

    def test_list_with_offset(self):
        """Test listing with offset."""
        for i in range(5):
            self.storage.add(CapturedRequest(path=f"/api/test/{i}"))

        requests = self.storage.list(offset=2)
        self.assertEqual(len(requests), 3)

    def test_list_filter_by_method(self):
        """Test filtering by HTTP method."""
        self.storage.add(CapturedRequest(method="GET"))
        self.storage.add(CapturedRequest(method="POST"))
        self.storage.add(CapturedRequest(method="GET"))

        get_requests = self.storage.list(method="GET")
        self.assertEqual(len(get_requests), 2)

        post_requests = self.storage.list(method="POST")
        self.assertEqual(len(post_requests), 1)

    def test_list_filter_by_status(self):
        """Test filtering by status code."""
        self.storage.add(CapturedRequest(response_status=200))
        self.storage.add(CapturedRequest(response_status=404))
        self.storage.add(CapturedRequest(response_status=200))

        success_requests = self.storage.list(status=200)
        self.assertEqual(len(success_requests), 2)

    def test_list_filter_by_status_range(self):
        """Test filtering by status code range."""
        self.storage.add(CapturedRequest(response_status=200))
        self.storage.add(CapturedRequest(response_status=201))
        self.storage.add(CapturedRequest(response_status=404))
        self.storage.add(CapturedRequest(response_status=500))

        # 2xx requests
        success_requests = self.storage.list(status_min=200, status_max=300)
        self.assertEqual(len(success_requests), 2)

        # 4xx+ requests
        error_requests = self.storage.list(status_min=400)
        self.assertEqual(len(error_requests), 2)

    def test_list_filter_by_path(self):
        """Test filtering by path contains."""
        self.storage.add(CapturedRequest(path="/api/users"))
        self.storage.add(CapturedRequest(path="/api/posts"))
        self.storage.add(CapturedRequest(path="/api/users/123"))

        user_requests = self.storage.list(path_contains="users")
        self.assertEqual(len(user_requests), 2)

    def test_count(self):
        """Test counting requests."""
        self.assertEqual(self.storage.count(), 0)

        for i in range(3):
            self.storage.add(CapturedRequest())

        self.assertEqual(self.storage.count(), 3)

    def test_clear(self):
        """Test clearing all requests."""
        for i in range(3):
            self.storage.add(CapturedRequest())

        cleared = self.storage.clear()
        self.assertEqual(cleared, 3)
        self.assertEqual(self.storage.count(), 0)

    def test_max_requests_limit(self):
        """Test that max_requests limit is enforced."""
        storage = MemoryStorage(max_requests=5)

        for i in range(10):
            storage.add(CapturedRequest(path=f"/api/test/{i}"))

        self.assertEqual(storage.count(), 5)

    def test_pause_and_resume(self):
        """Test pausing and resuming capture."""
        self.assertTrue(self.storage.is_capturing())

        self.storage.pause_capture()
        self.assertFalse(self.storage.is_capturing())

        # Adding should not work when paused
        self.storage.add(CapturedRequest())
        self.assertEqual(self.storage.count(), 0)

        self.storage.resume_capture()
        self.assertTrue(self.storage.is_capturing())

        # Adding should work after resume
        self.storage.add(CapturedRequest())
        self.assertEqual(self.storage.count(), 1)


# =============================================================================
# Export Tests
# =============================================================================


class TestExportFunctions(TestCase):
    """Tests for export functions."""

    def setUp(self):
        self.request = CapturedRequest(
            method="POST",
            path="/api/users",
            full_url="http://localhost:8000/api/users",
            request_headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer token123",
            },
            request_body='{"name": "John", "email": "john@example.com"}',
            response_status=201,
            response_body='{"id": 1, "name": "John"}',
            duration_ms=45.5,
        )

    def test_export_as_curl(self):
        """Test curl export."""
        result = export_as_curl(self.request)
        self.assertIn("curl", result)
        self.assertIn("-X POST", result)
        self.assertIn("Authorization:", result)
        self.assertIn("http://localhost:8000/api/users", result)

    def test_export_as_curl_with_response(self):
        """Test curl export with response included."""
        result = export_as_curl(self.request, include_response=True)
        self.assertIn("Expected response", result)
        self.assertIn("201", result)

    def test_export_as_httpie(self):
        """Test HTTPie export."""
        result = export_as_httpie(self.request)
        self.assertIn("http", result)
        self.assertIn("POST", result)
        self.assertIn("http://localhost:8000/api/users", result)

    def test_export_as_python(self):
        """Test Python requests export."""
        result = export_as_python(self.request)
        self.assertIn("import requests", result)
        self.assertIn("requests.post", result)
        self.assertIn("http://localhost:8000/api/users", result)

    def test_export_as_fetch(self):
        """Test JavaScript fetch export."""
        result = export_as_fetch(self.request)
        self.assertIn("fetch", result)
        self.assertIn("method: \"POST\"", result)
        self.assertIn("http://localhost:8000/api/users", result)

    def test_export_request_function(self):
        """Test the export_request convenience function."""
        for format_name in ["curl", "httpie", "python", "fetch"]:
            result = export_request(self.request, format=format_name)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)

    def test_export_request_invalid_format(self):
        """Test export_request with invalid format raises ValueError."""
        with self.assertRaises(ValueError) as context:
            export_request(self.request, format="invalid")
        self.assertIn("Unsupported export format", str(context.exception))


class TestExportEdgeCases(TestCase):
    """Tests for export edge cases."""

    def test_export_get_request(self):
        """Test exporting a simple GET request."""
        request = CapturedRequest(
            method="GET",
            path="/api/users",
            full_url="http://localhost:8000/api/users",
            response_status=200,
        )
        result = export_as_curl(request)
        self.assertIn("curl", result)
        self.assertNotIn("-X GET", result)  # curl defaults to GET

    def test_export_with_query_string(self):
        """Test exporting request with query string."""
        request = CapturedRequest(
            method="GET",
            path="/api/users",
            full_url="http://localhost:8000/api/users?page=1",
            query_string="page=1",
            response_status=200,
        )
        result = export_as_curl(request)
        self.assertIn("page=1", result)

    def test_export_without_body(self):
        """Test exporting request without body."""
        request = CapturedRequest(
            method="GET",
            path="/api/users",
            full_url="http://localhost:8000/api/users",
            response_status=200,
        )
        result = export_as_curl(request)
        self.assertNotIn("-d", result)


# =============================================================================
# Middleware Tests
# =============================================================================


class TestRequestCaptureMiddleware(TestCase):
    """Tests for RequestCaptureMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        reset_storage()

    def tearDown(self):
        reset_storage()

    def test_middleware_captures_request(self):
        """Test that middleware captures requests."""
        with patch.object(
            RequestCaptureMiddleware,
            "_get_config",
            return_value={
                "enabled": True,
                "max_body_size": 65536,
                "ignore_paths": [],
                "ignore_extensions": [],
                "capture_headers": True,
                "capture_body": True,
                "capture_response": True,
            },
        ):
            # Create middleware
            get_response = MagicMock(return_value=MagicMock(
                status_code=200,
                content=b'{"result": "ok"}',
                items=lambda: [("Content-Type", "application/json")],
            ))
            get_response.return_value.get = lambda k, d=None: "application/json" if k == "Content-Type" else d
            middleware = RequestCaptureMiddleware(get_response)

            # Make request
            request = self.factory.get("/api/test")
            middleware(request)

            # Check storage
            storage = get_storage()
            self.assertEqual(storage.count(), 1)

    def test_middleware_ignores_path(self):
        """Test that middleware ignores configured paths."""
        with patch.object(
            RequestCaptureMiddleware,
            "_get_config",
            return_value={
                "enabled": True,
                "max_body_size": 65536,
                "ignore_paths": ["/static/", "/_matt/"],
                "ignore_extensions": [],
                "capture_headers": True,
                "capture_body": True,
                "capture_response": True,
            },
        ):
            get_response = MagicMock(return_value=MagicMock(status_code=200))
            middleware = RequestCaptureMiddleware(get_response)

            request = self.factory.get("/static/test.css")
            middleware(request)

            storage = get_storage()
            self.assertEqual(storage.count(), 0)

    def test_middleware_disabled(self):
        """Test that middleware does nothing when disabled."""
        with patch.object(
            RequestCaptureMiddleware,
            "_get_config",
            return_value={
                "enabled": False,
                "max_body_size": 65536,
                "ignore_paths": [],
                "ignore_extensions": [],
                "capture_headers": True,
                "capture_body": True,
                "capture_response": True,
            },
        ):
            get_response = MagicMock(return_value=MagicMock(status_code=200))
            middleware = RequestCaptureMiddleware(get_response)

            request = self.factory.get("/api/test")
            middleware(request)

            storage = get_storage()
            self.assertEqual(storage.count(), 0)


# =============================================================================
# Schema Tests
# =============================================================================


class TestSchemas(TestCase):
    """Tests for Pydantic schemas."""

    def test_captured_request_schema(self):
        """Test CapturedRequestSchema validation."""
        data = {
            "id": "test-123",
            "timestamp": 1234567890.0,
            "method": "GET",
            "path": "/api/test",
            "full_url": "http://localhost/api/test",
            "response_status": 200,
            "duration_ms": 50.0,
            "client_ip": "127.0.0.1",
            "status_category": "success",
            "is_success": True,
            "is_error": False,
        }
        schema = CapturedRequestSchema(**data)
        self.assertEqual(schema.id, "test-123")
        self.assertEqual(schema.method, "GET")

    def test_inspector_stats_schema(self):
        """Test InspectorStatsSchema validation."""
        data = {
            "total_requests": 100,
            "success_count": 80,
            "error_count": 20,
            "avg_duration_ms": 45.5,
            "max_duration_ms": 200.0,
            "methods": {"GET": 50, "POST": 50},
            "status_codes": {"200": 80, "404": 20},
            "is_capturing": True,
        }
        schema = InspectorStatsSchema(**data)
        self.assertEqual(schema.total_requests, 100)
        self.assertEqual(schema.error_count, 20)

    def test_capture_status_schema(self):
        """Test CaptureStatusSchema validation."""
        data = {
            "is_capturing": True,
            "storage_type": "memory",
            "request_count": 50,
            "max_requests": 100,
        }
        schema = CaptureStatusSchema(**data)
        self.assertTrue(schema.is_capturing)
        self.assertEqual(schema.storage_type, "memory")


# =============================================================================
# Integration Tests
# =============================================================================


class TestInspectorIntegration(TestCase):
    """Integration tests for the Request Inspector."""

    def setUp(self):
        reset_storage()

    def tearDown(self):
        reset_storage()

    def test_full_workflow(self):
        """Test full inspector workflow: capture, list, export."""
        storage = MemoryStorage(max_requests=100)

        # Add some requests
        for i in range(5):
            request = CapturedRequest(
                method="GET" if i % 2 == 0 else "POST",
                path=f"/api/resource/{i}",
                full_url=f"http://localhost/api/resource/{i}",
                response_status=200 if i < 3 else 404,
                duration_ms=10.0 + i * 5,
            )
            storage.add(request)

        # List requests
        all_requests = storage.list()
        self.assertEqual(len(all_requests), 5)

        # Filter by method
        get_requests = storage.list(method="GET")
        self.assertEqual(len(get_requests), 3)

        # Filter by status
        success_requests = storage.list(status_min=200, status_max=300)
        self.assertEqual(len(success_requests), 3)

        # Export a request
        request = all_requests[0]
        curl_export = export_as_curl(request)
        self.assertIn("curl", curl_export)
        self.assertIn(request.path, curl_export)

        # Clear storage
        cleared = storage.clear()
        self.assertEqual(cleared, 5)
        self.assertEqual(storage.count(), 0)

    def test_pause_resume_workflow(self):
        """Test pause and resume workflow."""
        storage = MemoryStorage(max_requests=100)

        # Add initial request
        storage.add(CapturedRequest(path="/api/test/1"))
        self.assertEqual(storage.count(), 1)

        # Pause and try to add
        storage.pause_capture()
        storage.add(CapturedRequest(path="/api/test/2"))
        self.assertEqual(storage.count(), 1)  # Should not increase

        # Resume and add
        storage.resume_capture()
        storage.add(CapturedRequest(path="/api/test/3"))
        self.assertEqual(storage.count(), 2)  # Should increase


# =============================================================================
# Success-Criteria-Aligned Tests (Phase 07, Plan 02)
# =============================================================================


class TestInspectorCaptureSuccessCriteria(TestCase):
    """
    Verify OBS-04: Request inspector captures request/response pairs in dev mode.
    """

    def setUp(self):
        self.factory = RequestFactory()
        reset_storage()

    def tearDown(self):
        reset_storage()

    def test_inspector_captures_method_path_status_body(self):
        """Inspector middleware captures request method, path, status code, response body."""
        with patch.object(
            RequestCaptureMiddleware,
            "_get_config",
            return_value={
                "enabled": True,
                "max_body_size": 65536,
                "ignore_paths": [],
                "ignore_extensions": [],
                "capture_headers": True,
                "capture_body": True,
                "capture_response": True,
            },
        ):
            mock_response = MagicMock(
                status_code=200,
                content=b'{"users": []}',
                items=lambda: [("Content-Type", "application/json")],
            )
            mock_response.get = lambda k, d=None: "application/json" if k == "Content-Type" else d
            get_response = MagicMock(return_value=mock_response)
            middleware = RequestCaptureMiddleware(get_response)

            request = self.factory.post(
                "/api/users",
                data='{"name": "test"}',
                content_type="application/json",
            )
            middleware(request)

            storage = get_storage()
            self.assertEqual(storage.count(), 1)

            captured = storage.list()[0]
            self.assertEqual(captured.method, "POST")
            self.assertEqual(captured.path, "/api/users")
            self.assertEqual(captured.response_status, 200)
            self.assertIn("users", captured.response_body)

    def test_inspector_disabled_when_debug_false(self):
        """Inspector is disabled when DEBUG=False (production gating)."""
        with patch.object(
            RequestCaptureMiddleware,
            "_get_config",
            return_value={
                "enabled": False,  # Simulates DEBUG=False
                "max_body_size": 65536,
                "ignore_paths": [],
                "ignore_extensions": [],
                "capture_headers": True,
                "capture_body": True,
                "capture_response": True,
            },
        ):
            get_response = MagicMock(return_value=MagicMock(status_code=200))
            middleware = RequestCaptureMiddleware(get_response)

            request = self.factory.get("/api/test")
            middleware(request)

            storage = get_storage()
            self.assertEqual(storage.count(), 0)

    def test_inspector_storage_retrieves_captured_requests(self):
        """Inspector storage retrieves captured requests by ID."""
        storage = MemoryStorage(max_requests=100)

        req = CapturedRequest(
            method="GET",
            path="/api/items",
            response_status=200,
            response_body='[{"id":1}]',
        )
        storage.add(req)

        retrieved = storage.get(req.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.method, "GET")
        self.assertEqual(retrieved.path, "/api/items")
        self.assertEqual(retrieved.response_status, 200)
        self.assertEqual(retrieved.response_body, '[{"id":1}]')

    def test_inspector_captures_duration(self):
        """Inspector captures request duration."""
        with patch.object(
            RequestCaptureMiddleware,
            "_get_config",
            return_value={
                "enabled": True,
                "max_body_size": 65536,
                "ignore_paths": [],
                "ignore_extensions": [],
                "capture_headers": True,
                "capture_body": True,
                "capture_response": True,
            },
        ):
            mock_response = MagicMock(
                status_code=200,
                content=b"OK",
                items=lambda: [("Content-Type", "text/plain")],
            )
            mock_response.get = lambda k, d=None: "text/plain" if k == "Content-Type" else d
            get_response = MagicMock(return_value=mock_response)
            middleware = RequestCaptureMiddleware(get_response)

            request = self.factory.get("/api/test")
            middleware(request)

            storage = get_storage()
            captured = storage.list()[0]
            self.assertIsNotNone(captured.duration_ms)
            self.assertGreaterEqual(captured.duration_ms, 0)
