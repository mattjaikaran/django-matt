"""
Django Matt Settings Module.

This module provides a modern, environment-based settings structure.

Usage:
    # In your project's settings.py or manage.py
    from django_matt.config.settings import common, dev, staging, prod

    # Or use the configure function:
    from django_matt.config.settings import configure
    configure("dev")  # or "staging", "prod"

File structure:
    settings/
        __init__.py     - This file, exports all settings modules
        common.py       - Base settings for all environments
        dev.py          - Development environment settings
        staging.py      - Staging environment settings (optional)
        prod.py         - Production environment settings
"""

from django_matt.config.settings import common

# Lazy imports for environment-specific settings
_dev = None
_staging = None
_prod = None


def get_dev():
    """Get development settings (lazy load)."""
    global _dev
    if _dev is None:
        from django_matt.config.settings import dev as _dev_module

        _dev = _dev_module
    return _dev


def get_staging():
    """Get staging settings (lazy load)."""
    global _staging
    if _staging is None:
        from django_matt.config.settings import staging as _staging_module

        _staging = _staging_module
    return _staging


def get_prod():
    """Get production settings (lazy load)."""
    global _prod
    if _prod is None:
        from django_matt.config.settings import prod as _prod_module

        _prod = _prod_module
    return _prod


def configure(environment: str = "dev") -> dict:
    """
    Configure Django with the specified environment settings.

    Args:
        environment: One of "dev", "staging", or "prod"

    Returns:
        Dict of merged settings

    Example:
        # In your settings.py
        from django_matt.config.settings import configure
        locals().update(configure("dev"))
    """
    # Start with common settings
    settings = dict(common.settings)

    # Merge environment-specific settings
    if environment == "dev" or environment == "development":
        env_settings = get_dev().settings
    elif environment == "staging":
        env_settings = get_staging().settings
    elif environment == "prod" or environment == "production":
        env_settings = get_prod().settings
    else:
        raise ValueError(f"Unknown environment: {environment}")

    # Deep merge settings
    for key, value in env_settings.items():
        if key in settings and isinstance(settings[key], dict) and isinstance(value, dict):
            settings[key] = {**settings[key], **value}
        elif key in settings and isinstance(settings[key], list) and isinstance(value, list):
            # For lists like INSTALLED_APPS and MIDDLEWARE, extend rather than replace
            settings[key] = settings[key] + value
        else:
            settings[key] = value

    return settings


__all__ = [
    "common",
    "get_dev",
    "get_staging",
    "get_prod",
    "configure",
]
