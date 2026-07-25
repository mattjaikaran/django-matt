"""Output formatters for StructuredError — LLM, human, API, HTML, and log formats."""

from __future__ import annotations

import html
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


def format_for_html(error: StructuredError, *, include_debug: bool = False) -> str:
    """Format a structured error as a standalone HTML page.

    Designed so browsers rendering an error response still show useful,
    actionable information — replacing Django's default bare
    ``Server Error (500)`` page with the same structured detail that
    API clients receive as JSON.

    In production (``include_debug=False``): shows code, status, message,
    hint, exception type, and docs link. Omits traceback, related
    settings values, and internal context.

    In debug: adds traceback, related settings, context, and search terms.
    """
    esc = html.escape
    status = error.status_code
    severity_color = "#c0392b" if status >= 500 else "#d68910"

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="en"><head>')
    parts.append('<meta charset="utf-8">')
    parts.append(f"<title>{status} {esc(error.code)}</title>")
    parts.append(
        "<style>"
        "body{margin:0;padding:2rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
        "background:#f6f7f9;color:#1b1f23;line-height:1.5}"
        ".wrap{max-width:960px;margin:0 auto;background:#fff;border:1px solid #e1e4e8;"
        "border-radius:8px;overflow:hidden}"
        f".hdr{{background:{severity_color};color:#fff;padding:1.25rem 1.5rem}}"
        ".hdr .status{font-size:.85rem;opacity:.85;letter-spacing:.05em;text-transform:uppercase}"
        ".hdr .code{font-size:1.4rem;font-weight:600;margin-top:.25rem}"
        ".body{padding:1.5rem}"
        ".msg{font-size:1.05rem;margin:0 0 1rem;color:#24292e}"
        ".detail{color:#586069;margin:0 0 1.25rem}"
        "section{margin-top:1.25rem}"
        "section h3{margin:0 0 .5rem;font-size:.8rem;text-transform:uppercase;"
        "letter-spacing:.06em;color:#6a737d}"
        "ul{margin:0;padding-left:1.25rem}"
        "li{margin:.25rem 0}"
        "pre{background:#0d1117;color:#e6edf3;padding:1rem;border-radius:6px;"
        "overflow-x:auto;font-size:.82rem;margin:0}"
        ".kv{display:grid;grid-template-columns:max-content 1fr;gap:.25rem 1rem;font-size:.9rem}"
        ".kv dt{color:#6a737d}"
        ".kv dd{margin:0;color:#24292e}"
        "a{color:#0366d6;text-decoration:none}"
        "a:hover{text-decoration:underline}"
        "</style>"
    )
    parts.append('</head><body><div class="wrap">')

    parts.append('<div class="hdr">')
    parts.append(f'<div class="status">{status} error</div>')
    parts.append(f'<div class="code">{esc(error.code)}</div>')
    parts.append("</div>")

    parts.append('<div class="body">')
    parts.append(f'<p class="msg">{esc(error.message)}</p>')
    if error.detail:
        parts.append(f'<p class="detail">{esc(error.detail)}</p>')

    # Metadata grid: exception type, docs, timestamp
    meta_rows: list[tuple[str, str]] = []
    if error.exception_type:
        meta_rows.append(("Exception", error.exception_type))
    if error.docs_url:
        safe_url = esc(error.docs_url)
        meta_rows.append(("Docs", f'<a href="{safe_url}">{safe_url}</a>'))
    meta_rows.append(("Timestamp", error.timestamp))
    if meta_rows:
        parts.append('<dl class="kv">')
        for k, v in meta_rows:
            parts.append(f"<dt>{esc(k)}</dt><dd>{v}</dd>")
        parts.append("</dl>")

    if error.fix_suggestions:
        parts.append("<section><h3>Suggestions</h3><ul>")
        for s in error.fix_suggestions:
            parts.append(f"<li>{esc(s)}</li>")
        parts.append("</ul></section>")

    if include_debug:
        if error.context:
            parts.append("<section><h3>Context</h3><pre>")
            parts.append(esc(orjson.dumps(error.context, option=orjson.OPT_INDENT_2).decode()))
            parts.append("</pre></section>")

        if error.related_settings:
            parts.append("<section><h3>Related settings</h3><ul>")
            for s in error.related_settings:
                parts.append(f"<li><code>{esc(s)}</code></li>")
            parts.append("</ul></section>")

        if error.search_terms:
            parts.append("<section><h3>Search terms</h3><ul>")
            for t in error.search_terms:
                parts.append(f"<li>{esc(t)}</li>")
            parts.append("</ul></section>")

        if error.traceback_str:
            parts.append("<section><h3>Traceback</h3><pre>")
            parts.append(esc(error.traceback_str.rstrip()))
            parts.append("</pre></section>")

    parts.append("</div></div></body></html>")
    return "".join(parts)


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
