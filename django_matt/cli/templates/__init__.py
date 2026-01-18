"""
Scaffolding templates for generating code files.

This module contains templates for generating controllers, schemas, services, and tests.
"""

from django_matt.cli.templates.controller import generate_controller_template
from django_matt.cli.templates.schema import generate_schema_template
from django_matt.cli.templates.service import generate_service_template
from django_matt.cli.templates.test import generate_test_template
from django_matt.cli.templates.utils import pluralize

__all__ = [
    "generate_controller_template",
    "generate_schema_template",
    "generate_service_template",
    "generate_test_template",
    "pluralize",
]
