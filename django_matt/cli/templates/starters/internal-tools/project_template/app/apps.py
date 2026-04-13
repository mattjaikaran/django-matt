"""App config for {{ project_name }}."""

from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "{{ project_name }}_app"
    verbose_name = "{{ project_name }}"
