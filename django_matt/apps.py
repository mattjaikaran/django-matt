"""
Django Matt app configuration.
"""

import logging

from django.apps import AppConfig
from django.core import checks

logger = logging.getLogger("django_matt")


@checks.register(checks.Tags.compatibility)
def check_installed_apps_order(app_configs, **kwargs):
    """Validate django_matt placement in INSTALLED_APPS."""
    from django.conf import settings

    errors = []
    installed = list(settings.INSTALLED_APPS)

    if "django_matt" not in installed:
        errors.append(
            checks.Error(
                "'django_matt' is missing from INSTALLED_APPS.",
                hint="Add 'django_matt' to INSTALLED_APPS before your project apps.",
                id="django_matt.E001",
            )
        )
        return errors

    matt_idx = installed.index("django_matt")

    # django_matt must come after django.contrib.auth and contenttypes
    required_before = [
        "django.contrib.auth",
        "django.contrib.contenttypes",
    ]
    for app in required_before:
        if app in installed and installed.index(app) > matt_idx:
            errors.append(
                checks.Error(
                    f"'{app}' must appear before 'django_matt' in INSTALLED_APPS.",
                    hint=(
                        "django_matt depends on auth and contenttypes. "
                        "Move 'django_matt' below the django.contrib apps."
                    ),
                    id="django_matt.E002",
                )
            )

    # unfold must come before django.contrib.admin
    if "unfold" in installed and "django.contrib.admin" in installed:
        if installed.index("unfold") > installed.index("django.contrib.admin"):
            errors.append(
                checks.Warning(
                    "'unfold' should appear before 'django.contrib.admin' in INSTALLED_APPS.",
                    hint="The Unfold admin theme must be loaded before Django's admin app.",
                    id="django_matt.W001",
                )
            )

    return errors


class DjangoMattConfig(AppConfig):
    """Django Matt app configuration."""

    name = "django_matt"
    verbose_name = "Django Matt"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Called when Django starts."""
        import warnings

        from django.conf import settings

        # Auto-register Rust radix router middleware when available
        self._register_radix_middleware()

        if getattr(settings, "MATT_API_MODE", False):
            from django_matt.config.components.performance import apply_api_mode

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

    @staticmethod
    def _register_radix_middleware() -> None:
        """Auto-inject RadixRouterMiddleware into MIDDLEWARE when Rust is available."""
        try:
            from django.conf import settings

            from django_matt._accel import HAS_RUST
        except Exception:
            return

        if not HAS_RUST:
            return

        middleware_path = "django_matt.core.radix_middleware.RadixRouterMiddleware"
        current = list(settings.MIDDLEWARE)

        # Insert after SecurityMiddleware (first in chain), before Django's CommonMiddleware
        if middleware_path not in current:
            insert_at = 1  # after SecurityMiddleware
            current.insert(insert_at, middleware_path)
            settings.MIDDLEWARE = current
            logger.info("Rust radix router middleware auto-registered")
