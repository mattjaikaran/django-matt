"""
Django Matt CLI commands.

This package contains all CLI command modules for the standalone `matt` CLI.
"""

from django_matt.cli.commands.analyze import app as analyze_app
from django_matt.cli.commands.db import app as db_app
from django_matt.cli.commands.deploy import app as deploy_app
from django_matt.cli.commands.generate import app as generate_app
from django_matt.cli.commands.serve import app as serve_app
from django_matt.cli.commands.status import app as status_app
from django_matt.cli.commands.types import app as types_app

__all__ = [
    "analyze_app",
    "db_app",
    "deploy_app",
    "generate_app",
    "serve_app",
    "status_app",
    "types_app",
]
