from __future__ import annotations

import asyncio
import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from django_matt.rpc.auth import APIKeyAuth, BasicAuth, BearerAuth, CompositeAuth
from django_matt.rpc.cli import generate_rpc_client
from django_matt.rpc.client import RPCClient, TypedRPCClient
from django_matt.rpc.errors import (
    RPCAuthError,
    RPCConnectionError,
    RPCError,
    RPCNotFoundError,
    RPCTimeoutError,
    RPCValidationError,
    error_from_response,
)
from django_matt.rpc.generator import (
    generate_python_client,
    generate_typescript_client,
)
from django_matt.rpc.proxy import RPCProxy


# ---------------------------------------------------------------------------
# Test schemas
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str
    email: str


class UserSchema(BaseModel):
    id: int
    name: str
    email: str


class ItemSchema(BaseModel):
    id: int
    title: str
    price: float = 0.0


# ---------------------------------------------------------------------------
# Fake controller / API for introspection
# ---------------------------------------------------------------------------
class FakeController:
    prefix = "/users"

    def list_users(self) -> list[UserSchema]:
        ...

    def create_user(self, data: UserCreate) -> UserSchema:
        ...

    def get_user(self, pk: int) -> UserSchema:
        ...

    def delete_user(self, pk: int) -> None:
        ...


# Attach _route_info to simulate decorated methods
FakeController.list_users._route_info = {
    "path": "/",
    "methods": ["GET"],
    "response_model": UserSchema,
    "status_code": 200,
    "tags": [],
    "responses": {},
}
FakeController.create_user._route_info = {
    "path": "/",
    "methods": ["POST"],
    "response_model": UserSchema,
    "status_code": 201,
    "tags": [],
    "responses": {},
}
FakeController.get_user._route_info = {
    "path": "/<int:pk>/",
    "methods": ["GET"],
    "response_model": UserSchema,
    "status_code": 200,
    "tags": [],
    "responses": {},
}
FakeController.delete_user._route_info = {
    "path": "/<int:pk>/",
    "methods": ["DELETE"],
    "response_model": None,
    "status_code": 204,
    "tags": [],
    "responses": {},
}


class FakeAPI:
    routes = [
        {
            "name": "health",
            "path": "/health/",
            "methods": ["GET"],
            "endpoint": lambda request: {"status": "ok"},
            "response_model": None,
            "status_code": 200,
            "tags": [],
            "responses": {},
        }
    ]
    controllers = [FakeController]


# ===========================================================================
# Auth tests
# ===========================================================================
class TestBearerAuth:
    def test_apply(self):
        auth = BearerAuth("mytoken123")
        headers = auth.apply({})
        assert headers["Authorization"] == "Bearer mytoken123"

    def test_apply_preserves_existing(self):
        auth = BearerAuth("tok")
        headers = auth.apply({"X-Custom": "val"})
        assert headers["X-Custom"] == "val"
        assert headers["Authorization"] == "Bearer tok"


class TestAPIKeyAuth:
    def test_default_header(self):
        auth = APIKeyAuth("secret")
        headers = auth.apply({})
        assert headers["X-API-Key"] == "secret"

    def test_custom_header(self):
        auth = APIKeyAuth("secret", header="Authorization")
        headers = auth.apply({})
        assert headers["Authorization"] == "secret"


class TestBasicAuth:
    def test_apply(self):
        auth = BasicAuth("user", "pass")
        headers = auth.apply({})
        expected = base64.b64encode(b"user:pass").decode()
        assert headers["Authorization"] == f"Basic {expected}"


class TestCompositeAuth:
    def test_applies_all_strategies(self):
        auth = CompositeAuth(
            BearerAuth("tok"),
            APIKeyAuth("key", header="X-Key"),
        )
        headers = auth.apply({})
        # Last strategy wins for overlapping headers, but these don't overlap
        assert headers["Authorization"] == "Bearer tok"
        assert headers["X-Key"] == "key"


# ===========================================================================
# Error tests
# ===========================================================================
class TestRPCErrors:
    def test_base_error(self):
        e = RPCError("bad", status_code=400)
        assert e.message == "bad"
        assert e.status_code == 400
        assert "RPCError" in repr(e)

    def test_connection_error(self):
        e = RPCConnectionError()
        assert e.status_code == 503

    def test_validation_error(self):
        e = RPCValidationError(errors=[{"field": "name"}])
        assert e.status_code == 422
        assert len(e.errors) == 1

    def test_timeout_error(self):
        e = RPCTimeoutError()
        assert e.status_code == 504

    def test_auth_error(self):
        e = RPCAuthError()
        assert e.status_code == 401

    def test_not_found_error(self):
        e = RPCNotFoundError()
        assert e.status_code == 404

    def test_error_from_response_401(self):
        e = error_from_response(401, {"detail": "Invalid token"})
        assert isinstance(e, RPCAuthError)
        assert e.message == "Invalid token"

    def test_error_from_response_404(self):
        e = error_from_response(404)
        assert isinstance(e, RPCNotFoundError)

    def test_error_from_response_422(self):
        e = error_from_response(422, {"detail": "Bad data", "errors": [{"field": "x"}]})
        assert isinstance(e, RPCValidationError)
        assert len(e.errors) == 1

    def test_error_from_response_generic(self):
        e = error_from_response(500, {"detail": "Internal error"})
        assert isinstance(e, RPCError)
        assert e.status_code == 500


# ===========================================================================
# Client tests
# ===========================================================================
class TestRPCClient:
    def test_init(self):
        client = RPCClient("http://localhost:8000/api/")
        assert client.base_url == "http://localhost:8000/api"
        assert client.auth is None
        assert client.max_retries == 3

    def test_build_headers_no_auth(self):
        client = RPCClient("http://example.com")
        headers = client._build_headers()
        assert headers["Content-Type"] == "application/json"

    def test_build_headers_with_auth(self):
        client = RPCClient("http://example.com", auth=BearerAuth("tok"))
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer tok"

    def test_build_headers_extra(self):
        client = RPCClient("http://example.com")
        headers = client._build_headers({"X-Custom": "val"})
        assert headers["X-Custom"] == "val"

    def test_build_headers_default_headers(self):
        client = RPCClient("http://example.com", headers={"X-Tenant": "acme"})
        headers = client._build_headers()
        assert headers["X-Tenant"] == "acme"

    @pytest.mark.asyncio
    async def test_request_success(self):
        import orjson

        client = RPCClient("http://example.com")
        response_bytes = orjson.dumps({"id": 1, "name": "Alice", "email": "a@b.com"})
        client._do_request = AsyncMock(return_value=(200, response_bytes))

        result = await client.request("GET", "/users/1/", response_model=UserSchema)
        assert isinstance(result, UserSchema)
        assert result.id == 1
        assert result.name == "Alice"

    @pytest.mark.asyncio
    async def test_request_list_response(self):
        import orjson

        client = RPCClient("http://example.com")
        response_bytes = orjson.dumps([
            {"id": 1, "name": "Alice", "email": "a@b.com"},
            {"id": 2, "name": "Bob", "email": "b@b.com"},
        ])
        client._do_request = AsyncMock(return_value=(200, response_bytes))

        result = await client.request("GET", "/users/", response_model=UserSchema)
        assert len(result) == 2
        assert all(isinstance(u, UserSchema) for u in result)

    @pytest.mark.asyncio
    async def test_request_error_response(self):
        import orjson

        client = RPCClient("http://example.com")
        error_body = orjson.dumps({"detail": "Not found"})
        client._do_request = AsyncMock(return_value=(404, error_body))

        with pytest.raises(RPCNotFoundError):
            await client.request("GET", "/users/999/")

    @pytest.mark.asyncio
    async def test_request_no_content(self):
        client = RPCClient("http://example.com")
        client._do_request = AsyncMock(return_value=(204, b""))

        result = await client.request("DELETE", "/users/1/")
        assert result is None

    @pytest.mark.asyncio
    async def test_request_with_pydantic_body(self):
        import orjson

        client = RPCClient("http://example.com")
        response_bytes = orjson.dumps({"id": 1, "name": "New", "email": "n@b.com"})
        client._do_request = AsyncMock(return_value=(201, response_bytes))

        data = UserCreate(name="New", email="n@b.com")
        result = await client.request("POST", "/users/", data=data, response_model=UserSchema)
        assert isinstance(result, UserSchema)

        # Verify body was serialized
        call_args = client._do_request.call_args
        assert call_args[1]["body"] is not None

    @pytest.mark.asyncio
    async def test_request_with_dict_body(self):
        import orjson

        client = RPCClient("http://example.com")
        client._do_request = AsyncMock(return_value=(200, orjson.dumps({"ok": True})))

        result = await client.request("POST", "/action/", data={"key": "val"})
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        import orjson

        client = RPCClient("http://example.com", retry_backoff=0.01)
        success = (200, orjson.dumps({"ok": True}))
        client._do_request = AsyncMock(
            side_effect=[RPCConnectionError("fail"), success]
        )

        result = await client.request("GET", "/health/")
        assert result == {"ok": True}
        assert client._do_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        client = RPCClient("http://example.com", max_retries=2, retry_backoff=0.01)
        client._do_request = AsyncMock(
            side_effect=RPCConnectionError("fail")
        )

        with pytest.raises(RPCConnectionError):
            await client.request("GET", "/health/")
        assert client._do_request.call_count == 2

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with RPCClient("http://example.com") as client:
            assert client.base_url == "http://example.com"

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        client = RPCClient("http://example.com")
        await client.close()
        await client.close()  # no error


# ===========================================================================
# TypedRPCClient tests
# ===========================================================================
class TestTypedRPCClient:
    def test_builds_route_map(self):
        client = TypedRPCClient("http://example.com", api=FakeAPI())
        methods = client.get_available_methods()
        assert "list_users" in methods
        assert "create_user" in methods
        assert "health" in methods

    def test_resolve_method_by_name(self):
        client = TypedRPCClient("http://example.com", api=FakeAPI())
        route = client._resolve_method("list_users")
        assert route is not None
        assert route["methods"] == ["GET"]
        assert route["path"] == "/users/"

    def test_resolve_method_qualified(self):
        client = TypedRPCClient("http://example.com", api=FakeAPI())
        route = client._resolve_method("FakeController.create_user")
        assert route is not None
        assert route["methods"] == ["POST"]

    def test_resolve_unknown_returns_none(self):
        client = TypedRPCClient("http://example.com", api=FakeAPI())
        assert client._resolve_method("nonexistent") is None

    @pytest.mark.asyncio
    async def test_call_method(self):
        import orjson

        client = TypedRPCClient("http://example.com", api=FakeAPI())
        response_bytes = orjson.dumps([{"id": 1, "name": "A", "email": "a@b.com"}])
        client._do_request = AsyncMock(return_value=(200, response_bytes))

        result = await client.call("list_users", response_model=UserSchema)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_call_unknown_method(self):
        client = TypedRPCClient("http://example.com", api=FakeAPI())
        with pytest.raises(RPCError, match="Unknown method"):
            await client.call("nonexistent")


# ===========================================================================
# RPCProxy tests
# ===========================================================================
class TestRPCProxy:
    def test_builds_namespaces(self):
        proxy = RPCProxy(FakeAPI(), base_url="http://example.com")
        assert hasattr(proxy, "client")

    def test_namespace_access(self):
        proxy = RPCProxy(FakeAPI(), base_url="http://example.com")
        ns = proxy.users
        assert repr(ns).startswith("<RPCNamespace")

    def test_endpoint_access(self):
        proxy = RPCProxy(FakeAPI(), base_url="http://example.com")
        # users.list_users should resolve to an endpoint caller
        caller = proxy.users.list_users
        assert callable(caller)

    @pytest.mark.asyncio
    async def test_endpoint_call(self):
        import orjson

        proxy = RPCProxy(FakeAPI(), base_url="http://example.com")
        response_bytes = orjson.dumps([{"id": 1, "name": "A", "email": "a@b.com"}])
        proxy.client._do_request = AsyncMock(return_value=(200, response_bytes))

        result = await proxy.users.list_users()
        assert isinstance(result, list)
        assert result[0].id == 1

    @pytest.mark.asyncio
    async def test_endpoint_with_path_params(self):
        import orjson

        proxy = RPCProxy(FakeAPI(), base_url="http://example.com")
        response_bytes = orjson.dumps({"id": 5, "name": "A", "email": "a@b.com"})
        proxy.client._do_request = AsyncMock(return_value=(200, response_bytes))

        result = await proxy.users.get_user(pk="5")
        assert result.id == 5

    def test_unknown_namespace_raises(self):
        proxy = RPCProxy(FakeAPI(), base_url="http://example.com")
        with pytest.raises(AttributeError):
            _ = proxy.nonexistent.something

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with RPCProxy(FakeAPI(), base_url="http://example.com") as proxy:
            assert proxy.client is not None


# ===========================================================================
# Generator tests
# ===========================================================================
class TestPythonGenerator:
    def test_generates_class(self):
        code = generate_python_client(FakeAPI())
        assert "class GeneratedClient:" in code
        assert "async def list_users" in code
        assert "async def create_user" in code
        assert "async def close" in code

    def test_custom_class_name(self):
        code = generate_python_client(FakeAPI(), class_name="MyClient")
        assert "class MyClient:" in code

    def test_includes_health_route(self):
        code = generate_python_client(FakeAPI())
        assert "async def health" in code

    def test_includes_method_types(self):
        code = generate_python_client(FakeAPI())
        assert '"GET"' in code
        assert '"POST"' in code

    def test_generates_valid_python(self):
        code = generate_python_client(FakeAPI())
        compile(code, "<test>", "exec")  # should not raise


class TestTypescriptGenerator:
    def test_generates_class(self):
        code = generate_typescript_client(FakeAPI())
        assert "export class APIClient" in code
        assert "async listUsers" in code
        assert "async createUser" in code

    def test_custom_class_name(self):
        code = generate_typescript_client(FakeAPI(), class_name="MyAPI")
        assert "export class MyAPI" in code

    def test_generates_interfaces(self):
        code = generate_typescript_client(FakeAPI())
        assert "export interface UserSchema" in code

    def test_includes_fetch_helper(self):
        code = generate_typescript_client(FakeAPI())
        assert "private async request" in code

    def test_includes_health(self):
        code = generate_typescript_client(FakeAPI())
        assert "async health" in code


# ===========================================================================
# CLI helper tests
# ===========================================================================
class TestCLI:
    def test_generate_python(self):
        code = generate_rpc_client(FakeAPI(), lang="python")
        assert "class GeneratedClient:" in code

    def test_generate_typescript(self):
        code = generate_rpc_client(FakeAPI(), lang="typescript")
        assert "export class APIClient" in code

    def test_generate_ts_alias(self):
        code = generate_rpc_client(FakeAPI(), lang="ts")
        assert "export class APIClient" in code

    def test_unsupported_language(self):
        with pytest.raises(ValueError, match="Unsupported language"):
            generate_rpc_client(FakeAPI(), lang="ruby")

    def test_custom_class_name(self):
        code = generate_rpc_client(FakeAPI(), lang="python", class_name="Foo")
        assert "class Foo:" in code

    def test_write_to_file(self, tmp_path):
        output = tmp_path / "client.py"
        code = generate_rpc_client(FakeAPI(), lang="python", output=str(output))
        assert output.exists()
        assert output.read_text() == code
