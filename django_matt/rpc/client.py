"""Async RPC client with retry, auth, and typed response deserialization."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypeVar

import orjson
from pydantic import BaseModel

from django_matt.rpc.auth import AuthStrategy
from django_matt.rpc.errors import (
    RPCConnectionError,
    RPCError,
    RPCTimeoutError,
    error_from_response,
)

logger = logging.getLogger("django_matt.rpc")

T = TypeVar("T")

try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    httpx = None  # type: ignore[assignment]
    _HAS_HTTPX = False

try:
    import aiohttp

    _HAS_AIOHTTP = True
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    _HAS_AIOHTTP = False


class RPCClient:
    """Async HTTP client with retry logic and pluggable auth strategies."""

    def __init__(
        self,
        base_url: str,
        auth: AuthStrategy | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._default_headers = headers or {}
        self._httpx_client: Any | None = None
        self._aiohttp_session: Any | None = None

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self._default_headers,
        }
        if extra:
            headers.update(extra)
        if self.auth:
            headers = self.auth.apply(headers)
        return headers

    async def _get_httpx_client(self) -> Any:
        if not _HAS_HTTPX:
            raise ImportError("httpx is required: uv add httpx")
        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._httpx_client

    async def _get_aiohttp_session(self) -> Any:
        if not _HAS_AIOHTTP:
            raise ImportError("aiohttp is required: uv add aiohttp")
        if self._aiohttp_session is None:
            import aiohttp as aio

            self._aiohttp_session = aio.ClientSession(
                base_url=self.base_url,
                timeout=aio.ClientTimeout(total=self.timeout),
            )
        return self._aiohttp_session

    async def request(
        self,
        method: str,
        path: str,
        *,
        data: BaseModel | dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        """Send an HTTP request with automatic retry and optional response model parsing."""
        merged_headers = self._build_headers(headers)
        body: bytes | None = None
        if data is not None:
            if isinstance(data, BaseModel):
                body = orjson.dumps(data.model_dump(mode="json"))
            else:
                body = orjson.dumps(data)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                status, response_body = await self._do_request(
                    method, path, body=body, params=params, headers=merged_headers
                )
                break
            except (RPCConnectionError, RPCTimeoutError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_backoff * (2**attempt)
                    logger.warning(
                        f"RPC retry {attempt + 1}/{self.max_retries} after {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                continue
        else:
            raise last_error  # type: ignore[misc]

        if status >= 400:
            try:
                error_body = orjson.loads(response_body) if response_body else {}
            except (orjson.JSONDecodeError, ValueError):
                error_body = {
                    "detail": response_body.decode("utf-8", errors="replace")
                    if response_body
                    else ""
                }
            raise error_from_response(status, error_body)

        if not response_body:
            return None

        parsed = orjson.loads(response_body)
        if response_model is not None:
            if isinstance(parsed, list):
                return [response_model.model_validate(item) for item in parsed]
            return response_model.model_validate(parsed)
        return parsed

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        params: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        if _HAS_HTTPX:
            return await self._do_httpx(method, path, body=body, params=params, headers=headers)
        if _HAS_AIOHTTP:
            return await self._do_aiohttp(method, path, body=body, params=params, headers=headers)
        raise ImportError("Install httpx or aiohttp: uv add httpx")

    async def _do_httpx(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        params: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        client = await self._get_httpx_client()
        try:
            resp = await client.request(method, path, content=body, params=params, headers=headers)
            return resp.status_code, resp.content
        except httpx.ConnectError as e:
            raise RPCConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise RPCTimeoutError(str(e)) from e

    async def _do_aiohttp(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        params: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> tuple[int, bytes]:
        session = await self._get_aiohttp_session()
        try:
            async with session.request(
                method, path, data=body, params=params, headers=headers
            ) as resp:
                content = await resp.read()
                return resp.status, content
        except Exception as e:
            if "connect" in str(e).lower() or "resolve" in str(e).lower():
                raise RPCConnectionError(str(e)) from e
            if "timeout" in str(e).lower():
                raise RPCTimeoutError(str(e)) from e
            raise RPCConnectionError(str(e)) from e

    async def call(
        self,
        method_name: str,
        response_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Call a named RPC method, resolving it to an HTTP request."""
        route = self._resolve_method(method_name)
        if route is None:
            raise RPCError(f"Unknown method: {method_name}", status_code=404)
        http_method = route["methods"][0]
        path = route["path"]
        data = kwargs if http_method in ("POST", "PUT", "PATCH") else None
        params = kwargs if http_method == "GET" else None
        return await self.request(
            http_method, path, data=data, params=params, response_model=response_model
        )

    def _resolve_method(self, method_name: str) -> dict[str, Any] | None:
        return None

    async def close(self) -> None:
        """Close underlying HTTP client connections."""
        if self._httpx_client is not None:
            await self._httpx_client.aclose()
            self._httpx_client = None
        if self._aiohttp_session is not None:
            await self._aiohttp_session.close()
            self._aiohttp_session = None

    async def __aenter__(self) -> RPCClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class TypedRPCClient(RPCClient):
    """RPC client that builds a route map from an API instance for typed method calls."""

    def __init__(
        self,
        base_url: str,
        api: Any,
        auth: AuthStrategy | None = None,
        **kwargs: Any,
    ):
        super().__init__(base_url, auth=auth, **kwargs)
        self._routes: dict[str, dict[str, Any]] = {}
        self._build_route_map(api)

    def _build_route_map(self, api: Any) -> None:
        for route in getattr(api, "routes", []):
            name = route.get("name", "")
            self._routes[name] = route

        for controller_cls in getattr(api, "controllers", []):
            prefix = getattr(controller_cls, "prefix", "")
            for attr_name in dir(controller_cls):
                if attr_name.startswith("_"):
                    continue
                method = getattr(controller_cls, attr_name, None)
                if method is None or not callable(method):
                    continue
                route_info = getattr(method, "_route_info", None)
                if route_info is None:
                    continue
                full_path = prefix + route_info["path"]
                qualified_name = f"{controller_cls.__name__}.{attr_name}"
                self._routes[qualified_name] = {
                    **route_info,
                    "path": full_path,
                    "endpoint": method,
                }
                self._routes[attr_name] = self._routes[qualified_name]

    def _resolve_method(self, method_name: str) -> dict[str, Any] | None:
        return self._routes.get(method_name)

    def get_available_methods(self) -> list[str]:
        """Return sorted list of all available RPC method names."""
        return sorted(self._routes.keys())
