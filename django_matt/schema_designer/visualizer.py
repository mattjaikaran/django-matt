from __future__ import annotations

from django.apps import apps
from django.db import models


def _get_models(
    app_labels: list[str] | None = None,
    model_names: list[str] | None = None,
) -> list[type[models.Model]]:
    all_models = apps.get_models()
    if app_labels:
        all_models = [m for m in all_models if m._meta.app_label in app_labels]
    if model_names:
        all_models = [m for m in all_models if m.__name__ in model_names]
    return all_models


def _field_type_str(field: models.Field) -> str:
    type_name = type(field).__name__.replace("Field", "")
    if hasattr(field, "max_length") and field.max_length:
        return f"{type_name}({field.max_length})"
    return type_name


def _get_concrete_fields(model: type[models.Model]) -> list[models.Field]:
    return [
        f for f in model._meta.get_fields()
        if not isinstance(f, models.fields.related.ForeignObjectRel)
    ]


def generate_mermaid(
    app_labels: list[str] | None = None,
    model_names: list[str] | None = None,
) -> str:
    model_list = _get_models(app_labels, model_names)
    lines = ["erDiagram"]

    for model in model_list:
        meta = model._meta
        table = f"{meta.app_label}__{model.__name__}"
        lines.append(f"    {table} {{")
        for field in _get_concrete_fields(model):
            pk_marker = " PK" if getattr(field, "primary_key", False) else ""
            fk_marker = " FK" if isinstance(field, (models.ForeignKey, models.OneToOneField)) else ""
            nullable = " \"nullable\"" if getattr(field, "null", False) else ""
            lines.append(
                f"        {_field_type_str(field)} {field.name}{pk_marker}{fk_marker}{nullable}"
            )
        lines.append("    }")

    for model in model_list:
        meta = model._meta
        table = f"{meta.app_label}__{model.__name__}"
        for field in meta.get_fields():
            if isinstance(field, models.ForeignKey):
                rel = field.related_model
                rel_table = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f"    {table} }}o--|| {rel_table} : {field.name}")
            elif isinstance(field, models.OneToOneField):
                rel = field.related_model
                rel_table = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f"    {table} ||--|| {rel_table} : {field.name}")
            elif isinstance(field, models.ManyToManyField):
                rel = field.related_model
                rel_table = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f"    {table} }}o--o{{ {rel_table} : {field.name}")

    return "\n".join(lines)


def generate_dot(
    app_labels: list[str] | None = None,
    model_names: list[str] | None = None,
) -> str:
    model_list = _get_models(app_labels, model_names)
    lines = [
        "digraph schema {",
        "    rankdir=LR;",
        '    node [shape=record, style=filled, fillcolor="#1f2937", fontcolor=white, fontname="Helvetica"];',
        '    edge [color="#6b7280"];',
    ]

    for model in model_list:
        meta = model._meta
        table = f"{meta.app_label}__{model.__name__}"
        field_rows = []
        for field in _get_concrete_fields(model):
            field_rows.append(f"{field.name}: {_field_type_str(field)}")
        label = f"{model.__name__}|" + "\\l".join(field_rows) + "\\l"
        lines.append(f'    {table} [label="{{{label}}}"];')

    for model in model_list:
        meta = model._meta
        table = f"{meta.app_label}__{model.__name__}"
        for field in meta.get_fields():
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                rel = field.related_model
                rel_table = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    style = "bold" if isinstance(field, models.OneToOneField) else "solid"
                    lines.append(f'    {table} -> {rel_table} [label="{field.name}", style={style}];')
            elif isinstance(field, models.ManyToManyField):
                rel = field.related_model
                rel_table = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f'    {table} -> {rel_table} [label="{field.name}", style=dashed];')

    lines.append("}")
    return "\n".join(lines)


def generate_dbml(
    app_labels: list[str] | None = None,
    model_names: list[str] | None = None,
) -> str:
    model_list = _get_models(app_labels, model_names)
    lines: list[str] = []

    for model in model_list:
        meta = model._meta
        table_name = meta.db_table
        lines.append(f"Table {table_name} {{")
        for field in _get_concrete_fields(model):
            attrs: list[str] = []
            if getattr(field, "primary_key", False):
                attrs.append("pk")
            if getattr(field, "unique", False) and not getattr(field, "primary_key", False):
                attrs.append("unique")
            if not getattr(field, "null", False):
                attrs.append("not null")
            attr_str = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(f"  {field.column if hasattr(field, 'column') else field.name} {_field_type_str(field)}{attr_str}")
        lines.append("}")
        lines.append("")

    for model in model_list:
        meta = model._meta
        table_name = meta.db_table
        for field in meta.get_fields():
            if isinstance(field, models.ForeignKey):
                rel = field.related_model
                if rel in model_list:
                    lines.append(
                        f"Ref: {table_name}.{field.column} > {rel._meta.db_table}.{rel._meta.pk.column}"
                    )
            elif isinstance(field, models.ManyToManyField):
                rel = field.related_model
                if rel in model_list:
                    lines.append(
                        f"Ref: {table_name}.{meta.pk.column} <> {rel._meta.db_table}.{rel._meta.pk.column}"
                    )

    return "\n".join(lines)


def generate_plantuml(
    app_labels: list[str] | None = None,
    model_names: list[str] | None = None,
) -> str:
    model_list = _get_models(app_labels, model_names)
    lines = ["@startuml", "skinparam backgroundColor #111827", "skinparam class {",
             "  BackgroundColor #1f2937", "  BorderColor #4b5563",
             "  FontColor white", "  ArrowColor #6b7280", "}"]

    for model in model_list:
        meta = model._meta
        entity = f"{meta.app_label}__{model.__name__}"
        lines.append(f"entity {entity} {{")
        for field in _get_concrete_fields(model):
            pk = " <<PK>>" if getattr(field, "primary_key", False) else ""
            fk = " <<FK>>" if isinstance(field, (models.ForeignKey, models.OneToOneField)) else ""
            lines.append(f"  {field.name} : {_field_type_str(field)}{pk}{fk}")
        lines.append("}")

    for model in model_list:
        meta = model._meta
        entity = f"{meta.app_label}__{model.__name__}"
        for field in meta.get_fields():
            if isinstance(field, models.ForeignKey):
                rel = field.related_model
                rel_entity = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f"{entity} }}o--|| {rel_entity}")
            elif isinstance(field, models.OneToOneField):
                rel = field.related_model
                rel_entity = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f"{entity} ||--|| {rel_entity}")
            elif isinstance(field, models.ManyToManyField):
                rel = field.related_model
                rel_entity = f"{rel._meta.app_label}__{rel.__name__}"
                if rel in model_list:
                    lines.append(f"{entity} }}o--o{{ {rel_entity}")

    lines.append("@enduml")
    return "\n".join(lines)
