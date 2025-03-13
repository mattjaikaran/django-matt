"""
Django Matt CRUD generator command.

This command generates CRUD controllers, schemas, and routes for Django models.
"""

from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.db.models.fields.related import ForeignKey, ManyToManyField, OneToOneField


class Command(BaseCommand):
    help = "Generate CRUD controllers, schemas, and routes for Django models"

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
            help="URL prefix for the controller (default: model name in lowercase)",
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
            choices=["controller", "schema", "all"],
            help="Components to generate (default: controller schema)",
        )

    def handle(self, *args, **options):
        model_path = options["model"]
        output_dir = options["output_dir"]
        prefix = options["prefix"]
        force = options["force"]
        components = options["components"]

        if "all" in components:
            components = ["controller", "schema"]

        try:
            app_label, model_name = model_path.split(".")
        except ValueError:
            raise CommandError(
                "Model must be specified in the format app_name.ModelName"
            )

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

        # Determine prefix
        if prefix is None:
            prefix = model_name.lower() + "s"

        # Generate components
        if "schema" in components:
            self.generate_schema(model, output_dir, force)

        if "controller" in components:
            self.generate_controller(model, output_dir, prefix, force)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated CRUD for {model_name} in {output_dir}"
            )
        )

    def generate_schema(
        self, model: models.Model, output_dir: Path, force: bool
    ) -> None:
        """Generate Pydantic schemas for the model."""
        model_name = model.__name__
        schema_path = output_dir / "schemas.py"

        # Check if schemas.py exists
        schemas_exist = schema_path.exists()

        # Get model fields
        fields = self._get_model_fields(model)

        # Generate schema content
        schema_content = self._generate_schema_content(model, fields, schemas_exist)

        # Write or append to schemas.py
        if schemas_exist and not force:
            # Check if schema already exists in the file
            with open(schema_path) as f:
                content = f.read()

            if f"class {model_name}(" in content:
                self.stdout.write(
                    self.style.WARNING(
                        f"Schema for {model_name} already exists in {schema_path}. Use --force to overwrite."
                    )
                )
                return

            # Append to existing file
            with open(schema_path, "a") as f:
                f.write("\n\n" + schema_content)

            self.stdout.write(
                self.style.SUCCESS(f"Appended schema for {model_name} to {schema_path}")
            )
        else:
            # Create new file or overwrite existing
            with open(schema_path, "w") as f:
                if not schemas_exist:
                    # Add imports if creating a new file
                    f.write(
                        "from typing import List, Optional\n\n"
                        "from pydantic import BaseModel, Field\n\n"
                        "from django_matt.core.schema import Schema\n\n\n"
                    )
                f.write(schema_content)

            self.stdout.write(
                self.style.SUCCESS(f"Created schema for {model_name} in {schema_path}")
            )

    def generate_controller(
        self, model: models.Model, output_dir: Path, prefix: str, force: bool
    ) -> None:
        """Generate a CRUD controller for the model."""
        model_name = model.__name__
        controller_path = output_dir / "controllers.py"

        # Check if controllers.py exists
        controllers_exist = controller_path.exists()

        # Generate controller content
        controller_content = self._generate_controller_content(
            model, prefix, controllers_exist
        )

        # Write or append to controllers.py
        if controllers_exist and not force:
            # Check if controller already exists in the file
            with open(controller_path) as f:
                content = f.read()

            if f"class {model_name}Controller(" in content:
                self.stdout.write(
                    self.style.WARNING(
                        f"Controller for {model_name} already exists in {controller_path}. Use --force to overwrite."
                    )
                )
                return

            # Append to existing file
            with open(controller_path, "a") as f:
                f.write("\n\n" + controller_content)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Appended controller for {model_name} to {controller_path}"
                )
            )
        else:
            # Create new file or overwrite existing
            with open(controller_path, "w") as f:
                if not controllers_exist:
                    # Add imports if creating a new file
                    f.write(
                        "from typing import Any, Dict, List\n\n"
                        "from django.http import HttpRequest\n\n"
                        "from django_matt.core.controller import CRUDController\n"
                        "from django_matt.core.router import get, post, put, delete\n\n"
                        f"from .models import {model_name}\n"
                        f"from .schemas import {model_name}, {model_name}Create, {model_name}Update, {model_name}List\n\n\n"
                    )
                f.write(controller_content)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created controller for {model_name} in {controller_path}"
                )
            )

    def _get_model_fields(self, model: models.Model) -> list[dict[str, Any]]:
        """Get field information from a Django model."""
        fields = []

        for field in model._meta.fields:
            # Skip primary key if it's the default auto field
            if field.primary_key and field.auto_created:
                continue

            field_info = {
                "name": field.name,
                "type": self._get_python_type(field),
                "required": not field.null and not field.blank,
                "is_relation": isinstance(
                    field, (ForeignKey, OneToOneField, ManyToManyField)
                ),
                "relation_type": self._get_relation_type(field),
                "related_model": self._get_related_model(field),
            }

            fields.append(field_info)

        return fields

    def _get_python_type(self, field: models.Field) -> str:
        """Convert Django field type to Python/Pydantic type."""
        if isinstance(field, models.CharField) or isinstance(field, models.TextField):
            return "str"
        elif isinstance(field, models.IntegerField) or isinstance(
            field, models.AutoField
        ):
            return "int"
        elif isinstance(field, models.BooleanField):
            return "bool"
        elif isinstance(field, models.FloatField) or isinstance(
            field, models.DecimalField
        ):
            return "float"
        elif isinstance(field, models.DateField):
            return "date"
        elif isinstance(field, models.DateTimeField):
            return "datetime"
        elif isinstance(field, models.TimeField):
            return "time"
        elif isinstance(field, models.JSONField):
            return "dict"
        elif isinstance(field, models.UUIDField):
            return "UUID"
        elif isinstance(field, (ForeignKey, OneToOneField)):
            return "int"  # Foreign keys are represented as IDs in API
        elif isinstance(field, ManyToManyField):
            return "List[int]"  # Many-to-many as list of IDs
        else:
            return "Any"  # Default fallback

    def _get_relation_type(self, field: models.Field) -> str | None:
        """Get the type of relation for a field."""
        if isinstance(field, ForeignKey):
            return "foreign_key"
        elif isinstance(field, OneToOneField):
            return "one_to_one"
        elif isinstance(field, ManyToManyField):
            return "many_to_many"
        return None

    def _get_related_model(self, field: models.Field) -> str | None:
        """Get the related model name for a relation field."""
        if hasattr(field, "related_model") and field.related_model:
            return field.related_model.__name__
        return None

    def _generate_schema_content(
        self, model: models.Model, fields: list[dict[str, Any]], schemas_exist: bool
    ) -> str:
        """Generate Pydantic schema classes for a model."""
        model_name = model.__name__

        # Base schema (for responses)
        base_schema = f"class {model_name}(Schema):\n"
        base_schema += f'    """Schema for {model_name} model."""\n\n'

        # Create schema (for POST requests)
        create_schema = f"class {model_name}Create(BaseModel):\n"
        create_schema += f'    """Schema for creating a {model_name}."""\n\n'

        # Update schema (for PUT requests)
        update_schema = f"class {model_name}Update(BaseModel):\n"
        update_schema += f'    """Schema for updating a {model_name}."""\n\n'

        # Add fields to schemas
        for field in fields:
            field_type = field["type"]
            field_name = field["name"]
            required = field["required"]

            # Base schema includes all fields
            base_schema += f"    {field_name}: {field_type}\n"

            # Create schema includes required fields as required, optional fields as Optional
            if required:
                create_schema += f"    {field_name}: {field_type}\n"
            else:
                create_schema += f"    {field_name}: Optional[{field_type}] = None\n"

            # Update schema includes all fields as Optional
            update_schema += f"    {field_name}: Optional[{field_type}] = None\n"

        # List schema for returning multiple items
        list_schema = f"\n\nclass {model_name}List(BaseModel):\n"
        list_schema += f'    """Schema for a list of {model_name} objects."""\n\n'
        list_schema += f"    items: List[{model_name}]\n"
        list_schema += "    count: int"

        return (
            base_schema + "\n\n" + create_schema + "\n\n" + update_schema + list_schema
        )

    def _generate_controller_content(
        self, model: models.Model, prefix: str, controllers_exist: bool
    ) -> str:
        """Generate a CRUD controller for a model."""
        model_name = model.__name__

        controller = f"class {model_name}Controller(CRUDController):\n"
        controller += f'    """Controller for {model_name} objects."""\n\n'
        controller += f'    prefix = "{prefix}/"\n'
        controller += f"    model = {model_name}\n"
        controller += f"    schema = {model_name}\n"
        controller += f"    create_schema = {model_name}Create\n"
        controller += f"    update_schema = {model_name}Update\n\n"

        # GET all endpoint
        controller += f'    @get("", response_model={model_name}List)\n'
        controller += f"    async def get_{prefix}(self, request: HttpRequest) -> Dict[str, Any]:\n"
        controller += f'        """Get all {model_name} objects."""\n'
        controller += "        result = await self.list(request)\n"
        controller += "        return result\n\n"

        # GET one endpoint
        controller += f'    @get("{{id}}", response_model={model_name})\n'
        controller += f"    async def get_{model_name.lower()}(self, request: HttpRequest, id: str) -> Dict[str, Any]:\n"
        controller += f'        """Get a specific {model_name} by ID."""\n'
        controller += "        result = await self.retrieve(request, id)\n"
        controller += "        return result\n\n"

        # POST endpoint
        controller += f'    @post("", response_model={model_name}, status_code=201)\n'
        controller += f"    async def create_{model_name.lower()}(self, request: HttpRequest, data: {model_name}Create) -> Dict[str, Any]:\n"
        controller += f'        """Create a new {model_name}."""\n'
        controller += "        result = await self.create(request, data)\n"
        controller += "        return result\n\n"

        # PUT endpoint
        controller += f'    @put("{{id}}", response_model={model_name})\n'
        controller += f"    async def update_{model_name.lower()}(self, request: HttpRequest, id: str, data: {model_name}Update) -> Dict[str, Any]:\n"
        controller += f'        """Update an existing {model_name}."""\n'
        controller += "        result = await self.update(request, id, data)\n"
        controller += "        return result\n\n"

        # DELETE endpoint
        controller += '    @delete("{id}", status_code=204)\n'
        controller += f"    async def delete_{model_name.lower()}(self, request: HttpRequest, id: str) -> Dict[str, Any]:\n"
        controller += f'        """Delete a {model_name}."""\n'
        controller += "        await self.delete(request, id)\n"
        controller += "        return {}"

        return controller
