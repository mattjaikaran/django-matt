"""
Django app configuration for tasks_native.
"""

from django.apps import AppConfig


class TasksNativeConfig(AppConfig):
    """Configuration for the native task engine app."""

    name = "django_matt.tasks_native"
    label = "tasks_native"
    verbose_name = "Native Task Engine"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Initialize task system when Django starts."""
        pass
