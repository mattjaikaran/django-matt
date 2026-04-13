"""LLM-optimized error messages with structured suggestions."""

from __future__ import annotations

from django_matt.errors.dev_overlay import print_dev_error, render_dev_error
from django_matt.errors.formatters import (
    format_for_api,
    format_for_human,
    format_for_llm,
    format_for_log,
)
from django_matt.errors.middleware import ErrorEnhancementMiddleware
from django_matt.errors.structured import StructuredError
from django_matt.errors.suggestions import SuggestionEngine, default_engine

__all__ = [
    "ErrorEnhancementMiddleware",
    "StructuredError",
    "SuggestionEngine",
    "default_engine",
    "format_for_api",
    "format_for_human",
    "format_for_llm",
    "format_for_log",
    "print_dev_error",
    "render_dev_error",
]
