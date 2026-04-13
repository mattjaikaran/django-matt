"""ASGI/WSGI middleware that catches exceptions and enriches them with suggestions."""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

import orjson

from django_matt.errors.formatters import format_for_api, format_for_human, format_for_log
from django_matt.errors.suggestions import SuggestionEngine, default_engine

logger = logging.getLogger("django_matt.errors")


def _get_config() -> dict[str, Any]:
    """Read MATT_ERRORS from Django settings with defaults."""
    defaults: dict[str, Any] = {
        "enhanced": True,
        "suggestions": True,
        "docs_base_url": "https://django-matt.dev/docs/",
        "max_suggestions": 3,
        "include_search_terms": True,
        "custom_suggestions": {},
    }
    user_config = getattr(settings, "MATT_ERRORS", {})
    defaults.update(user_config)
    return defaults


class ErrorEnhancementMiddleware:
    """Middleware that catches exceptions and returns structured error responses.

    In DEBUG mode: includes full context, traceback, related settings values.
    In production: sanitized output — no settings values, no internal paths.

    Configure via the ``MATT_ERRORS`` setting dict.

    Supports both WSGI (sync) and ASGI (async) request paths.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response
        self._engine: SuggestionEngine = default_engine
        self._config = _get_config()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except Exception as exc:
            return self._handle(exc, request)

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        try:
            return await self.get_response(request)
        except Exception as exc:
            return self._handle(exc, request)

    def _handle(self, exc: Exception, request: HttpRequest) -> HttpResponse:
        config = self._config
        if not config.get("enhanced", True):
            raise exc

        is_debug = getattr(settings, "DEBUG", False)
        structured = self._engine.get_suggestions(exc)

        # enrich with request context
        structured.context["request"] = {
            "method": request.method,
            "path": request.path,
        }

        # add traceback in debug
        if is_debug:
            tb = sys.exc_info()[2]
            if tb:
                structured.traceback_str = "".join(
                    traceback.format_exception(type(exc), exc, tb)
                )

        # cap suggestions
        max_suggestions = config.get("max_suggestions", 3)
        structured.fix_suggestions = structured.fix_suggestions[:max_suggestions]

        # strip debug-only fields in production
        if not is_debug:
            structured.related_settings = []
            structured.search_terms = []
            structured.traceback_str = None

        # docs url
        docs_base = config.get("docs_base_url", "")
        if docs_base and not structured.docs_url:
            structured.docs_url = f"{docs_base.rstrip('/')}/errors/{structured.code.lower()}"

        # log structured
        log_data = format_for_log(structured)
        logger.error(
            f"[{structured.code}] {structured.message}",
            extra={"structured_error": log_data},
        )

        # dev terminal output
        if is_debug:
            human_output = format_for_human(structured)
            # print to stderr so it shows in dev console
            print(human_output, file=sys.stderr)  # noqa: T201

        # JSON response
        body = format_for_api(structured, include_debug=is_debug)
        response = HttpResponse(
            orjson.dumps(body),
            content_type="application/json",
            status=structured.status_code,
        )
        return response
