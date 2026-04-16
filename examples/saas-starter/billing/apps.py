from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    # Disambiguate from django_matt.billing, which uses the default label "billing".
    label = "project_billing"
    verbose_name = "Billing"
