"""Command/Query buses, domain events, and bus middleware for CQRS patterns."""

from .commands import Command, CommandBus, CommandHandler, command_handler, get_command_bus
from .decorators import command, query
from .events import DomainEvent, EventCollector, emits
from .middleware import (
    BusMiddleware,
    CachingMiddleware,
    LoggingMiddleware,
    TransactionMiddleware,
    ValidationMiddleware,
)
from .queries import Query, QueryBus, QueryHandler, get_query_bus, query_handler
from .testing import (
    InMemoryCommandBus,
    InMemoryQueryBus,
    assert_command_dispatched,
    assert_query_dispatched,
)

__all__ = [
    # Commands
    "Command",
    "CommandBus",
    "CommandHandler",
    "command_handler",
    "get_command_bus",
    # Queries
    "Query",
    "QueryBus",
    "QueryHandler",
    "query_handler",
    "get_query_bus",
    # Events
    "DomainEvent",
    "EventCollector",
    "emits",
    # Middleware
    "BusMiddleware",
    "LoggingMiddleware",
    "ValidationMiddleware",
    "TransactionMiddleware",
    "CachingMiddleware",
    # Decorators
    "command",
    "query",
    # Testing
    "InMemoryCommandBus",
    "InMemoryQueryBus",
    "assert_command_dispatched",
    "assert_query_dispatched",
]
