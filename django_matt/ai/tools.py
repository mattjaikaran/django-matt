"""
Tool decorator and registry for AI agents.

Provides @tool decorator to convert Python functions into LLM-callable tools,
and ToolRegistry for managing and dispatching tool calls.
"""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, overload

from django_matt.ai.base import ToolDefinition


@overload
def tool(func: Callable) -> Callable: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable], Callable]: ...


def tool(
    func: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable:
    """
    Decorator that marks a function as an LLM-callable tool.

    Usage:
        @tool
        def get_weather(city: str) -> str:
            '''Get the weather for a city.'''
            return f"Sunny in {city}"

        @tool(name="custom_name", description="Custom description")
        def my_func(x: int) -> int:
            return x
    """

    def decorator(fn: Callable) -> Callable:
        tool_def = ToolDefinition.from_function(fn, description=description)
        if name:
            tool_def = ToolDefinition(
                name=name,
                description=description if description else tool_def.description,
                parameters=tool_def.parameters,
            )
        if description and not name:
            tool_def = ToolDefinition(
                name=tool_def.name,
                description=description,
                parameters=tool_def.parameters,
            )

        if asyncio.iscoroutinefunction(fn):

            @wraps(fn)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)
        else:

            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return fn(*args, **kwargs)

        wrapper._tool_definition = tool_def
        wrapper._is_tool = True
        wrapper._original_func = fn
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def is_tool(func: Any) -> bool:
    """Check if a function is a decorated tool."""
    return getattr(func, "_is_tool", False)


class ToolRegistry:
    """
    Registry for managing and dispatching tool calls.

    Usage:
        registry = ToolRegistry()
        registry.register(my_tool)
        result = registry.execute("my_tool", {"arg": "value"})
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, func: Callable) -> None:
        """Register a @tool-decorated function."""
        if not is_tool(func):
            raise TypeError(f"{func.__name__} is not decorated with @tool")
        tool_name = func._tool_definition.name
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")
        self._tools[tool_name] = func

    def get(self, name: str) -> Callable:
        """Get a registered tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    @property
    def definitions(self) -> list[ToolDefinition]:
        """Return ToolDefinitions for all registered tools."""
        return [func._tool_definition for func in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a sync tool by name with arguments."""
        func = self.get(name)
        return func(**arguments)

    async def aexecute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name with arguments (async-safe)."""
        func = self.get(name)
        original = getattr(func, "_original_func", func)
        if asyncio.iscoroutinefunction(original):
            return await func(**arguments)
        return func(**arguments)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


__all__ = [
    "ToolRegistry",
    "is_tool",
    "tool",
]
