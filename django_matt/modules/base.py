from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MattModule:
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
        pass

    async def on_shutdown(self) -> None:
        pass

    def get_urls(self) -> list:
        return []

    def get_middleware(self) -> list[str]:
        return []

    def get_checks(self) -> list:
        return []

    def validate_config(self, config: dict[str, Any]) -> BaseModel | None:
        if self.config_schema is None:
            return None
        return self.config_schema(**config)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version}>"
