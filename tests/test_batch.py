"""Tests for django_matt.batch — HTTP batch endpoint."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from django.http import HttpRequest, JsonResponse
from django.test import RequestFactory

import orjson
import pytest

from django_matt.batch.request import BatchPayload, BatchRequest, BatchResponse
from django_matt.batch.resolver import (
    CyclicDependencyError,
    MissingDependencyError,
    interpolate_value,
    jsonpath_extract,
    topological_sort,
)

# ──────────────────────────────────────────────
# Schema tests
# ──────────────────────────────────────────────


class TestBatchRequest:
    def test_method_normalized_to_upper(self):
        req = BatchRequest(method="get", path="/foo")
        assert req.method == "GET"

    def test_defaults(self):
        req = BatchRequest(method="POST", path="/bar")
        assert req.headers == {}
        assert req.body is None
        assert req.name is None
        assert req.depends_on == []

    def test_with_dependencies(self):
        req = BatchRequest(
            method="POST",
            path="/orders",
            name="create_order",
            depends_on=["get_user"],
            body={"user_id": 1},
        )
        assert req.depends_on == ["get_user"]
        assert req.name == "create_order"


class TestBatchResponse:
    def test_basic(self):
        resp = BatchResponse(status=200, body={"id": 1})
        assert resp.status == 200
        assert resp.error is None

    def test_error(self):
        resp = BatchResponse(status=500, error="boom")
        assert resp.error == "boom"


class TestBatchPayload:
    def test_valid(self):
        payload = BatchPayload(
            requests=[
                BatchRequest(method="GET", path="/users"),
                BatchRequest(method="GET", path="/posts"),
            ]
        )
        assert len(payload.requests) == 2
        assert payload.atomic is False

    def test_empty_requests_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BatchPayload(requests=[])

    def test_atomic_flag(self):
        payload = BatchPayload(
            requests=[BatchRequest(method="GET", path="/")],
            atomic=True,
        )
        assert payload.atomic is True


# ──────────────────────────────────────────────
# JSONPath tests
# ──────────────────────────────────────────────


class TestJsonpathExtract:
    def test_root(self):
        assert jsonpath_extract({"a": 1}, "$") == {"a": 1}

    def test_simple_key(self):
        assert jsonpath_extract({"id": 42}, "$.id") == 42

    def test_nested_key(self):
        data = {"user": {"name": "Matt"}}
        assert jsonpath_extract(data, "$.user.name") == "Matt"

    def test_array_index(self):
        data = {"items": [10, 20, 30]}
        assert jsonpath_extract(data, "$.items[0]") == 10
        assert jsonpath_extract(data, "$.items[2]") == 30

    def test_nested_array(self):
        data = {"users": [{"name": "Alice"}, {"name": "Bob"}]}
        assert jsonpath_extract(data, "$.users[1].name") == "Bob"

    def test_missing_key_raises(self):
        with pytest.raises(KeyError):
            jsonpath_extract({"a": 1}, "$.b")

    def test_index_out_of_range_raises(self):
        with pytest.raises(IndexError):
            jsonpath_extract({"a": [1]}, "$.a[5]")

    def test_type_error_key_on_list(self):
        with pytest.raises(TypeError):
            jsonpath_extract([1, 2], "$.foo")

    def test_invalid_path_prefix(self):
        with pytest.raises(ValueError, match="must start with"):
            jsonpath_extract({}, "foo.bar")


# ──────────────────────────────────────────────
# Topological sort tests
# ──────────────────────────────────────────────


class TestTopologicalSort:
    def test_no_dependencies(self):
        reqs = [
            BatchRequest(method="GET", path="/a"),
            BatchRequest(method="GET", path="/b"),
            BatchRequest(method="GET", path="/c"),
        ]
        waves = topological_sort(reqs)
        # All in one wave
        assert len(waves) == 1
        assert sorted(waves[0]) == [0, 1, 2]

    def test_linear_chain(self):
        reqs = [
            BatchRequest(method="GET", path="/a", name="a"),
            BatchRequest(method="GET", path="/b", name="b", depends_on=["a"]),
            BatchRequest(method="GET", path="/c", name="c", depends_on=["b"]),
        ]
        waves = topological_sort(reqs)
        assert waves == [[0], [1], [2]]

    def test_diamond_dependency(self):
        reqs = [
            BatchRequest(method="GET", path="/a", name="a"),
            BatchRequest(method="GET", path="/b", name="b", depends_on=["a"]),
            BatchRequest(method="GET", path="/c", name="c", depends_on=["a"]),
            BatchRequest(method="GET", path="/d", name="d", depends_on=["b", "c"]),
        ]
        waves = topological_sort(reqs)
        assert waves[0] == [0]  # a
        assert sorted(waves[1]) == [1, 2]  # b, c in parallel
        assert waves[2] == [3]  # d

    def test_cycle_detected(self):
        reqs = [
            BatchRequest(method="GET", path="/a", name="a", depends_on=["b"]),
            BatchRequest(method="GET", path="/b", name="b", depends_on=["a"]),
        ]
        with pytest.raises(CyclicDependencyError):
            topological_sort(reqs)

    def test_missing_dependency(self):
        reqs = [
            BatchRequest(method="GET", path="/a", name="a", depends_on=["nonexistent"]),
        ]
        with pytest.raises(MissingDependencyError, match="nonexistent"):
            topological_sort(reqs)

    def test_mixed_named_and_unnamed(self):
        reqs = [
            BatchRequest(method="GET", path="/a", name="a"),
            BatchRequest(method="GET", path="/b"),  # unnamed, no deps
            BatchRequest(method="GET", path="/c", depends_on=["a"]),
        ]
        waves = topological_sort(reqs)
        assert 0 in waves[0]
        assert 1 in waves[0]  # unnamed runs in first wave
        assert 2 in waves[1]


# ──────────────────────────────────────────────
# Interpolation tests
# ──────────────────────────────────────────────


class TestInterpolation:
    def test_string_full_replacement_preserves_type(self):
        results = {"get_user": {"id": 42, "name": "Matt"}}
        val = interpolate_value("{result=get_user:$.id}", results)
        assert val == 42
        assert isinstance(val, int)

    def test_string_partial_replacement(self):
        results = {"get_user": {"id": 42}}
        val = interpolate_value("User ID: {result=get_user:$.id}", results)
        assert val == "User ID: 42"
        assert isinstance(val, str)

    def test_dict_interpolation(self):
        results = {"a": {"id": 1}}
        val = interpolate_value({"author_id": "{result=a:$.id}"}, results)
        assert val == {"author_id": 1}

    def test_list_interpolation(self):
        results = {"a": {"id": 1}}
        val = interpolate_value(["{result=a:$.id}", "static"], results)
        assert val == [1, "static"]

    def test_nested_dict_interpolation(self):
        results = {"a": {"user": {"id": 5}}}
        val = interpolate_value(
            {"data": {"user_id": "{result=a:$.user.id}"}}, results
        )
        assert val == {"data": {"user_id": 5}}

    def test_no_interpolation_passthrough(self):
        assert interpolate_value("plain string", {}) == "plain string"
        assert interpolate_value(42, {}) == 42
        assert interpolate_value(None, {}) is None

    def test_missing_result_raises(self):
        with pytest.raises(KeyError, match="no result"):
            interpolate_value("{result=missing:$.id}", {})

    def test_multiple_interpolations_in_string(self):
        results = {"a": {"first": "John"}, "b": {"last": "Doe"}}
        val = interpolate_value("{result=a:$.first} {result=b:$.last}", results)
        assert val == "John Doe"


# ──────────────────────────────────────────────
# BatchEndpoint tests
# ──────────────────────────────────────────────

pytestmark = pytest.mark.django_db


@pytest.fixture
def factory():
    return RequestFactory()


def _make_batch_request(factory: RequestFactory, payload: dict | list) -> HttpRequest:
    """Build a POST request with JSON body for the batch endpoint."""
    body = orjson.dumps(payload)
    request = factory.post("/batch", data=body, content_type="application/json")
    return request


class TestBatchEndpointValidation:
    @pytest.fixture
    def endpoint(self):
        from django_matt.api import MattAPI

        api = MattAPI(title="Test")
        from django_matt.batch.endpoint import BatchEndpoint

        return BatchEndpoint(api, max_requests=5)

    @pytest.mark.asyncio
    async def test_rejects_non_post(self, endpoint, factory):
        request = factory.get("/batch")
        resp = await endpoint.handle(request)
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self, endpoint, factory):
        request = factory.post("/batch", data=b"not json", content_type="application/json")
        resp = await endpoint.handle(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_empty_requests(self, endpoint, factory):
        request = _make_batch_request(factory, {"requests": []})
        resp = await endpoint.handle(request)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_too_many_requests(self, endpoint, factory):
        reqs = [{"method": "GET", "path": f"/item/{i}"} for i in range(10)]
        request = _make_batch_request(factory, {"requests": reqs})
        resp = await endpoint.handle(request)
        assert resp.status_code == 400
        body = orjson.loads(resp.content)
        assert "max 5" in body["detail"]

    @pytest.mark.asyncio
    async def test_rejects_cyclic_deps(self, endpoint, factory):
        request = _make_batch_request(
            factory,
            {
                "requests": [
                    {"method": "GET", "path": "/a", "name": "a", "depends_on": ["b"]},
                    {"method": "GET", "path": "/b", "name": "b", "depends_on": ["a"]},
                ]
            },
        )
        resp = await endpoint.handle(request)
        assert resp.status_code == 400
        body = orjson.loads(resp.content)
        assert "Cyclic" in body["detail"]

    @pytest.mark.asyncio
    async def test_accepts_bare_array(self, endpoint, factory):
        """Bare array [...] should be accepted as shorthand for {requests: [...]}."""
        with patch.object(endpoint, "_execute_waves", new_callable=AsyncMock):
            request = _make_batch_request(
                factory, [{"method": "GET", "path": "/foo"}]
            )
            resp = await endpoint.handle(request)
            # Should not fail validation
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dependencies_disabled(self, factory):
        from django_matt.api import MattAPI
        from django_matt.batch.endpoint import BatchEndpoint

        api = MattAPI(title="Test")
        ep = BatchEndpoint(api, allow_dependencies=False)
        request = _make_batch_request(
            factory,
            {
                "requests": [
                    {"method": "GET", "path": "/a", "name": "a"},
                    {"method": "GET", "path": "/b", "depends_on": ["a"]},
                ]
            },
        )
        resp = await ep.handle(request)
        assert resp.status_code == 400
        body = orjson.loads(resp.content)
        assert "disabled" in body["detail"]


class TestBatchEndpointExecution:
    """Integration-style tests that dispatch through Django's URL resolver."""

    @pytest.fixture
    def api_with_routes(self):
        from django_matt.api import MattAPI

        api = MattAPI(title="Test Batch")

        @api.get("/users/1")
        async def get_user(request):
            return {"id": 1, "name": "Matt"}

        @api.get("/users/2")
        async def get_user_2(request):
            return {"id": 2, "name": "Alice"}

        @api.post("/posts")
        async def create_post(request, body: dict = None):
            return {"id": 99, "author_id": body.get("author_id") if body else None}

        @api.get("/fail")
        async def fail_endpoint(request):
            raise ValueError("Intentional error")

        return api

    @pytest.fixture
    def batch_ep(self, api_with_routes):
        from django_matt.batch.endpoint import BatchEndpoint

        return BatchEndpoint(api_with_routes, max_requests=20)

    @pytest.mark.asyncio
    async def test_parallel_independent_requests(self, batch_ep, factory):
        """Independent requests should all succeed."""
        with self._patch_resolve(batch_ep):
            request = _make_batch_request(
                factory,
                [
                    {"method": "GET", "path": "/users/1"},
                    {"method": "GET", "path": "/users/2"},
                ],
            )
            resp = await batch_ep.handle(request)
            body = orjson.loads(resp.content)

        assert len(body) == 2
        assert body[0]["status"] == 200
        assert body[0]["body"]["name"] == "Matt"
        assert body[1]["status"] == 200
        assert body[1]["body"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_dependent_requests_with_interpolation(self, batch_ep, factory):
        """Dependent request should interpolate result from prior request."""
        with self._patch_resolve(batch_ep):
            request = _make_batch_request(
                factory,
                {
                    "requests": [
                        {"method": "GET", "path": "/users/1", "name": "get_user"},
                        {
                            "method": "POST",
                            "path": "/posts",
                            "body": {"author_id": "{result=get_user:$.id}"},
                            "depends_on": ["get_user"],
                        },
                    ]
                },
            )
            resp = await batch_ep.handle(request)
            body = orjson.loads(resp.content)

        assert body[0]["status"] == 200
        assert body[1]["status"] == 201
        assert body[1]["body"]["author_id"] == 1

    @pytest.mark.asyncio
    async def test_error_isolation(self, batch_ep, factory):
        """A failing request should not prevent others from returning."""
        with self._patch_resolve(batch_ep):
            request = _make_batch_request(
                factory,
                [
                    {"method": "GET", "path": "/users/1"},
                    {"method": "GET", "path": "/fail"},
                    {"method": "GET", "path": "/users/2"},
                ],
            )
            resp = await batch_ep.handle(request)
            body = orjson.loads(resp.content)

        assert body[0]["status"] == 200
        assert body[1]["status"] == 500
        assert body[1].get("error") is not None
        assert body[2]["status"] == 200

    @pytest.mark.asyncio
    async def test_named_response_included(self, batch_ep, factory):
        """Named requests should include name in response."""
        with self._patch_resolve(batch_ep):
            request = _make_batch_request(
                factory,
                [{"method": "GET", "path": "/users/1", "name": "get_user"}],
            )
            resp = await batch_ep.handle(request)
            body = orjson.loads(resp.content)

        assert body[0]["name"] == "get_user"

    @staticmethod
    def _patch_resolve(batch_ep):
        """Context manager that patches resolve() to route through the API's registered views."""
        from unittest.mock import MagicMock

        routes = {}
        for route in batch_ep.api.routes:
            routes[(route["methods"][0], route["path"])] = route

        class FakeResolveMatch:
            def __init__(self, func, kwargs=None):
                self.func = func
                self.kwargs = kwargs or {}

        def mock_resolve(path):
            # Try exact match first
            for (method_unused, route_path), route in routes.items():
                if route_path == path:
                    from django_matt.core.router import APIRouter

                    view = APIRouter._create_view_func(
                        endpoint=route["endpoint"],
                        response_model=route.get("response_model"),
                        status_code=route.get("status_code", 200),
                        methods=route.get("methods"),
                    )
                    return FakeResolveMatch(view)
            raise Exception(f"No route for {path}")

        return patch("django_matt.batch.endpoint.resolve", side_effect=mock_resolve)


class TestBatchEndpointRegistration:
    def test_register_batch_on_api(self):
        from django_matt.api import MattAPI
        from django_matt.batch import BatchEndpoint

        api = MattAPI(title="Test")
        batch = BatchEndpoint(api, path="/batch")
        api.register_batch(batch)

        assert len(api._batch_endpoints) == 1

    def test_batch_url_in_patterns(self):
        from django_matt.api import MattAPI
        from django_matt.batch import BatchEndpoint

        api = MattAPI(title="Test")
        batch = BatchEndpoint(api, path="/batch")
        api.register_batch(batch)

        urls = api.get_urls()
        batch_urls = [u for u in urls if hasattr(u, "name") and u.name == "batch-endpoint"]
        assert len(batch_urls) == 1
