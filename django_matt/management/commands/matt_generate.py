# file-length-max: 1000
"""
Angular CLI-style scaffolding generators for Django Matt.

Supports generating individual components: models, controllers, services,
schemas, tests, middleware, migrations, and factories.

Usage:
    python manage.py matt_generate model myapp.Product --fields "name:str price:decimal:2"
    python manage.py matt_generate controller myapp.Product
    python manage.py matt_generate service myapp.Product
    python manage.py matt_generate schema myapp.Product
    python manage.py matt_generate test myapp.Product
    python manage.py matt_generate middleware myapp.RequestLogger
    python manage.py matt_generate migration myapp --name populate_defaults
    python manage.py matt_generate factory myapp.Product
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.management.base import CommandError

from django_matt.cli import GeneratorCommand

# Field type DSL → Django field mapping
FIELD_TYPE_MAP: dict[str, dict[str, Any]] = {
    "str": {"field": "CharField", "kwargs": {"max_length": 255}},
    "text": {"field": "TextField", "kwargs": {}},
    "int": {"field": "IntegerField", "kwargs": {}},
    "float": {"field": "FloatField", "kwargs": {}},
    "bool": {"field": "BooleanField", "kwargs": {"default": False}},
    "date": {"field": "DateField", "kwargs": {}},
    "datetime": {"field": "DateTimeField", "kwargs": {}},
    "uuid": {"field": "UUIDField", "kwargs": {"default": "uuid.uuid4", "editable": False}},
    "email": {"field": "EmailField", "kwargs": {}},
    "url": {"field": "URLField", "kwargs": {}},
    "slug": {"field": "SlugField", "kwargs": {"unique": True}},
    "json": {"field": "JSONField", "kwargs": {"default": "dict"}},
    "file": {"field": "FileField", "kwargs": {"upload_to": "uploads/"}},
    "image": {"field": "ImageField", "kwargs": {"upload_to": "images/"}},
    "decimal": {"field": "DecimalField", "kwargs": {"max_digits": 10, "decimal_places": 2}},
}

# Field type → Faker provider for factory generation
FAKER_MAP: dict[str, str] = {
    "str": "fake.pystr(max_chars=50)",
    "text": "fake.paragraph()",
    "int": "fake.random_int(min=1, max=1000)",
    "float": "fake.pyfloat(positive=True)",
    "bool": "fake.pybool()",
    "date": "fake.date_object()",
    "datetime": "fake.date_time(tzinfo=timezone.utc)",
    "uuid": "uuid.uuid4()",
    "email": "fake.email()",
    "url": "fake.url()",
    "slug": "fake.slug()",
    "json": "{}",
    "decimal": "fake.pydecimal(left_digits=5, right_digits=2, positive=True)",
    "file": "None",
    "image": "None",
}

# Field type → Pydantic type annotation
PYDANTIC_TYPE_MAP: dict[str, str] = {
    "str": "str",
    "text": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "date": "date",
    "datetime": "datetime",
    "uuid": "UUID",
    "email": "str",
    "url": "str",
    "slug": "str",
    "json": "dict[str, Any]",
    "decimal": "Decimal",
    "file": "str | None",
    "image": "str | None",
    "fk": "int",
    "m2m": "list[int]",
}

VALID_GENERATORS = [
    "model",
    "controller",
    "service",
    "schema",
    "test",
    "middleware",
    "migration",
    "factory",
]


def _parse_field(field_str: str) -> dict[str, Any]:
    """Parse a field DSL string like 'name:str' or 'price:decimal:2' or 'category:fk:Category'."""
    parts = field_str.split(":")
    if len(parts) < 2:
        raise CommandError(
            f"Invalid field format: '{field_str}'. Expected 'name:type' or 'name:type:extra'"
        )

    name = parts[0]
    field_type = parts[1].lower()
    extra = parts[2] if len(parts) > 2 else None

    if field_type not in FIELD_TYPE_MAP and field_type not in ("fk", "m2m"):
        valid = ", ".join(sorted(set(list(FIELD_TYPE_MAP.keys()) + ["fk", "m2m"])))
        raise CommandError(
            f"Unknown field type '{field_type}' for field '{name}'. Valid types: {valid}"
        )

    return {"name": name, "type": field_type, "extra": extra}


def _pluralize(name: str) -> str:
    """Naive pluralization for URL prefixes."""
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"


def _snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


class Command(GeneratorCommand):
    """Scaffold individual components: model, controller, service, schema, test, middleware, migration, or factory."""

    help = "Generate individual Django Matt components (model, controller, service, schema, test, middleware, migration, factory)"

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "generator",
            choices=VALID_GENERATORS,
            help="Type of component to generate",
        )
        parser.add_argument(
            "target",
            help="Target in app.Name format (e.g. myapp.Product) or just app name for migration",
        )
        parser.add_argument(
            "--fields",
            type=str,
            default="",
            help='Field definitions DSL: "name:str price:decimal:2 category:fk:Category"',
        )
        parser.add_argument(
            "--name",
            type=str,
            default="",
            help="Name for migration (used with migration generator)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        generator = options["generator"]
        target = options["target"]

        self.header("Django Matt Generator", f"Generating {generator}")

        # Parse target into app_label and name
        if "." in target:
            self._app_label, self._name = target.rsplit(".", 1)
        else:
            self._app_label = target
            self._name = ""

        # Validate app exists
        self._validate_app(self._app_label)

        # Parse fields if provided
        self._fields: list[dict[str, Any]] = []
        if options["fields"]:
            for f in options["fields"].split():
                self._fields.append(_parse_field(f))

        # Store extra options
        self._migration_name = options.get("name", "")

        # Resolve app path
        app_config = apps.get_app_config(self._app_label)
        self._app_path = Path(app_config.path)

        # Dispatch to generator method
        method = getattr(self, f"_generate_{generator}")
        method()

        self.show_summary()

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_app(self, app_label: str) -> None:
        """Validate the Django app exists."""
        try:
            apps.get_app_config(app_label)
        except LookupError:
            installed = sorted(c.label for c in apps.get_app_configs())
            self.fail_invalid_argument(
                "target",
                f"App '{app_label}' is not installed",
                valid_values=installed[:20],
            )

    def _resolve_model_class(self) -> Any:
        """Try to resolve an existing Django model class. Returns None if not found."""
        try:
            return apps.get_model(self._app_label, self._name)
        except LookupError:
            return None

    def _get_model_fields_from_class(self, model_class: Any) -> list[dict[str, Any]]:
        """Extract field info from an existing Django model class."""
        from django.db.models.fields.related import ForeignKey, ManyToManyField

        fields: list[dict[str, Any]] = []
        for field in model_class._meta.get_fields():
            if field.name in ("id", "pk"):
                continue
            if isinstance(field, ManyToManyField):
                fields.append(
                    {
                        "name": field.name,
                        "type": "m2m",
                        "extra": field.related_model.__name__,
                    }
                )
            elif isinstance(field, ForeignKey):
                fields.append(
                    {
                        "name": field.name,
                        "type": "fk",
                        "extra": field.related_model.__name__,
                    }
                )
            elif hasattr(field, "get_internal_type"):
                django_type = field.get_internal_type()
                type_map = {
                    "CharField": "str",
                    "TextField": "text",
                    "IntegerField": "int",
                    "FloatField": "float",
                    "BooleanField": "bool",
                    "DateField": "date",
                    "DateTimeField": "datetime",
                    "UUIDField": "uuid",
                    "EmailField": "email",
                    "URLField": "url",
                    "SlugField": "slug",
                    "JSONField": "json",
                    "DecimalField": "decimal",
                    "FileField": "file",
                    "ImageField": "image",
                }
                field_type = type_map.get(django_type, "str")
                fields.append({"name": field.name, "type": field_type, "extra": None})
        return fields

    def _effective_fields(self) -> list[dict[str, Any]]:
        """Return fields from --fields flag, or auto-detect from existing model."""
        if self._fields:
            return self._fields
        model_class = self._resolve_model_class()
        if model_class is not None:
            return self._get_model_fields_from_class(model_class)
        return []

    # =========================================================================
    # Model Generator
    # =========================================================================

    def _generate_model(self) -> None:
        if not self._name:
            raise CommandError("Model generator requires app.ModelName format")
        if not self._fields:
            raise CommandError("Model generator requires --fields argument")

        snake = _snake_case(self._name)
        lines = [
            "import uuid",
            "",
            "from django.db import models",
            "",
            "",
            f"class {self._name}(models.Model):",
        ]

        # Build fields
        for f in self._fields:
            line = self._render_model_field(f)
            lines.append(f"    {line}")

        # Auto timestamp fields
        lines.append("    created_at = models.DateTimeField(auto_now_add=True)")
        lines.append("    updated_at = models.DateTimeField(auto_now=True)")

        # __str__
        first_str_field = next(
            (f["name"] for f in self._fields if f["type"] in ("str", "email", "slug")),
            None,
        )
        lines.append("")
        if first_str_field:
            lines.append("    def __str__(self) -> str:")
            lines.append(f"        return self.{first_str_field}")
        else:
            lines.append("    def __str__(self) -> str:")
            lines.append(f'        return f"{self._name} {{self.pk}}"')

        # Meta
        lines.append("")
        lines.append("    class Meta:")
        lines.append('        ordering = ["-created_at"]')
        lines.append(f'        verbose_name = "{self._name}"')
        lines.append(f'        verbose_name_plural = "{_pluralize(self._name)}"')
        lines.append("")

        content = "\n".join(lines)
        target_file = self._app_path / "models.py"

        if target_file.exists():
            self.append_to_file(target_file, content)
        else:
            self.write_file(target_file, content)

        self.success(f"Generated model {self._name}")

    def _render_model_field(self, field: dict[str, Any]) -> str:
        """Render a single Django model field definition."""
        name = field["name"]
        ftype = field["type"]
        extra = field["extra"]

        if ftype == "fk":
            related = extra or "MISSING_MODEL"
            return (
                f'{name} = models.ForeignKey("{related}", on_delete=models.CASCADE, '
                f'related_name="{_snake_case(self._name)}_{name}")'
            )
        if ftype == "m2m":
            related = extra or "MISSING_MODEL"
            return (
                f'{name} = models.ManyToManyField("{related}", '
                f'related_name="{_snake_case(self._name)}_{name}", blank=True)'
            )
        if ftype == "decimal":
            dp = int(extra) if extra else 2
            return f"{name} = models.DecimalField(max_digits=10, decimal_places={dp})"

        mapping = FIELD_TYPE_MAP.get(ftype)
        if not mapping:
            return f"{name} = models.CharField(max_length=255)  # unknown type: {ftype}"

        field_class = mapping["field"]
        kwargs = dict(mapping["kwargs"])

        # Handle special defaults that should be unquoted
        kwarg_parts: list[str] = []
        for k, v in kwargs.items():
            if (isinstance(v, str) and (v.startswith("uuid.") or v == "dict")) or isinstance(
                v, (bool, int)
            ):
                kwarg_parts.append(f"{k}={v}")
            else:
                kwarg_parts.append(f'{k}="{v}"')

        kwarg_str = ", ".join(kwarg_parts)
        return f"{name} = models.{field_class}({kwarg_str})"

    # =========================================================================
    # Controller Generator
    # =========================================================================

    def _generate_controller(self) -> None:
        if not self._name:
            raise CommandError("Controller generator requires app.ModelName format")

        snake = _snake_case(self._name)
        plural = _pluralize(snake)
        prefix = f"/{plural}"

        content = textwrap.dedent(f"""\
            from django_matt.core import APIController, api

            from .schemas import (
                {self._name}CreateSchema,
                {self._name}ListSchema,
                {self._name}Schema,
                {self._name}UpdateSchema,
            )
            from .services import {self._name}Service


            class {self._name}Controller(APIController):
                prefix = "{prefix}"
                tags = ["{self._name}"]
                permission_classes = []  # TODO: add permissions

                def __init__(self) -> None:
                    self.service = {self._name}Service()

                @api.get("/")
                async def list_{plural}(self) -> {self._name}ListSchema:
                    items = await self.service.list()
                    return {self._name}ListSchema(items=items, count=len(items))

                @api.post("/", status_code=201)
                async def create_{snake}(self, data: {self._name}CreateSchema) -> {self._name}Schema:
                    return await self.service.create(data)

                @api.get("/{{id}}")
                async def get_{snake}(self, id: int) -> {self._name}Schema:
                    return await self.service.get(id)

                @api.put("/{{id}}")
                async def update_{snake}(self, id: int, data: {self._name}UpdateSchema) -> {self._name}Schema:
                    return await self.service.update(id, data)

                @api.delete("/{{id}}", status_code=204)
                async def delete_{snake}(self, id: int) -> None:
                    await self.service.delete(id)
        """)

        target = self._app_path / "controllers.py"
        if target.exists() and not self._force:
            self.append_to_file(target, content)
        else:
            self.write_file(target, content)

        self.success(f"Generated controller for {self._name}")

    # =========================================================================
    # Service Generator
    # =========================================================================

    def _generate_service(self) -> None:
        if not self._name:
            raise CommandError("Service generator requires app.ModelName format")

        snake = _snake_case(self._name)

        content = textwrap.dedent(f"""\
            from django.shortcuts import aget_object_or_404

            from .models import {self._name}
            from .schemas import {self._name}CreateSchema, {self._name}Schema, {self._name}UpdateSchema


            class {self._name}Service:
                \"\"\"Service layer for {self._name} business logic.\"\"\"

                async def list(self) -> list[{self._name}Schema]:
                    items = []
                    async for obj in {self._name}.objects.all():
                        items.append({self._name}Schema.from_orm(obj))
                    return items

                async def get(self, id: int) -> {self._name}Schema:
                    obj = await aget_object_or_404({self._name}, pk=id)
                    return {self._name}Schema.from_orm(obj)

                async def create(self, data: {self._name}CreateSchema) -> {self._name}Schema:
                    obj = await {self._name}.objects.acreate(**data.model_dump())
                    return {self._name}Schema.from_orm(obj)

                async def update(self, id: int, data: {self._name}UpdateSchema) -> {self._name}Schema:
                    obj = await aget_object_or_404({self._name}, pk=id)
                    for attr, value in data.model_dump(exclude_unset=True).items():
                        setattr(obj, attr, value)
                    await obj.asave()
                    return {self._name}Schema.from_orm(obj)

                async def delete(self, id: int) -> None:
                    obj = await aget_object_or_404({self._name}, pk=id)
                    await obj.adelete()
        """)

        target = self._app_path / "services.py"
        if target.exists() and not self._force:
            self.append_to_file(target, content)
        else:
            self.write_file(target, content)

        self.success(f"Generated service for {self._name}")

    # =========================================================================
    # Schema Generator
    # =========================================================================

    def _generate_schema(self) -> None:
        if not self._name:
            raise CommandError("Schema generator requires app.ModelName format")

        fields = self._effective_fields()

        # Build field lines for schemas
        read_lines: list[str] = ["    id: int"]
        create_lines: list[str] = []
        update_lines: list[str] = []

        # Track needed imports
        needs_date = False
        needs_datetime = False
        needs_uuid = False
        needs_decimal = False
        needs_any = False

        for f in fields:
            fname = f["name"]
            ftype = f["type"]

            if ftype in ("date",):
                needs_date = True
            if ftype in ("datetime",):
                needs_datetime = True
            if ftype == "uuid":
                needs_uuid = True
            if ftype == "decimal":
                needs_decimal = True
            if ftype == "json":
                needs_any = True

            pydantic_type = PYDANTIC_TYPE_MAP.get(ftype, "str")

            # For FK fields, use the _id suffix in schemas
            if ftype == "fk":
                read_lines.append(f"    {fname}_id: int")
                create_lines.append(f"    {fname}_id: int")
                update_lines.append(f"    {fname}_id: int | None = None")
            elif ftype == "m2m":
                read_lines.append(f"    {fname}: list[int] = []")
                create_lines.append(f"    {fname}: list[int] = []")
                update_lines.append(f"    {fname}: list[int] | None = None")
            else:
                read_lines.append(f"    {fname}: {pydantic_type}")
                create_lines.append(f"    {fname}: {pydantic_type}")
                update_lines.append(f"    {fname}: {pydantic_type} | None = None")

        # Timestamp fields for read schema only
        read_lines.append("    created_at: datetime")
        read_lines.append("    updated_at: datetime")
        needs_datetime = True

        # Build imports
        type_imports: list[str] = []
        if needs_any:
            type_imports.append("Any")
        if needs_date:
            type_imports.append("date")
        if needs_datetime:
            type_imports.append("datetime")
        if needs_decimal:
            type_imports.append("Decimal")
        if needs_uuid:
            type_imports.append("UUID")

        import_lines: list[str] = ["from __future__ import annotations", ""]
        if type_imports:
            # Group stdlib imports properly
            datetime_imports = [t for t in type_imports if t in ("date", "datetime")]
            other_imports = [t for t in type_imports if t not in ("date", "datetime")]

            if datetime_imports:
                import_lines.append(f"from datetime import {', '.join(sorted(datetime_imports))}")
            if "Decimal" in other_imports:
                import_lines.append("from decimal import Decimal")
            if "Any" in other_imports:
                import_lines.append("from typing import Any")
            if "UUID" in other_imports:
                import_lines.append("from uuid import UUID")
            import_lines.append("")

        import_lines.append("from pydantic import BaseModel")

        read_fields = "\n".join(read_lines) if read_lines else "    pass"
        create_fields = "\n".join(create_lines) if create_lines else "    pass"
        update_fields = "\n".join(update_lines) if update_lines else "    pass"

        content = "\n".join(import_lines) + "\n"
        content += textwrap.dedent(f"""

            class {self._name}Schema(BaseModel):
                \"\"\"Read schema for {self._name}.\"\"\"

            {read_fields}

                model_config = {{"from_attributes": True}}


            class {self._name}CreateSchema(BaseModel):
                \"\"\"Create schema for {self._name}.\"\"\"

            {create_fields}


            class {self._name}UpdateSchema(BaseModel):
                \"\"\"Update schema for {self._name}.\"\"\"

            {update_fields}


            class {self._name}ListSchema(BaseModel):
                \"\"\"List response schema for {self._name}.\"\"\"

                items: list[{self._name}Schema]
                count: int
        """)

        target = self._app_path / "schemas.py"
        if target.exists() and not self._force:
            self.append_to_file(target, content)
        else:
            self.write_file(target, content)

        self.success(f"Generated schemas for {self._name}")

    # =========================================================================
    # Test Generator
    # =========================================================================

    def _generate_test(self) -> None:
        if not self._name:
            raise CommandError("Test generator requires app.ModelName format")

        snake = _snake_case(self._name)
        plural = _pluralize(snake)

        content = textwrap.dedent(f"""\
            import pytest

            from {self._app_label}.models import {self._name}


            @pytest.fixture
            def {snake}_data() -> dict:
                \"\"\"Sample data for creating a {self._name}.\"\"\"
                return {{
                    # TODO: fill in test data
                }}


            @pytest.fixture
            async def {snake}({snake}_data: dict) -> {self._name}:
                \"\"\"Create a {self._name} instance for testing.\"\"\"
                return await {self._name}.objects.acreate(**{snake}_data)


            @pytest.mark.django_db(transaction=True)
            class Test{self._name}Model:
                \"\"\"Tests for the {self._name} model.\"\"\"

                async def test_create_{snake}(self, {snake}_data: dict) -> None:
                    obj = await {self._name}.objects.acreate(**{snake}_data)
                    assert obj.pk is not None

                async def test_read_{snake}(self, {snake}: {self._name}) -> None:
                    fetched = await {self._name}.objects.aget(pk={snake}.pk)
                    assert fetched.pk == {snake}.pk

                async def test_update_{snake}(self, {snake}: {self._name}) -> None:
                    # TODO: update a field
                    await {snake}.asave()
                    await {snake}.arefresh_from_db()

                async def test_delete_{snake}(self, {snake}: {self._name}) -> None:
                    pk = {snake}.pk
                    await {snake}.adelete()
                    assert not await {self._name}.objects.filter(pk=pk).aexists()

                async def test_list_{plural}(self, {snake}: {self._name}) -> None:
                    count = await {self._name}.objects.acount()
                    assert count >= 1

                async def test_str_{snake}(self, {snake}: {self._name}) -> None:
                    assert str({snake})
        """)

        tests_dir = self._app_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        init_file = tests_dir / "__init__.py"
        if not init_file.exists():
            self.write_file(init_file, "")

        target = tests_dir / f"test_{snake}.py"
        self.write_file(target, content)

        self.success(f"Generated tests for {self._name}")

    # =========================================================================
    # Middleware Generator
    # =========================================================================

    def _generate_middleware(self) -> None:
        if not self._name:
            raise CommandError("Middleware generator requires app.MiddlewareName format")

        snake = _snake_case(self._name)

        content = textwrap.dedent(f"""\
            import logging
            from collections.abc import Callable

            from django.http import HttpRequest, HttpResponse

            logger = logging.getLogger(__name__)


            class {self._name}:
                \"\"\"
                {self._name} middleware.

                Add to MIDDLEWARE in settings:
                    '{self._app_label}.middleware.{self._name}'
                \"\"\"

                def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
                    self.get_response = get_response

                def __call__(self, request: HttpRequest) -> HttpResponse:
                    self.process_request(request)
                    response = self.get_response(request)
                    self.process_response(request, response)
                    return response

                async def __acall__(self, request: HttpRequest) -> HttpResponse:
                    self.process_request(request)
                    response = await self.get_response(request)
                    self.process_response(request, response)
                    return response

                def process_request(self, request: HttpRequest) -> None:
                    \"\"\"Called before the view. Modify request or perform checks.\"\"\"
                    pass

                def process_response(self, request: HttpRequest, response: HttpResponse) -> None:
                    \"\"\"Called after the view. Modify response or perform logging.\"\"\"
                    pass
        """)

        target = self._app_path / "middleware.py"
        if target.exists() and not self._force:
            self.append_to_file(target, content)
        else:
            self.write_file(target, content)

        self.success(f"Generated middleware {self._name}")

    # =========================================================================
    # Migration Generator
    # =========================================================================

    def _generate_migration(self) -> None:
        migration_name = self._migration_name or "custom_data_migration"
        snake_name = _snake_case(migration_name).replace(" ", "_")

        # Find next migration number
        migrations_dir = self._app_path / "migrations"
        if not migrations_dir.exists():
            raise CommandError(
                f"No migrations directory found at {migrations_dir}. "
                f"Run 'python manage.py makemigrations {self._app_label}' first."
            )

        existing = sorted(migrations_dir.glob("*.py"))
        max_num = 0
        for p in existing:
            match = re.match(r"^(\d+)", p.stem)
            if match:
                max_num = max(max_num, int(match.group(1)))

        next_num = f"{max_num + 1:04d}"
        filename = f"{next_num}_{snake_name}.py"

        # Find latest migration for dependency
        latest = "0001_initial"
        for p in existing:
            if p.stem != "__init__" and re.match(r"^\d+", p.stem):
                latest = p.stem

        content = textwrap.dedent(f"""\
            \"\"\"
            Data migration: {migration_name}

            Generated by matt_generate. Fill in forwards() and backwards() below.
            \"\"\"

            from django.db import migrations


            def forwards(apps, schema_editor):
                \"\"\"
                Apply data migration.

                Use apps.get_model('{self._app_label}', 'ModelName') to get model classes.
                Do NOT import models directly — use the historical versions from apps.
                \"\"\"
                # Example:
                # MyModel = apps.get_model('{self._app_label}', 'MyModel')
                # MyModel.objects.filter(status='').update(status='active')
                pass


            def backwards(apps, schema_editor):
                \"\"\"
                Reverse the data migration.

                Undo whatever forwards() did. If irreversible, raise RuntimeError.
                \"\"\"
                pass


            class Migration(migrations.Migration):
                dependencies = [
                    ('{self._app_label}', '{latest}'),
                ]

                operations = [
                    migrations.RunPython(forwards, backwards),
                ]
        """)

        target = migrations_dir / filename
        self.write_file(target, content)

        self.success(f"Generated migration {filename}")

    # =========================================================================
    # Factory Generator
    # =========================================================================

    def _generate_factory(self) -> None:
        if not self._name:
            raise CommandError("Factory generator requires app.ModelName format")

        snake = _snake_case(self._name)
        fields = self._effective_fields()

        # Build factory field assignments
        field_lines: list[str] = []
        needs_uuid = False
        needs_timezone = False

        for f in fields:
            fname = f["name"]
            ftype = f["type"]

            if ftype == "uuid":
                needs_uuid = True
            if ftype == "datetime":
                needs_timezone = True

            if ftype == "fk":
                field_lines.append(f"        # {fname}: create or pass a related object")
            elif ftype == "m2m":
                continue  # M2M set after creation
            else:
                faker_val = FAKER_MAP.get(ftype, "fake.pystr()")
                field_lines.append(f"        {fname}={faker_val},")

        factory_fields = "\n".join(field_lines) if field_lines else "        pass"

        # Build imports
        extra_imports: list[str] = []
        if needs_uuid:
            extra_imports.append("import uuid")
        if needs_timezone:
            extra_imports.append("from datetime import timezone")

        extra_import_str = "\n".join(extra_imports)
        if extra_import_str:
            extra_import_str += "\n"

        content = textwrap.dedent(f"""\
            {extra_import_str}from faker import Faker

            from {self._app_label}.models import {self._name}

            fake = Faker()


            def create_{snake}(**overrides) -> {self._name}:
                \"\"\"Create a {self._name} instance with realistic fake data.\"\"\"
                defaults = dict(
            {factory_fields}
                )
                defaults.update(overrides)
                return {self._name}.objects.create(**defaults)


            async def acreate_{snake}(**overrides) -> {self._name}:
                \"\"\"Async version of create_{snake}.\"\"\"
                defaults = dict(
            {factory_fields}
                )
                defaults.update(overrides)
                return await {self._name}.objects.acreate(**defaults)
        """)

        tests_dir = self._app_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        init_file = tests_dir / "__init__.py"
        if not init_file.exists():
            self.write_file(init_file, "")

        target = tests_dir / f"factories_{snake}.py"
        self.write_file(target, content)

        self.success(f"Generated factory for {self._name}")
