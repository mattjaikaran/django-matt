"""
Pytest configuration for Django Matt tests.

This file ensures Django is properly set up before any test imports happen.
"""

import os

# Configure Django settings before any other imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

# Setup Django before importing anything that might need it
django.setup()

# Force-import models so Django's model registry sees them.
# Now we can safely import pytest and other fixtures
from django.test import RequestFactory

import pytest

import django_matt.ai.models
import django_matt.auth.api_keys.models
import django_matt.auth.blacklist.models
import django_matt.auth.passkeys.models
import django_matt.auth.sso.models
import django_matt.messaging.models
import django_matt.multitenancy.models


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

        # Also create tables for test models that have FKs to auth.User,
        # since Django's cascade operations will fail if the tables don't exist.
        from tests.test_db import SoftArticle, SoftComment, SoftDocument

        models.extend([SoftArticle, SoftComment, SoftDocument])

        if models:
            with connection.schema_editor() as schema_editor:
                # Multiple passes to handle FK dependency ordering
                remaining = list(models)
                for _pass in range(3):
                    still_remaining = []
                    for model in remaining:
                        try:
                            schema_editor.create_model(model)
                        except Exception:
                            still_remaining.append(model)
                    remaining = still_remaining
                    if not remaining:
                        break


@pytest.fixture(autouse=True)
def _ensure_matt_tables(_create_matt_tables):
    """Ensure django_matt tables exist for every test (autouse)."""


@pytest.fixture
def request_factory():
    """Provide a Django RequestFactory for tests."""
    return RequestFactory()


@pytest.fixture
def rf():
    """Alias for request_factory fixture."""
    return RequestFactory()


@pytest.fixture(autouse=True)
def _reset_caches():
    """Reset module-level caches to prevent cross-test state leaks."""
    # Reset login config cache (otherwise MATT_AUTH overrides leak between tests)
    try:
        from django_matt.auth.login_config import reset_login_config
        reset_login_config()
    except Exception:
        pass
