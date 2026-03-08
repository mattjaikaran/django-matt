"""
Django Matt app configuration.
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger("django_matt")


class DjangoMattConfig(AppConfig):
    """Django Matt app configuration."""

    name = "django_matt"
    verbose_name = "Django Matt"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Called when Django starts."""
        import warnings

        from django.conf import settings

        if getattr(settings, "MATT_API_MODE", False):
            from django_matt.config.components.performance import apply_api_mode

            # Replace settings.MIDDLEWARE in-place with the filtered list.
            # This must run in ready() — never at module import time — to avoid
            # running during migrations, collectstatic, and other management commands
            # that don't go through the full WSGI/ASGI startup path.
            settings.MIDDLEWARE = apply_api_mode(list(settings.MIDDLEWARE))

        # Warn in production when JWT blacklist is disabled
        if not getattr(settings, "DEBUG", True):
            from django_matt.auth.blacklist.config import blacklist_config

            if not blacklist_config.enabled:
                warnings.warn(
                    "JWT blacklist backend is 'null' — token revocation is disabled. "
                    "Set DJANGO_MATT_JWT['BLACKLIST_BACKEND'] = 'cache' for production.",
                    stacklevel=2,
                )
