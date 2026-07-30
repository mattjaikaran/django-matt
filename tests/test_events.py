from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from django_matt.events.backends import InMemoryBackend
from django_matt.events.bus import Event, EventBus, get_event_bus, reset_event_bus
from django_matt.events.decorators import on
from django_matt.events.types import (
    ModelCreatedEvent,
    ModelDeletedEvent,
    ModelUpdatedEvent,
    RequestEvent,
    UserCreatedEvent,
    UserDeletedEvent,
    UserUpdatedEvent,
)


@pytest.fixture(autouse=True)
def _clean_bus():
    reset_event_bus()
    yield
    reset_event_bus()


# --- Event model ---


class TestEvent:
    def test_default_event_type_from_class_name(self):
        e = Event()
        assert e.event_type == "Event"

    def test_custom_event_type(self):
        e = Event(event_type="custom.event")
        assert e.event_type == "custom.event"

    def test_timestamp_auto(self):
        e = Event()
        assert e.timestamp > 0

    def test_metadata(self):
        e = Event(metadata={"key": "val"})
        assert e.metadata["key"] == "val"

    def test_serialize_deserialize(self):
        e = Event(event_type="test.roundtrip", metadata={"x": 1})
        data = e.serialize()
        e2 = Event.deserialize(data)
        assert e2.event_type == "test.roundtrip"
        assert e2.metadata == {"x": 1}


# --- Typed events ---


class TestTypedEvents:
    def test_user_created(self):
        e = UserCreatedEvent(user_id=1, email="a@b.com")
        assert e.event_type == "user.created"
        assert e.user_id == 1

    def test_user_updated(self):
        e = UserUpdatedEvent(user_id=2, changes={"name": "new"})
        assert e.event_type == "user.updated"
        assert e.changes == {"name": "new"}

    def test_user_deleted(self):
        e = UserDeletedEvent(user_id=3)
        assert e.event_type == "user.deleted"

    def test_model_created(self):
        e = ModelCreatedEvent(model_name="Product", instance_id=10)
        assert e.event_type == "model.created"
        assert e.model_name == "Product"

    def test_model_updated(self):
        e = ModelUpdatedEvent(model_name="Product", instance_id=10, changes={"price": 99})
        assert e.event_type == "model.updated"

    def test_model_deleted(self):
        e = ModelDeletedEvent(model_name="Product", instance_id=10)
        assert e.event_type == "model.deleted"

    def test_request_event(self):
        e = RequestEvent(method="GET", path="/api/users", status_code=200, duration_ms=12.5)
        assert e.event_type == "request"
        assert e.method == "GET"


# --- EventBus ---


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit(Event(event_type="test.event"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_sync_handler(self):
        bus = EventBus()
        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe("test.sync", handler)
        await bus.emit(Event(event_type="test.sync"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("test.unsub", handler)
        bus.unsubscribe("test.unsub", handler)
        await bus.emit(Event(event_type="test.unsub"))
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_missing_handler(self):
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.unsubscribe("nope", handler)  # should not raise

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event.event_type)

        bus.subscribe("user.*", handler)
        await bus.emit(Event(event_type="user.created"))
        await bus.emit(Event(event_type="user.deleted"))
        await bus.emit(Event(event_type="order.created"))
        assert received == ["user.created", "user.deleted"]

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        bus = EventBus()
        results = []

        async def h1(event: Event):
            results.append("h1")

        async def h2(event: Event):
            results.append("h2")

        bus.subscribe("multi", h1)
        bus.subscribe("multi", h2)
        await bus.emit(Event(event_type="multi"))
        assert sorted(results) == ["h1", "h2"]

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        bus = EventBus()
        results = []

        async def bad_handler(event: Event):
            raise ValueError("boom")

        async def good_handler(event: Event):
            results.append("ok")

        bus.subscribe("error.test", bad_handler)
        bus.subscribe("error.test", good_handler)
        outcomes = await bus.emit(Event(event_type="error.test"))
        assert results == ["ok"]
        assert any(isinstance(o, ValueError) for o in outcomes)

    @pytest.mark.asyncio
    async def test_emit_many(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event.event_type)

        bus.subscribe("batch.*", handler)
        events = [Event(event_type="batch.one"), Event(event_type="batch.two")]
        results = await bus.emit_many(events)
        assert len(results) == 2
        assert received == ["batch.one", "batch.two"]

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self):
        bus = EventBus()
        results = await bus.emit(Event(event_type="nobody.listens"))
        assert results == []

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("x", lambda e: None)
        bus.clear()
        assert bus.handlers_for("x") == []

    def test_subscribe_by_class(self):
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe(UserCreatedEvent, handler)
        assert len(bus.handlers_for(UserCreatedEvent)) == 1

    def test_duplicate_subscribe_ignored(self):
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("dup", handler)
        bus.subscribe("dup", handler)
        assert len(bus.handlers_for("dup")) == 1

    def test_handlers_for(self):
        bus = EventBus()

        async def h(event: Event):
            pass

        bus.subscribe("hf.test", h)
        assert bus.handlers_for("hf.test") == [h]
        assert bus.handlers_for("hf.other") == []


# --- Singleton ---


class TestSingleton:
    def test_get_event_bus_returns_same(self):
        b1 = get_event_bus()
        b2 = get_event_bus()
        assert b1 is b2

    def test_reset_clears(self):
        b1 = get_event_bus()
        reset_event_bus()
        b2 = get_event_bus()
        assert b1 is not b2


# --- Decorator ---


class TestOnDecorator:
    @pytest.mark.asyncio
    async def test_on_string(self):
        received = []

        @on("dec.string")
        async def handler(event: Event):
            received.append(event)

        bus = get_event_bus()
        await bus.emit(Event(event_type="dec.string"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_on_class(self):
        received = []

        @on(UserCreatedEvent)
        async def handler(event: Event):
            received.append(event)

        bus = get_event_bus()
        await bus.emit(UserCreatedEvent(user_id=1))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_on_wildcard(self):
        received = []

        @on("wc.*")
        async def handler(event: Event):
            received.append(event.event_type)

        bus = get_event_bus()
        await bus.emit(Event(event_type="wc.a"))
        await bus.emit(Event(event_type="wc.b"))
        await bus.emit(Event(event_type="other"))
        assert received == ["wc.a", "wc.b"]

    def test_on_sets_attribute(self):
        @on("attr.test")
        def handler(event: Event):
            pass

        assert handler._event_subscription == "attr.test"


# --- InMemoryBackend ---


class TestInMemoryBackend:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self):
        backend = InMemoryBackend()
        received = []

        async def handler(event: Event):
            received.append(event.event_type)

        await backend.subscribe("mem.test", handler)
        await backend.publish(Event(event_type="mem.test"))
        assert received == ["mem.test"]

    @pytest.mark.asyncio
    async def test_wildcard(self):
        backend = InMemoryBackend()
        received = []

        async def handler(event: Event):
            received.append(event.event_type)

        await backend.subscribe("mem.*", handler)
        await backend.publish(Event(event_type="mem.a"))
        await backend.publish(Event(event_type="mem.b"))
        await backend.publish(Event(event_type="other"))
        assert received == ["mem.a", "mem.b"]

    @pytest.mark.asyncio
    async def test_close(self):
        backend = InMemoryBackend()
        await backend.subscribe("x", lambda e: None)
        await backend.close()
        assert backend._subscribers == {}

    @pytest.mark.asyncio
    async def test_handler_error_isolated(self):
        backend = InMemoryBackend()
        received = []

        async def bad(event: Event):
            raise RuntimeError("fail")

        async def good(event: Event):
            received.append("ok")

        await backend.subscribe("iso", bad)
        await backend.subscribe("iso", good)
        await backend.publish(Event(event_type="iso"))
        assert received == ["ok"]


# --- BackendProtocol ---


class TestBackendProtocol:
    @pytest.mark.asyncio
    async def test_protocol_methods(self):
        from django_matt.events.bus import BackendProtocol

        bp = BackendProtocol()
        with pytest.raises(NotImplementedError):
            await bp.publish(Event())
        with pytest.raises(NotImplementedError):
            await bp.subscribe("x", lambda e: None)
        await bp.close()  # should not raise


# --- EventBus backend integration ---


class TestEventBusBackend:
    def test_set_backend(self):
        bus = EventBus()
        backend = InMemoryBackend()
        bus.backend = backend
        assert bus.backend is backend


# --- Middleware ---


class TestEventMiddleware:
    @pytest.mark.asyncio
    async def test_async_middleware_emits_on_success(self):
        from django_matt.events.middleware import EventMiddleware, collect_event

        emitted = []
        bus = get_event_bus()

        async def capture(event: Event):
            emitted.append(event.event_type)

        bus.subscribe("request", capture)
        bus.subscribe("custom.ev", capture)

        request = MagicMock()
        request.method = "GET"
        request.path = "/test"
        request.user = MagicMock()
        request.user.pk = 1

        response = MagicMock()
        response.status_code = 200

        async def get_response(req):
            collect_event(req, Event(event_type="custom.ev"))
            return response

        mw = EventMiddleware(get_response)
        result = await mw(request)
        assert result is response
        assert "request" in emitted
        assert "custom.ev" in emitted

    @pytest.mark.asyncio
    async def test_async_middleware_skips_on_error_status(self):
        from django_matt.events.middleware import EventMiddleware, collect_event

        emitted = []
        bus = get_event_bus()

        async def capture(event: Event):
            emitted.append(event.event_type)

        bus.subscribe("request", capture)

        request = MagicMock()
        request.method = "GET"
        request.path = "/fail"

        response = MagicMock()
        response.status_code = 500

        async def get_response(req):
            return response

        mw = EventMiddleware(get_response)
        await mw(request)
        assert emitted == []


# --- __init__ exports ---


class TestExports:
    def test_lazy_imports(self):
        import django_matt.events as mod

        assert mod.Event is Event
        assert mod.EventBus is EventBus
        assert mod.get_event_bus is get_event_bus
        assert mod.InMemoryBackend is InMemoryBackend
        assert mod.UserCreatedEvent is UserCreatedEvent
        assert mod.on is on

    def test_bad_attr(self):
        import django_matt.events as mod

        with pytest.raises(AttributeError):
            mod.DoesNotExist  # noqa: B018
