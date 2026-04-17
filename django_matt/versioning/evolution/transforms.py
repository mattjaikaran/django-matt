"""Schema transforms — bidirectional transformations for API evolution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SchemaTransform(ABC):
    """Base class for bidirectional schema transforms."""

    @abstractmethod
    def forward(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform data from old schema to new schema."""
        ...

    @abstractmethod
    def backward(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform data from new schema to old schema."""
        ...


class RenameField(SchemaTransform):
    """Rename a field: old clients see the old name, new clients the new name."""

    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def forward(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.old in data:
            data[self.new] = data.pop(self.old)
        return data

    def backward(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.new in data:
            data[self.old] = data.pop(self.new)
        return data


class AddField(SchemaTransform):
    """A field was added in the new version. Old clients don't see it."""

    def __init__(self, field: str, default: Any = None) -> None:
        self.field = field
        self.default = default

    def forward(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.field not in data:
            data[self.field] = self.default
        return data

    def backward(self, data: dict[str, Any]) -> dict[str, Any]:
        data.pop(self.field, None)
        return data


class RemoveField(SchemaTransform):
    """A field was removed in the new version. Old clients still see it."""

    def __init__(self, field: str, default: Any = None) -> None:
        self.field = field
        self.default = default

    def forward(self, data: dict[str, Any]) -> dict[str, Any]:
        data.pop(self.field, None)
        return data

    def backward(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.field not in data:
            data[self.field] = self.default
        return data


class TransformChain:
    """Chain of transforms applied in sequence."""

    def __init__(self, transforms: list[SchemaTransform] | None = None) -> None:
        self.transforms = transforms or []

    def forward(self, data: dict[str, Any]) -> dict[str, Any]:
        for t in self.transforms:
            data = t.forward(data)
        return data

    def backward(self, data: dict[str, Any]) -> dict[str, Any]:
        for t in reversed(self.transforms):
            data = t.backward(data)
        return data

    def add(self, transform: SchemaTransform) -> TransformChain:
        self.transforms.append(transform)
        return self
