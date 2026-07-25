"""ASGI/WSGI middleware that catches exceptions and enriches them with suggestions."""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

import orjson

from django_matt.errors.formatters import (
    format_for_api,
    format_for_html,
    format_for_human,
    format_for_log,
)
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


def _wants_json(request: HttpRequest) -> bool:
    """Decide whether the client expects a JSON response.

    JSON is returned when the request path is under ``/api/`` *or* the
    ``Accept`` header mentions JSON without a higher-priority HTML
    preference. Everything else gets HTML — that means opening an
    endpoint in a browser never shows Django's bare ``Server Error
    (500)`` page again.
    """
    if request.path.startswith("/api/"):
        return True

    accept = request.META.get("HTTP_ACCEPT", "")
    if not accept:
        return False

    accept_lower = accept.lower()
    has_html = "text/html" in accept_lower or "application/xhtml" in accept_lower
    has_json = "application/json" in accept_lower or "+json" in accept_lower

    if has_json and not has_html:
        return True
    return False


def build_error_response(
    exc: Exception,
    request: HttpRequest | None = None,
    *,
    engine: SuggestionEngine | None = None,
    config: dict[str, Any] | None = None,
) -> HttpResponse:
    """Render any exception into a structured HTML or JSON response.

    This is the single entry point used by the middleware and by
    ``install_default_handlers()`` for Django's handler400/403/404/500
    hooks. It guarantees that no request ever falls through to
    Django's bare ``Server Error (500)`` template.
    """
    engine = engine or default_engine
    config = config or _get_config()
    is_debug = getattr(settings, "DEBUG", False)

    structured = engine.get_suggestions(exc)

    if request is not None:
        structured.context["request"] = {
            "method": request.method,
            "path": request.path,
        }

    if is_debug:
        tb = sys.exc_info()[2]
        if tb:
            structured.traceback_str = "".join(traceback.format_exception(type(exc), exc, tb))

    max_suggestions = config.get("max_suggestions", 3)
    structured.fix_suggestions = structured.fix_suggestions[:max_suggestions]

    if not is_debug:
        structured.related_settings = []
        structured.search_terms = []
        structured.traceback_str = None

    docs_base = config.get("docs_base_url", "")
    if docs_base and not structured.docs_url:
        structured.docs_url = f"{docs_base.rstrip('/')}/errors/{structured.code.lower()}"

    log_data = format_for_log(structured)
    logger.error(
        f"[{structured.code}] {structured.message}",
        extra={"structured_error": log_data},
    )

    if is_debug:
        print(format_for_human(structured), file=sys.stderr)  # noqa: T201

    if request is not None and not _wants_json(request):
        html_body = format_for_html(structured, include_debug=is_debug)
        return HttpResponse(
            html_body,
            content_type="text/html; charset=utf-8",
            status=structured.status_code,
        )

    body = format_for_api(structured, include_debug=is_debug)
    return HttpResponse(
        orjson.dumps(body),
        content_type="application/json",
        status=structured.status_code,
    )


class ErrorEnhancementMiddleware:
    """Middleware that catches exceptions and returns structured error responses.

    Content-negotiates the response format:

    - API paths (``/api/...``) and JSON-only ``Accept`` headers get
      JSON with ``code``, ``detail``, ``hint``, ``docs_url``.
    - Browsers (anything with ``text/html`` in ``Accept``) get a clean
      HTML page replacing Django's bare ``Server Error (500)`` template.

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
        if not self._config.get("enhanced", True):
            raise exc
        return build_error_response(exc, request, engine=self._engine, config=self._config)


def install_default_handlers(urlconf_module: Any) -> None:
    """Install django_matt error handlers on a root URLconf module.

    Django calls ``handler400``/``handler403``/``handler404``/``handler500``
    from the root URLconf when the middleware chain doesn't catch an
    exception (e.g., when ``ErrorEnhancementMiddleware`` isn't in
    ``MIDDLEWARE``, or when Django raises from inside its own
    middleware). Installing these handlers guarantees structured
    output even then.

    Usage in ``urls.py``::

        from django_matt.errors import install_default_handlers
        import sys

        install_default_handlers(sys.modules[__name__])
    """
    from django.core.exceptions import PermissionDenied, SuspiciousOperation
    from django.http import Http404

    def _h400(request: HttpRequest, exception: Exception) -> HttpResponse:
        return build_error_response(exception or SuspiciousOperation("Bad request"), request)

    def _h403(request: HttpRequest, exception: Exception) -> HttpResponse:
        return build_error_response(exception or PermissionDenied("Forbidden"), request)

    def _h404(request: HttpRequest, exception: Exception) -> HttpResponse:
        return build_error_response(exception or Http404("Not found"), request)

    def _h500(request: HttpRequest) -> HttpResponse:
        exc_type, exc_value, _ = sys.exc_info()
        exc = exc_value if isinstance(exc_value, Exception) else Exception("Server error")
        return build_error_response(exc, request)

    urlconf_module.handler400 = _h400
    urlconf_module.handler403 = _h403
    urlconf_module.handler404 = _h404
    urlconf_module.handler500 = _h500
