"""Rewriter for CREATE INDEX without CONCURRENTLY."""

from __future__ import annotations

from typing import Any

from django.db.migrations.operations.models import AddIndex

from django_matt.migration_tools.rewriters.base import BaseRewriter, RewriteResult, RewriteStep


class ConcurrentIndexRewriter(BaseRewriter):
    """Rewrite CREATE INDEX to CREATE INDEX CONCURRENTLY.

    Unsafe pattern: CREATE INDEX blocks writes on the table.
    Safe rewrite: CREATE INDEX CONCURRENTLY (PostgreSQL only).

    Note: CONCURRENTLY cannot run inside a transaction, so the migration
    must use ``atomic = False``.
    """

    def can_handle(self, operation: Any) -> bool:
        if isinstance(operation, AddIndex):
            return True
        # Also catch RunSQL with CREATE INDEX
        from django.db.migrations.operations.special import RunSQL

        if isinstance(operation, RunSQL):
            sql = operation.sql if isinstance(operation.sql, str) else ""
            return "CREATE INDEX" in sql.upper() and "CONCURRENTLY" not in sql.upper()
        return False

    def rewrite(self, operation: Any, app_label: str, model_name: str) -> RewriteResult:
        if isinstance(operation, AddIndex):
            index = operation.index
            index_name = getattr(index, "name", "idx")
            fields = getattr(index, "fields", [])
            field_str = ", ".join(fields) if fields else "..."
            table = f"{app_label}_{model_name}".lower()

            steps = [
                RewriteStep(
                    description="Set migration as non-atomic (required for CONCURRENTLY)",
                    sql="-- Migration class must have: atomic = False",
                ),
                RewriteStep(
                    description=f"Create index concurrently on ({field_str})",
                    sql=(
                        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                        f"ON {table} ({field_str});"
                    ),
                ),
            ]

            return RewriteResult(
                original_description=f"AddIndex '{index_name}' on ({field_str})",
                steps=steps,
                explanation=(
                    "CREATE INDEX locks the table against writes. Using CONCURRENTLY "
                    "allows reads and writes during index creation, but requires "
                    "the migration to be non-atomic (atomic = False)."
                ),
            )

        # RunSQL case
        original_sql = operation.sql if isinstance(operation.sql, str) else str(operation.sql)
        safe_sql = original_sql.replace("CREATE INDEX", "CREATE INDEX CONCURRENTLY")

        return RewriteResult(
            original_description=f"RunSQL: {original_sql[:80]}...",
            steps=[
                RewriteStep(
                    description="Set migration as non-atomic",
                    sql="-- atomic = False",
                ),
                RewriteStep(
                    description="Create index concurrently",
                    sql=safe_sql,
                ),
            ],
            explanation="Rewrote CREATE INDEX to CREATE INDEX CONCURRENTLY to avoid write locks.",
        )
