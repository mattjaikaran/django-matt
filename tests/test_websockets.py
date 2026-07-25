"""
Tests for the Django Matt websockets module.

Tests cover:
- ConnectionState dataclass
- WebSocket error classes (WebSocketError, AuthenticationError, RateLimitError, ValidationError)
- WebSocketConfig and RateLimitConfig dataclasses
- Config loading from settings
- BaseMessage and all schema subclasses
- BaseConsumer (mock ASGI scope) - lifecycle, rate limiting, groups, messaging
- JsonConsumer, AuthenticatedConsumer, RoomConsumer
- Auth middleware classes
- Routing (WebSocketRouter, WebSocketRoute, websocket_route decorator, collect_routes)
- Groups/Presence (PresenceManager, PresenceInfo)
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth.models import AnonymousUser

import pytest

from django_matt.websockets.auth import (
    AuthMiddlewareBase,
    CombinedAuthMiddleware,
    JWTAuthMiddleware,
    SessionAuthMiddleware,
    TokenAuthMiddleware,
)
from django_matt.websockets.config import (
    RateLimitConfig,
    WebSocketConfig,
    get_websocket_config,
)
from django_matt.websockets.consumers import (
    AuthenticatedConsumer,
    AuthenticationError,
    BaseConsumer,
    ConnectionState,
    JsonConsumer,
    RateLimitError,
    RoomConsumer,
    ValidationError,
    WebSocketError,
)
from django_matt.websockets.groups import PresenceInfo, PresenceManager
from django_matt.websockets.routing import (
    WebSocketRoute,
    WebSocketRouter,
    collect_routes,
    websocket_route,
)
from django_matt.websockets.schemas import (
    AckMessage,
    AuthenticatedMessage,
    BaseMessage,
    ChatJoinMessage,
    ChatLeaveMessage,
    ChatMessage,
    ConnectedMessage,
    DataMessage,
    DisconnectedMessage,
    ErrorMessage,
    EventMessage,
    JoinRoomRequest,
    LeaveRoomRequest,
    NotificationMessage,
    PingMessage,
    PongMessage,
    PresenceListMessage,
    PresenceMessage,
    PublishMessage,
    RequestMessage,
    ResponseMessage,
    RoomJoinedMessage,
    RoomLeftMessage,
    RoomUsersMessage,
    SubscribedMessage,
    SubscribeMessage,
    TypingMessage,
    UnsubscribedMessage,
    UnsubscribeMessage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scope(**overrides):
    scope = {
        "type": "websocket",
        "path": "/ws/test/",
        "query_string": b"",
        "headers": [],
        "user": AnonymousUser(),
        "channel_name": "test.channel.1",
        "channel_layer": None,
    }
    scope.update(overrides)
    return scope


def _make_consumer(cls=BaseConsumer, scope_overrides=None):
    scope = _make_scope(**(scope_overrides or {}))
    receive = AsyncMock()
    send = AsyncMock()
    consumer = cls(scope, receive, send)
    return consumer, send, receive


# ===========================================================================
# ConnectionState
# ===========================================================================


class TestConnectionState:
    def test_defaults(self):
        state = ConnectionState()
        assert state.connected_at == 0
        assert state.last_message_at == 0
        assert state.message_count == 0
        assert state.groups == set()
        assert state.metadata == {}

    def test_groups_mutable(self):
        state = ConnectionState()
        state.groups.add("room_1")
        assert "room_1" in state.groups

    def test_metadata_mutable(self):
        state = ConnectionState()
        state.metadata["key"] = "value"
        assert state.metadata["key"] == "value"

    def test_separate_instances_independent(self):
        a = ConnectionState()
        b = ConnectionState()
        a.groups.add("x")
        assert "x" not in b.groups


# ===========================================================================
# Error classes
# ===========================================================================


class TestWebSocketErrors:
    def test_websocket_error(self):
        err = WebSocketError(4000, "boom")
        assert err.code == 4000
        assert err.message == "boom"
        assert err.data == {}

    def test_websocket_error_with_data(self):
        err = WebSocketError(4000, "err", {"field": "bad"})
        assert err.data == {"field": "bad"}

    def test_authentication_error_defaults(self):
        err = AuthenticationError()
        assert err.code == 4001
        assert "Authentication" in err.message

    def test_authentication_error_custom(self):
        err = AuthenticationError("Token expired")
        assert err.message == "Token expired"

    def test_rate_limit_error_defaults(self):
        err = RateLimitError()
        assert err.code == 4002

    def test_validation_error(self):
        err = ValidationError("Invalid JSON", {"detail": "missing field"})
        assert err.code == 4003
        assert err.data["detail"] == "missing field"

    def test_errors_are_exceptions(self):
        with pytest.raises(WebSocketError):
            raise WebSocketError(5000, "test")
        with pytest.raises(AuthenticationError):
            raise AuthenticationError()
        with pytest.raises(RateLimitError):
            raise RateLimitError()


# ===========================================================================
# Config
# ===========================================================================


class TestWebSocketConfig:
    def test_rate_limit_defaults(self):
        rl = RateLimitConfig()
        assert rl.enabled is True
        assert rl.messages_per_second == 10
        assert rl.burst_size == 20

    def test_config_defaults(self):
        cfg = WebSocketConfig()
        assert cfg.enabled is True
        assert cfg.auth_required is False
        assert cfg.heartbeat_interval == 30
        assert cfg.max_message_size == 65536
        assert cfg.group_prefix == "matt_"
        assert cfg.max_groups_per_user == 100
        assert cfg.allow_reconnect is True

    def test_config_from_settings(self):
        cfg = WebSocketConfig.from_settings()
        assert isinstance(cfg, WebSocketConfig)
        assert isinstance(cfg.rate_limit, RateLimitConfig)

    @patch("django_matt.websockets.config.settings")
    def test_config_from_custom_settings(self, mock_settings):
        mock_settings.DJANGO_MATT_WEBSOCKETS = {
            "ENABLED": False,
            "AUTH_REQUIRED": True,
            "HEARTBEAT_INTERVAL": 60,
            "RATE_LIMIT": {"ENABLED": False, "MESSAGES_PER_SECOND": 5},
        }
        cfg = WebSocketConfig.from_settings()
        assert cfg.enabled is False
        assert cfg.auth_required is True
        assert cfg.heartbeat_interval == 60
        assert cfg.rate_limit.enabled is False
        assert cfg.rate_limit.messages_per_second == 5

    def test_get_websocket_config_returns_instance(self):
        import django_matt.websockets.config as mod
        mod._websocket_config = None
        cfg = get_websocket_config()
        assert isinstance(cfg, WebSocketConfig)


# ===========================================================================
# Schemas
# ===========================================================================


class TestSchemas:
    def test_base_message_requires_type(self):
        msg = BaseMessage(type="test")
        assert msg.type == "test"

    def test_error_message(self):
        msg = ErrorMessage(code=4000, message="bad")
        assert msg.type == "error"
        assert msg.code == 4000

    def test_ack_message(self):
        msg = AckMessage(message_id="abc123")
        assert msg.type == "ack"
        assert msg.success is True

    def test_ping_pong(self):
        ping = PingMessage()
        pong = PongMessage()
        assert ping.type == "ping"
        assert pong.type == "pong"
        assert isinstance(ping.timestamp, datetime)

    def test_chat_message(self):
        msg = ChatMessage(message="hello", user="matt")
        assert msg.type == "chat_message"
        assert msg.message == "hello"

    def test_chat_join_leave(self):
        join = ChatJoinMessage(user="matt", room="lobby")
        leave = ChatLeaveMessage(user="matt", room="lobby")
        assert join.type == "user_joined"
        assert leave.type == "user_left"

    def test_typing_message(self):
        msg = TypingMessage(user="matt", room="lobby")
        assert msg.is_typing is True

    def test_room_messages(self):
        join = JoinRoomRequest(room="lobby")
        leave = LeaveRoomRequest()
        joined = RoomJoinedMessage(room="lobby")
        left = RoomLeftMessage(room="lobby")
        users = RoomUsersMessage(room="lobby", users=[], count=0)
        assert join.type == "join"
        assert leave.room is None
        assert joined.type == "room_joined"
        assert left.type == "room_left"
        assert users.count == 0

    def test_notification_message(self):
        msg = NotificationMessage(title="Hello", body="World")
        assert msg.level == "info"
        assert msg.action_url is None

    def test_presence_messages(self):
        p = PresenceMessage(user="matt", status="online")
        pl = PresenceListMessage(users=[])
        assert p.type == "presence"
        assert pl.type == "presence_list"

    def test_event_message(self):
        event = EventMessage(event="click")
        assert event.type == "event"

    def test_connected_auth_disconnected(self):
        conn = ConnectedMessage()
        auth = AuthenticatedMessage()
        disc = DisconnectedMessage()
        assert conn.type == "connected"
        assert auth.type == "authenticated"
        assert disc.code == 1000

    def test_request_response(self):
        req = RequestMessage(request_id="r1", action="get_data")
        resp = ResponseMessage(request_id="r1")
        assert req.type == "request"
        assert resp.success is True

    def test_subscribe_unsubscribe(self):
        sub = SubscribeMessage(channel="news")
        unsub = UnsubscribeMessage(channel="news")
        subd = SubscribedMessage(channel="news")
        unsubd = UnsubscribedMessage(channel="news")
        assert sub.type == "subscribe"
        assert unsub.type == "unsubscribe"
        assert subd.type == "subscribed"
        assert unsubd.type == "unsubscribed"

    def test_publish_message(self):
        msg = PublishMessage(channel="news", data={"headline": "test"})
        assert msg.type == "publish"
        assert msg.data["headline"] == "test"


# ===========================================================================
# BaseConsumer
# ===========================================================================


class TestBaseConsumer:
    def test_init(self):
        consumer, send, _ = _make_consumer()
        assert isinstance(consumer.state, ConnectionState)
        assert consumer._closed is False

    def test_user_anonymous_by_default(self):
        consumer, _, _ = _make_consumer()
        assert isinstance(consumer.user, AnonymousUser)
        assert consumer.is_authenticated is False

    def test_user_authenticated(self):
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        consumer, _, _ = _make_consumer(scope_overrides={"user": mock_user})
        assert consumer.is_authenticated is True

    def test_channel_name(self):
        consumer, _, _ = _make_consumer(scope_overrides={"channel_name": "x.y.z"})
        assert consumer.channel_name == "x.y.z"

    @pytest.mark.asyncio
    async def test_accept(self):
        consumer, send, _ = _make_consumer()
        await consumer.accept()
        send.assert_called_once()
        msg = send.call_args[0][0]
        assert msg["type"] == "websocket.accept"

    @pytest.mark.asyncio
    async def test_close(self):
        consumer, send, _ = _make_consumer()
        await consumer.close(code=1001)
        assert consumer._closed is True
        msg = send.call_args[0][0]
        assert msg["type"] == "websocket.close"
        assert msg["code"] == 1001

    @pytest.mark.asyncio
    async def test_send_text(self):
        consumer, send, _ = _make_consumer()
        await consumer.send(text_data="hello")
        msg = send.call_args[0][0]
        assert msg["text"] == "hello"

    @pytest.mark.asyncio
    async def test_send_json(self):
        consumer, send, _ = _make_consumer()
        await consumer.send_json({"key": "val"})
        sent = json.loads(send.call_args[0][0]["text"])
        assert sent["key"] == "val"

    @pytest.mark.asyncio
    async def test_send_error(self):
        consumer, send, _ = _make_consumer()
        await consumer.send_error(4000, "bad request")
        sent = json.loads(send.call_args[0][0]["text"])
        assert sent["type"] == "error"
        assert sent["code"] == 4000

    @pytest.mark.asyncio
    async def test_send_ignored_when_closed(self):
        consumer, send, _ = _make_consumer()
        consumer._closed = True
        await consumer.send(text_data="should not send")
        send.assert_not_called()

    def test_register_handlers(self):
        class MyConsumer(BaseConsumer):
            async def handle_ping(self, data):
                pass

            async def handle_echo(self, data):
                pass

        consumer, _, _ = _make_consumer(cls=MyConsumer)
        assert "ping" in consumer._handlers
        assert "echo" in consumer._handlers

    def test_rate_limit_disabled(self):
        consumer, _, _ = _make_consumer()
        consumer.config.rate_limit.enabled = False
        assert consumer._check_rate_limit() is True

    def test_rate_limit_allows_burst(self):
        consumer, _, _ = _make_consumer()
        consumer.config.rate_limit.enabled = True
        consumer.config.rate_limit.burst_size = 5
        for _ in range(5):
            assert consumer._check_rate_limit() is True

    def test_rate_limit_rejects_after_burst(self):
        consumer, _, _ = _make_consumer()
        consumer.config.rate_limit.enabled = True
        consumer.config.rate_limit.burst_size = 2
        consumer.config.rate_limit.messages_per_second = 0
        consumer._rate_limit_tokens = 2
        assert consumer._check_rate_limit() is True
        assert consumer._check_rate_limit() is True
        assert consumer._check_rate_limit() is False

    @pytest.mark.asyncio
    async def test_on_connect_default_accepts(self):
        consumer, send, _ = _make_consumer()
        await consumer.on_connect()
        msg = send.call_args[0][0]
        assert msg["type"] == "websocket.accept"

    @pytest.mark.asyncio
    async def test_handle_connect_auth_required_rejects(self):
        consumer, send, _ = _make_consumer()
        consumer.auth_required = True
        await consumer._handle_connect()
        msg = send.call_args[0][0]
        assert msg["type"] == "websocket.close"
        assert msg["code"] == 4001


# ===========================================================================
# JsonConsumer
# ===========================================================================


class TestJsonConsumer:
    @pytest.mark.asyncio
    async def test_on_connect_sends_welcome(self):
        consumer, send, _ = _make_consumer(cls=JsonConsumer)
        await consumer.on_connect()
        assert send.call_count == 2
        welcome = json.loads(send.call_args_list[1][0][0]["text"])
        assert welcome["type"] == "connected"


# ===========================================================================
# AuthenticatedConsumer
# ===========================================================================


class TestAuthenticatedConsumer:
    def test_auth_required_flag(self):
        assert AuthenticatedConsumer.auth_required is True

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated(self):
        consumer, send, _ = _make_consumer(cls=AuthenticatedConsumer)
        await consumer.on_connect()
        msg = send.call_args[0][0]
        assert msg["type"] == "websocket.close"
        assert msg["code"] == 4001

    @pytest.mark.asyncio
    async def test_accepts_authenticated(self):
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = 42
        consumer, send, _ = _make_consumer(
            cls=AuthenticatedConsumer,
            scope_overrides={"user": mock_user},
        )
        await consumer.on_connect()
        assert send.call_count == 2
        auth_msg = json.loads(send.call_args_list[1][0][0]["text"])
        assert auth_msg["type"] == "authenticated"
        assert auth_msg["user_id"] == "42"


# ===========================================================================
# RoomConsumer
# ===========================================================================


class TestRoomConsumer:
    def test_room_param_default(self):
        assert RoomConsumer.room_param == "room_name"

    @pytest.mark.asyncio
    async def test_join_room_without_channel_layer(self):
        consumer, send, _ = _make_consumer(cls=RoomConsumer)
        result = await consumer.join_room("lobby")
        assert result is False

    @pytest.mark.asyncio
    async def test_join_room_with_channel_layer(self):
        mock_layer = AsyncMock()
        consumer, send, _ = _make_consumer(
            cls=RoomConsumer,
            scope_overrides={"channel_layer": mock_layer},
        )
        result = await consumer.join_room("lobby")
        assert result is True
        assert consumer.room_name == "lobby"

    @pytest.mark.asyncio
    async def test_leave_room(self):
        mock_layer = AsyncMock()
        consumer, send, _ = _make_consumer(
            cls=RoomConsumer,
            scope_overrides={"channel_layer": mock_layer},
        )
        await consumer.join_room("lobby")
        await consumer.leave_room()
        assert consumer.room_name is None

    @pytest.mark.asyncio
    async def test_handle_join(self):
        mock_layer = AsyncMock()
        consumer, send, _ = _make_consumer(
            cls=RoomConsumer,
            scope_overrides={"channel_layer": mock_layer},
        )
        await consumer.handle_join({"room": "game"})
        assert consumer.room_name == "game"


# ===========================================================================
# Auth middleware
# ===========================================================================


class TestAuthMiddleware:
    def test_auth_base_init(self):
        app = AsyncMock()
        mw = AuthMiddlewareBase(app)
        assert mw.app is app

    @pytest.mark.asyncio
    async def test_auth_base_returns_anonymous(self):
        app = AsyncMock()
        mw = AuthMiddlewareBase(app)
        user = await mw.authenticate({})
        assert isinstance(user, AnonymousUser)

    def test_jwt_get_token_from_query(self):
        app = AsyncMock()
        mw = JWTAuthMiddleware(app)
        scope = {"query_string": b"token=abc123", "subprotocols": [], "headers": []}
        assert mw._get_token(scope) == "abc123"

    def test_jwt_get_token_from_subprotocol(self):
        app = AsyncMock()
        mw = JWTAuthMiddleware(app)
        scope = {"query_string": b"", "subprotocols": ["bearer.mytoken"], "headers": []}
        assert mw._get_token(scope) == "mytoken"

    def test_jwt_get_token_from_header(self):
        app = AsyncMock()
        mw = JWTAuthMiddleware(app)
        scope = {
            "query_string": b"",
            "subprotocols": [],
            "headers": [(b"authorization", b"Bearer headertoken")],
        }
        assert mw._get_token(scope) == "headertoken"

    def test_jwt_no_token(self):
        app = AsyncMock()
        mw = JWTAuthMiddleware(app)
        scope = {"query_string": b"", "subprotocols": [], "headers": []}
        assert mw._get_token(scope) is None

    def test_session_parse_cookies(self):
        app = AsyncMock()
        mw = SessionAuthMiddleware(app)
        scope = {"headers": [(b"cookie", b"sessionid=abc; csrftoken=xyz")]}
        cookies = mw._parse_cookies(scope)
        assert cookies["sessionid"] == "abc"
        assert cookies["csrftoken"] == "xyz"

    def test_token_auth_get_token(self):
        app = AsyncMock()
        mw = TokenAuthMiddleware(app)
        scope = {"query_string": b"token=myapikey", "subprotocols": [], "headers": []}
        assert mw._get_token(scope) == "myapikey"

    def test_combined_auth_init(self):
        app = AsyncMock()
        mw = CombinedAuthMiddleware(app)
        assert isinstance(mw.jwt_auth, JWTAuthMiddleware)
        assert isinstance(mw.session_auth, SessionAuthMiddleware)


# ===========================================================================
# Routing
# ===========================================================================


class TestRouting:
    def test_websocket_route_dataclass(self):
        route = WebSocketRoute(path="ws/test/", consumer=BaseConsumer)
        assert route.path == "ws/test/"
        assert route.auth_required is False
        assert route.kwargs == {}

    def test_router_add_route(self):
        router = WebSocketRouter()
        router.route("ws/chat/", BaseConsumer, name="chat")
        assert len(router.routes) == 1
        assert router.routes[0].name == "chat"

    def test_router_chaining(self):
        router = WebSocketRouter()
        result = router.route("ws/a/", BaseConsumer).route("ws/b/", BaseConsumer)
        assert result is router
        assert len(router.routes) == 2

    def test_router_include(self):
        child = WebSocketRouter()
        child.route("chat/", BaseConsumer)
        parent = WebSocketRouter()
        parent.include(child, prefix="ws/")
        assert len(parent.routes) == 1
        assert parent.routes[0].path == "ws/chat/"

    def test_websocket_route_decorator(self):
        @websocket_route("ws/decorated/", name="dec", auth_required=True)
        class Dec(BaseConsumer):
            pass

        assert Dec._websocket_path == "ws/decorated/"
        assert Dec._websocket_name == "dec"
        assert Dec._websocket_auth_required is True

    def test_collect_routes(self):
        @websocket_route("ws/a/")
        class A(BaseConsumer):
            pass

        @websocket_route("ws/b/", auth_required=True)
        class B(BaseConsumer):
            pass

        router = collect_routes(A, B)
        assert len(router.routes) == 2
        assert router.routes[1].auth_required is True


# ===========================================================================
# Presence
# ===========================================================================


class TestPresenceInfo:
    def test_defaults(self):
        info = PresenceInfo(user_id="u1", channel_name="ch1")
        assert info.user_id == "u1"
        assert isinstance(info.joined_at, datetime)
        assert info.metadata == {}


class TestPresenceManager:
    @pytest.mark.asyncio
    async def test_user_join_and_get(self):
        pm = PresenceManager()
        await pm.user_joined("room1", "user1", "ch1")
        users = await pm.get_users("room1")
        assert len(users) == 1
        assert users[0].user_id == "user1"

    @pytest.mark.asyncio
    async def test_user_count(self):
        pm = PresenceManager()
        await pm.user_joined("room2", "u1", "ch1")
        await pm.user_joined("room2", "u2", "ch2")
        count = await pm.get_user_count("room2")
        assert count == 2

    @pytest.mark.asyncio
    async def test_user_leave(self):
        pm = PresenceManager()
        await pm.user_joined("room3", "u1", "ch1")
        await pm.user_left("room3", "u1")
        assert await pm.get_user_count("room3") == 0

    @pytest.mark.asyncio
    async def test_is_user_in_group(self):
        pm = PresenceManager()
        await pm.user_joined("room4", "u1", "ch1")
        assert await pm.is_user_in_group("room4", "u1") is True
        assert await pm.is_user_in_group("room4", "u2") is False

    @pytest.mark.asyncio
    async def test_clear_group(self):
        pm = PresenceManager()
        await pm.user_joined("room5", "u1", "ch1")
        await pm.clear_group("room5")
        assert await pm.get_user_count("room5") == 0
