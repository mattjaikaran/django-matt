"""
Django Matt migration analysis helpers.

Modules here back the `matt_migrate_from` management command. Each module
holds the source-framework-specific analysis, suggestions, and generated
templates so the command stays a thin orchestrator.
"""

from django_matt.migrate.ninja_extra import (
    analyze_ninja_extra,
    generate_ninja_extra_controller_template,
    generate_ninja_extra_suggestions,
)

__all__ = [
    "analyze_ninja_extra",
    "generate_ninja_extra_suggestions",
    "generate_ninja_extra_controller_template",
]
