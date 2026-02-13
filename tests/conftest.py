"""
Pytest configuration for Django Matt tests.

This file ensures Django is properly set up before any test imports happen.
"""

import os

# Configure Django settings before any other imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

# Allow sync ORM calls inside async contexts during tests.
# This is needed because some source code (e.g., create_access_token) makes
# synchronous ORM queries (user.groups.values_list) that are called from
# async controller methods.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

import django

# Setup Django before importing anything that might need it
django.setup()

# Force-import models so Django's model registry sees them.
import django_matt.multitenancy.models  # noqa: F401, E402
import django_matt.auth.passkeys.models  # noqa: F401, E402
import django_matt.auth.api_keys.models  # noqa: F401, E402
import django_matt.auth.blacklist.models  # noqa: F401, E402

# Now we can safely import pytest and other fixtures
from django.test import RequestFactory

import pytest


@pytest.fixture(scope="session")
def _create_matt_tables(django_db_setup, django_db_blocker):
    """
    Create database tables for django_matt models after the test DB is set up.

    Django 6.0 no longer auto-creates tables for unmigrated apps via syncdb.
    This fixture uses SchemaEditor to create them manually.
    """
    with django_db_blocker.unblock():
        from django.apps import apps
        from django.db import connection

        app_config = apps.get_app_config("django_matt")
        models = list(app_config.get_models())

        if models:
            with connection.schema_editor() as schema_editor:
                for model in models:
                    try:
                        schema_editor.create_model(model)
                    except Exception:
                        pass  # Table may already exist


@pytest.fixture(autouse=True)
def _ensure_matt_tables(_create_matt_tables):
    """Ensure django_matt tables exist for every test (autouse)."""
    pass


@pytest.fixture
def request_factory():
    """Provide a Django RequestFactory for tests."""
    return RequestFactory()


@pytest.fixture
def rf():
    """Alias for request_factory fixture."""
    return RequestFactory()
