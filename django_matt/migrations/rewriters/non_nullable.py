"""Rewriter for AddField NOT NULL without default."""

from __future__ import annotations

from typing import Any

from django.db.migrations.operations.fields import AddField

from django_matt.migrations.rewriters.base import BaseRewriter, RewriteResult, RewriteStep


class AddNonNullableRewriter(BaseRewriter):
    """Rewrite AddField NOT NULL without server-side default.

    Unsafe pattern: ADD COLUMN ... NOT NULL DEFAULT x
    This locks the table while backfilling the default for every row.

    Safe rewrite:
      1. ADD COLUMN ... NULL (instant, no lock)
      2. UPDATE in batches SET col = default WHERE col IS NULL
      3. ALTER COLUMN SET NOT NULL (with NOT VALID + VALIDATE CONSTRAINT)
    """

    batch_size: int = 10_000

    def can_handle(self, operation: Any) -> bool:
        if not isinstance(operation, AddField):
            return False
        field = operation.field
        # Unsafe if NOT NULL and has a default (server-side backfill)
        return not field.null and field.has_default()

    def rewrite(self, operation: Any, app_label: str, model_name: str) -> RewriteResult:
        field = operation.field
        field_name = operation.name
        table = f"{app_label}_{model_name}".lower()
        default_val = field.default
        if callable(default_val):
            default_repr = f"{default_val.__name__}()"
        else:
            default_repr = repr(default_val)

        col_type = self._get_column_type(field)

        steps = [
            RewriteStep(
                description=f"ADD COLUMN {field_name} as nullable (instant, no lock)",
                sql=f"ALTER TABLE {table} ADD COLUMN {field_name} {col_type} NULL;",
                operation_class="AddField",
                operation_kwargs={
                    "model_name": model_name,
                    "name": field_name,
                    "field_kwargs": {"null": True},
                },
            ),
            RewriteStep(
                description=f"Backfill default value ({default_repr}) in batches of {self.batch_size}",
                sql=(
                    f"UPDATE {table} SET {field_name} = {default_repr} "
                    f"WHERE {field_name} IS NULL;"
                ),
            ),
            RewriteStep(
                description=f"Set NOT NULL constraint on {field_name}",
                sql=(
                    f"ALTER TABLE {table} ADD CONSTRAINT {table}_{field_name}_not_null "
                    f"CHECK ({field_name} IS NOT NULL) NOT VALID;\n"
                    f"ALTER TABLE {table} VALIDATE CONSTRAINT {table}_{field_name}_not_null;\n"
                    f"ALTER TABLE {table} ALTER COLUMN {field_name} SET NOT NULL;\n"
                    f"ALTER TABLE {table} DROP CONSTRAINT {table}_{field_name}_not_null;"
                ),
            ),
        ]

        return RewriteResult(
            original_description=(
                f"AddField '{field_name}' {type(field).__name__}(default={default_repr}) NOT NULL"
            ),
            steps=steps,
            explanation=(
                "Adding a NOT NULL column with a default locks the table during backfill. "
                "This rewrite adds the column as NULL first, backfills in batches, "
                "then sets NOT NULL using NOT VALID + VALIDATE for minimal locking."
            ),
        )

    @staticmethod
    def _get_column_type(field: Any) -> str:
        db_type = getattr(field, "db_type", None)
        if callable(db_type):
            try:
                from django.db import connection
                return db_type(connection)
            except Exception:
                pass
        # Fallback to common type names
        type_name = type(field).__name__
        type_map = {
            "BooleanField": "BOOLEAN",
            "IntegerField": "INTEGER",
            "BigIntegerField": "BIGINT",
            "CharField": f"VARCHAR({getattr(field, 'max_length', 255)})",
            "TextField": "TEXT",
            "FloatField": "DOUBLE PRECISION",
            "DecimalField": "NUMERIC",
            "DateTimeField": "TIMESTAMP WITH TIME ZONE",
            "DateField": "DATE",
            "UUIDField": "UUID",
            "JSONField": "JSONB",
        }
        return type_map.get(type_name, "TEXT")
