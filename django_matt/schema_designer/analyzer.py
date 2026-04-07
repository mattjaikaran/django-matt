from __future__ import annotations

from enum import Enum
from typing import Any

from django.apps import apps
from django.db import models

from pydantic import BaseModel


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FieldIssue(BaseModel):
    field_name: str
    issue: str
    severity: Severity
    suggestion: str


class ModelReport(BaseModel):
    app_label: str
    model_name: str
    full_name: str
    field_count: int
    issues: list[FieldIssue]
    fields: list[dict[str, Any]]
    indexes: list[str]
    relationships: list[dict[str, str]]

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)


class SchemaReport(BaseModel):
    models: list[ModelReport]
    total_issues: int
    total_errors: int
    total_warnings: int
    total_info: int


class SchemaAnalyzer:
    def __init__(self, app_labels: list[str] | None = None):
        self.app_labels = app_labels

    def get_models(self) -> list[type[models.Model]]:
        all_models = apps.get_models()
        if self.app_labels:
            return [m for m in all_models if m._meta.app_label in self.app_labels]
        return all_models

    def analyze_all(self) -> SchemaReport:
        model_reports = [self.analyze_model(m) for m in self.get_models()]
        total_issues = sum(len(r.issues) for r in model_reports)
        total_errors = sum(r.error_count for r in model_reports)
        total_warnings = sum(r.warning_count for r in model_reports)
        total_info = total_issues - total_errors - total_warnings
        return SchemaReport(
            models=model_reports,
            total_issues=total_issues,
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_info=total_info,
        )

    def analyze_model(self, model: type[models.Model]) -> ModelReport:
        meta = model._meta
        issues: list[FieldIssue] = []
        fields_info: list[dict[str, Any]] = []
        relationships: list[dict[str, str]] = []
        index_names: list[str] = []

        concrete_fields = meta.get_fields()

        for field in concrete_fields:
            field_data = self._extract_field_info(field)
            if field_data:
                fields_info.append(field_data)

            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                relationships.append({
                    "type": "fk" if isinstance(field, models.ForeignKey) else "one_to_one",
                    "field": field.name,
                    "related_model": f"{field.related_model._meta.app_label}.{field.related_model.__name__}",
                })

            if isinstance(field, models.ManyToManyField):
                relationships.append({
                    "type": "m2m",
                    "field": field.name,
                    "related_model": f"{field.related_model._meta.app_label}.{field.related_model.__name__}",
                })

            issues.extend(self._check_field(field, model))

        issues.extend(self._check_model_level(model, concrete_fields))

        for idx in meta.indexes:
            idx_name = idx.name or ", ".join(idx.fields)
            index_names.append(idx_name)

        return ModelReport(
            app_label=meta.app_label,
            model_name=model.__name__,
            full_name=f"{meta.app_label}.{model.__name__}",
            field_count=len(fields_info),
            issues=issues,
            fields=fields_info,
            indexes=index_names,
            relationships=relationships,
        )

    def _extract_field_info(self, field: Any) -> dict[str, Any] | None:
        if isinstance(field, models.fields.related.ForeignObjectRel):
            return None

        info: dict[str, Any] = {
            "name": field.name,
            "type": type(field).__name__,
        }

        if hasattr(field, "max_length") and field.max_length is not None:
            info["max_length"] = field.max_length
        if hasattr(field, "null"):
            info["null"] = field.null
        if hasattr(field, "blank"):
            info["blank"] = field.blank
        if hasattr(field, "db_index"):
            info["db_index"] = field.db_index
        if hasattr(field, "unique"):
            info["unique"] = field.unique
        if hasattr(field, "default") and field.default is not models.fields.NOT_PROVIDED:
            info["has_default"] = True

        return info

    def _check_field(self, field: Any, model: type[models.Model]) -> list[FieldIssue]:
        issues: list[FieldIssue] = []

        if isinstance(field, models.fields.related.ForeignObjectRel):
            return issues

        # Missing index on FK
        if isinstance(field, models.ForeignKey):
            if not field.db_index and not field.unique:
                issues.append(FieldIssue(
                    field_name=field.name,
                    issue="ForeignKey without db_index",
                    severity=Severity.WARNING,
                    suggestion=f"Add db_index=True to {field.name} for faster joins",
                ))

        # Missing related_name on FK/M2M
        if isinstance(field, (models.ForeignKey, models.ManyToManyField)):
            related_name = field.remote_field.related_name
            if not related_name or related_name.endswith("+"):
                issues.append(FieldIssue(
                    field_name=field.name,
                    issue="Missing explicit related_name",
                    severity=Severity.INFO,
                    suggestion=f"Add related_name to {field.name} for clearer reverse lookups",
                ))

        # Large CharField without max_length optimization
        if isinstance(field, models.CharField):
            if hasattr(field, "max_length") and field.max_length and field.max_length > 500:
                issues.append(FieldIssue(
                    field_name=field.name,
                    issue=f"CharField with large max_length ({field.max_length})",
                    severity=Severity.INFO,
                    suggestion="Consider using TextField instead for large text content",
                ))

        # Nullable fields without defaults
        if hasattr(field, "null") and field.null and hasattr(field, "default"):
            if field.default is models.fields.NOT_PROVIDED:
                if not isinstance(field, (models.ForeignKey, models.OneToOneField, models.ManyToManyField)):
                    issues.append(FieldIssue(
                        field_name=field.name,
                        issue="Nullable field without default",
                        severity=Severity.INFO,
                        suggestion=f"Consider adding default=None to {field.name}",
                    ))

        return issues

    def _check_model_level(
        self, model: type[models.Model], fields: Any
    ) -> list[FieldIssue]:
        issues: list[FieldIssue] = []
        meta = model._meta

        # Missing __str__
        if model.__str__ is models.Model.__str__:
            issues.append(FieldIssue(
                field_name="__str__",
                issue="Missing __str__ method",
                severity=Severity.INFO,
                suggestion="Add a __str__ method for better admin/debugging display",
            ))

        # Missing ordering
        if not meta.ordering:
            issues.append(FieldIssue(
                field_name="Meta.ordering",
                issue="Missing ordering in Meta",
                severity=Severity.INFO,
                suggestion="Add ordering in Meta for consistent query results",
            ))

        # Too many columns
        concrete_count = len([
            f for f in fields
            if not isinstance(f, models.fields.related.ForeignObjectRel)
        ])
        if concrete_count > 30:
            issues.append(FieldIssue(
                field_name="*",
                issue=f"Table has {concrete_count} columns (>30)",
                severity=Severity.WARNING,
                suggestion="Consider splitting into related models to reduce table width",
            ))

        # Missing created_at/updated_at
        field_names = {f.name for f in fields if hasattr(f, "name")}
        has_created = any(n in field_names for n in ("created_at", "date_created", "created"))
        has_updated = any(n in field_names for n in ("updated_at", "date_updated", "modified", "modified_at"))
        if not has_created and not meta.proxy and not meta.abstract:
            issues.append(FieldIssue(
                field_name="created_at",
                issue="Missing created_at timestamp",
                severity=Severity.INFO,
                suggestion="Add created_at = models.DateTimeField(auto_now_add=True)",
            ))
        if not has_updated and not meta.proxy and not meta.abstract:
            issues.append(FieldIssue(
                field_name="updated_at",
                issue="Missing updated_at timestamp",
                severity=Severity.INFO,
                suggestion="Add updated_at = models.DateTimeField(auto_now=True)",
            ))

        # Soft delete without index
        if "is_active" in field_names or "deleted_at" in field_names:
            soft_field_name = "deleted_at" if "deleted_at" in field_names else "is_active"
            try:
                soft_field = meta.get_field(soft_field_name)
                if hasattr(soft_field, "db_index") and not soft_field.db_index:
                    issues.append(FieldIssue(
                        field_name=soft_field_name,
                        issue=f"Soft delete field '{soft_field_name}' without index",
                        severity=Severity.WARNING,
                        suggestion=f"Add db_index=True to {soft_field_name} for efficient filtering",
                    ))
            except Exception:
                pass

        # Circular FK detection
        issues.extend(self._check_circular_fks(model))

        return issues

    def _check_circular_fks(self, model: type[models.Model]) -> list[FieldIssue]:
        issues: list[FieldIssue] = []
        visited: set[str] = set()
        model_key = f"{model._meta.app_label}.{model.__name__}"

        def _walk(current: type[models.Model], path: list[str]) -> bool:
            key = f"{current._meta.app_label}.{current.__name__}"
            if key in visited:
                return False
            if key == model_key and len(path) > 1:
                issues.append(FieldIssue(
                    field_name="*",
                    issue=f"Circular FK dependency: {' -> '.join(path)} -> {key}",
                    severity=Severity.WARNING,
                    suggestion="Consider breaking circular dependency with nullable FK or restructuring",
                ))
                return True
            visited.add(key)
            for field in current._meta.get_fields():
                if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    if _walk(field.related_model, [*path, key]):
                        return True
            visited.discard(key)
            return False

        for field in model._meta.get_fields():
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                visited.clear()
                _walk(field.related_model, [model_key])

        return issues
