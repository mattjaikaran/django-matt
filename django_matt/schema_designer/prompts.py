from __future__ import annotations

from django_matt.schema_designer.analyzer import SchemaAnalyzer, Severity
from django_matt.schema_designer.visualizer import _get_models, _field_type_str, _get_concrete_fields


def _compact_schema(app_labels: list[str] | None = None) -> str:
    lines: list[str] = []
    for model in _get_models(app_labels):
        meta = model._meta
        lines.append(f"## {meta.app_label}.{model.__name__} (table: {meta.db_table})")
        for field in _get_concrete_fields(model):
            markers: list[str] = []
            if getattr(field, "primary_key", False):
                markers.append("PK")
            if getattr(field, "unique", False):
                markers.append("UNIQUE")
            if getattr(field, "null", False):
                markers.append("NULL")
            if getattr(field, "db_index", False):
                markers.append("INDEXED")
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            lines.append(f"  - {field.name}: {_field_type_str(field)}{marker_str}")
        lines.append("")
    return "\n".join(lines)


def generate_schema_prompt(
    app_labels: list[str] | None = None,
) -> str:
    schema_text = _compact_schema(app_labels)
    analyzer = SchemaAnalyzer(app_labels=app_labels)
    report = analyzer.analyze_all()

    issues_text = ""
    if report.total_issues > 0:
        issue_lines: list[str] = []
        for model_report in report.models:
            if model_report.issues:
                issue_lines.append(f"\n### {model_report.full_name}")
                for issue in model_report.issues:
                    icon = {"error": "ERROR", "warning": "WARN", "info": "INFO"}[issue.severity.value]
                    issue_lines.append(f"  [{icon}] {issue.field_name}: {issue.issue}")
        issues_text = "\n".join(issue_lines)

    return f"""You are a database schema expert reviewing a Django project.

## Current Schema

{schema_text}

## Automated Analysis Results

Found {report.total_issues} issues ({report.total_errors} errors, {report.total_warnings} warnings, {report.total_info} info).
{issues_text}

## Task

Review this schema and provide:
1. Critical issues that could cause data integrity problems
2. Performance optimizations (missing indexes, N+1 risks, denormalization opportunities)
3. Schema design improvements (naming, normalization, constraints)
4. Migration safety concerns for suggested changes

Use Django best practices. Be specific with field names and model references.
Prioritize suggestions by impact.
"""


def generate_migration_prompt(
    from_description: str,
    to_description: str,
) -> str:
    return f"""You are a Django migration expert.

## Current Schema State

{from_description}

## Desired Schema State

{to_description}

## Task

Generate a Django migration plan:
1. List each migration operation needed (AddField, RemoveField, AlterField, AddIndex, etc.)
2. Identify data migrations needed (RunPython operations)
3. Flag any destructive operations (column drops, type changes) that need special handling
4. Suggest a safe deployment order if multiple migrations are needed
5. Note any operations that require downtime vs. online-safe operations

Output the migration operations in Django migration format.
Consider backwards compatibility and rollback safety.
"""


def generate_review_prompt(
    app_labels: list[str] | None = None,
) -> str:
    schema_text = _compact_schema(app_labels)
    model_list = _get_models(app_labels)

    relationship_text: list[str] = []
    for model in model_list:
        from django.db import models as m
        for field in model._meta.get_fields():
            if isinstance(field, m.ForeignKey):
                relationship_text.append(
                    f"  {model.__name__}.{field.name} -> {field.related_model.__name__} (FK)"
                )
            elif isinstance(field, m.ManyToManyField):
                relationship_text.append(
                    f"  {model.__name__}.{field.name} <-> {field.related_model.__name__} (M2M)"
                )

    rels = "\n".join(relationship_text) if relationship_text else "  (no relationships found)"

    return f"""You are reviewing a Django database schema for correctness and best practices.

## Schema

{schema_text}

## Relationships

{rels}

## Review Checklist

Please evaluate:
1. **Normalization**: Are there redundant fields? Should any data be normalized/denormalized?
2. **Naming**: Do field/model names follow Django conventions? Are they clear and consistent?
3. **Constraints**: Are there missing unique_together, CheckConstraint, or validation rules?
4. **Indexes**: Are commonly queried fields indexed? Are there unnecessary indexes?
5. **Relationships**: Are FK/M2M relationships correct? Missing on_delete handlers?
6. **Data Types**: Are field types optimal? (CharField vs TextField, Integer sizes, etc.)
7. **Defaults**: Are sensible defaults provided? Are null/blank used correctly?
8. **Timestamps**: Do models have created_at/updated_at where appropriate?
9. **Security**: Are there fields that should be encrypted or have restricted access?
10. **Scalability**: Will this schema perform well at scale? Partitioning needs?

Provide specific, actionable feedback for each point.
"""
