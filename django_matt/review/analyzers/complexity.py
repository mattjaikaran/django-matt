"""AST-based code complexity analyzer.

Checks cyclomatic complexity, cognitive complexity, function/class length,
nesting depth, parameter count, and return statement count.
"""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import ASTVisitorAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity


class ComplexityAnalyzer(ASTVisitorAnalyzer):
    """Analyzer that detects overly complex code via AST inspection."""

    name = "complexity"
    description = "Checks cyclomatic/cognitive complexity, length, nesting, parameters, and returns"

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        self._findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()
        self._current_class: str | None = None

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                self._check_class(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function(node, class_name=None)

        return self._findings

    def _check_class(self, node: ast.ClassDef) -> None:
        self._check_class_length(node)
        prev = self._current_class
        self._current_class = node.name
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function(child, class_name=node.name)
            elif isinstance(child, ast.ClassDef):
                self._check_class(child)
        self._current_class = prev

    def _check_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, class_name: str | None
    ) -> None:
        name = node.name
        loc = Location(
            file=str(self._file_path),
            line=node.lineno,
            function=name,
            class_name=class_name,
        )

        self._check_cyclomatic(node, loc)
        self._check_cognitive(node, loc)
        self._check_function_length(node, loc)
        self._check_nesting_depth(node, loc)
        self._check_parameters(node, loc)
        self._check_returns(node, loc)

    # ── CX001: Cyclomatic complexity ──────────────────────────────────

    def _cyclomatic_complexity(self, node: ast.AST) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.ExceptHandler,
                    ast.With,
                    ast.AsyncWith,
                    ast.Assert,
                ),
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    def _check_cyclomatic(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, loc: Location
    ) -> None:
        cc = self._cyclomatic_complexity(node)
        threshold = self.config.complexity.max_cyclomatic

        if cc > threshold * 2:
            self._add_finding(
                Finding(
                    rule_id="CX001",
                    message=f"Cyclomatic complexity is {cc} (max {threshold})",
                    severity=Severity.ERROR,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Break this function into smaller helper functions",
                    metadata={"cyclomatic": cc},
                )
            )
        elif cc > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX001",
                    message=f"Cyclomatic complexity is {cc} (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Consider extracting branches into separate functions",
                    metadata={"cyclomatic": cc},
                )
            )

    # ── CX002: Cognitive complexity ───────────────────────────────────

    def _cognitive_complexity(self, node: ast.AST) -> int:
        score = 0

        def _walk(n: ast.AST, depth: int) -> None:
            nonlocal score
            for child in ast.iter_child_nodes(n):
                increment = 0
                nesting_bump = 0

                if isinstance(
                    child,
                    (
                        ast.If,
                        ast.For,
                        ast.AsyncFor,
                        ast.While,
                        ast.ExceptHandler,
                        ast.With,
                        ast.AsyncWith,
                    ),
                ):
                    increment = 1
                    nesting_bump = depth
                elif isinstance(child, ast.BoolOp):
                    increment += len(child.values) - 1

                score += increment + nesting_bump

                if isinstance(
                    child,
                    (
                        ast.If,
                        ast.For,
                        ast.AsyncFor,
                        ast.While,
                        ast.With,
                        ast.AsyncWith,
                        ast.ExceptHandler,
                    ),
                ):
                    _walk(child, depth + 1)
                else:
                    _walk(child, depth)

        _walk(node, 0)
        return score

    def _check_cognitive(self, node: ast.FunctionDef | ast.AsyncFunctionDef, loc: Location) -> None:
        cc = self._cognitive_complexity(node)
        threshold = self.config.complexity.max_cognitive

        if cc > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX002",
                    message=f"Cognitive complexity is {cc} (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Reduce nesting and extract complex conditionals",
                    metadata={"cognitive": cc},
                )
            )

    # ── CX003: Function too long ──────────────────────────────────────

    def _check_function_length(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, loc: Location
    ) -> None:
        end = node.end_lineno or node.lineno
        length = end - node.lineno + 1
        threshold = self.config.complexity.max_function_lines

        if length > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX003",
                    message=f"Function is {length} lines long (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Extract logical sections into helper functions",
                    metadata={"lines": length},
                )
            )

    # ── CX004: Class too long ─────────────────────────────────────────

    def _check_class_length(self, node: ast.ClassDef) -> None:
        end = node.end_lineno or node.lineno
        length = end - node.lineno + 1
        threshold = self.config.complexity.max_class_lines

        if length > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX004",
                    message=f"Class is {length} lines long (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=Location(
                        file=str(self._file_path),
                        line=node.lineno,
                        class_name=node.name,
                    ),
                    suggestion="Split into smaller classes with single responsibilities",
                    metadata={"lines": length},
                )
            )

    # ── CX005: Nesting depth ─────────────────────────────────────────

    def _max_nesting_depth(self, node: ast.AST) -> int:
        max_depth = 0

        def _walk(n: ast.AST, depth: int) -> None:
            nonlocal max_depth
            for child in ast.iter_child_nodes(n):
                if isinstance(
                    child,
                    (
                        ast.If,
                        ast.For,
                        ast.AsyncFor,
                        ast.While,
                        ast.With,
                        ast.AsyncWith,
                        ast.Try,
                        ast.TryStar,
                    ),
                ):
                    new_depth = depth + 1
                    max_depth = max(max_depth, new_depth)
                    _walk(child, new_depth)
                else:
                    _walk(child, depth)

        _walk(node, 0)
        return max_depth

    def _check_nesting_depth(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, loc: Location
    ) -> None:
        depth = self._max_nesting_depth(node)
        threshold = self.config.complexity.max_nesting_depth

        if depth > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX005",
                    message=f"Nesting depth is {depth} (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Use early returns or extract nested blocks",
                    metadata={"nesting_depth": depth},
                )
            )

    # ── CX006: Too many parameters ────────────────────────────────────

    def _check_parameters(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, loc: Location
    ) -> None:
        args = node.args
        count = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
        if args.vararg:
            count += 1
        if args.kwarg:
            count += 1
        # Exclude 'self' and 'cls'
        if args.args and args.args[0].arg in ("self", "cls"):
            count -= 1

        threshold = self.config.complexity.max_parameters

        if count > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX006",
                    message=f"Function has {count} parameters (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Group related parameters into a dataclass or TypedDict",
                    metadata={"parameters": count},
                )
            )

    # ── CX007: Too many return statements ─────────────────────────────

    def _check_returns(self, node: ast.FunctionDef | ast.AsyncFunctionDef, loc: Location) -> None:
        count = sum(1 for child in ast.walk(node) if isinstance(child, ast.Return))
        threshold = self.config.complexity.max_returns

        if count > threshold:
            self._add_finding(
                Finding(
                    rule_id="CX007",
                    message=f"Function has {count} return statements (max {threshold})",
                    severity=Severity.WARNING,
                    category=Category.COMPLEXITY,
                    location=loc,
                    suggestion="Consolidate return paths or extract into smaller functions",
                    metadata={"returns": count},
                )
            )
