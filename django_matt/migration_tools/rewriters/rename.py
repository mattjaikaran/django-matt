"""Rewriter for RenameField operations."""

from __future__ import annotations

from typing import Any

from django.db.migrations.operations.fields import RenameField

from django_matt.migration_tools.rewriters.base import BaseRewriter, RewriteResult, RewriteStep


class RenameFieldRewriter(BaseRewriter):
    """Rewrite RenameField into a safe expand-contract sequence.

    Unsafe pattern: ALTER TABLE RENAME COLUMN breaks code that references
    the old column name until all application code is deployed.

    Safe rewrite:
      1. Add new column (copy of old)
      2. Dual-write trigger (old → new)
      3. Backfill existing rows
      4. Switch application reads to new column
      5. Drop trigger + old column
    """

    def can_handle(self, operation: Any) -> bool:
        return isinstance(operation, RenameField)

    def rewrite(self, operation: Any, app_label: str, model_name: str) -> RewriteResult:
        old_name = operation.old_name
        new_name = operation.new_name
        table = f"{app_label}_{model_name}".lower()

        steps = [
            RewriteStep(
                description=f"Add new column '{new_name}' as a copy of '{old_name}'",
                sql=(
                    f"ALTER TABLE {table} ADD COLUMN {new_name} /* same type as {old_name} */ NULL;"
                ),
            ),
            RewriteStep(
                description="Create dual-write trigger (writes to old column also write to new)",
                sql=(
                    f"CREATE OR REPLACE FUNCTION {table}_dualwrite_{old_name}() "
                    f"RETURNS TRIGGER AS $$ BEGIN "
                    f"NEW.{new_name} := NEW.{old_name}; RETURN NEW; "
                    f"END; $$ LANGUAGE plpgsql;\n"
                    f"CREATE TRIGGER {table}_dualwrite_{old_name}_trigger "
                    f"BEFORE INSERT OR UPDATE ON {table} "
                    f"FOR EACH ROW EXECUTE FUNCTION {table}_dualwrite_{old_name}();"
                ),
            ),
            RewriteStep(
                description=f"Backfill: copy {old_name} → {new_name} for existing rows",
                sql=(f"UPDATE {table} SET {new_name} = {old_name} WHERE {new_name} IS NULL;"),
            ),
            RewriteStep(
                description="Deploy application code reading from new column name",
                sql="-- Application code change required (no SQL)",
            ),
            RewriteStep(
                description=f"Drop trigger and old column '{old_name}'",
                sql=(
                    f"DROP TRIGGER IF EXISTS {table}_dualwrite_{old_name}_trigger ON {table};\n"
                    f"DROP FUNCTION IF EXISTS {table}_dualwrite_{old_name}();\n"
                    f"ALTER TABLE {table} DROP COLUMN {old_name};"
                ),
            ),
        ]

        return RewriteResult(
            original_description=f"RenameField '{old_name}' → '{new_name}' on {model_name}",
            steps=steps,
            explanation=(
                "Direct column rename breaks running application code that references "
                "the old name. This expand-contract sequence adds the new column alongside "
                "the old, dual-writes to keep them in sync, then drops the old after "
                "application code has switched."
            ),
        )
