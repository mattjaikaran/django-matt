"""Blacklist configuration reading from DJANGO_MATT_JWT settings."""

from django.conf import settings


class BlacklistConfig:
    """Reads blacklist settings from DJANGO_MATT_JWT.

    All properties read from Django settings dynamically so that
    test overrides (via pytest's ``settings`` fixture) take effect.
    """

    @property
    def _config(self) -> dict:
        return getattr(settings, "DJANGO_MATT_JWT", {})

    @property
    def backend(self) -> str:
        """Backend type: 'null', 'cache', 'database'. Default: 'null' (disabled)."""
        return self._config.get("BLACKLIST_BACKEND", "null")

    @property
    def enabled(self) -> bool:
        return self.backend != "null"

    @property
    def cache_prefix(self) -> str:
        return self._config.get("BLACKLIST_CACHE_PREFIX", "jwt_blacklist:")

    @property
    def blacklist_after_rotation(self) -> bool:
        return self._config.get("BLACKLIST_AFTER_ROTATION", True)


blacklist_config = BlacklistConfig()
