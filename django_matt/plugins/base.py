from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django_matt.api import MattAPI

logger = logging.getLogger("django_matt.plugins")


class CheckMessage:
    """Simple check message for plugin health checks."""

    def __init__(
        self, level: str, msg: str, hint: str = "", obj: Any = None
    ) -> None:
        self.level = level
        self.msg = msg
        self.hint = hint
        self.obj = obj

    def __repr__(self) -> str:
        return f"<CheckMessage level={self.level!r} msg={self.msg!r}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CheckMessage):
            return NotImplemented
        return self.level == other.level and self.msg == other.msg

    def __hash__(self) -> int:
        return hash((self.level, self.msg))

    def is_serious(self) -> bool:
        return self.level in ("error", "critical")


class MattPlugin(ABC):
    """Base class for all django-matt plugins."""

    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    django_matt_version: str = "0.1.0"
    dependencies: list[str] = []
    settings_prefix: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower().removesuffix("plugin")

    @abstractmethod
    def setup(self, api: MattAPI) -> None:
        """Called when the plugin is loaded into an API instance."""
        ...

    def on_startup(self) -> None:
        """Called when the application starts."""

    async def on_startup_async(self) -> None:
        """Async variant of on_startup."""

    def on_shutdown(self) -> None:
        """Called when the application shuts down."""

    async def on_shutdown_async(self) -> None:
        """Async variant of on_shutdown."""

    def get_urls(self) -> list:
        """Return URL patterns contributed by this plugin."""
        return []

    def get_middleware(self) -> list:
        """Return middleware classes contributed by this plugin."""
        return []

    def get_settings_schema(self) -> dict[str, Any]:
        """Return JSON Schema for this plugin's settings."""
        return {}

    def check(self) -> list[CheckMessage]:
        """Run health checks for this plugin."""
        return []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
