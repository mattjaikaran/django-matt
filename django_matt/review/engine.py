"""
Review engine — orchestrates analyzers and collects findings.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path

from django_matt.review.analyzers.base import BaseAnalyzer
from django_matt.review.config import ReviewConfig
from django_matt.review.findings import ReviewSummary

# Registry of built-in analyzer names → import paths
_BUILTIN_ANALYZERS: dict[str, str] = {
    "complexity": "django_matt.review.analyzers.complexity.ComplexityAnalyzer",
    "solid": "django_matt.review.analyzers.solid.SolidAnalyzer",
    "django": "django_matt.review.analyzers.django.DjangoBestPracticesAnalyzer",
    "ai_friendly": "django_matt.review.analyzers.ai_friendly.AIFriendlyAnalyzer",
    "security": "django_matt.review.analyzers.security.SecurityAnalyzer",
    "modularity": "django_matt.review.analyzers.modularity.ModularityAnalyzer",
    "performance": "django_matt.review.analyzers.performance.PerformanceAnalyzer",
    "async_safety": "django_matt.review.analyzers.async_safety.AsyncSafetyAnalyzer",
    "n_plus_one": "django_matt.review.analyzers.n_plus_one.NPlusOneAnalyzer",
    "migration_safety": "django_matt.review.analyzers.migration_safety.MigrationSafetyAnalyzer",
    "api_design": "django_matt.review.analyzers.api_design.APIDesignAnalyzer",
}


def _import_analyzer(dotted_path: str) -> type[BaseAnalyzer]:
    """Import an analyzer class from a dotted path."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class ReviewEngine:
    """Orchestrates code review analyzers across a codebase."""

    def __init__(
        self,
        config: ReviewConfig | None = None,
        custom_analyzers: list[BaseAnalyzer] | None = None,
    ) -> None:
        self.config = config or ReviewConfig()
        self._analyzers: list[BaseAnalyzer] = []

        # Load built-in analyzers
        for name in self.config.analyzers:
            if name in _BUILTIN_ANALYZERS:
                cls = _import_analyzer(_BUILTIN_ANALYZERS[name])
                self._analyzers.append(cls(self.config))

        # Add custom analyzers
        if custom_analyzers:
            self._analyzers.extend(custom_analyzers)

    @property
    def analyzers(self) -> list[BaseAnalyzer]:
        return list(self._analyzers)

    def review_file(self, file_path: Path) -> ReviewSummary:
        """Review a single file."""
        return self.review_paths([file_path])

    def review_paths(self, paths: list[Path]) -> ReviewSummary:
        """Review a list of files/directories."""
        summary = ReviewSummary()
        start = time.monotonic()

        # Expand directories into files
        files = self._collect_files(paths)
        summary.files_analyzed = len(files)
        summary.analyzers_run = [a.name for a in self._analyzers]

        for file_path in sorted(files):
            try:
                source = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            try:
                tree = ast.parse(source, filename=str(file_path))
            except SyntaxError:
                continue

            for analyzer in self._analyzers:
                if analyzer.should_skip_file(file_path):
                    continue
                try:
                    findings = analyzer.analyze_file(file_path, tree, source)
                    summary.findings.extend(findings)
                except Exception:
                    # Don't let one analyzer crash the whole run
                    continue

        summary.duration_ms = (time.monotonic() - start) * 1000

        # Deduplicate: same file + line + category = keep highest severity
        summary.findings = self._deduplicate(summary.findings)

        # Sort findings
        if self.config.sort_by == "severity":
            summary.findings.sort(key=lambda f: (-f.severity, f.location.file))
        elif self.config.sort_by == "file":
            summary.findings.sort(key=lambda f: (f.location.file, f.location.line or 0))
        elif self.config.sort_by == "category":
            summary.findings.sort(key=lambda f: (f.category, -f.severity))

        return summary

    def review_directory(self, directory: Path) -> ReviewSummary:
        """Review all Python files in a directory."""
        return self.review_paths([directory])

    @staticmethod
    def _deduplicate(findings: list) -> list:
        """Deduplicate overlapping findings, keeping highest severity.

        Two findings at the same file+line with substantially similar messages
        (from different analyzers/categories) are merged. Findings with distinct
        messages at the same location are preserved.
        """
        from django_matt.review.findings import Finding

        best: dict[tuple, Finding] = {}
        for f in findings:
            # Normalize: strip punctuation and lowercase for fuzzy message matching
            norm_msg = f.message.lower().rstrip(".")
            key = (f.location.file, f.location.line, norm_msg)
            existing = best.get(key)
            if existing is None or f.severity > existing.severity:
                best[key] = f
        return list(best.values())

    def _collect_files(self, paths: list[Path]) -> list[Path]:
        """Expand paths into individual Python files, respecting config filters."""
        files: list[Path] = []
        for path in paths:
            if path.is_file():
                if self.config.should_analyze_file(path):
                    files.append(path)
            elif path.is_dir():
                for py_file in path.rglob("*.py"):
                    if self.config.should_analyze_file(py_file):
                        if str(py_file) not in self.config.ignore_files:
                            files.append(py_file)
        return files
