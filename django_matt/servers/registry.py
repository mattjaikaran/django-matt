"""Server backend registry and discovery."""

from __future__ import annotations

from typing import Any

from django_matt.servers.base import ServerBackend


class ServerRegistry:
    """Central registry for server backends."""

    _backends: dict[str, type[ServerBackend]] = {}

    @classmethod
    def register(cls, backend_cls: type[ServerBackend]) -> type[ServerBackend]:
        """Register a backend class by its ``name`` attribute."""
        cls._backends[backend_cls.name] = backend_cls
        return backend_cls

    @classmethod
    def get(cls, name: str) -> ServerBackend:
        """Instantiate and return a backend by name.

        Raises:
            KeyError: If the backend name is not registered.
        """
        cls._ensure_builtins()
        if name not in cls._backends:
            available = ", ".join(sorted(cls._backends))
            raise KeyError(f"Unknown server backend '{name}'. Available: {available}")
        return cls._backends[name]()

    @classmethod
    def list_backends(cls) -> list[tuple[str, bool]]:
        """Return ``[(name, is_available), ...]`` for all registered backends."""
        cls._ensure_builtins()
        result: list[tuple[str, bool]] = []
        for name in sorted(cls._backends):
            instance = cls._backends[name]()
            result.append((name, instance.check_available()))
        return result

    @classmethod
    def get_best_available(cls) -> ServerBackend:
        """Return the first available backend in priority order.

        Priority: granian > robyn > uvicorn (uvicorn is always the fallback).
        """
        cls._ensure_builtins()
        for name in ("granian", "robyn", "uvicorn"):
            if name in cls._backends:
                instance = cls._backends[name]()
                if instance.check_available():
                    return instance
        # Absolute fallback — return uvicorn even if not installed so the
        # caller gets a clear error when they try to start it.
        return cls._backends["uvicorn"]()

    @classmethod
    def _ensure_builtins(cls) -> None:
        """Lazy-register built-in backends on first access."""
        if cls._backends:
            return
        from django_matt.servers.granian_backend import GranianBackend
        from django_matt.servers.robyn_backend import RobynBackend
        from django_matt.servers.uvicorn_backend import UvicornBackend

        cls.register(UvicornBackend)
        cls.register(RobynBackend)
        cls.register(GranianBackend)


def get_backend(name: str | None = None, **kwargs: Any) -> ServerBackend:
    """Convenience factory.

    Args:
        name: Backend name. ``None`` = auto-detect best available.

    Returns:
        Instantiated ServerBackend.
    """
    if name is None:
        return ServerRegistry.get_best_available()
    return ServerRegistry.get(name)
