"""
Modern forms integration module.

Bridges Django forms with the django-matt component system, modern CSS
frameworks, and client-side validation generation.
"""

from django_matt.forms.bridge import (
    THEME_CLASSES,
    form_to_components,
    render_form,
)
from django_matt.forms.builder import FormBuilder
from django_matt.forms.decorators import ajax_form
from django_matt.forms.validation import (
    form_to_json_schema,
    form_to_yup,
    form_to_zod,
)

__all__ = [
    # Bridge
    "form_to_components",
    "render_form",
    "THEME_CLASSES",
    # Validation
    "form_to_zod",
    "form_to_yup",
    "form_to_json_schema",
    # Decorators
    "ajax_form",
    # Builder
    "FormBuilder",
]
