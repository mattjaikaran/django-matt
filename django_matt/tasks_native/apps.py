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
        from .loading import get_loader, should_register_admin

        loader = get_loader()

        # Register admin if available
        if should_register_admin():
            try:
                from .admin import register_admin

                register_admin()
                loader.mark_loaded("admin")
            except Exception:
                pass

        loader.mark_loaded("core")
