"""Strict template mode — catch undefined variables at render time."""

from django_matt.templates.strict import (
    StrictContext,
    StrictEngine,
    StrictRequestContext,
    StrictTemplateMixin,
    UndefinedVariableError,
    strict_template,
)

__all__ = [
    "StrictContext",
    "StrictEngine",
    "StrictRequestContext",
    "StrictTemplateMixin",
    "UndefinedVariableError",
    "strict_template",
]
