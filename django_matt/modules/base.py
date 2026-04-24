"""Base module class defining the lifecycle and configuration interface for plugins."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MattModule:
    """Base class for django_matt plugins with lifecycle hooks and configuration."""
    name: str = ""
    version: str = "0.1.0"
    dependencies: list[str] = []
    config_namespace: str | None = None
    config_schema: type[BaseModel] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower().removesuffix("module")

    async def on_ready(self) -> None:
        """Called when the module is loaded and ready."""

    async def on_shutdown(self) -> None:
        """Called when the module is being unloaded."""

    def get_urls(self) -> list:
        """Return URL patterns contributed by this module."""
        return []

    def get_middleware(self) -> list[str]:
        """Return middleware classes contributed by this module."""
        return []

    def get_checks(self) -> list:
        """Return health checks contributed by this module."""
        return []

    def validate_config(self, config: dict[str, Any]) -> BaseModel | None:
        """Validate configuration against the module's config schema."""
        if self.config_schema is None:
            return None
        return self.config_schema(**config)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
