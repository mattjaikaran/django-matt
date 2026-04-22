"""
Task registry for the native task engine.

Provides centralized registration and discovery of tasks.
"""

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import NativeTask


class TaskRegistry:
    """
    Registry for all native tasks.

    Tasks are automatically registered when decorated with @task.
    Supports multiple registries for testing isolation.
    """

    def __init__(self):
        self._tasks: dict[str, "NativeTask"] = {}

    def register(self, task: "NativeTask") -> None:
        """Register a task."""
        if task.name in self._tasks:
            existing = self._tasks[task.name]
            if existing.func is not task.func:
                raise ValueError(
                    f"Task '{task.name}' is already registered with a different function. "
                    f"Use explicit name= parameter to avoid conflicts."
                )
        self._tasks[task.name] = task

    def unregister(self, name: str) -> None:
        """Unregister a task by name."""
        self._tasks.pop(name, None)

    def get(self, name: str) -> "NativeTask | None":
        """Get a task by name."""
        return self._tasks.get(name)

    def get_or_raise(self, name: str) -> "NativeTask":
        """Get a task by name or raise KeyError."""
        task = self._tasks.get(name)
        if task is None:
            raise KeyError(f"Task '{name}' not found in registry")
        return task

    def all(self) -> dict[str, "NativeTask"]:
        """Get all registered tasks."""
        return self._tasks.copy()

    def names(self) -> list[str]:
        """Get all task names."""
        return list(self._tasks.keys())

    def clear(self) -> None:
        """Clear all registered tasks (useful for testing)."""
        self._tasks.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._tasks

    def __iter__(self) -> Iterator["NativeTask"]:
        return iter(self._tasks.values())

    def __len__(self) -> int:
        return len(self._tasks)

    def __repr__(self) -> str:
        return f"TaskRegistry({len(self._tasks)} tasks)"


# Global task registry
task_registry = TaskRegistry()
