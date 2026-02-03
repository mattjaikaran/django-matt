"""Catalog app configuration."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Catalog app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ecommerce.catalog"
    verbose_name = "Catalog"
