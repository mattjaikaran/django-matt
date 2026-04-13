"""Output formatters for StructuredError — LLM, human, API, and log formats."""

from __future__ import annotations

import logging
from typing import Any

import orjson

from django_matt.errors.structured import StructuredError

logger = logging.getLogger("django_matt.errors")


def format_for_llm(error: StructuredError) -> str:
    """Format a structured error as markdown optimized for LLM consumption.

    Includes full context, suggestions, related settings, and search terms
    in a format that language models can parse and act on.
    """
    lines: list[str] = []
    lines.append(f"# Error: {error.code}")
    lines.append("")
    lines.append(f"**Message:** {error.message}")
    if error.detail:
        lines.append(f"**Detail:** {error.detail}")
    lines.append(f"**Status:** {error.status_code}")
    if error.exception_type:
        lines.append(f"**Exception:** {error.exception_type}")
    lines.append("")

    if error.fix_suggestions:
        lines.append("## Fix Suggestions")
        for i, suggestion in enumerate(error.fix_suggestions, 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")

    if error.context:
        lines.append("## Context")
        lines.append("```json")
        lines.append(orjson.dumps(error.context, option=orjson.OPT_INDENT_2).decode())
        lines.append("```")
        lines.append("")

    if error.related_settings:
        lines.append("## Related Settings")
        for setting in error.related_settings:
            lines.append(f"- `{setting}`")
        lines.append("")

    if error.docs_url:
        lines.append(f"## Documentation\n{error.docs_url}")
        lines.append("")

    if error.search_terms:
        lines.append("## Search Terms")
        lines.append(", ".join(f"`{t}`" for t in error.search_terms))
        lines.append("")

    if error.traceback_str:
        lines.append("## Traceback")
        lines.append("```python")
        lines.append(error.traceback_str.rstrip())
        lines.append("```")

    return "\n".join(lines)


def format_for_human(error: StructuredError, *, color: bool = True) -> str:
    """Format a structured error for terminal display.

    Uses ANSI color codes when ``color=True``. Falls back to plain text
    when color is disabled.
    """
    if color:
        red = "\033[91m"
        yellow = "\033[93m"
        cyan = "\033[96m"
        dim = "\033[2m"
        bold = "\033[1m"
        reset = "\033[0m"
    else:
        red = yellow = cyan = dim = bold = reset = ""

    lines: list[str] = []
    lines.append(f"{red}{bold}ERROR [{error.code}]{reset} {error.message}")
    if error.detail:
        lines.append(f"  {dim}{error.detail}{reset}")
    lines.append("")

    if error.fix_suggestions:
        lines.append(f"  {yellow}{bold}Suggestions:{reset}")
        for suggestion in error.fix_suggestions:
            lines.append(f"  {cyan}>{reset} {suggestion}")
        lines.append("")

    if error.related_settings:
        lines.append(f"  {dim}Related settings: {', '.join(error.related_settings)}{reset}")

    if error.docs_url:
        lines.append(f"  {dim}Docs: {error.docs_url}{reset}")

    if error.traceback_str:
        lines.append("")
        lines.append(f"  {dim}Traceback:{reset}")
        for tb_line in error.traceback_str.rstrip().splitlines():
            lines.append(f"  {dim}{tb_line}{reset}")

    return "\n".join(lines)


def format_for_api(error: StructuredError, *, include_debug: bool = False) -> dict[str, Any]:
    """Format a structured error as a JSON-serializable API response.

    Production mode omits traceback and internal paths. Debug mode
    includes everything.
    """
    result: dict[str, Any] = {
        "status": error.status_code,
        "code": error.code,
        "detail": error.message,
    }

    if error.fix_suggestions:
        result["hint"] = error.fix_suggestions[0]

    if error.docs_url:
        result["docs_url"] = error.docs_url

    if include_debug:
        if error.detail:
            result["detail_extended"] = error.detail
        if len(error.fix_suggestions) > 1:
            result["fix_suggestions"] = error.fix_suggestions
        if error.context:
            result["context"] = error.context
        if error.related_settings:
            result["related_settings"] = error.related_settings
        if error.search_terms:
            result["search_terms"] = error.search_terms
        if error.exception_type:
            result["exception_type"] = error.exception_type
        if error.traceback_str:
            result["traceback"] = error.traceback_str

    result["extra"] = None
    return result


def format_for_log(error: StructuredError) -> dict[str, Any]:
    """Format a structured error for structured logging (e.g., JSON logger).

    Always includes machine-readable fields. Never includes ANSI codes.
    Traceback is included as a string field.
    """
    result: dict[str, Any] = {
        "level": "error",
        "code": error.code,
        "message": error.message,
        "status_code": error.status_code,
        "timestamp": error.timestamp,
    }
    if error.exception_type:
        result["exception_type"] = error.exception_type
    if error.detail:
        result["detail"] = error.detail
    if error.context:
        result["context"] = error.context
    if error.fix_suggestions:
        result["fix_suggestions"] = error.fix_suggestions
    if error.related_settings:
        result["related_settings"] = error.related_settings
    if error.traceback_str:
        result["traceback"] = error.traceback_str
    return result
