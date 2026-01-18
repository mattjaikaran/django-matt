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

# Now we can safely import pytest and other fixtures
from django.test import RequestFactory

import pytest


@pytest.fixture
def request_factory():
    """Provide a Django RequestFactory for tests."""
    return RequestFactory()


@pytest.fixture
def rf():
    """Alias for request_factory fixture."""
    return RequestFactory()
