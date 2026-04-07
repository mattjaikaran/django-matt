from __future__ import annotations

from django.apps import apps
from django.db import models

from pydantic import BaseModel


class IndexSuggestion(BaseModel):
    model_name: str
    field_name: str
    index_type: str
    reason: str
    migration_code: str


class NPlusOneWarning(BaseModel):
    model_name: str
    field_name: str
    related_model: str
    suggestion: str


class DenormSuggestion(BaseModel):
    source_model: str
    target_model: str
    field_name: str
    reason: str
    suggestion: str


class SchemaOptimizer:
    def suggest_indexes(self, model: type[models.Model]) -> list[IndexSuggestion]:
        suggestions: list[IndexSuggestion] = []
        meta = model._meta
        model_name = f"{meta.app_label}.{model.__name__}"

        existing_indexed: set[str] = set()
        for idx in meta.indexes:
            for field_name in idx.fields:
                existing_indexed.add(field_name.lstrip("-"))

        for field in meta.get_fields():
            if isinstance(field, models.fields.related.ForeignObjectRel):
                continue

            # FK fields that somehow lost their index
            if isinstance(field, models.ForeignKey):
                if not field.db_index and not field.unique and field.name not in existing_indexed:
                    suggestions.append(IndexSuggestion(
                        model_name=model_name,
                        field_name=field.name,
                        index_type="btree",
                        reason="ForeignKey without index slows joins",
                        migration_code=self._gen_index_migration(model, field.name),
                    ))

            # Boolean/status fields used in filtering
            if isinstance(field, models.BooleanField):
                if field.name in ("is_active", "is_published", "is_deleted", "is_archived"):
                    if not field.db_index and field.name not in existing_indexed:
                        suggestions.append(IndexSuggestion(
                            model_name=model_name,
                            field_name=field.name,
                            index_type="btree",
                            reason=f"Status field '{field.name}' likely filtered frequently",
                            migration_code=self._gen_index_migration(model, field.name),
                        ))

            # DateTimeField likely used in ordering/filtering
            if isinstance(field, (models.DateTimeField, models.DateField)):
                if field.name in ("created_at", "updated_at", "published_at", "deleted_at"):
                    if not field.db_index and field.name not in existing_indexed:
                        suggestions.append(IndexSuggestion(
                            model_name=model_name,
                            field_name=field.name,
                            index_type="btree",
                            reason=f"Timestamp field '{field.name}' commonly used in ordering/filtering",
                            migration_code=self._gen_index_migration(model, field.name),
                        ))

            # SlugField without index
            if isinstance(field, models.SlugField):
                if not field.db_index and not field.unique and field.name not in existing_indexed:
                    suggestions.append(IndexSuggestion(
                        model_name=model_name,
                        field_name=field.name,
                        index_type="btree",
                        reason="SlugField used in URL lookups should be indexed",
                        migration_code=self._gen_index_migration(model, field.name),
                    ))

        return suggestions

    def suggest_select_related(
        self, model: type[models.Model]
    ) -> list[str]:
        paths: list[str] = []
        for field in model._meta.get_fields():
            if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                paths.append(field.name)
        return paths

    def suggest_prefetch_related(
        self, model: type[models.Model]
    ) -> list[str]:
        paths: list[str] = []
        for field in model._meta.get_fields():
            if isinstance(field, models.ManyToManyField):
                paths.append(field.name)
            elif isinstance(field, models.fields.related.ForeignObjectRel):
                if hasattr(field, "related_name") and field.related_name:
                    name = field.related_name
                    if not name.endswith("+"):
                        paths.append(name)
        return paths

    def detect_n_plus_one(
        self, model: type[models.Model]
    ) -> list[NPlusOneWarning]:
        warnings: list[NPlusOneWarning] = []
        model_name = f"{model._meta.app_label}.{model.__name__}"

        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey):
                warnings.append(NPlusOneWarning(
                    model_name=model_name,
                    field_name=field.name,
                    related_model=f"{field.related_model._meta.app_label}.{field.related_model.__name__}",
                    suggestion=f"Use select_related('{field.name}') when querying {model.__name__}",
                ))
            elif isinstance(field, models.ManyToManyField):
                warnings.append(NPlusOneWarning(
                    model_name=model_name,
                    field_name=field.name,
                    related_model=f"{field.related_model._meta.app_label}.{field.related_model.__name__}",
                    suggestion=f"Use prefetch_related('{field.name}') when querying {model.__name__}",
                ))

        return warnings

    def suggest_denormalization(
        self,
        model_classes: list[type[models.Model]] | None = None,
    ) -> list[DenormSuggestion]:
        if model_classes is None:
            model_classes = apps.get_models()

        suggestions: list[DenormSuggestion] = []
        fk_count: dict[str, int] = {}

        for model in model_classes:
            for field in model._meta.get_fields():
                if isinstance(field, models.ForeignKey):
                    rel_key = f"{field.related_model._meta.app_label}.{field.related_model.__name__}"
                    fk_count[rel_key] = fk_count.get(rel_key, 0) + 1

        for rel_key, count in fk_count.items():
            if count >= 3:
                suggestions.append(DenormSuggestion(
                    source_model=rel_key,
                    target_model="multiple",
                    field_name="*",
                    reason=f"{rel_key} is referenced by {count} ForeignKeys — frequent join target",
                    suggestion=f"Consider denormalizing commonly accessed fields from {rel_key} into referencing tables",
                ))

        return suggestions

    def generate_migration(self, suggestions: list[IndexSuggestion]) -> str:
        if not suggestions:
            return "# No index suggestions to apply"

        lines = [
            "from django.db import migrations, models",
            "",
            "",
            "class Migration(migrations.Migration):",
            "",
            '    dependencies = []  # Add your dependency here',
            "",
            "    operations = [",
        ]

        for s in suggestions:
            parts = s.model_name.split(".")
            model_lower = parts[-1].lower() if parts else "model"
            lines.append(
                "        migrations.AddIndex("
            )
            lines.append(
                f"            model_name='{model_lower}',"
            )
            lines.append(
                f"            index=models.Index(fields=['{s.field_name}'], name='idx_{model_lower}_{s.field_name}'),"
            )
            lines.append("        ),")

        lines.append("    ]")
        return "\n".join(lines)

    def _gen_index_migration(self, model: type[models.Model], field_name: str) -> str:
        model_lower = model.__name__.lower()
        return (
            f"migrations.AddIndex("
            f"model_name='{model_lower}', "
            f"index=models.Index(fields=['{field_name}'], name='idx_{model_lower}_{field_name}'))"
        )
