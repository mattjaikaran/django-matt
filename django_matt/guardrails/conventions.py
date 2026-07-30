"""
Convention check engine for django-matt projects.

Detects convention violations across 10 categories using AST analysis.
Produces a scored ConventionReport with per-category breakdowns.

Usage:
    >>> from django_matt.guardrails.conventions import ConventionChecker, ConventionCategory
    >>> checker = ConventionChecker(Path("/path/to/project"))
    >>> report = checker.check()
    >>> print(report.formatted_report())
    >>> if not report.passed:
    ...     for finding in report.findings:
    ...         print(f"  {finding.file}:{finding.line} - {finding.message}")
"""

from __future__ import annotations

import ast
import enum
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    pass

logger = logging.getLogger("django_matt.guardrails.conventions")

# ── Skip directories (never scanned) ──────────────────────────────────────────

_SKIP_DIRS: frozenset[str] = frozenset({
    ".venv", "venv", "env", "node_modules", ".git", "__pycache__",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "site-packages",
    "dist", "build", ".tox", "eggs", "migrations",
})

# File name patterns that identify controller files
_CONTROLLER_NAMES: frozenset[str] = frozenset({
    "controller", "controllers", "views", "viewset", "view",
})

# File name patterns that identify service files
_SERVICE_NAMES: frozenset[str] = frozenset({
    "service", "services", "repository", "repositories",
})

# Django ORM methods that indicate direct model access
_ORM_METHODS: frozenset[str] = frozenset({
    "objects", "filter", "get", "create", "update", "delete",
    "all", "exclude", "annotate", "aggregate", "select_related",
    "prefetch_related", "order_by", "values", "values_list",
    "first", "last", "exists", "count", "bulk_create", "bulk_update",
    "get_or_create", "update_or_create",
})

# Known schema/BaseModel superclass names
_SCHEMA_BASES: frozenset[str] = frozenset({
    "BaseModel", "Schema", "PydanticModel",
})

# Soft-delete mixin names
_SOFT_DELETE_MIXINS: frozenset[str] = frozenset({
    "SoftDeleteMixin", "SoftDeletable",
})


class ConventionCategory(enum.StrEnum):
    """Categories of convention violations."""

    ERROR_HANDLING = "error_handling"
    CONTROLLER_PATTERNS = "controller_patterns"
    SERVICE_LAYER = "service_layer"
    TYPE_HINTS = "type_hints"
    DOCSTRINGS = "docstrings"
    ORM_ACCESS = "orm_access"
    IMPORT_STYLE = "import_style"
    SOFT_DELETE = "soft_delete"
    QUERY_OPTIMIZATION = "query_optimization"
    SCHEMA_USAGE = "schema_usage"


@dataclass
class ConventionFinding:
    """A single convention violation detected in a file."""

    file: str
    line: int
    category: ConventionCategory
    message: str
    deduction: int  # 1-3 points deducted

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "category": str(self.category),
            "message": self.message,
            "deduction": self.deduction,
        }


@dataclass
class ConventionReport:
    """Report produced by ConventionChecker.check()."""

    total_score: int
    category_scores: dict[ConventionCategory, int]
    findings: list[ConventionFinding] = field(default_factory=list)
    max_deduction_per_category: int = 10

    @property
    def passed(self) -> bool:
        """Convention check passes if score >= 70."""
        return self.total_score >= 70

    @property
    def grade(self) -> str:
        """Letter grade based on total score."""
        if self.total_score >= 90:
            return "A"
        if self.total_score >= 80:
            return "B"
        if self.total_score >= 70:
            return "C"
        if self.total_score >= 60:
            return "D"
        return "F"

    def formatted_report(self) -> str:
        """Rich-formatted table report of convention findings.

        Returns a str rendered by Rich if available, otherwise a plain-text
        fallback.
        """
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel

            console = Console()
            output_lines: list[str] = []

            # Header panel
            status_color = "green" if self.passed else "red"
            header = Panel(
                f"[bold]Convention Check Report[/bold]\n"
                f"Score: [bold {status_color}]{self.total_score}/100[/bold {status_color}]  "
                f"Grade: [bold {status_color}]{self.grade}[/bold {status_color}]  "
                f"Status: [bold {status_color}]{'PASSED' if self.passed else 'FAILED'}[/bold {status_color}]",
                border_style=status_color,
            )

            # Capture Rich output
            with console.capture() as capture:
                console.print(header)

                # Category scores table
                cat_table = Table(title="Category Scores", show_header=True, header_style="bold")
                cat_table.add_column("Category", style="dim")
                cat_table.add_column("Score", justify="right")
                cat_table.add_column("Deductions", justify="right")
                cat_table.add_column("Status")

                for cat in ConventionCategory:
                    score = self.category_scores.get(cat, 10)
                    deductions = self.max_deduction_per_category - score
                    cat_status = (
                        "[green]✓[/green]" if deductions == 0
                        else f"[yellow]{deductions} issues[/yellow]"
                    )
                    cat_table.add_row(
                        str(cat),
                        f"{score}/10",
                        str(deductions),
                        cat_status,
                    )

                console.print(cat_table)
                console.print()

                # Findings table (if any)
                if self.findings:
                    find_table = Table(
                        title=f"Violations ({len(self.findings)} total)",
                        show_header=True,
                        header_style="bold",
                        show_lines=False,
                    )
                    find_table.add_column("File", style="dim", max_width=40)
                    find_table.add_column("Line", justify="right")
                    find_table.add_column("Category", style="cyan")
                    find_table.add_column("Deduction", justify="center")
                    find_table.add_column("Message")

                    for f in self.findings:
                        find_table.add_row(
                            f.file,
                            str(f.line),
                            str(f.category),
                            str(f.deduction),
                            f.message,
                        )

                    console.print(find_table)

            output_lines.append(capture.get())
            return "\n".join(output_lines)

        except ImportError:
            return self._plain_text_report()

    def _plain_text_report(self) -> str:
        """Plain-text report fallback when Rich is not available."""
        lines: list[str] = []
        status = "PASSED" if self.passed else "FAILED"
        lines.append("=" * 60)
        lines.append(f"  Convention Check Report")
        lines.append(f"  Score: {self.total_score}/100  Grade: {self.grade}  Status: {status}")
        lines.append("=" * 60)
        lines.append("")
        lines.append("  Category Scores:")
        for cat in ConventionCategory:
            score = self.category_scores.get(cat, 10)
            deductions = self.max_deduction_per_category - score
            flag = "✓" if deductions == 0 else f"{deductions} issues"
            lines.append(f"    {cat.value:<25s} {score:>3d}/10  {flag}")
        lines.append("")
        if self.findings:
            lines.append(f"  Violations ({len(self.findings)} total):")
            for f in self.findings:
                lines.append(f"    {f.file}:{f.line}  [{f.category.value}] {f.message}  (-{f.deduction})")
        else:
            lines.append("  No violations found.")
        lines.append("")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize report to JSON string."""
        return json.dumps({
            "total_score": self.total_score,
            "grade": self.grade,
            "passed": self.passed,
            "category_scores": {str(k): v for k, v in self.category_scores.items()},
            "findings": [f.to_dict() for f in self.findings],
        }, indent=2)


class ConventionChecker:
    """Scans a project for convention violations using AST analysis.

    Usage:
        >>> checker = ConventionChecker(Path("/path/to/project"))
        >>> report = checker.check()
        >>> print(report.formatted_report())
    """

    # Each category has a max deduction; deductions per finding are 1-3.
    MAX_DEDUCTION_PER_CATEGORY: ClassVar[int] = 10

    def __init__(
        self,
        project_path: Path,
        categories: set[ConventionCategory] | None = None,
    ) -> None:
        self.project_path = project_path.resolve()
        self.categories = categories or set(ConventionCategory)
        self._findings: list[ConventionFinding] = []
        self._deductions: dict[ConventionCategory, int] = field(default_factory=dict)
        # Track project-wide observations needed for contextual checks
        self._project_has_soft_delete = False
        self._project_model_count = 0
        self._project_service_count = 0

    def check(self) -> ConventionReport:
        """Run all enabled convention checks and produce a report.

        Returns:
            ConventionReport with total score, per-category scores, and findings.
        """
        self._findings = []
        self._deductions = {cat: 0 for cat in ConventionCategory}
        self._project_has_soft_delete = False
        self._project_model_count = 0
        self._project_service_count = 0

        # Phase 1: Gather project-wide context (model classes, soft-delete usage, etc.)
        self._gather_project_context()

        # Phase 2: Scan each Python file
        for py_file in self._iter_python_files():
            tree = self._parse_file(py_file)
            if tree is None:
                continue

            rel_path = str(py_file.relative_to(self.project_path))

            # Run each enabled check
            if ConventionCategory.ERROR_HANDLING in self.categories:
                self._check_error_handling(tree, rel_path)
            if ConventionCategory.CONTROLLER_PATTERNS in self.categories:
                self._check_controller_patterns(tree, rel_path)
            if ConventionCategory.SERVICE_LAYER in self.categories:
                self._check_service_layer(tree, rel_path)
            if ConventionCategory.TYPE_HINTS in self.categories:
                self._check_type_hints(tree, rel_path)
            if ConventionCategory.DOCSTRINGS in self.categories:
                self._check_docstrings(tree, rel_path)
            if ConventionCategory.ORM_ACCESS in self.categories:
                self._check_orm_access(tree, rel_path)
            if ConventionCategory.IMPORT_STYLE in self.categories:
                self._check_import_style(tree, rel_path)
            if ConventionCategory.SOFT_DELETE in self.categories:
                self._check_soft_delete(tree, rel_path)
            if ConventionCategory.QUERY_OPTIMIZATION in self.categories:
                self._check_query_optimization(tree, rel_path)
            if ConventionCategory.SCHEMA_USAGE in self.categories:
                self._check_schema_usage(tree, rel_path)

        # Compute category scores (each starts at max, deductions cap at max)
        category_scores: dict[ConventionCategory, int] = {}
        for cat in ConventionCategory:
            deductions = min(self._deductions.get(cat, 0), self.MAX_DEDUCTION_PER_CATEGORY)
            category_scores[cat] = self.MAX_DEDUCTION_PER_CATEGORY - deductions

        # Total score: start at 100, subtract deductions across all categories
        total_deductions = sum(
            self.MAX_DEDUCTION_PER_CATEGORY - score
            for score in category_scores.values()
        )
        total_score = max(0, 100 - total_deductions)

        return ConventionReport(
            total_score=total_score,
            category_scores=category_scores,
            findings=self._findings,
            max_deduction_per_category=self.MAX_DEDUCTION_PER_CATEGORY,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _iter_python_files(self) -> list[Path]:
        """Collect all .py files in the project (exclude known skip dirs)."""
        files: list[Path] = []
        for entry in self.project_path.rglob("*.py"):
            parts = set(entry.parts)
            if parts & _SKIP_DIRS:
                continue
            # Skip test directories
            if "tests" in parts or "test" in parts:
                continue
            files.append(entry)
        return sorted(files)

    def _parse_file(self, path: Path) -> ast.Module | None:
        """Parse a Python file into an AST, returning None on failure."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return ast.parse(content, filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as e:
            logger.debug("Skipping %s: %s", path, e)
            return None

    def _add_finding(
        self,
        file: str,
        line: int,
        category: ConventionCategory,
        message: str,
        deduction: int,
    ) -> None:
        """Record a finding and accumulate deductions (capped per category)."""
        current = self._deductions.get(category, 0)
        if current >= self.MAX_DEDUCTION_PER_CATEGORY:
            return
        effective = min(deduction, self.MAX_DEDUCTION_PER_CATEGORY - current)
        self._deductions[category] = current + effective
        self._findings.append(
            ConventionFinding(
                file=file,
                line=line,
                category=category,
                message=message,
                deduction=effective,
            )
        )

    def _is_controller_file(self, path: str) -> bool:
        """Check if a file path suggests it's a controller file."""
        name = Path(path).stem.lower()
        return any(kw in name for kw in _CONTROLLER_NAMES)

    def _is_service_file(self, path: str) -> bool:
        """Check if a file path suggests it's a service file."""
        name = Path(path).stem.lower()
        return any(kw in name for kw in _SERVICE_NAMES)

    def _gather_project_context(self) -> None:
        """Scan all files to gather project-wide context (model classes, soft delete usage)."""
        for py_file in self._iter_python_files():
            tree = self._parse_file(py_file)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if this class inherits from SoftDeleteMixin
                    for base in node.bases:
                        base_name = self._get_name(base)
                        if base_name in _SOFT_DELETE_MIXINS:
                            self._project_has_soft_delete = True
                        if base_name == "Model" or (
                            isinstance(base, ast.Attribute)
                            and self._get_name(base) == "Model"
                        ):
                            self._project_model_count += 1

                    # Count service classes (inheriting from CRUDService, BaseService)
                    for base in node.bases:
                        base_name = self._get_name(base)
                        if base_name in ("CRUDService", "BaseService", "Service"):
                            self._project_service_count += 1

    @staticmethod
    def _get_name(node: ast.expr) -> str | None:
        """Extract a simple name from an AST expression node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    # ── Checkers ───────────────────────────────────────────────────────────────

    def _check_error_handling(self, tree: ast.Module, file: str) -> None:
        """Detect inconsistent error handling patterns.

        Checks:
        - Bare except: clauses (deduction 3)
        - Catching BaseException instead of ServiceError (deduction 2)
        - Mixed except Exception and except ServiceError in same function (deduction 1)
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    # Bare except
                    if handler.type is None:
                        self._add_finding(
                            file, handler.lineno, ConventionCategory.ERROR_HANDLING,
                            "Bare 'except:' clause — use specific exception types",
                            deduction=3,
                        )
                    else:
                        type_name = self._get_name(handler.type)
                        if type_name == "BaseException":
                            self._add_finding(
                                file, handler.lineno, ConventionCategory.ERROR_HANDLING,
                                "Catching 'BaseException' — prefer ServiceError or more specific types",
                                deduction=2,
                            )

        # Check for mixed pattern: except Exception + except ServiceError in same file
        # Use a coarser file-level check
        has_generic_except = False
        has_service_error = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type:
                type_name = self._get_name(node.type)
                if type_name in ("Exception",):
                    has_generic_except = True
                if type_name in ("ServiceError", "APIError", "ValidationError"):
                    has_service_error = True

        if has_generic_except and has_service_error:
            self._add_finding(
                file, 1, ConventionCategory.ERROR_HANDLING,
                "Mixed error handling patterns: using both generic 'Exception' and framework error types",
                deduction=1,
            )

    def _check_controller_patterns(self, tree: ast.Module, file: str) -> None:
        """Detect mixing function-based and class-based controllers in the same file.

        Only applies to controller files.
        """
        if not self._is_controller_file(file):
            return

        has_function_controllers = False
        has_class_controllers = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                # Check if this is a function-based controller (has route decorators)
                for dec in node.decorator_list:
                    dec_name = self._get_name(dec)
                    if dec_name in ("get", "post", "put", "patch", "delete", "route", "api_view"):
                        has_function_controllers = True
                        break

            if isinstance(node, ast.ClassDef):
                # Check if this is a controller class
                for base in node.bases:
                    base_name = self._get_name(base)
                    if base_name in ("Controller", "APIController", "BaseController", "ViewSet"):
                        has_class_controllers = True
                        break

        if has_function_controllers and has_class_controllers:
            self._add_finding(
                file, 1, ConventionCategory.CONTROLLER_PATTERNS,
                "Mixing function-based and class-based controllers — prefer one consistent pattern",
                deduction=2,
            )

    def _check_service_layer(self, tree: ast.Module, file: str) -> None:
        """Detect controllers with direct ORM access that should use a service layer."""
        if not self._is_controller_file(file):
            return

        # If the project has no services at all, don't flag this
        if self._project_service_count == 0:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = self._get_name(base)
                    if base_name not in ("Controller", "APIController", "BaseController", "ViewSet"):
                        continue

                    # Found a controller class — check for direct ORM in methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if self._has_direct_orm(item):
                                self._add_finding(
                                    file, item.lineno, ConventionCategory.SERVICE_LAYER,
                                    f"Controller method '{item.name}' has direct ORM access — "
                                    "use a service layer instead",
                                    deduction=2,
                                )

    def _has_direct_orm(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function AST contains direct ORM attribute access."""
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                # Match patterns like Model.objects, Model.objects.filter(), etc.
                if child.attr in _ORM_METHODS and child.attr not in (
                    "_meta", "_state", "_default_manager"
                ):
                    # Exclude self.service.X patterns
                    if isinstance(child.value, ast.Attribute) and child.value.attr == "service":
                        continue
                    return True
        return False

    def _check_type_hints(self, tree: ast.Module, file: str) -> None:
        """Detect functions missing type hints.

        Checks:
        - Public functions without return type annotation (deduction 1)
        - Public functions with untyped parameters (deduction 1, up to 2 per file)
        """
        missing_return_count = 0
        missing_param_count = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                # Skip special methods
                if node.name in ("__init__", "__str__", "__repr__", "__call__"):
                    continue

                # Check return type
                if node.returns is None:
                    missing_return_count += 1
                    if missing_return_count <= 3:  # Cap per-file findings
                        self._add_finding(
                            file, node.lineno, ConventionCategory.TYPE_HINTS,
                            f"Function '{node.name}' is missing return type annotation",
                            deduction=1,
                        )

                # Check parameter types
                untyped_params: list[str] = []
                for arg in node.args.args:
                    if arg.arg == "self" or arg.arg == "cls":
                        continue
                    if arg.annotation is None:
                        untyped_params.append(arg.arg)

                if untyped_params and missing_param_count < 3:
                    missing_param_count += 1
                    params_str = ", ".join(untyped_params[:3])
                    if len(untyped_params) > 3:
                        params_str += f" (+{len(untyped_params) - 3})"
                    self._add_finding(
                        file, node.lineno, ConventionCategory.TYPE_HINTS,
                        f"Function '{node.name}' has untyped parameters: {params_str}",
                        deduction=1,
                    )

    def _check_docstrings(self, tree: ast.Module, file: str) -> None:
        """Detect public functions and classes without docstrings."""
        missing_funcs = 0
        missing_classes = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                if node.name in ("__init__", "__str__", "__repr__", "__call__"):
                    continue
                if ast.get_docstring(node) is None:
                    missing_funcs += 1
                    if missing_funcs <= 5:
                        self._add_finding(
                            file, node.lineno, ConventionCategory.DOCSTRINGS,
                            f"Public function '{node.name}' is missing a docstring",
                            deduction=1,
                        )

            if isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                if ast.get_docstring(node) is None:
                    missing_classes += 1
                    if missing_classes <= 3:
                        self._add_finding(
                            file, node.lineno, ConventionCategory.DOCSTRINGS,
                            f"Public class '{node.name}' is missing a docstring",
                            deduction=1,
                        )

    def _check_orm_access(self, tree: ast.Module, file: str) -> None:
        """Detect direct ORM access in controller files.

        Looks for patterns like Model.objects.filter/get/create in controller code.
        """
        if not self._is_controller_file(file):
            return

        orm_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if node.attr == "objects":
                    # Found a Model.objects pattern
                    orm_count += 1
                    if orm_count <= 3:
                        self._add_finding(
                            file, node.lineno, ConventionCategory.ORM_ACCESS,
                            "Direct ORM access (Model.objects) in controller — use service layer",
                            deduction=2,
                        )

    def _check_import_style(self, tree: ast.Module, file: str) -> None:
        """Detect mixing absolute and relative imports in the same file."""
        has_absolute = False
        has_relative = False

        # Only look at imports that are within the project (not third-party)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    has_relative = True
                elif node.module and not node.module.startswith("."):
                    # Absolute import — check if it's a project import
                    top = node.module.split(".")[0]
                    if top in ("django_matt", "django") or top in self._get_project_package_names():
                        has_absolute = True

        if has_absolute and has_relative:
            self._add_finding(
                file, 1, ConventionCategory.IMPORT_STYLE,
                "Mixing absolute and relative imports — prefer one consistent style",
                deduction=1,
            )

    def _get_project_package_names(self) -> set[str]:
        """Get top-level package names in the project (excluding django_matt)."""
        names: set[str] = set()
        for entry in self.project_path.iterdir():
            if entry.is_dir() and not entry.name.startswith(".") and not entry.name.startswith("_"):
                if (entry / "__init__.py").exists():
                    names.add(entry.name)
        return names

    def _check_soft_delete(self, tree: ast.Module, file: str) -> None:
        """Detect models that don't use SoftDeleteMixin when other models in the project do.

        Only flags if the project has at least one model using SoftDeleteMixin
        and at least 3 models total.
        """
        if not self._project_has_soft_delete or self._project_model_count < 3:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if this is a Model subclass
                is_model = False
                has_soft_delete = False
                for base in node.bases:
                    base_name = self._get_name(base)
                    if base_name == "Model" or (
                        isinstance(base, ast.Attribute) and base.attr == "Model"
                    ):
                        is_model = True

                # Check if it already has SoftDeleteMixin
                for base in node.bases:
                    base_name = self._get_name(base)
                    if base_name in _SOFT_DELETE_MIXINS:
                        has_soft_delete = True

                if is_model and not has_soft_delete:
                    self._add_finding(
                        file, node.lineno, ConventionCategory.SOFT_DELETE,
                        f"Model '{node.name}' does not use SoftDeleteMixin — "
                        "consider soft-delete for consistency with project conventions",
                        deduction=2,
                    )

    def _check_query_optimization(self, tree: ast.Module, file: str) -> None:
        """Detect potential N+1 query patterns.

        Looks for:
        - for loops over querysets where items access related objects
          without select_related/prefetch_related
        - querysets used in loops without optimization hints
        """
        # Find for loops that iterate over querysets
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.AsyncFor)):
                # Check if the iterable looks like a queryset access
                if self._is_queryset_loop(node, tree):
                    self._add_finding(
                        file, node.lineno, ConventionCategory.QUERY_OPTIMIZATION,
                        "Potential N+1 query: queryset loop without visible "
                        "select_related/prefetch_related optimization",
                        deduction=3,
                    )

    def _is_queryset_loop(self, for_node: ast.For | ast.AsyncFor, tree: ast.Module) -> bool:
        """Check if a for-loop iterates over something that looks like a queryset.

        Heuristics:
        - iter is an attribute access ending in .all() or .filter()
        - iter variable name contains 'queryset' or 'qs'
        """
        iter_node = for_node.iter

        # Check for .all() or .filter() calls
        if isinstance(iter_node, ast.Call):
            if isinstance(iter_node.func, ast.Attribute):
                if iter_node.func.attr in ("all", "filter", "exclude", "annotate"):
                    # Check if select_related/prefetch_related was called in the chain
                    chain = self._collect_method_chain(iter_node.func.value)
                    if not chain.intersection({"select_related", "prefetch_related"}):
                        return True
            return False

        # Check for variable names that suggest querysets
        if isinstance(iter_node, ast.Name):
            if "queryset" in iter_node.id.lower() or "qs" == iter_node.id:
                # Heuristic: look for select_related/prefetch_related in the function scope
                fn = self._enclosing_function(for_node, tree)
                if fn and not self._has_optimization_in_scope(fn):
                    return True

        return False

    @staticmethod
    def _collect_method_chain(node: ast.expr) -> set[str]:
        """Collect method names from a chained attribute access.

        For `Model.objects.filter(x).select_related(y)`, collects {'filter', 'select_related'}.
        """
        methods: set[str] = set()
        current = node
        while isinstance(current, ast.Call):
            if isinstance(current.func, ast.Attribute):
                methods.add(current.func.attr)
                current = current.func.value
            else:
                break
        return methods

    @staticmethod
    def _enclosing_function(
        target: ast.AST, tree: ast.Module
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """Find the enclosing function of an AST node."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    node.lineno <= target.lineno
                    and (node.end_lineno or float("inf")) >= (target.end_lineno or target.lineno)
                ):
                    # The target might be inside this function
                    for child in ast.walk(node):
                        if child is target:
                            return node
        return None

    @staticmethod
    def _has_optimization_in_scope(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if select_related or prefetch_related appears in the function body."""
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute):
                if node.attr in ("select_related", "prefetch_related"):
                    return True
        return False

    def _check_schema_usage(self, tree: ast.Module, file: str) -> None:
        """Detect controllers returning plain dicts instead of Schema/BaseModel objects."""
        if not self._is_controller_file(file):
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                returns_dict = False
                is_controller_method = False

                # Check if this is a controller class method
                # (walk up parent classes)
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        for base in parent.bases:
                            base_name = self._get_name(base)
                            if base_name in ("Controller", "APIController", "BaseController", "ViewSet"):
                                for item in parent.body:
                                    if item is node:
                                        is_controller_method = True
                                        break

                if not is_controller_method:
                    continue

                # Check return statements for dict literals
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and child.value:
                        if isinstance(child.value, ast.Dict):
                            returns_dict = True
                        elif isinstance(child.value, ast.Call):
                            # Check if it's calling dict()
                            if self._get_name(child.value.func) == "dict":
                                returns_dict = True

                if returns_dict:
                    self._add_finding(
                        file, node.lineno, ConventionCategory.SCHEMA_USAGE,
                        f"Controller method '{node.name}' returns a plain dict — "
                        "consider using a Pydantic Schema/BaseModel for type safety",
                        deduction=2,
                    )
