"""
Django Matt CRUD generator command.

This command generates CRUD controllers, schemas, and tests for Django models.

Usage:
    python manage.py generate_crud myapp.MyModel
    python manage.py generate_crud myapp.MyModel --output-dir ./api
    python manage.py generate_crud myapp.MyModel --components all --with-tests
    python manage.py generate_crud myapp.MyModel --permissions IsAuthenticated
"""

from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models.fields.related import ForeignKey, ManyToManyField, OneToOneField


class Command(BaseCommand):
    help = "Generate CRUD controllers, schemas, and tests for Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            "model",
            help="The model to generate CRUD for (format: app_name.ModelName)",
        )
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory to output the generated files (default: app directory)",
        )
        parser.add_argument(
            "--prefix",
            default=None,
            help="URL prefix for the controller (default: model name in lowercase plural)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing files",
        )
        parser.add_argument(
            "--components",
            nargs="+",
            default=["controller", "schema"],
            choices=["controller", "schema", "test", "all"],
            help="Components to generate (default: controller schema)",
        )
        parser.add_argument(
            "--permissions",
            nargs="+",
            default=[],
            help="Permission classes to use (e.g., IsAuthenticated IsAdmin)",
        )
        parser.add_argument(
            "--with-tests",
            action="store_true",
            help="Also generate test file",
        )
        parser.add_argument(
            "--pagination",
            action="store_true",
            default=True,
            help="Include pagination in list endpoint (default: True)",
        )
        parser.add_argument(
            "--filtering",
            action="store_true",
            default=False,
            help="Include filtering support",
        )
        parser.add_argument(
            "--soft-delete",
            action="store_true",
            default=False,
            help="Use soft delete instead of hard delete",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print generated code without writing files",
        )

    def handle(self, *args, **options):
        model_path = options["model"]
        output_dir = options["output_dir"]
        prefix = options["prefix"]
        force = options["force"]
        components = options["components"]
        permissions = options["permissions"]
        with_tests = options["with_tests"]
        pagination = options["pagination"]
        filtering = options["filtering"]
        soft_delete = options["soft_delete"]
        dry_run = options["dry_run"]

        if "all" in components:
            components = ["controller", "schema", "test"]

        if with_tests and "test" not in components:
            components.append("test")

        try:
            app_label, model_name = model_path.split(".")
        except ValueError:
            raise CommandError("Model must be specified in the format app_name.ModelName")

        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            raise CommandError(f"Model {model_path} not found")

        # Determine output directory
        if output_dir is None:
            app_config = apps.get_app_config(app_label)
            output_dir = Path(app_config.path)
        else:
            output_dir = Path(output_dir)

        # Determine prefix (pluralize model name)
        if prefix is None:
            prefix = self._pluralize(model_name.lower())

        # Get model fields
        fields = self._get_model_fields(model)

        # Store generation context
        context = {
            "model": model,
            "model_name": model_name,
            "app_label": app_label,
            "prefix": prefix,
            "fields": fields,
            "permissions": permissions,
            "pagination": pagination,
            "filtering": filtering,
            "soft_delete": soft_delete,
        }

        # Generate components
        if "schema" in components:
            content = self._generate_schema_content(context)
            if dry_run:
                self.stdout.write(self.style.NOTICE("=== schemas.py ==="))
                self.stdout.write(content)
            else:
                self._write_file(output_dir / "schemas.py", content, model_name, force, "Schema")

        if "controller" in components:
            content = self._generate_controller_content(context)
            if dry_run:
                self.stdout.write(self.style.NOTICE("\n=== controllers.py ==="))
                self.stdout.write(content)
            else:
                self._write_file(
                    output_dir / "controllers.py", content, model_name, force, "Controller"
                )

        if "test" in components:
            content = self._generate_test_content(context)
            if dry_run:
                self.stdout.write(self.style.NOTICE("\n=== tests.py ==="))
                self.stdout.write(content)
            else:
                self._write_file(output_dir / "tests.py", content, model_name, force, "Test")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully generated CRUD for {model_name} in {output_dir}"
                )
            )
            self.stdout.write(
                self.style.NOTICE(
                    f"\nNext steps:\n"
                    f"1. Review generated files in {output_dir}\n"
                    f"2. Register controller in your API:\n"
                    f"   from {app_label}.controllers import {model_name}Controller\n"
                    f"   api.register_controller({model_name}Controller)\n"
                )
            )

    def _pluralize(self, word: str) -> str:
        """Simple pluralization."""
        if word.endswith("y"):
            return word[:-1] + "ies"
        if word.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        return word + "s"

    def _write_file(self, path: Path, content: str, model_name: str, force: bool, component: str):
        """Write content to file, handling existing files."""
        exists = path.exists()

        if exists and not force:
            with open(path) as f:
                existing = f.read()

            if f"class {model_name}" in existing:
                self.stdout.write(
                    self.style.WARNING(
                        f"{component} for {model_name} already exists in {path}. Use --force to overwrite."
                    )
                )
                return

            # Append to existing file
            with open(path, "a") as f:
                f.write("\n\n" + content)

            self.stdout.write(
                self.style.SUCCESS(f"Appended {component.lower()} for {model_name} to {path}")
            )
        else:
            with open(path, "w") as f:
                f.write(content)

            self.stdout.write(
                self.style.SUCCESS(f"Created {component.lower()} for {model_name} in {path}")
            )

    def _get_model_fields(self, model: models.Model) -> list[dict[str, Any]]:
        """Get field information from a Django model."""
        fields = []

        for field in model._meta.fields:
            field_info = {
                "name": field.name,
                "type": self._get_python_type(field),
                "pydantic_type": self._get_pydantic_type(field),
                "required": not field.null and not field.blank and not field.has_default(),
                "has_default": field.has_default(),
                "default": field.default if field.has_default() else None,
                "is_pk": field.primary_key,
                "is_auto": field.primary_key
                and hasattr(field, "auto_created")
                and field.auto_created,
                "is_relation": isinstance(field, (ForeignKey, OneToOneField)),
                "is_m2m": False,
                "relation_type": self._get_relation_type(field),
                "related_model": self._get_related_model(field),
                "max_length": getattr(field, "max_length", None),
                "help_text": field.help_text or "",
                "verbose_name": str(field.verbose_name),
            }
            fields.append(field_info)

        # Add many-to-many fields
        for field in model._meta.many_to_many:
            field_info = {
                "name": field.name,
                "type": "list[int]",
                "pydantic_type": "list[int]",
                "required": False,
                "has_default": True,
                "default": [],
                "is_pk": False,
                "is_auto": False,
                "is_relation": True,
                "is_m2m": True,
                "relation_type": "many_to_many",
                "related_model": field.related_model.__name__,
                "max_length": None,
                "help_text": field.help_text or "",
                "verbose_name": str(field.verbose_name),
            }
            fields.append(field_info)

        return fields

    def _get_python_type(self, field: models.Field) -> str:
        """Convert Django field type to Python type."""
        type_map = {
            models.CharField: "str",
            models.TextField: "str",
            models.EmailField: "str",
            models.URLField: "str",
            models.SlugField: "str",
            models.IntegerField: "int",
            models.BigIntegerField: "int",
            models.SmallIntegerField: "int",
            models.PositiveIntegerField: "int",
            models.PositiveSmallIntegerField: "int",
            models.PositiveBigIntegerField: "int",
            models.AutoField: "int",
            models.BigAutoField: "int",
            models.BooleanField: "bool",
            models.NullBooleanField: "bool | None",
            models.FloatField: "float",
            models.DecimalField: "float",
            models.DateField: "date",
            models.DateTimeField: "datetime",
            models.TimeField: "time",
            models.DurationField: "timedelta",
            models.JSONField: "dict",
            models.UUIDField: "UUID",
            models.BinaryField: "bytes",
            models.FileField: "str",
            models.ImageField: "str",
            ForeignKey: "int",
            OneToOneField: "int",
        }

        for field_class, python_type in type_map.items():
            if isinstance(field, field_class):
                return python_type

        return "Any"

    def _get_pydantic_type(self, field: models.Field) -> str:
        """Get Pydantic-compatible type annotation."""
        base_type = self._get_python_type(field)

        # Add Field constraints for certain types
        if isinstance(field, models.CharField) and field.max_length:
            return "str"  # Will add Field(max_length=...) separately
        if isinstance(field, models.EmailField):
            return "EmailStr"
        if isinstance(field, models.URLField):
            return "HttpUrl"

        return base_type

    def _get_relation_type(self, field: models.Field) -> str | None:
        """Get the type of relation for a field."""
        if isinstance(field, ForeignKey):
            return "foreign_key"
        if isinstance(field, OneToOneField):
            return "one_to_one"
        if isinstance(field, ManyToManyField):
            return "many_to_many"
        return None

    def _get_related_model(self, field: models.Field) -> str | None:
        """Get the related model name for a relation field."""
        if hasattr(field, "related_model") and field.related_model:
            return field.related_model.__name__
        return None

    def _generate_schema_content(self, context: dict) -> str:
        """Generate Pydantic schema classes for a model."""
        model_name = context["model_name"]
        fields = context["fields"]

        # Determine imports needed
        imports = self._get_schema_imports(fields)

        # Build schema content
        lines = [imports, ""]

        # Base response schema
        lines.append(f"class {model_name}Schema(BaseModel):")
        lines.append(f'    """Response schema for {model_name}."""')
        lines.append("")

        for field in fields:
            if field["is_auto"]:
                lines.append(f"    {field['name']}: int")
            elif field["required"]:
                lines.append(f"    {field['name']}: {field['pydantic_type']}")
            else:
                lines.append(f"    {field['name']}: {field['pydantic_type']} | None = None")

        lines.append("")
        lines.append("    class Config:")
        lines.append("        from_attributes = True")
        lines.append("")

        # Create schema (for POST)
        lines.append("")
        lines.append(f"class {model_name}CreateSchema(BaseModel):")
        lines.append(f'    """Schema for creating a {model_name}."""')
        lines.append("")

        for field in fields:
            if field["is_auto"] or field["is_pk"]:
                continue  # Skip auto fields in create

            if field["required"]:
                if field["max_length"]:
                    lines.append(
                        f"    {field['name']}: str = Field(max_length={field['max_length']})"
                    )
                else:
                    lines.append(f"    {field['name']}: {field['pydantic_type']}")
            else:
                default = "None"
                if field["is_m2m"]:
                    default = "Field(default_factory=list)"
                lines.append(f"    {field['name']}: {field['pydantic_type']} | None = {default}")

        lines.append("")

        # Update schema (for PUT/PATCH)
        lines.append("")
        lines.append(f"class {model_name}UpdateSchema(BaseModel):")
        lines.append(f'    """Schema for updating a {model_name}."""')
        lines.append("")

        for field in fields:
            if field["is_auto"] or field["is_pk"]:
                continue

            lines.append(f"    {field['name']}: {field['pydantic_type']} | None = None")

        lines.append("")

        # List schema
        lines.append("")
        lines.append(f"class {model_name}ListSchema(BaseModel):")
        lines.append(f'    """Schema for list of {model_name} objects."""')
        lines.append("")
        lines.append(f"    items: list[{model_name}Schema]")
        lines.append("    total: int")
        lines.append("    page: int = 1")
        lines.append("    page_size: int = 20")

        return "\n".join(lines)

    def _get_schema_imports(self, fields: list[dict]) -> str:
        """Generate import statements for schemas."""
        imports = ["from pydantic import BaseModel, Field"]

        # Check if we need special types
        needs_datetime = any(f["type"] == "datetime" for f in fields)
        needs_date = any(f["type"] == "date" for f in fields)
        needs_time = any(f["type"] == "time" for f in fields)
        needs_uuid = any(f["type"] == "UUID" for f in fields)
        needs_email = any(f["pydantic_type"] == "EmailStr" for f in fields)
        needs_url = any(f["pydantic_type"] == "HttpUrl" for f in fields)
        needs_any = any(f["type"] == "Any" for f in fields)

        typing_imports = []
        if needs_any:
            typing_imports.append("Any")

        if typing_imports:
            imports.insert(0, f"from typing import {', '.join(typing_imports)}")

        datetime_imports = []
        if needs_datetime:
            datetime_imports.append("datetime")
        if needs_date:
            datetime_imports.append("date")
        if needs_time:
            datetime_imports.append("time")

        if datetime_imports:
            imports.insert(0, f"from datetime import {', '.join(datetime_imports)}")

        if needs_uuid:
            imports.insert(0, "from uuid import UUID")

        pydantic_extras = []
        if needs_email:
            pydantic_extras.append("EmailStr")
        if needs_url:
            pydantic_extras.append("HttpUrl")

        if pydantic_extras:
            imports[imports.index("from pydantic import BaseModel, Field")] = (
                f"from pydantic import BaseModel, Field, {', '.join(pydantic_extras)}"
            )

        return "\n".join(imports)

    def _generate_controller_content(self, context: dict) -> str:
        """Generate a CRUD controller for a model."""
        model_name = context["model_name"]
        app_label = context["app_label"]
        prefix = context["prefix"]
        permissions = context["permissions"]
        pagination = context["pagination"]
        soft_delete = context["soft_delete"]

        lines = []

        # Imports
        lines.append("from django.http import Http404")
        lines.append("from django.db.models import Q")
        lines.append("")
        lines.append("from django_matt.core.controller import APIController")
        lines.append("from django_matt.core.router import get, post, put, patch, delete")

        if permissions:
            perm_imports = ", ".join(permissions)
            lines.append(f"from django_matt.permissions import {perm_imports}")

        lines.append("")
        lines.append(f"from .models import {model_name}")
        lines.append("from .schemas import (")
        lines.append(f"    {model_name}Schema,")
        lines.append(f"    {model_name}CreateSchema,")
        lines.append(f"    {model_name}UpdateSchema,")
        lines.append(f"    {model_name}ListSchema,")
        lines.append(")")
        lines.append("")
        lines.append("")

        # Controller class
        lines.append(f"class {model_name}Controller(APIController):")
        lines.append(f'    """CRUD controller for {model_name}."""')
        lines.append("")
        lines.append(f'    prefix = "/{prefix}"')
        lines.append(f'    tags = ["{model_name}"]')

        if permissions:
            lines.append(f"    permission_classes = [{', '.join(permissions)}]")

        lines.append("")

        # List endpoint
        lines.append('    @get("/")')
        lines.append(f"    async def list_{prefix}(")
        lines.append("        self,")
        lines.append("        request,")
        if pagination:
            lines.append("        page: int = 1,")
            lines.append("        page_size: int = 20,")
        lines.append("        search: str | None = None,")
        lines.append(f"    ) -> {model_name}ListSchema:")
        lines.append(f'        """List all {model_name} objects."""')
        lines.append(f"        queryset = {model_name}.objects.all()")
        lines.append("")
        lines.append("        # Apply search filter")
        lines.append("        if search:")
        lines.append("            queryset = queryset.filter(")
        lines.append("                Q(id__icontains=search)  # Add more searchable fields")
        lines.append("            )")
        lines.append("")

        if pagination:
            lines.append("        # Get total count")
            lines.append("        total = await queryset.acount()")
            lines.append("")
            lines.append("        # Apply pagination")
            lines.append("        offset = (page - 1) * page_size")
            lines.append(
                "        items = [item async for item in queryset[offset:offset + page_size]]"
            )
            lines.append("")
            lines.append(f"        return {model_name}ListSchema(")
            lines.append(
                f"            items=[{model_name}Schema.model_validate(item) for item in items],"
            )
            lines.append("            total=total,")
            lines.append("            page=page,")
            lines.append("            page_size=page_size,")
            lines.append("        )")
        else:
            lines.append("        items = [item async for item in queryset]")
            lines.append(f"        return {model_name}ListSchema(")
            lines.append(
                f"            items=[{model_name}Schema.model_validate(item) for item in items],"
            )
            lines.append("            total=len(items),")
            lines.append("        )")

        lines.append("")

        # Get single endpoint
        lines.append('    @get("/{id}")')
        lines.append(
            f"    async def get_{model_name.lower()}(self, request, id: int) -> {model_name}Schema:"
        )
        lines.append(f'        """Get a single {model_name} by ID."""')
        lines.append("        try:")
        lines.append(f"            item = await {model_name}.objects.aget(pk=id)")
        lines.append("        except {model_name}.DoesNotExist:")
        lines.append(f'            raise Http404("{model_name} not found")')
        lines.append(f"        return {model_name}Schema.model_validate(item)")
        lines.append("")

        # Create endpoint
        lines.append('    @post("/")')
        lines.append(f"    async def create_{model_name.lower()}(")
        lines.append("        self,")
        lines.append("        request,")
        lines.append(f"        data: {model_name}CreateSchema,")
        lines.append(f"    ) -> {model_name}Schema:")
        lines.append(f'        """Create a new {model_name}."""')
        lines.append(f"        item = await {model_name}.objects.acreate(**data.model_dump())")
        lines.append(f"        return {model_name}Schema.model_validate(item)")
        lines.append("")

        # Update endpoint (PUT - full update)
        lines.append('    @put("/{id}")')
        lines.append(f"    async def update_{model_name.lower()}(")
        lines.append("        self,")
        lines.append("        request,")
        lines.append("        id: int,")
        lines.append(f"        data: {model_name}UpdateSchema,")
        lines.append(f"    ) -> {model_name}Schema:")
        lines.append(f'        """Update a {model_name} (full update)."""')
        lines.append("        try:")
        lines.append(f"            item = await {model_name}.objects.aget(pk=id)")
        lines.append(f"        except {model_name}.DoesNotExist:")
        lines.append(f'            raise Http404("{model_name} not found")')
        lines.append("")
        lines.append("        for key, value in data.model_dump(exclude_unset=True).items():")
        lines.append("            setattr(item, key, value)")
        lines.append("        await item.asave()")
        lines.append(f"        return {model_name}Schema.model_validate(item)")
        lines.append("")

        # Patch endpoint (partial update)
        lines.append('    @patch("/{id}")')
        lines.append(f"    async def patch_{model_name.lower()}(")
        lines.append("        self,")
        lines.append("        request,")
        lines.append("        id: int,")
        lines.append(f"        data: {model_name}UpdateSchema,")
        lines.append(f"    ) -> {model_name}Schema:")
        lines.append(f'        """Partially update a {model_name}."""')
        lines.append("        try:")
        lines.append(f"            item = await {model_name}.objects.aget(pk=id)")
        lines.append(f"        except {model_name}.DoesNotExist:")
        lines.append(f'            raise Http404("{model_name} not found")')
        lines.append("")
        lines.append("        for key, value in data.model_dump(exclude_unset=True).items():")
        lines.append("            if value is not None:")
        lines.append("                setattr(item, key, value)")
        lines.append("        await item.asave()")
        lines.append(f"        return {model_name}Schema.model_validate(item)")
        lines.append("")

        # Delete endpoint
        lines.append('    @delete("/{id}")')
        lines.append(f"    async def delete_{model_name.lower()}(self, request, id: int) -> dict:")
        lines.append(f'        """Delete a {model_name}."""')
        lines.append("        try:")
        lines.append(f"            item = await {model_name}.objects.aget(pk=id)")
        lines.append(f"        except {model_name}.DoesNotExist:")
        lines.append(f'            raise Http404("{model_name} not found")')
        lines.append("")

        if soft_delete:
            lines.append("        # Soft delete")
            lines.append("        item.is_deleted = True")
            lines.append("        await item.asave()")
        else:
            lines.append("        await item.adelete()")

        lines.append('        return {"success": True, "message": f"{model_name} {id} deleted"}')

        return "\n".join(lines)

    def _generate_test_content(self, context: dict) -> str:
        """Generate test file for the CRUD controller."""
        model_name = context["model_name"]
        app_label = context["app_label"]
        prefix = context["prefix"]

        lines = []

        # Imports
        lines.append("import pytest")
        lines.append("from django.test import AsyncClient")
        lines.append("")
        lines.append(f"from .models import {model_name}")
        lines.append(f"from .schemas import {model_name}CreateSchema")
        lines.append("")
        lines.append("")

        # Test class
        lines.append("@pytest.mark.django_db")
        lines.append(f"class Test{model_name}Controller:")
        lines.append(f'    """Tests for {model_name} CRUD endpoints."""')
        lines.append("")
        lines.append(f'    base_url = "/api/{prefix}"')
        lines.append("")

        # Test list
        lines.append("    @pytest.mark.asyncio")
        lines.append(f"    async def test_list_{prefix}(self, async_client: AsyncClient):")
        lines.append(f'        """Test listing {model_name} objects."""')
        lines.append("        response = await async_client.get(self.base_url)")
        lines.append("        assert response.status_code == 200")
        lines.append("        data = response.json()")
        lines.append('        assert "items" in data')
        lines.append('        assert "total" in data')
        lines.append("")

        # Test create
        lines.append("    @pytest.mark.asyncio")
        lines.append(
            f"    async def test_create_{model_name.lower()}(self, async_client: AsyncClient):"
        )
        lines.append(f'        """Test creating a {model_name}."""')
        lines.append("        payload = {")
        lines.append("            # Add required fields here")
        lines.append("        }")
        lines.append("        response = await async_client.post(self.base_url, json=payload)")
        lines.append("        assert response.status_code in [200, 201]")
        lines.append("")

        # Test get
        lines.append("    @pytest.mark.asyncio")
        lines.append(
            f"    async def test_get_{model_name.lower()}(self, async_client: AsyncClient):"
        )
        lines.append(f'        """Test getting a single {model_name}."""')
        lines.append(f"        # Create a {model_name} first")
        lines.append(f"        item = await {model_name}.objects.acreate(")
        lines.append("            # Add required fields here")
        lines.append("        )")
        lines.append('        response = await async_client.get(f"{self.base_url}/{item.pk}")')
        lines.append("        assert response.status_code == 200")
        lines.append("")

        # Test update
        lines.append("    @pytest.mark.asyncio")
        lines.append(
            f"    async def test_update_{model_name.lower()}(self, async_client: AsyncClient):"
        )
        lines.append(f'        """Test updating a {model_name}."""')
        lines.append(f"        item = await {model_name}.objects.acreate(")
        lines.append("            # Add required fields here")
        lines.append("        )")
        lines.append("        payload = {")
        lines.append("            # Add fields to update")
        lines.append("        }")
        lines.append(
            '        response = await async_client.put(f"{self.base_url}/{item.pk}", json=payload)'
        )
        lines.append("        assert response.status_code == 200")
        lines.append("")

        # Test delete
        lines.append("    @pytest.mark.asyncio")
        lines.append(
            f"    async def test_delete_{model_name.lower()}(self, async_client: AsyncClient):"
        )
        lines.append(f'        """Test deleting a {model_name}."""')
        lines.append(f"        item = await {model_name}.objects.acreate(")
        lines.append("            # Add required fields here")
        lines.append("        )")
        lines.append('        response = await async_client.delete(f"{self.base_url}/{item.pk}")')
        lines.append("        assert response.status_code == 200")
        lines.append("")

        # Test not found
        lines.append("    @pytest.mark.asyncio")
        lines.append(
            f"    async def test_{model_name.lower()}_not_found(self, async_client: AsyncClient):"
        )
        lines.append(f'        """Test 404 for non-existent {model_name}."""')
        lines.append('        response = await async_client.get(f"{self.base_url}/99999")')
        lines.append("        assert response.status_code == 404")

        return "\n".join(lines)
