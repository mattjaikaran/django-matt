from __future__ import annotations

import pytest
from pydantic import ValidationError

from django_matt.cqrs import (
    CachingMiddleware,
    Command,
    CommandBus,
    DomainEvent,
    EventCollector,
    InMemoryCommandBus,
    InMemoryQueryBus,
    LoggingMiddleware,
    Query,
    QueryBus,
    ValidationMiddleware,
    assert_command_dispatched,
    assert_query_dispatched,
    command_handler,
    emits,
    query_handler,
)

# ---------------------------------------------------------------------------
# Fixtures: command/query types and handlers
# ---------------------------------------------------------------------------


class CreateUser(Command):
    name: str
    email: str


class DeleteUser(Command):
    user_id: int


class GetUser(Query):
    user_id: int


class ListUsers(Query):
    page: int = 1


class UserCreated(DomainEvent):
    name: str
    email: str


class CreateUserHandler:
    async def execute(self, command: CreateUser) -> dict:
        return {"id": 1, "name": command.name, "email": command.email}


class DeleteUserHandler:
    async def execute(self, command: DeleteUser) -> bool:
        return True


class GetUserHandler:
    async def execute(self, query: GetUser) -> dict:
        return {"id": query.user_id, "name": "Alice"}


class ListUsersHandler:
    async def execute(self, query: ListUsers) -> list[dict]:
        return [{"id": 1, "name": "Alice"}]


# ---------------------------------------------------------------------------
# Command tests
# ---------------------------------------------------------------------------


class TestCommand:
    def test_command_is_frozen(self):
        cmd = CreateUser(name="Alice", email="alice@example.com")
        with pytest.raises(ValidationError):
            cmd.name = "Bob"

    def test_command_serialization(self):
        cmd = CreateUser(name="Alice", email="alice@example.com")
        data = cmd.model_dump()
        assert data == {"name": "Alice", "email": "alice@example.com"}
        restored = CreateUser.model_validate(data)
        assert restored == cmd


class TestCommandBus:
    @pytest.fixture()
    def bus(self) -> CommandBus:
        b = CommandBus()
        b.register(CreateUser, CreateUserHandler())
        b.register(DeleteUser, DeleteUserHandler())
        return b

    @pytest.mark.asyncio
    async def test_dispatch(self, bus: CommandBus):
        result = await bus.dispatch(CreateUser(name="Alice", email="a@b.com"))
        assert result["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_dispatch_unregistered_raises(self):
        bus = CommandBus()
        with pytest.raises(LookupError, match="No handler registered"):
            await bus.dispatch(CreateUser(name="X", email="x@y.com"))

    def test_duplicate_registration_raises(self, bus: CommandBus):
        with pytest.raises(ValueError, match="Handler already registered"):
            bus.register(CreateUser, CreateUserHandler())

    def test_handlers_property(self, bus: CommandBus):
        assert CreateUser in bus.handlers
        assert DeleteUser in bus.handlers

    @pytest.mark.asyncio
    async def test_middleware_execution_order(self):
        order: list[str] = []

        class MW1:
            async def before(self, msg):
                order.append("mw1_before")

            async def after(self, msg, result):
                order.append("mw1_after")
                return result

        class MW2:
            async def before(self, msg):
                order.append("mw2_before")

            async def after(self, msg, result):
                order.append("mw2_after")
                return result

        bus = CommandBus()
        bus.use(MW1()).use(MW2())
        bus.register(CreateUser, CreateUserHandler())
        await bus.dispatch(CreateUser(name="A", email="a@b.com"))
        assert order == ["mw1_before", "mw2_before", "mw2_after", "mw1_after"]


class TestCommandHandlerDecorator:
    def test_decorator_registers_handler(self):
        bus = CommandBus()

        @command_handler(DeleteUser, bus=bus)
        class _Handler:
            async def execute(self, command: DeleteUser) -> bool:
                return True

        assert DeleteUser in bus.handlers


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------


class TestQuery:
    def test_query_is_frozen(self):
        q = GetUser(user_id=1)
        with pytest.raises(ValidationError):
            q.user_id = 2

    def test_query_defaults(self):
        q = ListUsers()
        assert q.page == 1


class TestQueryBus:
    @pytest.fixture()
    def bus(self) -> QueryBus:
        b = QueryBus()
        b.register(GetUser, GetUserHandler())
        b.register(ListUsers, ListUsersHandler())
        return b

    @pytest.mark.asyncio
    async def test_dispatch(self, bus: QueryBus):
        result = await bus.dispatch(GetUser(user_id=42))
        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_dispatch_unregistered_raises(self):
        bus = QueryBus()
        with pytest.raises(LookupError):
            await bus.dispatch(GetUser(user_id=1))

    def test_duplicate_registration_raises(self, bus: QueryBus):
        with pytest.raises(ValueError):
            bus.register(GetUser, GetUserHandler())


class TestQueryHandlerDecorator:
    def test_decorator_registers_handler(self):
        bus = QueryBus()

        @query_handler(ListUsers, bus=bus)
        class _Handler:
            async def execute(self, query: ListUsers) -> list:
                return []

        assert ListUsers in bus.handlers


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    @pytest.mark.asyncio
    async def test_logs_dispatch(self, caplog):
        import logging

        mw = LoggingMiddleware(log=logging.getLogger("test"))
        bus = CommandBus()
        bus.use(mw)
        bus.register(CreateUser, CreateUserHandler())

        with caplog.at_level(logging.INFO, logger="test"):
            await bus.dispatch(CreateUser(name="A", email="a@b.com"))

        assert any("dispatching CreateUser" in r.message for r in caplog.records)
        assert any("completed CreateUser" in r.message for r in caplog.records)


class TestValidationMiddleware:
    @pytest.mark.asyncio
    async def test_validates_command(self):
        mw = ValidationMiddleware()
        cmd = CreateUser(name="Alice", email="alice@example.com")
        await mw.before(cmd)  # should not raise
        result = await mw.after(cmd, {"ok": True})
        assert result == {"ok": True}


class TestCachingMiddleware:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        call_count = 0

        class CountingHandler:
            async def execute(self, query: GetUser) -> dict:
                nonlocal call_count
                call_count += 1
                return {"id": query.user_id, "name": "Alice"}

        mw = CachingMiddleware(ttl=60)
        bus = QueryBus()
        bus.use(mw)
        bus.register(GetUser, CountingHandler())

        q = GetUser(user_id=1)
        r1 = await bus.dispatch(q)
        r2 = await bus.dispatch(q)

        assert r1 == r2
        assert call_count == 1  # second call served from cache

    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self):
        call_count = 0

        class CountingHandler:
            async def execute(self, query: GetUser) -> dict:
                nonlocal call_count
                call_count += 1
                return {"id": query.user_id}

        mw = CachingMiddleware(ttl=60)
        bus = QueryBus()
        bus.use(mw)
        bus.register(GetUser, CountingHandler())

        await bus.dispatch(GetUser(user_id=1))
        mw.invalidate()
        await bus.dispatch(GetUser(user_id=1))

        assert call_count == 2


# ---------------------------------------------------------------------------
# Events tests
# ---------------------------------------------------------------------------


class TestDomainEvent:
    def test_event_has_id_and_timestamp(self):
        event = UserCreated(name="Alice", email="alice@example.com")
        assert event.event_id
        assert event.occurred_at > 0

    def test_event_is_frozen(self):
        event = UserCreated(name="Alice", email="a@b.com")
        with pytest.raises(ValidationError):
            event.name = "Bob"


class TestEmitsDecorator:
    def test_marks_handler_with_events(self):
        @emits(UserCreated)
        class Handler:
            async def execute(self, command: CreateUser) -> dict:
                return {}

        assert Handler._emitted_events == (UserCreated,)


class TestEventCollector:
    @pytest.mark.asyncio
    async def test_collect_and_publish(self):
        received: list[DomainEvent] = []

        async def on_created(event: UserCreated):
            received.append(event)

        collector = EventCollector()
        collector.on(UserCreated, on_created)

        event = UserCreated(name="Alice", email="alice@example.com")
        collector.collect(event)
        assert len(collector.events) == 1

        await collector.publish()
        assert len(received) == 1
        assert received[0].name == "Alice"
        assert len(collector.events) == 0  # cleared after publish

    def test_clear(self):
        collector = EventCollector()
        collector.collect(UserCreated(name="A", email="a@b.com"))
        collector.clear()
        assert len(collector.events) == 0


# ---------------------------------------------------------------------------
# Testing utilities
# ---------------------------------------------------------------------------


class TestInMemoryCommandBus:
    @pytest.mark.asyncio
    async def test_records_dispatched_commands(self):
        bus = InMemoryCommandBus()
        cmd = CreateUser(name="Alice", email="alice@example.com")
        await bus.dispatch(cmd)
        assert len(bus.dispatched) == 1
        assert bus.dispatched[0] == cmd

    @pytest.mark.asyncio
    async def test_set_response(self):
        bus = InMemoryCommandBus()
        bus.set_response(CreateUser, {"id": 42})
        result = await bus.dispatch(CreateUser(name="A", email="a@b.com"))
        assert result == {"id": 42}

    @pytest.mark.asyncio
    async def test_callable_response(self):
        bus = InMemoryCommandBus()
        bus.set_response(CreateUser, lambda cmd: {"name": cmd.name})
        result = await bus.dispatch(CreateUser(name="Bob", email="b@c.com"))
        assert result == {"name": "Bob"}

    def test_clear(self):
        bus = InMemoryCommandBus()

        async def _dispatch():
            await bus.dispatch(CreateUser(name="A", email="a@b.com"))

        import asyncio

        asyncio.get_event_loop().run_until_complete(_dispatch())
        bus.clear()
        assert len(bus.dispatched) == 0


class TestInMemoryQueryBus:
    @pytest.mark.asyncio
    async def test_records_dispatched_queries(self):
        bus = InMemoryQueryBus()
        bus.set_response(GetUser, {"id": 1, "name": "Alice"})
        q = GetUser(user_id=1)
        result = await bus.dispatch(q)
        assert result["name"] == "Alice"
        assert len(bus.dispatched) == 1


class TestAssertCommandDispatched:
    @pytest.mark.asyncio
    async def test_basic_assertion(self):
        bus = InMemoryCommandBus()
        await bus.dispatch(CreateUser(name="Alice", email="alice@example.com"))
        cmd = assert_command_dispatched(bus, CreateUser)
        assert cmd.name == "Alice"

    @pytest.mark.asyncio
    async def test_assertion_with_kwargs(self):
        bus = InMemoryCommandBus()
        await bus.dispatch(CreateUser(name="Alice", email="alice@example.com"))
        cmd = assert_command_dispatched(bus, CreateUser, name="Alice")
        assert cmd.email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_assertion_fails_when_not_dispatched(self):
        bus = InMemoryCommandBus()
        with pytest.raises(AssertionError, match="No CreateUser was dispatched"):
            assert_command_dispatched(bus, CreateUser)

    @pytest.mark.asyncio
    async def test_assertion_fails_when_kwargs_mismatch(self):
        bus = InMemoryCommandBus()
        await bus.dispatch(CreateUser(name="Alice", email="a@b.com"))
        with pytest.raises(AssertionError, match="none matched"):
            assert_command_dispatched(bus, CreateUser, name="Bob")


class TestAssertQueryDispatched:
    @pytest.mark.asyncio
    async def test_basic_assertion(self):
        bus = InMemoryQueryBus()
        await bus.dispatch(GetUser(user_id=42))
        q = assert_query_dispatched(bus, GetUser)
        assert q.user_id == 42

    @pytest.mark.asyncio
    async def test_assertion_with_kwargs(self):
        bus = InMemoryQueryBus()
        await bus.dispatch(GetUser(user_id=42))
        assert_query_dispatched(bus, GetUser, user_id=42)

    @pytest.mark.asyncio
    async def test_assertion_fails(self):
        bus = InMemoryQueryBus()
        with pytest.raises(AssertionError):
            assert_query_dispatched(bus, GetUser)


# ---------------------------------------------------------------------------
# Integration: DI container resolution
# ---------------------------------------------------------------------------


class TestDIIntegration:
    def test_register_bus_in_container(self):
        from django_matt.di import Container, Singleton

        container = Container()
        bus = CommandBus()
        bus.register(CreateUser, CreateUserHandler())
        container.register_instance(bus, CommandBus)

        resolved = container.resolve(CommandBus)
        assert resolved is bus
        assert CreateUser in resolved.handlers
