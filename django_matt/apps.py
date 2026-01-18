"""
Django Matt app configuration.
"""

from django.apps import AppConfig


class DjangoMattConfig(AppConfig):
    """Django Matt app configuration."""

    name = "django_matt"
    verbose_name = "Django Matt"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Called when Django starts."""
