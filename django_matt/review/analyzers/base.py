"""
Base analyzer protocol — all analyzers implement this interface.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from pathlib import Path

from django_matt.review.config import ReviewConfig
from django_matt.review.findings import Finding


class BaseAnalyzer(ABC):
    """Base class for code review analyzers."""

    name: str = "base"
    description: str = ""

    def __init__(self, config: ReviewConfig) -> None:
        self.config = config

    @abstractmethod
    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        """Analyze a single file and return findings.

        Args:
            file_path: Path to the file being analyzed.
            tree: Parsed AST of the file.
            source: Raw source code of the file.

        Returns:
            List of findings for this file.
        """
        ...

    def should_skip_file(self, file_path: Path) -> bool:
        """Override to skip specific files for this analyzer."""
        return False


class ASTVisitorAnalyzer(BaseAnalyzer):
    """Base for analyzers that walk the AST with a visitor pattern."""

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()
        self.visit(tree)
        return self._findings

    def visit(self, node: ast.AST) -> None:
        method = f"visit_{type(node).__name__}"
        visitor = getattr(self, method, self.generic_visit)
        visitor(node)

    def generic_visit(self, node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def _add_finding(self, finding: Finding) -> None:
        if self.config.should_report_finding(finding.rule_id, finding.severity):
            self._findings.append(finding)

    def _get_source_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self._source_lines):
            return self._source_lines[lineno - 1]
        return ""
