"""
Custom startapp command that creates a package-based app structure.

Extends Django's built-in startapp to generate organized directories for
models, schemas, controllers, admin, services, tests, and utilities.

Usage:
    python manage.py startapp blog
    python manage.py startapp blog --models Post Comment
    python manage.py startapp blog --models Post Comment --no-service
    python manage.py startapp blog --models Post --dry-run
"""

import os

from django.core.management.commands.startapp import Command as StartAppCommand


def smart_pluralize(singular: str) -> str:
    """Pluralize an English word with irregular and rule-based handling."""
    specific_variations = {
        "blog": "blogs",
        "message": "messages",
        "category": "categories",
        "history": "histories",
    }
    if singular.lower() in specific_variations:
        return specific_variations[singular.lower()]

    irregulars = {
        "child": "children",
        "goose": "geese",
        "man": "men",
        "woman": "women",
        "tooth": "teeth",
        "foot": "feet",
        "mouse": "mice",
        "person": "people",
        "leaf": "leaves",
        "sheep": "sheep",
        "deer": "deer",
        "fish": "fish",
    }
    if singular.lower() in irregulars:
        return irregulars[singular.lower()]

    if singular.endswith("y"):
        if singular[-2] in "aeiou":
            return singular + "s"
        return singular[:-1] + "ies"

    if singular.endswith("is"):
        return singular[:-2] + "es"

    if singular.endswith(("s", "ss", "sh", "ch", "x", "o")):
        return singular + "es"

    return singular + "s"


def get_model_name(app_name: str) -> str:
    """Derive a model name from an app name (e.g. 'blogs' -> 'Blog')."""
    specific_models = {
        "blogs": "Blog",
        "messaging": "Message",
    }
    return specific_models.get(app_name.lower(), app_name.capitalize())


class Command(StartAppCommand):
    help = (
        "Creates a Django app with package-based directory structure: "
        "models/, schemas/, controllers/, admin/, services/, tests/, utils/"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--models",
            "-m",
            nargs="+",
            default=None,
            help="Model names to scaffold (space-separated, e.g. --models Post Comment)",
        )
        parser.add_argument(
            "--no-service",
            action="store_true",
            default=False,
            help="Skip generating the service layer",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview files that would be created without writing them",
        )

    def handle(self, **options):
        app_name = options["name"]
        target = options.get("directory")
        model_names = options.get("models") or []
        no_service = options.get("no_service", False)
        dry_run = options.get("dry_run", False)

        if target is None:
            target = os.getcwd()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no files will be written\n"))
            self._preview(app_name, target, model_names, no_service)
            return

        # Run Django's built-in startapp first
        super().handle(**options)

        app_directory = os.path.join(target, app_name)

        # If no models given, derive one from the app name
        if not model_names:
            model_names = [get_model_name(app_name)]

        created_files = self._create_structure(
            app_name, app_directory, model_names, no_service
        )

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully created app '{app_name}' with package structure")
        )
        self.stdout.write("Created files:")
        for f in created_files:
            rel = os.path.relpath(f, target)
            self.stdout.write(f"  {rel}")

        self.stdout.write(f"\n{self.style.WARNING('Next steps:')}")
        self.stdout.write(f"  1. Add '{app_name}' to INSTALLED_APPS")
        self.stdout.write(f"  2. Run: python manage.py makemigrations {app_name}")
        self.stdout.write(f"  3. Run: python manage.py migrate {app_name}")

    # -------------------------------------------------------------------------
    # Preview (dry-run)
    # -------------------------------------------------------------------------

    def _preview(self, app_name, target, model_names, no_service):
        if not model_names:
            model_names = [get_model_name(app_name)]

        app_dir = os.path.join(target, app_name)
        dirs = ["models", "schemas", "controllers", "admin", "tests", "tests/factories", "utils"]
        if not no_service:
            dirs.append("services")
        dirs.extend(["management", "management/commands"])

        self.stdout.write("Directories:")
        for d in dirs:
            self.stdout.write(f"  {app_name}/{d}/")

        self.stdout.write("\nFiles:")
        base_files = [
            "__init__.py",
            "apps.py",
            "urls.py",
        ]
        for f in base_files:
            self.stdout.write(f"  {app_name}/{f}")

        for d in dirs:
            self.stdout.write(f"  {app_name}/{d}/__init__.py")

        for model in model_names:
            lower = model.lower()
            self.stdout.write(f"  {app_name}/models/{lower}.py")
            self.stdout.write(f"  {app_name}/schemas/{lower}_schema.py")
            self.stdout.write(f"  {app_name}/controllers/{lower}_controller.py")
            self.stdout.write(f"  {app_name}/admin/{lower}_admin.py")
            if not no_service:
                self.stdout.write(f"  {app_name}/services/{lower}_service.py")
            self.stdout.write(f"  {app_name}/tests/test_{lower}.py")
            self.stdout.write(f"  {app_name}/tests/factories/{lower}_factory.py")

    # -------------------------------------------------------------------------
    # Structure creation
    # -------------------------------------------------------------------------

    def _create_structure(self, app_name, app_directory, model_names, no_service):
        created_files = []

        # Create package directories
        dirs = [
            "models",
            "schemas",
            "controllers",
            "admin",
            "tests",
            "tests/factories",
            "utils",
            "management/commands",
        ]
        if not no_service:
            dirs.append("services")

        for dir_name in dirs:
            dir_path = os.path.join(app_directory, dir_name)
            os.makedirs(dir_path, exist_ok=True)

            # Nested dirs need parent __init__.py too
            if "/" in dir_name:
                parent = dir_name.split("/")[0]
                parent_init = os.path.join(app_directory, parent, "__init__.py")
                if not os.path.exists(parent_init):
                    created_files.extend(self._write_file(parent_init, ""))

            init_path = os.path.join(dir_path, "__init__.py")
            if not os.path.exists(init_path):
                created_files.extend(self._write_file(init_path, ""))

        # Scaffold per-model files
        for model_name in model_names:
            lower = model_name.lower()

            created_files.extend(
                self._write_file(
                    os.path.join(app_directory, "models", f"{lower}.py"),
                    self._model_template(app_name, model_name),
                )
            )
            created_files.extend(
                self._write_file(
                    os.path.join(app_directory, "schemas", f"{lower}_schema.py"),
                    self._schema_template(app_name, model_name),
                )
            )
            created_files.extend(
                self._write_file(
                    os.path.join(app_directory, "controllers", f"{lower}_controller.py"),
                    self._controller_template(app_name, model_name),
                )
            )
            created_files.extend(
                self._write_file(
                    os.path.join(app_directory, "admin", f"{lower}_admin.py"),
                    self._admin_template(app_name, model_name),
                )
            )
            if not no_service:
                created_files.extend(
                    self._write_file(
                        os.path.join(app_directory, "services", f"{lower}_service.py"),
                        self._service_template(app_name, model_name),
                    )
                )
            created_files.extend(
                self._write_file(
                    os.path.join(app_directory, "tests", f"test_{lower}.py"),
                    self._test_template(app_name, model_name),
                )
            )
            created_files.extend(
                self._write_file(
                    os.path.join(
                        app_directory, "tests", "factories", f"{lower}_factory.py"
                    ),
                    self._factory_template(app_name, model_name),
                )
            )

        # Write __init__.py with auto-imports
        self._write_init_files(app_directory, app_name, model_names, no_service)

        # Write urls.py
        created_files.extend(
            self._write_file(
                os.path.join(app_directory, "urls.py"),
                self._urls_template(app_name, model_names),
            )
        )

        # Delete flat files left by Django's startapp
        self._delete_original_files(app_directory)

        return created_files

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _write_file(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return [path]

    def _delete_original_files(self, app_directory):
        from pathlib import Path

        for name in ("models.py", "admin.py", "views.py", "tests.py"):
            path = Path(app_directory) / name
            if path.exists():
                path.unlink()

    def _write_init_files(self, app_directory, app_name, model_names, no_service):
        # models/__init__.py
        imports = [
            f"from {app_name}.models.{m.lower()} import {m}" for m in model_names
        ]
        all_names = [f'"{m}"' for m in model_names]
        self._write_file(
            os.path.join(app_directory, "models", "__init__.py"),
            "\n".join(imports) + f"\n\n__all__ = [{', '.join(all_names)}]\n",
        )

        # schemas/__init__.py
        schema_imports = []
        schema_all = []
        for m in model_names:
            schema_imports.append(
                f"from {app_name}.schemas.{m.lower()}_schema import ("
                f"\n    {m}Schema,"
                f"\n    {m}CreateSchema,"
                f"\n    {m}UpdateSchema,"
                f"\n)"
            )
            schema_all.extend(
                [f'"{m}Schema"', f'"{m}CreateSchema"', f'"{m}UpdateSchema"']
            )
        self._write_file(
            os.path.join(app_directory, "schemas", "__init__.py"),
            "\n".join(schema_imports) + f"\n\n__all__ = [{', '.join(schema_all)}]\n",
        )

        # controllers/__init__.py
        ctrl_imports = [
            f"from {app_name}.controllers.{m.lower()}_controller import {m}Controller"
            for m in model_names
        ]
        ctrl_all = [f'"{m}Controller"' for m in model_names]
        self._write_file(
            os.path.join(app_directory, "controllers", "__init__.py"),
            "\n".join(ctrl_imports) + f"\n\n__all__ = [{', '.join(ctrl_all)}]\n",
        )

        # admin/__init__.py
        admin_imports = [
            f"from {app_name}.admin.{m.lower()}_admin import {m}Admin"
            for m in model_names
        ]
        admin_all = [f'"{m}Admin"' for m in model_names]
        self._write_file(
            os.path.join(app_directory, "admin", "__init__.py"),
            "\n".join(admin_imports) + f"\n\n__all__ = [{', '.join(admin_all)}]\n",
        )

        # services/__init__.py
        if not no_service:
            svc_imports = [
                f"from {app_name}.services.{m.lower()}_service import {m}Service"
                for m in model_names
            ]
            svc_all = [f'"{m}Service"' for m in model_names]
            self._write_file(
                os.path.join(app_directory, "services", "__init__.py"),
                "\n".join(svc_imports) + f"\n\n__all__ = [{', '.join(svc_all)}]\n",
            )

        # tests/__init__.py
        self._write_file(
            os.path.join(app_directory, "tests", "__init__.py"), ""
        )

        # tests/factories/__init__.py
        factory_imports = [
            f"from {app_name}.tests.factories.{m.lower()}_factory import {m}Factory"
            for m in model_names
        ]
        factory_all = [f'"{m}Factory"' for m in model_names]
        self._write_file(
            os.path.join(app_directory, "tests", "factories", "__init__.py"),
            "\n".join(factory_imports) + f"\n\n__all__ = [{', '.join(factory_all)}]\n",
        )

    # -------------------------------------------------------------------------
    # Templates
    # -------------------------------------------------------------------------

    def _model_template(self, app_name, model_name):
        plural = smart_pluralize(model_name.lower())
        plural_display = smart_pluralize(model_name)
        return f'''import uuid

from django.db import models


class {model_name}(models.Model):
    """The {model_name} model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "{model_name}"
        verbose_name_plural = "{plural_display}"
'''

    def _schema_template(self, app_name, model_name):
        return f'''import datetime
import uuid
from typing import Optional

from pydantic import Field

from django_matt.core.schema import Schema


class {model_name}Schema(Schema):
    """Full {model_name} representation."""

    id: uuid.UUID
    title: str
    description: str
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class {model_name}CreateSchema(Schema):
    """Schema for creating a {model_name}."""

    title: str = Field(..., max_length=255)
    description: str = ""


class {model_name}UpdateSchema(Schema):
    """Schema for updating a {model_name}."""

    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
'''

    def _controller_template(self, app_name, model_name):
        lower = model_name.lower()
        plural = smart_pluralize(lower)
        return f'''import uuid
from typing import Any

from django.http import HttpRequest

from django_matt.core.controller import CRUDController
from django_matt.core.router import delete, get, post, put

from {app_name}.models import {model_name}
from {app_name}.schemas import {model_name}Schema, {model_name}CreateSchema, {model_name}UpdateSchema


class {model_name}Controller(CRUDController):
    """{model_name} CRUD controller."""

    prefix = "{plural}/"
    model = {model_name}
    schema = {model_name}Schema
    create_schema = {model_name}CreateSchema
    update_schema = {model_name}UpdateSchema

    @get("", response_model={model_name}Schema)
    async def list_{plural}(self, request: HttpRequest) -> dict[str, Any]:
        """List all {plural}."""
        return await self.list(request)

    @get("{{id}}", response_model={model_name}Schema)
    async def get_{lower}(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """Get a {lower} by ID."""
        return await self.retrieve(request, uuid.UUID(id))

    @post("", response_model={model_name}Schema)
    async def create_{lower}(
        self, request: HttpRequest, data: {model_name}CreateSchema
    ) -> dict[str, Any]:
        """Create a new {lower}."""
        return await self.create(request, data)

    @put("{{id}}", response_model={model_name}Schema)
    async def update_{lower}(
        self, request: HttpRequest, id: str, data: {model_name}UpdateSchema
    ) -> dict[str, Any]:
        """Update a {lower}."""
        return await self.update(request, uuid.UUID(id), data)

    @delete("{{id}}")
    async def delete_{lower}(self, request: HttpRequest, id: str) -> dict[str, Any]:
        """Delete a {lower}."""
        await self.delete(request, uuid.UUID(id))
        return {{}}
'''

    def _admin_template(self, app_name, model_name):
        return f'''from django.contrib import admin

from {app_name}.models import {model_name}


@admin.register({model_name})
class {model_name}Admin(admin.ModelAdmin):
    """{model_name} admin configuration."""

    list_display = ("id", "title", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")
'''

    def _service_template(self, app_name, model_name):
        lower = model_name.lower()
        plural = smart_pluralize(lower)
        return f'''import uuid

from django.db.models import QuerySet

from {app_name}.models import {model_name}
from {app_name}.schemas import {model_name}CreateSchema, {model_name}UpdateSchema


class {model_name}Service:
    """Business logic for {model_name} operations."""

    @staticmethod
    async def get_all() -> QuerySet:
        """Return all {plural}."""
        return {model_name}.objects.all()

    @staticmethod
    async def get_by_id({lower}_id: uuid.UUID) -> {model_name}:
        """Get a {lower} by ID."""
        return await {model_name}.objects.aget(id={lower}_id)

    @staticmethod
    async def create(data: {model_name}CreateSchema) -> {model_name}:
        """Create a new {lower}."""
        return await {model_name}.objects.acreate(**data.model_dump())

    @staticmethod
    async def update({lower}_id: uuid.UUID, data: {model_name}UpdateSchema) -> {model_name}:
        """Update an existing {lower}."""
        {lower} = await {model_name}.objects.aget(id={lower}_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr({lower}, field, value)
        await {lower}.asave()
        return {lower}

    @staticmethod
    async def delete({lower}_id: uuid.UUID) -> None:
        """Delete a {lower}."""
        {lower} = await {model_name}.objects.aget(id={lower}_id)
        await {lower}.adelete()
'''

    def _test_template(self, app_name, model_name):
        lower = model_name.lower()
        plural = smart_pluralize(lower)
        return f'''import pytest

from {app_name}.models import {model_name}
from {app_name}.tests.factories import {model_name}Factory


@pytest.mark.django_db
class Test{model_name}Model:
    """Tests for the {model_name} model."""

    def test_create_{lower}(self):
        {lower} = {model_name}Factory()
        assert {lower}.pk is not None
        assert {lower}.title

    def test_{lower}_str(self):
        {lower} = {model_name}Factory(title="Test {model_name}")
        assert str({lower}) == "Test {model_name}"

    def test_{lower}_ordering(self):
        first = {model_name}Factory(title="First")
        second = {model_name}Factory(title="Second")
        {plural} = list({model_name}.objects.all())
        assert {plural}[0] == second
        assert {plural}[1] == first


@pytest.mark.django_db
class Test{model_name}API:
    """Tests for the {model_name} API endpoints."""

    base_url = "/api/{plural}"

    def test_list_{plural}(self, client):
        {model_name}Factory.create_batch(3)
        response = client.get(self.base_url)
        assert response.status_code == 200

    def test_create_{lower}(self, client):
        payload = {{"title": "New {model_name}"}}
        response = client.post(
            self.base_url,
            data=payload,
            content_type="application/json",
        )
        assert response.status_code in [200, 201]

    def test_get_{lower}(self, client):
        item = {model_name}Factory()
        response = client.get(f"{{self.base_url}}/{{item.pk}}")
        assert response.status_code == 200

    def test_update_{lower}(self, client):
        item = {model_name}Factory()
        payload = {{"title": "Updated"}}
        response = client.put(
            f"{{self.base_url}}/{{item.pk}}",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 200

    def test_delete_{lower}(self, client):
        item = {model_name}Factory()
        response = client.delete(f"{{self.base_url}}/{{item.pk}}")
        assert response.status_code == 200
'''

    def _factory_template(self, app_name, model_name):
        return f'''import factory

from {app_name}.models import {model_name}


class {model_name}Factory(factory.django.DjangoModelFactory):
    """Factory for {model_name} model."""

    class Meta:
        model = {model_name}

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph")
'''

    def _urls_template(self, app_name, model_names):
        imports = [
            f"from {app_name}.controllers import {m}Controller" for m in model_names
        ]
        registers = [
            f"router.register_controller({m}Controller)" for m in model_names
        ]
        return (
            'from django_matt import APIRouter\n\n'
            + "\n".join(imports)
            + "\n\n"
            + f'router = APIRouter(prefix="api/{app_name}/", tags=["{app_name}"])\n\n'
            + "\n".join(registers)
            + "\n\n"
            + "urlpatterns = router.get_urls()\n"
        )
