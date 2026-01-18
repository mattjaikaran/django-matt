"""
Component registry for Livewire components.

Manages registration and lookup of component classes.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_matt.livewire.component import LiveComponent


class ComponentRegistry:
    """
    Registry for Livewire components.

    Usage:
        from django_matt.livewire import registry

        # Register a component
        @registry.register("counter")
        class Counter(LiveComponent):
            ...

        # Or register directly
        registry.register_class("counter", Counter)

        # Lookup
        CounterClass = registry.get("counter")
    """

    def __init__(self):
        self._components: dict[str, type[LiveComponent]] = {}
        self._aliases: dict[str, str] = {}

    def register(self, name: str, aliases: list[str] | None = None):
        """
        Decorator to register a component class.

        Usage:
            @registry.register("todo-list", aliases=["todos"])
            class TodoList(LiveComponent):
                ...
        """

        def decorator(cls: type["LiveComponent"]) -> type["LiveComponent"]:
            self.register_class(name, cls, aliases=aliases)
            return cls

        return decorator

    def register_class(
        self,
        name: str,
        cls: type["LiveComponent"],
        aliases: list[str] | None = None,
    ):
        """Register a component class directly."""
        self._components[name] = cls

        if aliases:
            for alias in aliases:
                self._aliases[alias] = name

    def get(self, name: str) -> type["LiveComponent"] | None:
        """Get a component class by name."""
        # Check aliases first
        if name in self._aliases:
            name = self._aliases[name]

        return self._components.get(name)

    def create(self, name: str, **kwargs) -> "LiveComponent":
        """Create a component instance by name."""
        cls = self.get(name)
        if cls is None:
            raise ValueError(f"Unknown component: {name}")
        return cls(**kwargs)

    def list(self) -> list[str]:
        """List all registered component names."""
        return list(self._components.keys())

    def unregister(self, name: str):
        """Unregister a component."""
        if name in self._components:
            del self._components[name]

        # Remove aliases pointing to this name
        self._aliases = {k: v for k, v in self._aliases.items() if v != name}

    def clear(self):
        """Clear all registrations."""
        self._components.clear()
        self._aliases.clear()

    def __contains__(self, name: str) -> bool:
        """Check if a component is registered."""
        if name in self._aliases:
            name = self._aliases[name]
        return name in self._components


# Global registry instance
registry = ComponentRegistry()


def register_component(name: str, aliases: list[str] | None = None):
    """Convenience decorator for registering components."""
    return registry.register(name, aliases=aliases)


__all__ = [
    "ComponentRegistry",
    "register_component",
    "registry",
]
