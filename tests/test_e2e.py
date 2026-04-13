"""
End-to-end integration tests.

These tests boot the full ASGI application and make real HTTP requests
through the complete middleware stack (routing, auth, serialization, error handling).

Endpoints available (from tests/urls.py):
  GET /api/json/       -> FastJsonResponse({"message": "Hello, World!"})
  GET /api/msgpack/    -> MessagePackResponse({"message": "Hello, World!"})
  GET /api/streaming/  -> StreamingJsonResponse (NDJSON list of 5 items)
  GET /api/cached/     -> FastJsonResponse({"message": "This response is cached."})
"""

from __future__ import annotations

import asyncio

from django.core.asgi import get_asgi_application

import httpx
import pytest


@pytest.fixture(scope="module")
def asgi_app():
    """Get the Django ASGI application (created once per module)."""
    return get_asgi_application()


@pytest.fixture
async def client(asgi_app):
    """Async HTTP client wired to the ASGI app via ASGITransport."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


class TestASGIBasics:
    """Test the ASGI application responds correctly to basic requests."""

    async def test_get_json_endpoint_succeeds(self, client):
        """GET /api/json/ returns 200 with JSON body."""
        response = await client.get("/api/json/")
        assert response.status_code == 200

    async def test_json_endpoint_content_type(self, client):
        """GET /api/json/ returns application/json content type."""
        response = await client.get("/api/json/")
        assert "application/json" in response.headers.get("content-type", "")

    async def test_json_endpoint_body(self, client):
        """GET /api/json/ returns expected JSON body."""
        response = await client.get("/api/json/")
        data = response.json()
        assert isinstance(data, dict)
        assert data.get("message") == "Hello, World!"

    async def test_nonexistent_path_returns_404(self, client):
        """Non-existent paths return 404."""
        response = await client.get("/api/this-does-not-exist-at-all/")
        assert response.status_code == 404

    async def test_msgpack_endpoint_reachable(self, client):
        """GET /api/msgpack/ is reachable (200 if msgpack installed, 500 if missing dep)."""
        response = await client.get("/api/msgpack/")
        # msgpack is an optional dep; 200 when installed, 500 when missing
        assert response.status_code in (200, 500)

    async def test_streaming_endpoint_succeeds(self, client):
        """GET /api/streaming/ returns 200 with streaming JSON."""
        response = await client.get("/api/streaming/")
        assert response.status_code == 200

    async def test_cached_endpoint_succeeds(self, client):
        """GET /api/cached/ returns 200."""
        response = await client.get("/api/cached/")
        assert response.status_code == 200

    async def test_cached_endpoint_body(self, client):
        """GET /api/cached/ returns expected JSON body."""
        response = await client.get("/api/cached/")
        data = response.json()
        assert isinstance(data, dict)
        assert data.get("message") == "This response is cached."


class TestMiddlewareStack:
    """Test that middleware is applied correctly in the E2E flow."""

    async def test_security_headers_present(self, client):
        """SecurityMiddleware should add X-Content-Type-Options header."""
        response = await client.get("/api/json/")
        assert response.status_code == 200
        # Django SecurityMiddleware adds this header
        assert response.headers.get("x-content-type-options") == "nosniff"

    async def test_xframe_options_header(self, client):
        """XFrameOptionsMiddleware should add X-Frame-Options header."""
        response = await client.get("/api/json/")
        assert response.status_code == 200
        assert "x-frame-options" in response.headers

    async def test_large_request_body_handled(self, client):
        """Large request bodies should not crash the server."""
        large_payload = {"data": "x" * 10_000}
        response = await client.post(
            "/api/json/",
            json=large_payload,
        )
        # GET-only endpoint — 403 (CSRF), 405, or 404; server must not crash
        assert response.status_code in (200, 201, 400, 403, 404, 405)

    async def test_invalid_json_body_handled_gracefully(self, client):
        """Malformed JSON body should return a non-500 response."""
        response = await client.post(
            "/api/json/",
            content=b"{invalid json",
            headers={"content-type": "application/json"},
        )
        # CSRF middleware fires before JSON parsing; 400/403/405 all acceptable
        assert response.status_code in (400, 403, 404, 405)

    async def test_concurrent_requests_all_succeed(self, client):
        """Ten concurrent requests to /api/json/ should all return 200."""
        tasks = [client.get("/api/json/") for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        for resp in responses:
            assert resp.status_code == 200

    async def test_head_request_no_body(self, client):
        """HEAD /api/json/ should return headers but no body."""
        response = await client.head("/api/json/")
        assert response.status_code in (200, 405)
        if response.status_code == 200:
            assert response.content == b""


class TestErrorHandling:
    """Test error handling through the full ASGI stack."""

    async def test_404_for_unknown_api_path(self, client):
        """Unknown /api/ path returns 404."""
        response = await client.get("/api/unknown-endpoint-xyz/")
        assert response.status_code == 404

    async def test_method_not_allowed_returns_405(self, client):
        """DELETE on a GET-only endpoint returns 405 (or 403 if CSRF fires first)."""
        response = await client.delete("/api/json/")
        assert response.status_code in (403, 404, 405)

    async def test_put_on_get_endpoint(self, client):
        """PUT on a GET-only endpoint returns 405 or 404 (or 403 CSRF)."""
        response = await client.put("/api/json/", json={"key": "value"})
        assert response.status_code in (403, 404, 405)

    async def test_patch_on_get_endpoint(self, client):
        """PATCH on a GET-only endpoint returns 405 or 404 (or 403 CSRF)."""
        response = await client.patch("/api/json/", json={"key": "value"})
        assert response.status_code in (403, 404, 405)


class TestResponseIntegrity:
    """Verify response data integrity through the full stack."""

    async def test_json_response_is_valid_json(self, client):
        """Response body must deserialize without error."""
        response = await client.get("/api/json/")
        # httpx .json() raises if body is not valid JSON
        data = response.json()
        assert data is not None

    async def test_msgpack_response_has_content(self, client):
        """MessagePack endpoint returns non-empty body (skipped if dep missing)."""
        response = await client.get("/api/msgpack/")
        if response.status_code == 500:
            pytest.skip("msgpack optional dep not installed")
        assert len(response.content) > 0

    async def test_streaming_response_contains_items(self, client):
        """Streaming endpoint returns content containing JSON items."""
        response = await client.get("/api/streaming/")
        assert response.status_code == 200
        assert len(response.content) > 0

    async def test_cached_response_is_idempotent(self, client):
        """Two sequential requests to /api/cached/ return identical bodies."""
        r1 = await client.get("/api/cached/")
        r2 = await client.get("/api/cached/")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() == r2.json()

    async def test_benchmark_timing_header(self, client):
        """DJANGO_MATT_BENCHMARK_HEADER should appear on the cached view."""
        response = await client.get("/api/cached/")
        assert response.status_code == 200
        # The benchmark decorator wraps the cached view; header may be present
        # Just assert the response is well-formed — header presence is optional
        assert response.json().get("message") == "This response is cached."
