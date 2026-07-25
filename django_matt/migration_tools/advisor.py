"""Migration advisor — detect and rewrite unsafe DDL operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django_matt.migration_tools.rewriters.base import BaseRewriter, RewriteResult, Severity

logger = logging.getLogger("django_matt.migration_tools.advisor")


@dataclass
class MigrationIssue:
    """A detected issue in a migration."""

    app_label: str
    migration_name: str
    operation_index: int
    operation_description: str
    severity: Severity
    message: str
    rewrite: RewriteResult | None = None


class MigrationAdvisor:
    """Analyze migrations for unsafe DDL patterns and suggest safe rewrites.

    Usage::

        advisor = MigrationAdvisor()
        issues = advisor.analyze_pending()
        for issue in issues:
            print(f"{issue.severity.value}: {issue.message}")
            if issue.rewrite:
                for step in issue.rewrite.steps:
                    print(f"  → {step.description}")
    """

    def __init__(self, rewriters: list[BaseRewriter] | None = None) -> None:
        if rewriters is None:
            from django_matt.migration_tools.rewriters import (
                AddNonNullableRewriter,
                ConcurrentIndexRewriter,
                RenameFieldRewriter,
            )

            rewriters = [
                AddNonNullableRewriter(),
                ConcurrentIndexRewriter(),
                RenameFieldRewriter(),
            ]
        self.rewriters = rewriters

    def analyze_pending(self) -> list[MigrationIssue]:
        """Analyze all pending (unapplied) migrations for safety issues."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        applied = loader.applied_migrations

        issues: list[MigrationIssue] = []
        for (app_label, migration_name), migration in loader.disk_migrations.items():
            if (app_label, migration_name) in applied:
                continue
            issues.extend(self._analyze_migration(app_label, migration_name, migration))

        return issues

    def analyze_app(self, app_label: str) -> list[MigrationIssue]:
        """Analyze all migrations for a specific app."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        issues: list[MigrationIssue] = []

        for (al, mn), migration in loader.disk_migrations.items():
            if al != app_label:
                continue
            issues.extend(self._analyze_migration(al, mn, migration))

        return issues

    def analyze_operations(
        self,
        operations: list[Any],
        app_label: str = "app",
        migration_name: str = "0001",
    ) -> list[MigrationIssue]:
        """Analyze a list of migration operations directly (for testing)."""
        issues: list[MigrationIssue] = []
        for i, op in enumerate(operations):
            for rewriter in self.rewriters:
                if rewriter.can_handle(op):
                    model_name = self._get_model_name(op)
                    rewrite = rewriter.rewrite(op, app_label, model_name)
                    issues.append(
                        MigrationIssue(
                            app_label=app_label,
                            migration_name=migration_name,
                            operation_index=i,
                            operation_description=rewrite.original_description,
                            severity=Severity.WARNING,
                            message=rewrite.explanation,
                            rewrite=rewrite,
                        )
                    )
        return issues

    def _analyze_migration(
        self, app_label: str, migration_name: str, migration: Any
    ) -> list[MigrationIssue]:
        """Analyze a single migration object."""
        issues: list[MigrationIssue] = []
        operations = getattr(migration, "operations", [])

        for i, operation in enumerate(operations):
            for rewriter in self.rewriters:
                if rewriter.can_handle(operation):
                    model_name = self._get_model_name(operation)
                    try:
                        rewrite = rewriter.rewrite(operation, app_label, model_name)
                    except Exception as e:
                        logger.warning(
                            "Rewriter %s failed on %s.%s op %d: %s",
                            type(rewriter).__name__,
                            app_label,
                            migration_name,
                            i,
                            e,
                        )
                        continue

                    issues.append(
                        MigrationIssue(
                            app_label=app_label,
                            migration_name=migration_name,
                            operation_index=i,
                            operation_description=rewrite.original_description,
                            severity=Severity.WARNING,
                            message=rewrite.explanation,
                            rewrite=rewrite,
                        )
                    )
        return issues

    @staticmethod
    def _get_model_name(operation: Any) -> str:
        """Extract model name from a migration operation."""
        return getattr(operation, "model_name", "unknown") or "unknown"
