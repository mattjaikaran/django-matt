"""
Base codemod classes and result types.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CodemodResult:
    """Result of a single codemod transformation."""

    transformed: str
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 1.0

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0


class Codemod(ABC):
    """Base class for all codemods."""

    name: str = ""
    source_framework: str = ""  # "drf", "ninja", "fastapi"
    description: str = ""

    @abstractmethod
    def detect(self, source: str, filename: str) -> bool:
        """Return True if this codemod applies to the given source."""
        ...

    @abstractmethod
    def transform(self, source: str, filename: str) -> CodemodResult:
        """Transform the source code and return a CodemodResult."""
        ...

    def _parse(self, source: str) -> ast.Module:
        return ast.parse(source)

    def _unparse(self, tree: ast.Module) -> str:
        return ast.unparse(tree)
