"""
Django Matt API project generator command.

This command generates a new Django project with django-matt API configuration.
"""

import os
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Generate a new Django project with django-matt API configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "name",
            help="Name of the project to create",
        )
        parser.add_argument(
            "--directory",
            default=None,
            help="Directory to create the project in (default: current directory)",
        )
        parser.add_argument(
            "--api-app",
            default="api",
            help="Name of the API app to create (default: api)",
        )
        parser.add_argument(
            "--db",
            choices=["postgres", "mysql", "sqlite"],
            default="postgres",
            help="Default database to use",
        )
        parser.add_argument(
            "--with-example",
            action="store_true",
            help="Include example models, schemas, and controllers",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing files",
        )

    def handle(self, *args, **options):
        project_name = options["name"]
        directory = options["directory"] or os.getcwd()
        api_app = options["api_app"]
        db = options["db"]
        with_example = options["with_example"]
        force = options["force"]

        # Create the project directory
        project_dir = Path(directory)
        if project_dir.exists() and not force:
            if (project_dir / project_name).exists() or (project_dir / "manage.py").exists():
                raise CommandError(f"Project already exists in {project_dir}. Use --force to overwrite.")
        else:
            os.makedirs(project_dir, exist_ok=True)

        # Create the project
        self.stdout.write(f"Creating Django project {project_name}...")
        self._create_project(project_name, directory)

        # Change to the project directory
        original_dir = os.getcwd()
        os.chdir(project_dir)

        try:
            # Create the API app
            self.stdout.write(f"Creating API app {api_app}...")
            self._create_api_app(api_app)

            # Configure the project with django-matt
            self.stdout.write("Configuring project with django-matt...")
            self._configure_project(project_name, api_app, db)

            # Create example models, schemas, and controllers if requested
            if with_example:
                self.stdout.write("Creating example models, schemas, and controllers...")
                self._create_example(api_app)

            self.stdout.write(self.style.SUCCESS(f"Successfully created django-matt API project {project_name}"))

            # Use the directory option directly for the success message
            cd_path = directory if directory else "."

            self.stdout.write(
                f"Run the following commands to start the development server:\n"
                f"  cd {cd_path}\n"
                f"  python manage.py migrate\n"
                f"  python manage.py runserver_hot"
            )
        finally:
            # Change back to the original directory
            os.chdir(original_dir)

    def _create_project(self, project_name, directory):
        """Create a new Django project."""
        try:
            # Create the project in the specified directory
            # When directory is specified, django-admin startproject expects the directory to be the parent
            # directory where the project will be created, not the directory to create the project in
            subprocess.run(
                [
                    "django-admin",
                    "startproject",
                    project_name,
                    directory,
                ],
                check=True,
            )
        except subprocess.CalledProcessError:
            raise CommandError("Failed to create Django project")

    def _create_api_app(self, api_app):
        """Create a new Django app for the API."""
        try:
            # Use the manage.py in the current directory
            # We're already in the project directory at this point
            manage_py = "./manage.py"
            subprocess.run(
                [
                    "python",
                    manage_py,
                    "startapp",
                    api_app,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise CommandError("Failed to create API app")

    def _configure_project(self, project_name, api_app, db):
        """Configure the project with django-matt."""
        # Add django_matt and api_app to INSTALLED_APPS
        settings_path = Path(f"{project_name}/settings.py")
        if settings_path.exists():
            with open(settings_path) as f:
                settings_content = f.read()

            # Add django_matt and api_app to INSTALLED_APPS
            settings_content = settings_content.replace(
                "INSTALLED_APPS = [",
                f'INSTALLED_APPS = [\n    "django_matt",\n    "{api_app}",',
            )

            # Write the updated settings
            with open(settings_path, "w") as f:
                f.write(settings_content)

        # Initialize django-matt configuration
        try:
            manage_py = "./manage.py"
            subprocess.run(
                [
                    "python",
                    manage_py,
                    "config",
                    "init",
                    "--db",
                    db,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise CommandError("Failed to initialize django-matt configuration")

        # Update the project's urls.py to include the API router
        urls_path = Path(f"{project_name}/urls.py")
        if urls_path.exists():
            with open(urls_path) as f:
                urls_content = f.read()

            # Add import for include and api_app router
            urls_content = urls_content.replace(
                "from django.urls import path",
                "from django.urls import path, include",
            )

            # Add the API router to urlpatterns
            urls_content = urls_content.replace(
                "urlpatterns = [",
                f'urlpatterns = [\n    path("", include("{api_app}.urls")),',
            )

            # Write the updated urls
            with open(urls_path, "w") as f:
                f.write(urls_content)

    def _create_example(self, api_app):
        """Create example models, schemas, controllers, and admin with proper folder structure."""
        # Create directory structure
        directories = ["models", "schemas", "controllers", "admin", "tests"]
        for directory in directories:
            dir_path = Path(f"{api_app}/{directory}")
            os.makedirs(dir_path, exist_ok=True)
            # Create __init__.py in each directory
            with open(dir_path / "__init__.py", "w") as f:
                if directory == "models":
                    f.write('from .task import Task\n\n__all__ = ["Task"]\n')
                elif directory == "schemas":
                    f.write(
                        'from .task import TaskBase, TaskCreate, TaskUpdate, Task, TaskList\n\n__all__ = ["TaskBase", "TaskCreate", "TaskUpdate", "Task", "TaskList"]\n'
                    )
                elif directory == "controllers":
                    f.write('from .task import TaskController\n\n__all__ = ["TaskController"]\n')
                elif directory == "admin":
                    f.write('from .task import TaskAdmin\n\n__all__ = ["TaskAdmin"]\n')

        # Create models
        with open(Path(f"{api_app}/models/task.py"), "w") as f:
            f.write(self._get_example_model_task())

        # Create schemas
        with open(Path(f"{api_app}/schemas/task.py"), "w") as f:
            f.write(self._get_example_schema_task())

        # Create controllers
        with open(Path(f"{api_app}/controllers/task.py"), "w") as f:
            f.write(self._get_example_controller_task())

        # Create admin
        with open(Path(f"{api_app}/admin/task.py"), "w") as f:
            f.write(self._get_example_admin_task())

        # Create main __init__.py
        with open(Path(f"{api_app}/__init__.py"), "w") as f:
            f.write('default_app_config = "api.apps.ApiConfig"\n')

        # Create apps.py
        with open(Path(f"{api_app}/apps.py"), "w") as f:
            f.write(self._get_example_apps(api_app))

        # Create urls.py
        with open(Path(f"{api_app}/urls.py"), "w") as f:
            f.write(self._get_example_urls())

    def _get_example_model_task(self):
        """Get the content for the example task model file."""
        return '''import uuid

from django.db import models


class Task(models.Model):
    """Task model for the example API."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
'''

    def _get_example_schema_task(self):
        """Get the content for the example task schema file."""
        return '''import datetime
import uuid
from typing import Optional, List

from pydantic import Field

from django_matt.core.schema import Schema


class TaskBase(Schema):
    """Base schema for Task items."""

    title: str = Field(..., description="The title of the task")
    description: Optional[str] = Field(
        None, description="A detailed description of the task"
    )
    completed: bool = Field(False, description="Whether the task is completed")


class TaskCreate(TaskBase):
    """Schema for creating a new Task."""
    
    class Config:
        from_attributes = True


class TaskUpdate(Schema):
    """Schema for updating an existing Task."""

    title: Optional[str] = Field(None, description="The title of the task")
    description: Optional[str] = Field(
        None, description="A detailed description of the task"
    )
    completed: Optional[bool] = Field(
        None, description="Whether the task is completed"
    )
    
    class Config:
        from_attributes = True


class Task(TaskBase):
    """Schema for a Task with all fields."""

    id: uuid.UUID = Field(..., description="The unique identifier for the task")
    created_at: datetime.datetime = Field(
        ..., description="When the task was created"
    )
    updated_at: Optional[datetime.datetime] = Field(
        None, description="When the task was last updated"
    )

    class Config:
        from_attributes = True


class TaskList(Schema):
    """Schema for a list of Tasks."""

    items: List[Task] = Field(..., description="List of tasks")
    count: int = Field(..., description="Total number of tasks")
    
    class Config:
        from_attributes = True
'''

    def _get_example_controller_task(self):
        """Get the content for the example task controller file."""
        return '''import uuid
from typing import Any, Dict, Tuple, Optional

from django.http import HttpRequest
from ninja_extra import status

from django_matt.core.controller import CRUDController
from django_matt.core.router import delete, get, post, put

from ..models import Task
from ..schemas import Task as TaskSchema
from ..schemas import TaskCreate, TaskList, TaskUpdate


class TaskController(CRUDController):
    """Controller for Task items."""

    prefix = "tasks/"
    model = Task
    schema = TaskSchema
    create_schema = TaskCreate
    update_schema = TaskUpdate

    @get("", response_model=TaskList)
    async def get_tasks(self, request: HttpRequest) -> Dict[str, Any]:
        """Get all tasks."""
        try:
            result = await self.list(request)
            return result
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @get("{id}", response_model=TaskSchema)
    async def get_task(self, request: HttpRequest, id: str) -> Dict[str, Any]:
        """Get a specific task by ID."""
        try:
            task_id = uuid.UUID(id)
            result = await self.retrieve(request, task_id)
            return result
        except Task.DoesNotExist:
            return {"error": "Task not found"}, status.HTTP_404_NOT_FOUND
        except ValueError:
            return {"error": "Invalid UUID format"}, status.HTTP_400_BAD_REQUEST
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @post("", response_model=TaskSchema, status_code=status.HTTP_201_CREATED)
    async def create_task(
        self, request: HttpRequest, data: TaskCreate
    ) -> Dict[str, Any]:
        """Create a new task."""
        try:
            result = await self.create(request, data)
            return result
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @put("{id}", response_model=TaskSchema)
    async def update_task(
        self, request: HttpRequest, id: str, data: TaskUpdate
    ) -> Dict[str, Any]:
        """Update an existing task."""
        try:
            task_id = uuid.UUID(id)
            result = await self.update(request, task_id, data)
            return result
        except Task.DoesNotExist:
            return {"error": "Task not found"}, status.HTTP_404_NOT_FOUND
        except ValueError:
            return {"error": "Invalid UUID format"}, status.HTTP_400_BAD_REQUEST
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    @delete("{id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_task(self, request: HttpRequest, id: str) -> Dict[str, Any]:
        """Delete a task."""
        try:
            task_id = uuid.UUID(id)
            await self.delete(request, task_id)
            return {}
        except Task.DoesNotExist:
            return {"error": "Task not found"}, status.HTTP_404_NOT_FOUND
        except ValueError:
            return {"error": "Invalid UUID format"}, status.HTTP_400_BAD_REQUEST
        except Exception as e:
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR
'''

    def _get_example_admin_task(self):
        """Get the content for the example task admin file."""
        return '''from django.contrib import admin

from ..models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin configuration for Task model."""
    
    list_display = ("title", "completed", "created_at", "updated_at")
    list_filter = ("completed", "created_at", "updated_at")
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("id", "title", "description", "completed")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
'''

    def _get_example_apps(self, api_app):
        """Get the content for the apps.py file."""
        return f'''from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for the {api_app} app."""
    
    default_auto_field = "django.db.models.BigAutoField"
    name = "{api_app}"
    
    def ready(self):
        """Perform initialization when the app is ready."""
        # Import signals or perform other initialization here
        pass
'''

    def _get_example_urls(self):
        """Get the content for the example urls.py file."""
        return """from django.urls import path
from django_matt import APIRouter

from .controllers import TaskController

# Create a router for the API
router = APIRouter(prefix="api/", tags=["tasks"])

# Register the TaskController
router.register_controller(TaskController)

# Get the URL patterns
urlpatterns = router.get_urls()
"""

    def _get_example_models(self):
        """Get the content for the example models.py file (legacy method)."""
        return self._get_example_model_task()

    def _get_example_schemas(self):
        """Get the content for the example schemas.py file (legacy method)."""
        return self._get_example_schema_task()

    def _get_example_controllers(self, api_app):
        """Get the content for the example controllers.py file (legacy method)."""
        return self._get_example_controller_task()
