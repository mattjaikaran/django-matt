"""
AI-powered refactoring analyzer.

Detects common code quality issues in Python files and produces
structured, actionable suggestions with maintainability scoring.

Usage:
    from django_matt.ai.refactor import analyze_file

    result = analyze_file("blog/controllers.py")
    print(result.format())
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

_FAT_CONTROLLER_THRESHOLD = 200  # lines

# ORM patterns that indicate direct DB access in controllers
_ORM_PATTERNS = (
    ".objects.",
    ".filter(",
    ".get(",
    ".all(",
    ".exclude(",
    ".create(",
    ".update(",
    ".delete(",
    ".bulk_create(",
    ".bulk_update(",
    ".select_related(",
    ".prefetch_related(",
    ".annotate(",
    ".aggregate(",
    ".values(",
    ".values_list(",
    ".only(",
    ".defer(",
    ".order_by(",
    ".aexists(",
    ".acount(",
    ".asave(",
    ".adelete(",
    ".aupdate(",
    ".aaggregate(",
)

# Auth patterns that indicate auth checks inside business logic
_AUTH_PATTERNS = (
    "request.user.is_authenticated",
    "request.user.has_perm",
    "request.user.has_perms",
    "user.has_perm",
    "user.has_perms",
    "self.request.user.is_authenticated",
    "self.request.user.has_perm",
    "permission_classes",
)

_DECORATOR_AUTH_PATTERNS = (
    "permission_classes",
    "@login_required",
    "@permission_required",
    "@jwt_required",
    "@IsAuthenticated",
    "IsAuthenticated",
)

# Deductions from the base score (100)
_FAT_CONTROLLER_DEDUCTION = 25
_ORM_IN_CONTROLLER_DEDUCTION = 20
_MIXED_CONCERNS_DEDUCTION = 15
_ORM_LINE_PENALTY = 1  # per line with ORM call (capped at 30)
_AUTH_LINE_PENALTY = 2  # per line with auth check (capped at 20)


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class Suggestion:
    """A single refactoring suggestion with context."""

    line: int
    severity: str  # "HIGH", "MEDIUM", "LOW"
    issue_type: str  # e.g. "fat_controller", "orm_in_controller", "mixed_concerns"
    message: str
    before: str  # problematic snippet
    after: str  # suggested fix snippet

    def format(self) -> str:
        parts = [f"  Line {self.line}: [{self.severity}] {self.message}"]
        if self.before:
            parts.append(f"    Before: {self.before}")
        if self.after:
            parts.append(f"    After:  {self.after}")
        return "\n".join(parts)


@dataclass
class FileIssue:
    """A file-level issue (e.g., fat controller)."""

    issue_type: str
    severity: str
    message: str
    suggestion: str
    lines: list[int] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis of a single file."""

    file_path: str
    score: int
    total_lines: int
    controller_classes: list[str]
    issues: list[FileIssue] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)

    def format(self) -> str:
        lines: list[str] = []
        lines.append(f"\n{self.file_path} — Score: {self.score}/100\n")

        for issue in self.issues:
            lines.append(f"ISSUE: {issue.message}")
            lines.append(f"  Suggest: {issue.suggestion}")
            lines.append("")

        for sug in self.suggestions:
            lines.append(f"  Line {sug.line}: [{sug.severity}] {sug.message}")

        lines.append("")
        lines.append(f"Auto-fix: matt refactor --apply {self.file_path}")
        lines.append("")
        return "\n".join(lines)


# ── Core analysis ────────────────────────────────────────────────────────────


def analyze_file(
    file_path: str | Path,
    *,
    threshold: int = _FAT_CONTROLLER_THRESHOLD,
) -> AnalysisResult:
    """Analyze a Python file for refactoring opportunities.

    Args:
        file_path: Path to a Python file.
        threshold: Lines threshold for flagging fat controllers.

    Returns:
        AnalysisResult with score, issues, and actionable suggestions.
    """
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    total_lines = len(source.splitlines())

    tree = ast.parse(source, filename=str(path))
    controller_classes = _find_controller_classes(tree, source)

    score = 100
    issues: list[FileIssue] = []
    suggestions: list[Suggestion] = []

    # 1. Detect fat controllers
    fat_issues = _detect_fat_controllers(tree, source, path, threshold)
    if fat_issues:
        issues.extend(fat_issues)
        score -= _FAT_CONTROLLER_DEDUCTION

    # 2. Detect ORM calls in controllers
    orm_issues, orm_suggestions = _detect_orm_in_controllers(tree, source, path, controller_classes)
    if orm_issues:
        issues.extend(orm_issues)
        score -= _ORM_IN_CONTROLLER_DEDUCTION
    suggestions.extend(orm_suggestions)
    score -= min(len(orm_suggestions) * _ORM_LINE_PENALTY, 30)

    # 3. Detect mixed concerns (auth + business logic)
    auth_issues, auth_suggestions = _detect_mixed_concerns(tree, source, path, controller_classes)
    if auth_issues:
        issues.extend(auth_issues)
        score -= _MIXED_CONCERNS_DEDUCTION
    suggestions.extend(auth_suggestions)
    score -= min(len(auth_suggestions) * _AUTH_LINE_PENALTY, 20)

    score = max(0, min(100, score))

    return AnalysisResult(
        file_path=str(path),
        score=score,
        total_lines=total_lines,
        controller_classes=controller_classes,
        issues=issues,
        suggestions=suggestions,
    )


# ── Detectors ────────────────────────────────────────────────────────────────


def _class_lines(node: ast.ClassDef, source_lines: list[str]) -> int:
    """Count lines from class header to end of class body."""
    start = node.lineno
    child_ends = [
        getattr(n, "end_lineno", 0) or getattr(n, "lineno", 0)
        for n in ast.walk(node)
        if hasattr(n, "lineno")
    ]
    end = max([node.end_lineno or start, *child_ends], default=start)
    return end - start + 1


def _find_controller_classes(tree: ast.AST, source: str) -> list[str]:
    """Find class names that appear to be controllers."""
    source_lines = source.splitlines()
    controllers: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        name_lower = node.name.lower()
        if "controller" in name_lower:
            nlines = _class_lines(node, source_lines)
            controllers.append((node.name, nlines))
            continue
        for base in node.bases:
            base_name = _get_name(base)
            if base_name and "controller" in base_name.lower():
                nlines = _class_lines(node, source_lines)
                controllers.append((node.name, nlines))
                break

    return [name for name, _ in controllers]


def _get_name(node: ast.expr) -> str | None:
    """Extract a dotted name from an AST expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _detect_fat_controllers(
    tree: ast.AST,
    source: str,
    path: Path,
    threshold: int,
) -> list[FileIssue]:
    """Flag controller classes that exceed the line threshold."""
    source_lines = source.splitlines()
    issues: list[FileIssue] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        name_lower = node.name.lower()
        is_controller = "controller" in name_lower
        if not is_controller:
            for base in node.bases:
                base_name = _get_name(base)
                if base_name and "controller" in base_name.lower():
                    is_controller = True
                    break
        if not is_controller:
            continue

        nlines = _class_lines(node, source_lines)
        if nlines > threshold:
            issues.append(
                FileIssue(
                    issue_type="fat_controller",
                    severity="HIGH",
                    message=f"Fat controller ({nlines} lines)",
                    suggestion="Split into smaller controllers by resource group",
                )
            )

    return issues


def _has_decorator_auth(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has auth-related decorators."""
    for dec in node.decorator_list:
        dec_str = ast.unparse(dec)
        for pat in _DECORATOR_AUTH_PATTERNS:
            if pat in dec_str:
                return True
    return False


def _detect_orm_in_controllers(
    tree: ast.AST,
    source: str,
    path: Path,
    controller_classes: list[str],
) -> tuple[list[FileIssue], list[Suggestion]]:
    """Detect ORM calls inside controller method bodies."""
    suggestions: list[Suggestion] = []
    orm_lines: list[int] = []
    seen_lines: set[int] = set()

    class_methods = _get_controller_methods(tree, controller_classes)

    for class_name, methods in class_methods.items():
        for method_node in methods:
            for child in ast.walk(method_node):
                if not isinstance(child, ast.Call):
                    continue
                lineno = child.lineno
                if lineno in seen_lines:
                    continue
                call_str = ast.unparse(child)
                if any(pat in call_str for pat in _ORM_PATTERNS):
                    seen_lines.add(lineno)
                    orm_lines.append(lineno)
                    suggestions.append(
                        Suggestion(
                            line=lineno,
                            severity="MEDIUM",
                            issue_type="orm_in_controller",
                            message="ORM call in controller method",
                            before=f"{class_name}.{method_node.name}() calls ORM directly",
                            after=f"Move to a service layer (e.g., {class_name.replace('Controller', 'Service')}.{method_node.name}())",
                        )
                    )

    issues: list[FileIssue] = []
    if orm_lines:
        unique_lines = sorted(set(orm_lines))
        issues.append(
            FileIssue(
                issue_type="orm_in_controller",
                severity="MEDIUM",
                message="ORM calls in controller (line {})".format(
                    ", ".join(map(str, unique_lines[:5]))
                    + (", ..." if len(unique_lines) > 5 else "")
                ),
                suggestion="Move ORM operations to a dedicated service layer",
                lines=unique_lines[:10],
            )
        )

    return issues, suggestions


def _detect_mixed_concerns(
    tree: ast.AST,
    source: str,
    path: Path,
    controller_classes: list[str],
) -> tuple[list[FileIssue], list[Suggestion]]:
    """Detect methods that mix auth checks with business logic."""
    suggestions: list[Suggestion] = []
    auth_lines: set[int] = set()

    class_methods = _get_controller_methods(tree, controller_classes)

    for class_name, methods in class_methods.items():
        for method_node in methods:
            has_decorator = _has_decorator_auth(method_node)

            # Check for auth patterns in calls and attribute access
            for child in ast.walk(method_node):
                if not isinstance(child, (ast.Call, ast.Attribute)):
                    continue
                lineno = getattr(child, "lineno", 0)
                if lineno in auth_lines:
                    continue
                node_str = ast.unparse(child)
                if any(pat in node_str for pat in _AUTH_PATTERNS):
                    auth_lines.add(lineno)
                    severity = "LOW" if has_decorator else "MEDIUM"
                    suggestions.append(
                        Suggestion(
                            line=lineno,
                            severity=severity,
                            issue_type="mixed_concerns",
                            message="Inline auth check mixed with business logic",
                            before=f"{class_name}.{method_node.name}() checks auth inline",
                            after="Extract auth check to a decorator (e.g., @permission_required or permission_classes)",
                        )
                    )

    issues: list[FileIssue] = []
    if auth_lines:
        unique = sorted(auth_lines)
        issues.append(
            FileIssue(
                issue_type="mixed_concerns",
                severity="MEDIUM",
                message="Mixed auth + business logic (line {})".format(
                    ", ".join(map(str, unique[:5])) + (", ..." if len(unique) > 5 else "")
                ),
                suggestion="Extract auth checks to permission_classes or decorators",
                lines=unique[:10],
            )
        )

    return issues, suggestions


def _get_controller_methods(
    tree: ast.AST, controller_classes: list[str]
) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Map controller class names to their method AST nodes."""
    result: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name not in controller_classes:
            continue
        methods: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not item.name.startswith("_"):
                    methods.append(item)
        if methods:
            result[node.name] = methods

    return result
