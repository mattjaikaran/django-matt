"""
Codemod engine - orchestrates detection, transformation, and reporting.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from django_matt.codemods.base import Codemod, CodemodResult
from django_matt.codemods.drf import DRFCodemods
from django_matt.codemods.fastapi import FastAPICodemods
from django_matt.codemods.ninja import NinjaCodemods


class CodemodEngine:
    """Orchestrates codemod detection and execution."""

    def __init__(self, extra_codemods: list[Codemod] | None = None) -> None:
        self._codemods: list[Codemod] = []
        self._codemods.extend(DRFCodemods.all())
        self._codemods.extend(NinjaCodemods.all())
        self._codemods.extend(FastAPICodemods.all())
        if extra_codemods:
            self._codemods.extend(extra_codemods)

    @property
    def codemods(self) -> list[Codemod]:
        return list(self._codemods)

    def detect_framework(self, source: str, filename: str = "") -> str | None:
        """Auto-detect the source framework from import statements.

        Returns "drf", "ninja", "fastapi", or None.
        """
        if "rest_framework" in source:
            return "drf"
        if "from ninja" in source or "import ninja" in source:
            return "ninja"
        if "from fastapi" in source or "import fastapi" in source:
            return "fastapi"
        return None

    def detect_framework_directory(self, directory: str | Path) -> str | None:
        """Detect framework across an entire directory."""
        directory = Path(directory)
        counts: dict[str, int] = {"drf": 0, "ninja": 0, "fastapi": 0}

        for py_file in directory.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            try:
                source = py_file.read_text()
                fw = self.detect_framework(source, str(py_file))
                if fw:
                    counts[fw] += 1
            except Exception:
                continue

        if not any(counts.values()):
            return None
        return max(counts, key=counts.get)  # type: ignore[arg-type]

    def get_applicable_codemods(
        self,
        source: str,
        filename: str,
        framework: str | None = None,
    ) -> list[Codemod]:
        """Return codemods that apply to the given source."""
        if framework is None:
            framework = self.detect_framework(source, filename)

        applicable = []
        for codemod in self._codemods:
            if framework and codemod.source_framework != framework:
                continue
            if codemod.detect(source, filename):
                applicable.append(codemod)
        return applicable

    def run(
        self,
        source: str,
        filename: str = "",
        framework: str | None = None,
    ) -> CodemodResult:
        """Run all applicable codemods on a single source string.

        Codemods are applied sequentially; each one transforms the output of
        the previous one. Changes, warnings, and confidence are aggregated.
        """
        codemods = self.get_applicable_codemods(source, filename, framework)

        if not codemods:
            return CodemodResult(transformed=source, confidence=0.0)

        current = source
        all_changes: list[str] = []
        all_warnings: list[str] = []
        min_confidence = 1.0

        for codemod in codemods:
            try:
                result = codemod.transform(current, filename)
                if result.has_changes:
                    current = result.transformed
                    all_changes.extend(result.changes)
                    all_warnings.extend(result.warnings)
                    min_confidence = min(min_confidence, result.confidence)
            except Exception as e:
                all_warnings.append(f"Codemod {codemod.name} failed: {e}")
                min_confidence = min(min_confidence, 0.3)

        if not all_changes:
            return CodemodResult(transformed=source, confidence=0.0)

        return CodemodResult(
            transformed=current,
            changes=all_changes,
            warnings=all_warnings,
            confidence=min_confidence,
        )

    def run_file(
        self,
        file_path: str | Path,
        framework: str | None = None,
        dry_run: bool = True,
    ) -> CodemodResult | None:
        """Run codemods on a single file.

        Args:
            file_path: Path to the Python file.
            framework: Force a specific framework (or auto-detect).
            dry_run: If True, don't write changes back.

        Returns:
            CodemodResult if changes were made, None otherwise.
        """
        file_path = Path(file_path)
        source = file_path.read_text()
        result = self.run(source, str(file_path), framework)

        if not result.has_changes:
            return None

        if not dry_run:
            file_path.write_text(result.transformed)

        return result

    def run_directory(
        self,
        directory: str | Path,
        framework: str | None = None,
        dry_run: bool = True,
        progress_callback: Any = None,
    ) -> dict[str, CodemodResult]:
        """Run codemods on all Python files in a directory.

        Args:
            directory: Root directory to scan.
            framework: Force a specific framework (or auto-detect per file).
            dry_run: If True, don't write changes back.
            progress_callback: Optional callback(file_path, result) per file.

        Returns:
            Dict mapping file paths to their CodemodResults.
        """
        directory = Path(directory)
        results: dict[str, CodemodResult] = {}

        if framework is None:
            framework = self.detect_framework_directory(directory)

        py_files = sorted(directory.rglob("*.py"))
        for py_file in py_files:
            if self._should_skip(py_file):
                continue

            result = self.run_file(py_file, framework, dry_run)
            if result and result.has_changes:
                results[str(py_file)] = result
                if progress_callback:
                    progress_callback(str(py_file), result)

        return results

    def diff(self, source: str, filename: str = "", framework: str | None = None) -> str:
        """Return a unified diff of what would change."""
        result = self.run(source, filename, framework)
        if not result.has_changes:
            return ""

        original_lines = source.splitlines(keepends=True)
        transformed_lines = result.transformed.splitlines(keepends=True)

        return "".join(
            difflib.unified_diff(
                original_lines,
                transformed_lines,
                fromfile=f"a/{filename}" if filename else "a/source.py",
                tofile=f"b/{filename}" if filename else "b/source.py",
            )
        )

    def generate_report(self, results: dict[str, CodemodResult]) -> str:
        """Generate a summary report from batch results."""
        if not results:
            return "No changes detected."

        lines: list[str] = []
        lines.append("# Codemod Migration Report")
        lines.append("")
        lines.append(f"**Files modified:** {len(results)}")

        total_changes = sum(len(r.changes) for r in results.values())
        total_warnings = sum(len(r.warnings) for r in results.values())
        avg_confidence = sum(r.confidence for r in results.values()) / len(results)

        lines.append(f"**Total changes:** {total_changes}")
        lines.append(f"**Warnings:** {total_warnings}")
        lines.append(f"**Average confidence:** {avg_confidence:.0%}")
        lines.append("")

        for file_path, result in sorted(results.items()):
            lines.append(f"## {file_path}")
            lines.append(f"Confidence: {result.confidence:.0%}")
            lines.append("")

            if result.changes:
                lines.append("### Changes")
                for change in result.changes:
                    lines.append(f"- {change}")
                lines.append("")

            if result.warnings:
                lines.append("### Warnings (manual review needed)")
                for warning in result.warnings:
                    lines.append(f"- {warning}")
                lines.append("")

        return "\n".join(lines)

    def _should_skip(self, path: Path) -> bool:
        """Check if a file should be skipped."""
        parts = path.parts
        skip_dirs = {"__pycache__", "migrations", ".git", "node_modules", ".venv", "venv"}
        return bool(skip_dirs & set(parts))
