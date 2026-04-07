# CQRS Recipes

Command/Query separation with dedicated buses, middleware, and domain events.

## Basic Command/Query Setup

```python
from django_matt.cqrs import (
    Command,
    CommandBus,
    Query,
    QueryBus,
    command_handler,
    get_command_bus,
    get_query_bus,
    query_handler,
)


# Define commands (immutable via frozen=True from Pydantic)
class CreateUserCommand(Command):
    email: str
    name: str
    role: str = "member"


class DeactivateUserCommand(Command):
    user_id: int
    reason: str = ""


# Define queries
class GetUserQuery(Query):
    user_id: int


class ListUsersQuery(Query):
    role: str | None = None
    limit: int = 50


# Register handlers — one handler per command/query
@command_handler(CreateUserCommand)
class CreateUserHandler:
    async def execute(self, command: CreateUserCommand) -> dict:
        user = await User.objects.acreate(
            email=command.email,
            name=command.name,
            role=command.role,
        )
        return {"id": user.pk, "email": user.email}


@query_handler(GetUserQuery)
class GetUserHandler:
    async def execute(self, query: GetUserQuery) -> dict:
        user = await User.objects.aget(pk=query.user_id)
        return {"id": user.pk, "email": user.email, "name": user.name}


# Dispatch
bus = get_command_bus()
result = await bus.dispatch(CreateUserCommand(email="matt@example.com", name="Matt"))

query_bus = get_query_bus()
user = await query_bus.dispatch(GetUserQuery(user_id=1))
```

## Transaction Wrapping for Commands

```python
from django_matt.cqrs import TransactionMiddleware, get_command_bus

# Add TransactionMiddleware — wraps each command in a database transaction
bus = get_command_bus()
bus.use(TransactionMiddleware())

# Now all commands execute inside an atomic block
# If the handler raises, the transaction rolls back automatically
await bus.dispatch(CreateUserCommand(email="test@example.com", name="Test"))
```

## Query Result Caching

```python
from django_matt.cqrs import CachingMiddleware, get_query_bus

# Cache query results for 5 minutes
caching = CachingMiddleware(ttl=300)

query_bus = get_query_bus()
query_bus.use(caching)

# First call executes the handler
result1 = await query_bus.dispatch(GetUserQuery(user_id=1))

# Second call with same params returns cached result
result2 = await query_bus.dispatch(GetUserQuery(user_id=1))

# Invalidate all cached results when data changes
caching.invalidate()
```

## Domain Events from Commands

```python
from django_matt.cqrs import (
    Command,
    DomainEvent,
    EventCollector,
    command_handler,
    emits,
    get_command_bus,
)


class UserCreatedDomainEvent(DomainEvent):
    user_id: int
    email: str


class UserDeactivatedDomainEvent(DomainEvent):
    user_id: int
    reason: str


@emits(UserCreatedDomainEvent)
@command_handler(CreateUserCommand)
class CreateUserWithEvents:
    def __init__(self):
        self.events = EventCollector()
        self.events.on(UserCreatedDomainEvent, self._on_created)

    async def _on_created(self, event: UserCreatedDomainEvent):
        await email_service.send_welcome(event.email)

    async def execute(self, command: CreateUserCommand) -> dict:
        user = await User.objects.acreate(
            email=command.email, name=command.name
        )
        self.events.collect(
            UserCreatedDomainEvent(user_id=user.pk, email=user.email)
        )
        await self.events.publish()
        return {"id": user.pk}
```

## Logging and Validation Middleware

```python
import logging

from django_matt.cqrs import (
    LoggingMiddleware,
    ValidationMiddleware,
    get_command_bus,
    get_query_bus,
)

logger = logging.getLogger("cqrs")

# Stack multiple middleware — they execute in order
command_bus = get_command_bus()
command_bus.use(LoggingMiddleware(log=logger))  # logs dispatch timing
command_bus.use(ValidationMiddleware())          # re-validates Pydantic models

query_bus = get_query_bus()
query_bus.use(LoggingMiddleware(log=logger))
query_bus.use(CachingMiddleware(ttl=60))
```

## Testing with InMemoryBus

```python
import pytest

from django_matt.cqrs import (
    InMemoryCommandBus,
    InMemoryQueryBus,
    assert_command_dispatched,
    assert_query_dispatched,
)


@pytest.fixture
def command_bus():
    bus = InMemoryCommandBus()
    bus.set_response(CreateUserCommand, {"id": 1, "email": "test@example.com"})
    return bus


@pytest.fixture
def query_bus():
    bus = InMemoryQueryBus()
    bus.set_response(GetUserQuery, {"id": 1, "email": "test@example.com", "name": "Test"})
    return bus


async def test_create_user(command_bus):
    result = await command_bus.dispatch(
        CreateUserCommand(email="test@example.com", name="Test")
    )
    assert result["id"] == 1

    # Assert the right command was dispatched with correct data
    cmd = assert_command_dispatched(
        command_bus,
        CreateUserCommand,
        email="test@example.com",
    )
    assert cmd.name == "Test"


async def test_get_user(query_bus):
    result = await query_bus.dispatch(GetUserQuery(user_id=1))
    assert result["email"] == "test@example.com"

    assert_query_dispatched(query_bus, GetUserQuery, user_id=1)


async def test_dynamic_responses(command_bus):
    # Use a callable for dynamic responses
    command_bus.set_response(
        CreateUserCommand,
        lambda cmd: {"id": 42, "email": cmd.email},
    )
    result = await command_bus.dispatch(
        CreateUserCommand(email="dynamic@example.com", name="Dynamic")
    )
    assert result["email"] == "dynamic@example.com"
```

## Controller Integration with @command/@query Decorators

```python
from django_matt.cqrs import command, query


class UserController:
    """Controller methods that auto-dispatch through the CQRS bus."""

    @command(CreateUserCommand)
    async def create(self, request, data=None):
        # The @command decorator:
        # 1. Constructs CreateUserCommand from request body or `data`
        # 2. Dispatches through the command bus
        # 3. Returns the handler result
        ...

    @query(GetUserQuery)
    async def get(self, request, user_id: int):
        # The @query decorator:
        # 1. Constructs GetUserQuery from query params + kwargs
        # 2. Dispatches through the query bus
        # 3. Returns the handler result
        ...

    @query(ListUsersQuery)
    async def list(self, request):
        # Query params like ?role=admin&limit=10 are passed to ListUsersQuery
        ...
```
