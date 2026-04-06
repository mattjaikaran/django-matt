from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("django_matt.cqrs.commands")

C = TypeVar("C", bound="Command")
R = TypeVar("R")


class Command(BaseModel):
    model_config = ConfigDict(frozen=True)


@runtime_checkable
class CommandHandler(Protocol[C, R]):
    async def execute(self, command: C) -> R: ...


class CommandBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Command], CommandHandler] = {}
        self._middleware: list[Any] = []

    def use(self, middleware: Any) -> CommandBus:
        self._middleware.append(middleware)
        return self

    def register(self, command_type: type[Command], handler: CommandHandler) -> CommandBus:
        if command_type in self._handlers:
            raise ValueError(
                f"Handler already registered for {command_type.__name__}. "
                "Commands must have exactly one handler."
            )
        self._handlers[command_type] = handler
        return self

    async def dispatch(self, command: Command) -> Any:
        command_type = type(command)
        handler = self._handlers.get(command_type)
        if handler is None:
            raise LookupError(f"No handler registered for {command_type.__name__}")

        for mw in self._middleware:
            if hasattr(mw, "before"):
                await mw.before(command)

        result = await handler.execute(command)

        for mw in reversed(self._middleware):
            if hasattr(mw, "after"):
                result = await mw.after(command, result) or result

        return result

    @property
    def handlers(self) -> dict[type[Command], CommandHandler]:
        return dict(self._handlers)


_default_command_bus = CommandBus()


def get_command_bus() -> CommandBus:
    return _default_command_bus


def command_handler(
    command_type: type[Command],
    *,
    bus: CommandBus | None = None,
) -> Callable:
    def decorator(cls: type) -> type:
        target_bus = bus or _default_command_bus
        target_bus.register(command_type, cls())
        return cls

    return decorator
