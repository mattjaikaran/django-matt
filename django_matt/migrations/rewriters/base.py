"""Base class for migration rewriters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


@dataclass
class RewriteStep:
    """A single step in a safe migration rewrite."""

    description: str
    sql: str | None = None
    operation_class: str | None = None
    operation_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class RewriteResult:
    """Result of rewriting an unsafe migration operation."""

    original_description: str
    steps: list[RewriteStep]
    explanation: str


class BaseRewriter(ABC):
    """Base class for migration operation rewriters."""

    @abstractmethod
    def can_handle(self, operation: Any) -> bool:
        """Return True if this rewriter can handle the given operation."""
        ...

    @abstractmethod
    def rewrite(self, operation: Any, app_label: str, model_name: str) -> RewriteResult:
        """Rewrite an unsafe operation into safe steps."""
        ...
