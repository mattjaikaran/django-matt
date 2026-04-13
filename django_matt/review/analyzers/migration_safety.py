"""AST-based migration safety checker.

Detects unsafe migration patterns: non-nullable fields without defaults,
RunPython without reverse_code, and data migrations using ORM without
.using(schema_editor.connection.alias).
"""

from __future__ import annotations

import ast
from pathlib import Path

from django_matt.review.analyzers.base import BaseAnalyzer
from django_matt.review.findings import Category, Finding, Location, Severity


class MigrationSafetyAnalyzer(BaseAnalyzer):
    """Analyzer that detects unsafe migration patterns via AST inspection."""

    name = "migration_safety"
    description = "Checks for non-nullable fields without defaults, RunPython without reverse, unsafe ORM in data migrations"

    def should_skip_file(self, file_path: Path) -> bool:
        """Only analyze migration files."""
        parts = file_path.parts
        # Must be inside a migrations/ directory and not __init__.py
        if "migrations" not in parts:
            return True
        if file_path.name == "__init__.py":
            return True
        return False

    def analyze_file(self, file_path: Path, tree: ast.Module, source: str) -> list[Finding]:
        findings: list[Finding] = []
        self._file_path = file_path
        self._source = source
        self._source_lines = source.splitlines()

        # Skip non-migration files even when called directly
        if self.should_skip_file(file_path):
            return findings

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                self._check_add_field(node, findings)
                self._check_run_python(node, findings)
                self._check_alter_field(node, findings)

        # Check for data migration functions that use ORM without .using()
        self._check_data_migration_orm(tree, findings)

        return findings

    def _make_location(self, lineno: int, function: str | None = None) -> Location:
        return Location(
            file=str(self._file_path),
            line=lineno,
            function=function,
        )

    def _get_source_line(self, lineno: int) -> str:
        if 1 <= lineno <= len(self._source_lines):
            return self._source_lines[lineno - 1]
        return ""

    def _check_add_field(self, node: ast.Call, findings: list[Finding]) -> None:
        """MIG001: Detect AddField with non-nullable field and no default."""
        func_name = self._get_call_attr(node)
        if func_name != "AddField":
            return

        field_call = self._find_field_kwarg(node)
        if field_call is None:
            return

        has_null_true = False
        has_default = False

        for kw in field_call.keywords:
            if kw.arg == "null":
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    has_null_true = True
            if kw.arg == "default":
                has_default = True

        if not has_null_true and not has_default:
            field_type = self._get_call_attr(field_call) or "Field"
            # Skip BooleanField (defaults to False in Django)
            if field_type in ("BooleanField", "NullBooleanField"):
                return
            finding = Finding(
                rule_id="MIG001",
                message=f"AddField with non-nullable {field_type} and no default value",
                severity=Severity.ERROR,
                category=Category.MIGRATION,
                location=self._make_location(node.lineno),
                suggestion="Add a default value or set null=True to avoid breaking existing rows",
                context=self._get_source_line(node.lineno).strip(),
            )
            if self.config.should_report_finding(finding.rule_id, finding.severity):
                findings.append(finding)

    def _check_run_python(self, node: ast.Call, findings: list[Finding]) -> None:
        """MIG002: Detect RunPython without reverse_code."""
        func_name = self._get_call_attr(node)
        if func_name != "RunPython":
            return

        has_reverse = False
        # RunPython(forward, reverse) — check positional args
        if len(node.args) >= 2:
            has_reverse = True
        # RunPython(forward, reverse_code=reverse)
        for kw in node.keywords:
            if kw.arg == "reverse_code":
                has_reverse = True

        if not has_reverse:
            finding = Finding(
                rule_id="MIG002",
                message="RunPython() without reverse_code — migration is irreversible",
                severity=Severity.WARNING,
                category=Category.MIGRATION,
                location=self._make_location(node.lineno),
                suggestion="Add reverse_code parameter or use migrations.RunPython.noop as reverse",
                context=self._get_source_line(node.lineno).strip(),
            )
            if self.config.should_report_finding(finding.rule_id, finding.severity):
                findings.append(finding)

    def _check_alter_field(self, node: ast.Call, findings: list[Finding]) -> None:
        """MIG003: Detect AlterField removing nullable or adding NOT NULL."""
        func_name = self._get_call_attr(node)
        if func_name != "AlterField":
            return

        field_call = self._find_field_kwarg(node)
        if field_call is None:
            return

        has_null_true = False
        has_default = False

        for kw in field_call.keywords:
            if kw.arg == "null":
                if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    has_null_true = True
            if kw.arg == "default":
                has_default = True

        if not has_null_true and not has_default:
            field_type = self._get_call_attr(field_call) or "Field"
            if field_type in ("BooleanField", "NullBooleanField"):
                return
            finding = Finding(
                rule_id="MIG003",
                message=f"AlterField to non-nullable {field_type} without default — may fail on existing data",
                severity=Severity.WARNING,
                category=Category.MIGRATION,
                location=self._make_location(node.lineno),
                suggestion="Add a default value or use a multi-step migration (add nullable, backfill, alter)",
                context=self._get_source_line(node.lineno).strip(),
            )
            if self.config.should_report_finding(finding.rule_id, finding.severity):
                findings.append(finding)

    def _check_data_migration_orm(self, tree: ast.Module, findings: list[Finding]) -> None:
        """MIG004: Detect data migration functions using ORM without .using()."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Data migration functions typically have (apps, schema_editor) params
            args = [a.arg for a in node.args.args]
            if len(args) < 2:
                continue
            if "schema_editor" not in args and "se" not in args:
                continue

            # Walk function body for ORM calls without .using()
            has_orm_call = False
            has_using = False
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute):
                    if child.attr == "objects":
                        has_orm_call = True
                    if child.attr == "using":
                        has_using = True

            if has_orm_call and not has_using:
                finding = Finding(
                    rule_id="MIG004",
                    message=f"Data migration function '{node.name}' uses ORM without .using(schema_editor.connection.alias)",
                    severity=Severity.WARNING,
                    category=Category.MIGRATION,
                    location=self._make_location(node.lineno, function=node.name),
                    suggestion="Add .using(schema_editor.connection.alias) to all ORM queries in data migrations",
                    context=self._get_source_line(node.lineno).strip(),
                )
                if self.config.should_report_finding(finding.rule_id, finding.severity):
                    findings.append(finding)

    # -- Helpers -----------------------------------------------------------

    def _get_call_attr(self, node: ast.Call) -> str | None:
        """Get the function/method name from a Call node."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
        return None

    def _find_field_kwarg(self, node: ast.Call) -> ast.Call | None:
        """Find the 'field' keyword argument that contains a Field() constructor call."""
        for kw in node.keywords:
            if kw.arg == "field" and isinstance(kw.value, ast.Call):
                return kw.value
        # Also check positional args — some migration operations pass field as positional
        for arg in node.args:
            if isinstance(arg, ast.Call):
                name = self._get_call_attr(arg)
                if name and "Field" in name:
                    return arg
        return None
