from __future__ import annotations

import os
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


class _MaskedStr(str):
    """String subclass that masks its value in repr/str for logging safety."""

    def __repr__(self) -> str:
        return "'***'"

    def __str__(self) -> str:
        return "***"

    @property
    def secret_value(self) -> str:
        return super().__str__()


class SecretField:
    """Pydantic field type that auto-resolves from the secrets manager.

    Usage in a Pydantic model:
        class Settings(BaseModel):
            db_password: SecretField = SecretField(key="DB_PASSWORD")

    The value is masked in repr/str but accessible via .secret_value.
    """

    def __init__(self, key: str, default: str | None = None) -> None:
        self._key = key
        self._default = default

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: "***", info_arg=False
            ),
        )

    @classmethod
    def _validate(cls, value: Any) -> _MaskedStr:
        if isinstance(value, _MaskedStr):
            return value
        if isinstance(value, str):
            return _MaskedStr(value)
        raise ValueError(f"expected str, got {type(value).__name__}")


class _LazySecret:
    """Lazy secret resolver for use in Django settings."""

    def __init__(self, key: str, default: str | None = None, backend: str | None = None) -> None:
        self._key = key
        self._default = default
        self._backend = backend
        self._resolved: str | None = None
        self._is_resolved = False

    def _resolve(self) -> str | None:
        if self._is_resolved:
            return self._resolved

        value = os.environ.get(self._key)
        if value is None:
            value = self._default
        self._resolved = value
        self._is_resolved = True
        return self._resolved

    def __str__(self) -> str:
        value = self._resolve()
        return value if value is not None else ""

    def __repr__(self) -> str:
        return f"secret('{self._key}')"

    def __bool__(self) -> bool:
        return self._resolve() is not None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self._resolve() == other
        if isinstance(other, _LazySecret):
            return self._resolve() == other._resolve()
        return NotImplemented

    def __hash__(self) -> int:
        value = self._resolve()
        return hash(value)

    def __len__(self) -> int:
        value = self._resolve()
        return len(value) if value is not None else 0

    def __add__(self, other: str) -> str:
        return str(self) + other

    def __radd__(self, other: str) -> str:
        return other + str(self)


def secret(key: str, default: str | None = None, backend: str | None = None) -> _LazySecret:
    """Lazy secret resolver for settings.py.

    Usage:
        DATABASE_PASSWORD = secret("DB_PASSWORD", default="devpass")
    """
    return _LazySecret(key=key, default=default, backend=backend)
