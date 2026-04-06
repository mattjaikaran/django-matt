from __future__ import annotations

import re
from typing import Any

from django_matt.rpc.auth import AuthStrategy
from django_matt.rpc.client import RPCClient


class _Namespace:
    def __init__(self, client: RPCClient, prefix: str, routes: dict[str, dict[str, Any]]):
        self._client = client
        self._prefix = prefix
        self._routes = routes

    def __getattr__(self, name: str) -> Any:
        matching: dict[str, dict[str, Any]] = {}
        sub_prefix = f"{self._prefix}.{name}" if self._prefix else name
        for key, route in self._routes.items():
            if key == sub_prefix:
                return _EndpointCaller(self._client, route)
            if key.startswith(f"{sub_prefix}."):
                matching[key] = route
        if matching:
            return _Namespace(self._client, sub_prefix, self._routes)
        raise AttributeError(f"No endpoint or namespace: {sub_prefix}")

    def __repr__(self) -> str:
        return f"<RPCNamespace prefix={self._prefix!r}>"


class _EndpointCaller:
    def __init__(self, client: RPCClient, route: dict[str, Any]):
        self._client = client
        self._route = route

    async def __call__(self, **kwargs: Any) -> Any:
        http_method = self._route["methods"][0]
        path = self._route["path"]
        response_model = self._route.get("response_model")

        # Substitute path params
        for key in list(kwargs.keys()):
            placeholder = f"<{key}>"
            django_placeholder = f"{{{key}}}"
            if placeholder in path:
                path = path.replace(placeholder, str(kwargs.pop(key)))
            elif django_placeholder in path:
                path = path.replace(django_placeholder, str(kwargs.pop(key)))

        # Also handle Django-style <type:name> patterns
        path = re.sub(r"<\w+:(\w+)>", lambda m: str(kwargs.pop(m.group(1), m.group(0))), path)

        data = kwargs if http_method in ("POST", "PUT", "PATCH") and kwargs else None
        params = kwargs if http_method == "GET" and kwargs else None

        return await self._client.request(
            http_method, path, data=data, params=params, response_model=response_model
        )


class RPCProxy:
    def __init__(
        self,
        api: Any,
        base_url: str = "http://localhost:8000",
        auth: AuthStrategy | None = None,
        **client_kwargs: Any,
    ):
        self._client = RPCClient(base_url, auth=auth, **client_kwargs)
        self._routes: dict[str, dict[str, Any]] = {}
        self._build_routes(api)

    def _build_routes(self, api: Any) -> None:
        for route in getattr(api, "routes", []):
            name = route.get("name", "")
            self._routes[name] = route

        for controller_cls in getattr(api, "controllers", []):
            prefix_name = getattr(controller_cls, "prefix", "").strip("/").replace("/", ".")
            if not prefix_name:
                prefix_name = controller_cls.__name__.lower().replace("controller", "")

            for attr_name in dir(controller_cls):
                if attr_name.startswith("_"):
                    continue
                method = getattr(controller_cls, attr_name, None)
                if method is None or not callable(method):
                    continue
                route_info = getattr(method, "_route_info", None)
                if route_info is None:
                    continue

                full_path = getattr(controller_cls, "prefix", "") + route_info["path"]
                qualified = f"{prefix_name}.{attr_name}"
                self._routes[qualified] = {
                    **route_info,
                    "path": full_path,
                }

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return _Namespace(self._client, name, self._routes)

    @property
    def client(self) -> RPCClient:
        return self._client

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> RPCProxy:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
