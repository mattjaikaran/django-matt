"""AST-based AI-friendliness analyzer.

Scores how consumable code is for LLM/AI tools by checking file size,
function length, type hint coverage, naming clarity, nesting depth,
magic literals, and module docstrings.
"""

from __future__ import annotations

import ast
import keyword
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity

# Single-letter names acceptable in common idioms (loop vars, exception, file handle, coords)
_ACCEPTABLE_SHORT_NAMES: frozenset[str] = frozenset({
    "i", "j", "k", "x", "y", "e", "f", "n", "_",
})

# Common abbreviations that are universally understood
_ACCEPTABLE_ABBREVIATIONS: frozenset[str] = frozenset({
    "id", "db", "pk", "ok", "os", "io", "ip", "ui", "fn", "fs", "qs",
    "re", "ws", "gc", "fd",
})

# Numeric literals that are idiomatic / not magic
_NON_MAGIC_NUMBERS: frozenset[int | float] = frozenset({
    0, 1, -1, 2, 10, 100,
    # Common HTTP status codes
    200, 201, 204, 301, 302, 304, 400, 401, 403, 404, 405, 409, 422, 429, 500, 502, 503,
    # Common math / bit
    0.5, 2.0,
    # Powers of 2
    8, 16, 32, 64, 128, 256, 512, 1024,
})


class AIFriendlyAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that evaluates code for LLM/AI readability and comprehension."""

    name = "ai_friendly"
    description = "Checks file size, naming clarity, type hints, nesting, and magic literals for AI readability"

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()

        self._check_file_length()
        self._check_module_docstring(tree)
        self._check_type_hint_coverage(tree)
        self._check_naming_clarity(tree)

        # Walk the tree for per-function checks
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function_length(node)
                self._check_nesting_depth(node)
                self._check_magic_literals(node)

        return self._findings

    # ── AI001: File too large for LLM context ────────────────────────────

    def _check_file_length(self) -> None:
        num_lines = len(self._source_lines)
        threshold = self.config.ai_friendly.max_file_lines

        if num_lines > threshold:
            self._add_finding(Finding(
                rule_id="AI001",
                message=f"File is {num_lines} lines (max {threshold} for LLM context)",
                severity=Severity.WARNING,
                category=Category.AI_FRIENDLY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Split into smaller, focused modules to fit LLM context windows",
                metadata={"lines": num_lines},
            ))

    # ── AI002: Function too long for LLM comprehension ───────────────────

    def _check_function_length(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        end = node.end_lineno or node.lineno
        length = end - node.lineno + 1
        threshold = self.config.ai_friendly.max_function_lines

        if length > threshold:
            self._add_finding(Finding(
                rule_id="AI002",
                message=f"Function '{node.name}' is {length} lines (max {threshold} for LLM comprehension)",
                severity=Severity.WARNING,
                category=Category.AI_FRIENDLY,
                location=Location(
                    file=str(self._file_path),
                    line=node.lineno,
                    function=node.name,
                ),
                suggestion="Extract helper functions to improve LLM comprehension",
                metadata={"lines": length, "function": node.name},
            ))

    # ── AI003: Low type hint coverage ────────────────────────────────────

    def _check_type_hint_coverage(self, tree: ast.Module) -> None:
        annotated = 0
        total = 0

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Skip dunder methods and test functions — they're less critical
            if node.name.startswith("__") and node.name.endswith("__"):
                continue

            total += 1
            has_return = node.returns is not None

            # Count annotated params (excluding self/cls)
            args = node.args
            all_args = args.posonlyargs + args.args + args.kwonlyargs
            param_count = 0
            param_annotated = 0
            for arg in all_args:
                if arg.arg in ("self", "cls"):
                    continue
                param_count += 1
                if arg.annotation is not None:
                    param_annotated += 1

            if param_count == 0:
                # No params besides self/cls — only return annotation matters
                if has_return:
                    annotated += 1
            else:
                # Both return and params should be annotated
                param_ratio = param_annotated / param_count
                if has_return and param_ratio >= 0.5:
                    annotated += 1

        if total == 0:
            return

        coverage = annotated / total
        threshold = self.config.ai_friendly.min_type_hint_coverage

        if coverage < threshold:
            self._add_finding(Finding(
                rule_id="AI003",
                message=f"Type hint coverage is {coverage:.0%} ({annotated}/{total} functions annotated, min {threshold:.0%})",
                severity=Severity.HINT,
                category=Category.AI_FRIENDLY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Add type annotations to function signatures for better AI inference",
                metadata={"coverage": round(coverage, 2), "annotated": annotated, "total": total},
            ))

    # ── AI004: Poor naming clarity ───────────────────────────────────────

    def _check_naming_clarity(self, tree: ast.Module) -> None:
        clear_names = 0
        total_names = 0

        for node in ast.walk(tree):
            names = self._extract_names(node)
            for name in names:
                if name.startswith("_") and len(name) > 1:
                    # Strip leading underscores for length check
                    check_name = name.lstrip("_")
                else:
                    check_name = name

                if not check_name or check_name == "_":
                    continue

                total_names += 1

                if self._is_clear_name(check_name):
                    clear_names += 1

        if total_names == 0:
            return

        clarity = clear_names / total_names
        threshold = self.config.ai_friendly.min_naming_clarity

        if clarity < threshold:
            self._add_finding(Finding(
                rule_id="AI004",
                message=f"Naming clarity score is {clarity:.0%} (min {threshold:.0%})",
                severity=Severity.HINT,
                category=Category.AI_FRIENDLY,
                location=Location(file=str(self._file_path), line=1),
                suggestion="Use descriptive names; avoid single-letter variables and cryptic abbreviations",
                metadata={"clarity": round(clarity, 2), "clear": clear_names, "total": total_names},
            ))

    def _extract_names(self, node: ast.AST) -> list[str]:
        """Extract user-defined names from an AST node."""
        names: list[str] = []

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not (node.name.startswith("__") and node.name.endswith("__")):
                names.append(node.name)
            # Parameter names
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                if arg.arg not in ("self", "cls"):
                    names.append(arg.arg)

        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)

        elif isinstance(node, ast.ClassDef):
            names.append(node.name)

        return names

    def _is_clear_name(self, name: str) -> bool:
        """Check if a name is descriptive enough for AI comprehension."""
        if name in _ACCEPTABLE_SHORT_NAMES:
            return True
        if name in _ACCEPTABLE_ABBREVIATIONS:
            return True
        if keyword.iskeyword(name) or keyword.issoftkeyword(name):
            return True
        # Names shorter than 3 chars that aren't in the acceptable sets
        if len(name) < 3:
            return False
        return True

    # ── AI005: Deep nesting hurts comprehension ──────────────────────────

    def _check_nesting_depth(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        max_depth = self._max_nesting(node)
        threshold = self.config.ai_friendly.max_nesting_depth

        if max_depth > threshold:
            self._add_finding(Finding(
                rule_id="AI005",
                message=f"Function '{node.name}' has nesting depth {max_depth} (max {threshold})",
                severity=Severity.WARNING,
                category=Category.AI_FRIENDLY,
                location=Location(
                    file=str(self._file_path),
                    line=node.lineno,
                    function=node.name,
                ),
                suggestion="Use early returns or extract nested logic into helper functions",
                metadata={"depth": max_depth, "function": node.name},
            ))

    def _max_nesting(self, node: ast.AST) -> int:
        """Calculate maximum nesting depth inside a function body."""
        max_depth = 0
        _nesting_types = (
            ast.If, ast.For, ast.AsyncFor, ast.While,
            ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler,
        )
        # Include TryStar if available (3.11+)
        if hasattr(ast, "TryStar"):
            _nesting_types = (*_nesting_types, ast.TryStar)

        def _walk(n: ast.AST, depth: int) -> None:
            nonlocal max_depth
            for child in ast.iter_child_nodes(n):
                if isinstance(child, _nesting_types):
                    new_depth = depth + 1
                    max_depth = max(max_depth, new_depth)
                    _walk(child, new_depth)
                else:
                    _walk(child, depth)

        _walk(node, 0)
        return max_depth

    # ── AI006: Magic numbers/strings ─────────────────────────────────────

    def _check_magic_literals(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Detect magic numbers and long strings used in conditionals or assignments."""
        for child in ast.walk(node):
            if not isinstance(child, (ast.If, ast.Compare, ast.Assign, ast.AugAssign, ast.AnnAssign)):
                continue

            for inner in ast.walk(child):
                if isinstance(inner, ast.Constant):
                    if self._is_magic_literal(inner):
                        self._add_finding(Finding(
                            rule_id="AI006",
                            message=f"Magic literal {self._literal_repr(inner.value)} in '{node.name}'",
                            severity=Severity.HINT,
                            category=Category.AI_FRIENDLY,
                            location=Location(
                                file=str(self._file_path),
                                line=inner.lineno,
                                function=node.name,
                            ),
                            suggestion="Extract to a named constant for clarity",
                            metadata={"value": repr(inner.value), "function": node.name},
                        ))

    def _is_magic_literal(self, node: ast.Constant) -> bool:
        """Check if a constant is a 'magic' literal that should be named."""
        value = node.value

        if isinstance(value, bool | type(None)):
            return False

        if isinstance(value, int | float):
            return value not in _NON_MAGIC_NUMBERS

        if isinstance(value, str):
            # Long strings in conditionals are suspicious
            return len(value) > 50

        return False

    def _literal_repr(self, value: object) -> str:
        """Compact repr for finding messages."""
        r = repr(value)
        if len(r) > 40:
            return r[:37] + "..."
        return r

    # ── AI007: Missing module docstring ──────────────────────────────────

    def _check_module_docstring(self, tree: ast.Module) -> None:
        if ast.get_docstring(tree) is not None:
            return

        self._add_finding(Finding(
            rule_id="AI007",
            message="Module has no docstring",
            severity=Severity.INFO,
            category=Category.AI_FRIENDLY,
            location=Location(file=str(self._file_path), line=1),
            suggestion="Add a brief module docstring describing purpose and contents for AI context",
        ))
