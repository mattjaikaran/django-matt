"""Structured error responses with machine+human+LLM-readable context."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

import orjson


@dataclass
class StructuredError:
    """Error with machine+human+LLM-readable context.

    Designed to be consumed by API clients, developer tools, and LLM agents
    equally well. Every field has a clear purpose:

    - ``code``: Machine-readable identifier for programmatic switching.
    - ``message``: One-line human-readable summary.
    - ``detail``: Extended explanation (may be multi-sentence).
    - ``fix_suggestions``: Actionable steps the developer/agent can take.
    - ``docs_url``: Direct link to relevant documentation.
    - ``context``: Structured key-value pairs safe to log and display.
    - ``related_settings``: Django/django-matt settings that affect this error.
    - ``search_terms``: Keywords for searching docs, StackOverflow, GitHub issues.
    """

    code: str
    message: str
    status_code: int = 500
    detail: str | None = None
    fix_suggestions: list[str] = field(default_factory=list)
    docs_url: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    related_settings: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
    exception_type: str | None = None
    traceback_str: str | None = None

    def to_dict(self, *, include_debug: bool = False) -> dict[str, Any]:
        """Serialize to a dictionary suitable for JSON responses.

        When ``include_debug`` is False (production), traceback and
        related_settings values are omitted.
        """
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
            "timestamp": self.timestamp,
        }
        if self.detail:
            result["detail"] = self.detail
        if self.fix_suggestions:
            result["fix_suggestions"] = self.fix_suggestions
        if self.docs_url:
            result["docs_url"] = self.docs_url
        if self.context:
            result["context"] = self.context
        if self.search_terms:
            result["search_terms"] = self.search_terms
        if self.related_settings:
            result["related_settings"] = self.related_settings
        if include_debug:
            if self.exception_type:
                result["exception_type"] = self.exception_type
            if self.traceback_str:
                result["traceback"] = self.traceback_str
        return result

    def to_json(self, *, include_debug: bool = False) -> bytes:
        """Serialize to JSON bytes using orjson."""
        return orjson.dumps(self.to_dict(include_debug=include_debug))

    def to_json_str(self, *, include_debug: bool = False) -> str:
        """Serialize to JSON string."""
        return orjson.dumps(
            self.to_dict(include_debug=include_debug),
            option=orjson.OPT_INDENT_2,
        ).decode()
