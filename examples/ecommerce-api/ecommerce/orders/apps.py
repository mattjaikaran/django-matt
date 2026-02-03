"""Orders app configuration."""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Orders app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "ecommerce.orders"
    verbose_name = "Orders"
