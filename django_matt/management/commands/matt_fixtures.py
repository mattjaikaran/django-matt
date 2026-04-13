"""
Generate fixture definition files (reusable seed configs).

Usage:
    python manage.py matt_fixtures myapp.Product --output fixtures/products.py
    python manage.py matt_fixtures myapp --output fixtures/myapp.py
"""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.core.management.base import CommandError
from django.db import models

from django_matt.cli import MattCommand

# Map Django field types to faker-style generator strings
_FIELD_GENERATORS: dict[type, str | None] = {
    models.AutoField: None,
    models.BigAutoField: None,
    models.SmallAutoField: None,
    models.CharField: "faker.lorem.word",
    models.TextField: "faker.lorem.paragraph",
    models.IntegerField: "faker.random_int(0, 10000)",
    models.BigIntegerField: "faker.random_int(0, 100000)",
    models.SmallIntegerField: "faker.random_int(0, 1000)",
    models.PositiveIntegerField: "faker.random_int(0, 10000)",
    models.PositiveSmallIntegerField: "faker.random_int(0, 1000)",
    models.FloatField: "faker.random_float(0, 1000)",
    models.DecimalField: "faker.decimal(max_digits=10, decimal_places=2)",
    models.BooleanField: "faker.boolean",
    models.DateField: "faker.date.this_year",
    models.DateTimeField: "faker.datetime.this_year",
    models.TimeField: "faker.time",
    models.DurationField: "faker.duration",
    models.EmailField: "faker.internet.email",
    models.URLField: "faker.internet.url",
    models.SlugField: "faker.lorem.slug",
    models.UUIDField: "faker.uuid4",
    models.IPAddressField: "faker.internet.ip_address",
    models.GenericIPAddressField: "faker.internet.ip_address",
    models.JSONField: "faker.json_object",
    models.BinaryField: None,
    models.FileField: None,
    models.ImageField: None,
    models.FilePathField: None,
}

# Name-based overrides for CharField/TextField
_NAME_OVERRIDES: dict[str, str] = {
    "email": "faker.internet.email",
    "first_name": "faker.name.first_name",
    "last_name": "faker.name.last_name",
    "name": "faker.name.full_name",
    "full_name": "faker.name.full_name",
    "username": "faker.internet.username",
    "phone": "faker.phone_number",
    "phone_number": "faker.phone_number",
    "title": "faker.lorem.sentence",
    "subject": "faker.lorem.sentence",
    "headline": "faker.lorem.sentence",
    "description": "faker.lorem.paragraph",
    "bio": "faker.lorem.paragraph",
    "body": "faker.lorem.paragraph",
    "content": "faker.lorem.paragraph",
    "summary": "faker.lorem.paragraph",
    "address": "faker.address.street_address",
    "city": "faker.address.city",
    "state": "faker.address.state",
    "country": "faker.address.country",
    "zip_code": "faker.address.zip_code",
    "postal_code": "faker.address.zip_code",
    "company": "faker.company.name",
    "organization": "faker.company.name",
    "website": "faker.internet.url",
    "url": "faker.internet.url",
    "price": "faker.commerce.price",
    "cost": "faker.commerce.price",
    "amount": "faker.commerce.price",
    "avatar": "faker.internet.url",
    "image": "faker.internet.url",
}


def _get_generator_for_field(field: models.Field) -> str | None:
    """Determine the generator string for a field."""
    if field.primary_key:
        return None

    # FK fields
    if isinstance(field, models.ForeignKey):
        related = field.related_model
        return f"random:{related._meta.app_label}.{related.__name__}"

    # name-based heuristic for char/text fields
    if isinstance(field, (models.CharField, models.TextField)):
        override = _NAME_OVERRIDES.get(field.name.lower())
        if override:
            return override

    # type-based lookup
    for field_type, generator in _FIELD_GENERATORS.items():
        if isinstance(field, field_type):
            return generator

    return "faker.lorem.word"


def _generate_fixture_code(
    model: type[models.Model],
) -> str:
    """Generate fixture definition code for a single model."""
    app_label = model._meta.app_label
    model_name = model.__name__
    lines = []

    # collect field generators
    field_defs: dict[str, str] = {}
    for field in model._meta.fields:
        gen = _get_generator_for_field(field)
        if gen is not None:
            field_defs[field.name] = gen

    if not field_defs:
        return ""

    lines.append(f'{model_name}Factory = factory("{app_label}.{model_name}", {{')
    for fname, gen in field_defs.items():
        lines.append(f'    "{fname}": "{gen}",')
    lines.append("})")

    return "\n".join(lines)


class Command(MattCommand):
    help = "Generate fixture definition files for reusable seed configs"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "target",
            help="Model (myapp.Product) or app (myapp) to generate fixtures for",
        )
        parser.add_argument(
            "--output",
            "-o",
            help="Output file path (default: stdout)",
        )

    def handle(self, *args, **options):
        target = options["target"]
        output_path = options.get("output")

        target_models = self._resolve_targets(target)
        if not target_models:
            raise CommandError("No models found for the given target")

        self.console.header("Fixture Generator", f"{len(target_models)} model(s)")

        # generate code
        sections: list[str] = []
        header_lines = [
            '"""',
            f"Fixture definitions for {target}.",
            "",
            "Generated by: python manage.py matt_fixtures",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "from django_matt.testing.factories import factory",
            "",
        ]

        sections.append("\n".join(header_lines))

        for model in target_models:
            code = _generate_fixture_code(model)
            if code:
                sections.append(code)
                self.console.success(
                    f"Generated factory for {model._meta.app_label}.{model.__name__}"
                )

        full_code = "\n\n".join(sections) + "\n"

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(full_code)
            self.console.newline()
            self.console.success(f"Wrote fixture definitions to {output_path}")
        else:
            self.console.newline()
            self.console.code(full_code, language="python")

    def _resolve_targets(self, target: str) -> list[type[models.Model]]:
        """Resolve target string to a list of model classes."""
        # try as model first (app_label.ModelName)
        if "." in target:
            parts = target.rsplit(".", 1)
            try:
                return [apps.get_model(parts[0], parts[1])]
            except LookupError:
                raise CommandError(f"Model '{target}' not found.")

        # try as app
        try:
            app_config = apps.get_app_config(target)
            return list(app_config.get_models())
        except LookupError:
            raise CommandError(
                f"'{target}' is not a valid app or model. "
                "Use 'app_label.ModelName' for a model or 'app_label' for an app."
            )
