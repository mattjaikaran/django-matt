"""LLM-optimized error messages with structured suggestions."""

from __future__ import annotations

from django_matt.errors.dev_overlay import print_dev_error, render_dev_error
from django_matt.errors.formatters import (
    format_for_api,
    format_for_html,
    format_for_human,
    format_for_llm,
    format_for_log,
)
from django_matt.errors.middleware import (
    ErrorEnhancementMiddleware,
    build_error_response,
    install_default_handlers,
)
from django_matt.errors.structured import StructuredError
from django_matt.errors.suggestions import SuggestionEngine, default_engine

__all__ = [
    "ErrorEnhancementMiddleware",
    "StructuredError",
    "SuggestionEngine",
    "build_error_response",
    "default_engine",
    "format_for_api",
    "format_for_html",
    "format_for_human",
    "format_for_llm",
    "format_for_log",
    "install_default_handlers",
    "print_dev_error",
    "render_dev_error",
]
