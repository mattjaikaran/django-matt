"""In-memory bus implementations and assertions for testing CQRS handlers."""

from __future__ import annotations

from typing import Any

from .commands import Command, CommandBus
from .queries import Query, QueryBus


class InMemoryCommandBus(CommandBus):
    """Test double that records dispatched commands without executing handlers."""
    def __init__(self) -> None:
        super().__init__()
        self._dispatched: list[Command] = []
        self._responses: dict[type[Command], Any] = {}

    async def dispatch(self, command: Command) -> Any:
        self._dispatched.append(command)
        response = self._responses.get(type(command))
        if callable(response):
            return response(command)
        return response

    def set_response(self, command_type: type[Command], response: Any) -> None:
        self._responses[command_type] = response

    @property
    def dispatched(self) -> list[Command]:
        return list(self._dispatched)

    def clear(self) -> None:
        self._dispatched.clear()


class InMemoryQueryBus(QueryBus):
    """Test double that records dispatched queries without executing handlers."""

    def __init__(self) -> None:
        super().__init__()
        self._dispatched: list[Query] = []
        self._responses: dict[type[Query], Any] = {}

    async def dispatch(self, query: Query) -> Any:
        self._dispatched.append(query)
        response = self._responses.get(type(query))
        if callable(response):
            return response(query)
        return response

    def set_response(self, query_type: type[Query], response: Any) -> None:
        self._responses[query_type] = response

    @property
    def dispatched(self) -> list[Query]:
        return list(self._dispatched)

    def clear(self) -> None:
        self._dispatched.clear()


def assert_command_dispatched(
    bus: InMemoryCommandBus,
    command_type: type[Command],
    **kwargs: Any,
) -> Command:
    """Assert that a command of the given type was dispatched, optionally matching fields."""
    matches = [c for c in bus.dispatched if isinstance(c, command_type)]
    assert matches, f"No {command_type.__name__} was dispatched"

    if kwargs:
        for cmd in matches:
            data = cmd.model_dump()
            if all(data.get(k) == v for k, v in kwargs.items()):
                return cmd
        raise AssertionError(
            f"{command_type.__name__} dispatched but none matched {kwargs}. "
            f"Got: {[c.model_dump() for c in matches]}"
        )

    return matches[-1]


def assert_query_dispatched(
    bus: InMemoryQueryBus,
    query_type: type[Query],
    **kwargs: Any,
) -> Query:
    """Assert that a query of the given type was dispatched, optionally matching fields."""
    matches = [q for q in bus.dispatched if isinstance(q, query_type)]
    assert matches, f"No {query_type.__name__} was dispatched"

    if kwargs:
        for qry in matches:
            data = qry.model_dump()
            if all(data.get(k) == v for k, v in kwargs.items()):
                return qry
        raise AssertionError(
            f"{query_type.__name__} dispatched but none matched {kwargs}. "
            f"Got: {[q.model_dump() for q in matches]}"
        )

    return matches[-1]
