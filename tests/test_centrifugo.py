"""
Tests for the Centrifugo WebSocket backend.

Covers:
- CentrifugoConfig dataclass and from_settings()
- get_centrifugo_config() singleton
- generate_connection_token() / generate_subscription_token()
- CentrifugoClient API calls (mocked httpx)
- CentrifugoAPIError
- Proxy views: connect, subscribe, publish, rpc
- get_centrifugo_urls() URL patterns
- WebSocketConfig.backend field
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

httpx = pytest.importorskip("httpx")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestCentrifugoConfig:
    def test_defaults(self):
        from django_matt.websockets.centrifugo.config import CentrifugoConfig

        cfg = CentrifugoConfig()
        assert cfg.api_url == "http://localhost:8000/api"
        assert cfg.api_key == ""
        assert cfg.secret == ""
        assert cfg.ws_url == "ws://localhost:8001/connection/websocket"
        assert cfg.token_expire == 3600
        assert cfg.proxy_connect_path == "connect/"
        assert cfg.proxy_subscribe_path == "subscribe/"
        assert cfg.proxy_publish_path == "publish/"
        assert cfg.proxy_rpc_path == "rpc/"

    def test_from_settings(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {
            "API_URL": "http://centrifugo:8000/api",
            "API_KEY": "testkey",
            "SECRET": "mysecret",
            "WS_URL": "ws://centrifugo:8001/connection/websocket",
            "TOKEN_EXPIRE": 7200,
            "PROXY_CONNECT_PATH": "/centrifugo/connect/",
        }
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None  # reset singleton
        cfg = cfg_module.CentrifugoConfig.from_settings()

        assert cfg.api_url == "http://centrifugo:8000/api"
        assert cfg.api_key == "testkey"
        assert cfg.secret == "mysecret"
        assert cfg.token_expire == 7200
        assert cfg.proxy_connect_path == "centrifugo/connect/"  # leading slash stripped

    def test_singleton(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {"SECRET": "singleton-secret"}
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None
        a = cfg_module.get_centrifugo_config()
        b = cfg_module.get_centrifugo_config()
        assert a is b

    def teardown_method(self):
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class TestCentrifugoTokens:
    def setup_method(self):
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None

    def teardown_method(self):
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None

    def test_connection_token(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {"SECRET": "test-secret"}
        from django_matt.auth.jwt_builtin import decode_jwt
        from django_matt.websockets.centrifugo.tokens import generate_connection_token

        token = generate_connection_token("user-42", expire_in=600)
        payload = decode_jwt(token, secret="test-secret")
        assert payload["sub"] == "user-42"
        assert "exp" in payload

    def test_connection_token_with_info(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {"SECRET": "test-secret"}
        from django_matt.auth.jwt_builtin import decode_jwt
        from django_matt.websockets.centrifugo.tokens import generate_connection_token

        token = generate_connection_token("user-1", info={"role": "admin"})
        payload = decode_jwt(token, secret="test-secret")
        assert payload["info"] == {"role": "admin"}

    def test_subscription_token(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {"SECRET": "test-secret"}
        from django_matt.auth.jwt_builtin import decode_jwt
        from django_matt.websockets.centrifugo.tokens import generate_subscription_token

        token = generate_subscription_token("user-7", "private:room-1")
        payload = decode_jwt(token, secret="test-secret")
        assert payload["sub"] == "user-7"
        assert payload["channel"] == "private:room-1"

    def test_token_uses_config_expire(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {"SECRET": "s", "TOKEN_EXPIRE": 300}
        import time

        from django_matt.auth.jwt_builtin import decode_jwt
        from django_matt.websockets.centrifugo.tokens import generate_connection_token

        before = int(time.time())
        token = generate_connection_token("u")
        payload = decode_jwt(token, secret="s")
        exp = payload["exp"]
        assert before + 280 <= exp <= before + 320


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class TestCentrifugoClient:
    def setup_method(self):
        from django_matt.websockets.centrifugo import client as client_module
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None
        client_module._client = None

    def teardown_method(self):
        from django_matt.websockets.centrifugo import client as client_module
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None
        client_module._client = None

    def _make_response(self, result: dict) -> MagicMock:
        resp = MagicMock()
        resp.content = __import__("orjson").dumps({"result": result})
        resp.raise_for_status = MagicMock()
        return resp

    def _make_error_response(self, code: int, message: str) -> MagicMock:
        resp = MagicMock()
        resp.content = __import__("orjson").dumps({"error": {"code": code, "message": message}})
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_publish(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {
            "API_URL": "http://centrifugo/api",
            "API_KEY": "key",
            "SECRET": "s",
        }
        from django_matt.websockets.centrifugo.client import CentrifugoClient

        client = CentrifugoClient()
        resp = self._make_response({"offset": 1})

        with patch.object(
            client._get_http(),
            "post",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await client.publish("chat:room-1", {"text": "hello"})
        assert result == {"offset": 1}

    @pytest.mark.asyncio
    async def test_broadcast(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {
            "API_URL": "http://centrifugo/api",
            "API_KEY": "key",
            "SECRET": "s",
        }
        from django_matt.websockets.centrifugo.client import CentrifugoClient

        client = CentrifugoClient()
        resp = self._make_response({})

        with patch.object(
            client._get_http(),
            "post",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await client.broadcast(["ch1", "ch2"], {"msg": "hi"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_api_error_raised(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {
            "API_URL": "http://centrifugo/api",
            "API_KEY": "key",
            "SECRET": "s",
        }
        from django_matt.websockets.centrifugo.client import (
            CentrifugoAPIError,
            CentrifugoClient,
        )

        client = CentrifugoClient()
        resp = self._make_error_response(102, "channel not found")

        with (
            patch.object(
                client._get_http(),
                "post",
                new_callable=AsyncMock,
                return_value=resp,
            ),
            pytest.raises(CentrifugoAPIError) as exc_info,
        ):
            await client.presence("nonexistent")

        assert exc_info.value.code == 102
        assert "channel not found" in exc_info.value.message

    def test_singleton(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {"SECRET": "s", "API_KEY": "k"}
        from django_matt.websockets.centrifugo.client import get_centrifugo_client

        a = get_centrifugo_client()
        b = get_centrifugo_client()
        assert a is b

    @pytest.mark.asyncio
    async def test_info(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {
            "API_URL": "http://centrifugo/api",
            "API_KEY": "key",
            "SECRET": "s",
        }
        from django_matt.websockets.centrifugo.client import CentrifugoClient

        client = CentrifugoClient()
        resp = self._make_response({"nodes": []})

        with patch.object(
            client._get_http(),
            "post",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await client.info()
        assert result == {"nodes": []}

    @pytest.mark.asyncio
    async def test_history_with_limit(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {
            "API_URL": "http://centrifugo/api",
            "API_KEY": "key",
            "SECRET": "s",
        }
        import orjson

        from django_matt.websockets.centrifugo.client import CentrifugoClient

        client = CentrifugoClient()
        resp = self._make_response({"publications": []})
        post_mock = AsyncMock(return_value=resp)

        with patch.object(client._get_http(), "post", post_mock):
            await client.history("chat:1", limit=50)

        # Verify limit was included in params
        call_args = post_mock.call_args
        body = orjson.loads(call_args.kwargs.get("content") or call_args.args[1])
        assert body["params"]["limit"] == 50


# ---------------------------------------------------------------------------
# Proxy Views
# ---------------------------------------------------------------------------


class TestCentrifugoProxyViews:
    def _make_request(self, body: dict) -> MagicMock:
        import orjson

        req = MagicMock()
        req.body = orjson.dumps(body)
        return req

    @pytest.mark.asyncio
    async def test_connect_proxy_default(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoConnectProxy

        view = CentrifugoConnectProxy()
        req = self._make_request({"user": "42", "token": "abc"})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert "result" in data

    @pytest.mark.asyncio
    async def test_connect_proxy_custom(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoConnectProxy

        class MyProxy(CentrifugoConnectProxy):
            async def on_connect(self, data: dict) -> dict:
                return {"user": data.get("user", ""), "channels": ["#personal"]}

        view = MyProxy()
        req = self._make_request({"user": "99"})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert data["result"]["user"] == "99"
        assert "#personal" in data["result"]["channels"]

    @pytest.mark.asyncio
    async def test_subscribe_proxy_allow(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoSubscribeProxy

        view = CentrifugoSubscribeProxy()
        req = self._make_request({"channel": "news", "user": "1"})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert "result" in data

    @pytest.mark.asyncio
    async def test_subscribe_proxy_deny(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoSubscribeProxy

        class DenyProxy(CentrifugoSubscribeProxy):
            async def on_subscribe(self, channel: str, data: dict) -> dict:
                raise PermissionError("not allowed")

        view = DenyProxy()
        req = self._make_request({"channel": "private:secret"})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert data["error"]["code"] == 403

    @pytest.mark.asyncio
    async def test_publish_proxy_default(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoPublishProxy

        view = CentrifugoPublishProxy()
        req = self._make_request({"channel": "chat:1", "data": {"msg": "hi"}})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert "result" in data

    @pytest.mark.asyncio
    async def test_rpc_proxy_default(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoRPCProxy

        view = CentrifugoRPCProxy()
        req = self._make_request({"method": "ping", "data": {}})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert "result" in data

    @pytest.mark.asyncio
    async def test_rpc_proxy_custom(self):
        from django_matt.websockets.centrifugo.proxy import CentrifugoRPCProxy

        class PingProxy(CentrifugoRPCProxy):
            async def on_rpc(self, method: str, data: dict, raw: dict) -> dict:
                if method == "ping":
                    return {"result": {"pong": True}}
                raise ValueError(f"unknown method: {method}")

        view = PingProxy()
        req = self._make_request({"method": "ping", "data": {}})
        resp = await view.post(req)
        import orjson

        data = orjson.loads(resp.content)
        assert data["result"]["result"]["pong"] is True

    def test_get_centrifugo_urls(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {}
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None
        from django_matt.websockets.centrifugo.proxy import get_centrifugo_urls

        patterns = get_centrifugo_urls()
        assert len(patterns) == 4
        names = {p.name for p in patterns}
        assert names == {
            "centrifugo_connect",
            "centrifugo_subscribe",
            "centrifugo_publish",
            "centrifugo_rpc",
        }
        cfg_module._config = None

    def test_get_centrifugo_urls_custom_views(self, settings):
        settings.DJANGO_MATT_CENTRIFUGO = {}
        from django_matt.websockets.centrifugo import config as cfg_module

        cfg_module._config = None
        from django_matt.websockets.centrifugo.proxy import (
            CentrifugoConnectProxy,
            get_centrifugo_urls,
        )

        class MyConnect(CentrifugoConnectProxy):
            pass

        patterns = get_centrifugo_urls(connect_view=MyConnect)
        connect_pattern = next(p for p in patterns if p.name == "centrifugo_connect")
        assert connect_pattern.callback.view_class is MyConnect
        cfg_module._config = None


# ---------------------------------------------------------------------------
# WebSocketConfig.backend field
# ---------------------------------------------------------------------------


class TestWebSocketConfigBackend:
    def test_default_backend_is_centrifugo(self):
        from django_matt.websockets.config import WebSocketConfig

        cfg = WebSocketConfig()
        assert cfg.backend == "centrifugo"

    def test_backend_from_settings(self, settings):
        settings.DJANGO_MATT_WEBSOCKETS = {"BACKEND": "channels"}
        # Reset singleton
        import django_matt.websockets.config as ws_cfg
        from django_matt.websockets.config import WebSocketConfig, _websocket_config

        ws_cfg._websocket_config = None
        cfg = WebSocketConfig.from_settings()
        assert cfg.backend == "channels"
        ws_cfg._websocket_config = None

    def test_channels_backend_valid(self):
        from django_matt.websockets.config import WebSocketConfig

        cfg = WebSocketConfig(backend="channels")
        assert cfg.backend == "channels"
