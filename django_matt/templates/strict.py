"""Strict template mode — raises on undefined variables instead of silent empty strings."""

from __future__ import annotations

import functools
import logging
from typing import Any

from django.conf import settings
from django.template import Context, RequestContext
from django.template.backends.django import DjangoTemplates

logger = logging.getLogger("django_matt.templates")

# Django built-in context processor variables that should always be allowed
DEFAULT_ALLOWLIST: frozenset[str] = frozenset({
    "csrf_token",
    "request",
    "user",
    "perms",
    "messages",
    "DEFAULT_MESSAGE_LEVELS",
    "True",
    "False",
    "None",
    "forloop",
    "block",
})


def _get_config() -> dict[str, Any]:
    return getattr(settings, "MATT_TEMPLATES", {})


class UndefinedVariableError(Exception):
    """Raised when a template variable is undefined in strict mode."""

    def __init__(
        self,
        variable: str,
        template_name: str | None = None,
        line: int | None = None,
    ) -> None:
        self.variable = variable
        self.template_name = template_name or "<unknown>"
        self.line = line
        loc = f" at line {line}" if line else ""
        super().__init__(
            f"Variable '{variable}' is undefined in template "
            f"'{self.template_name}'{loc}"
        )


class _StrictLookupMixin:
    """Shared strict-lookup logic for Context subclasses."""

    _allow_undefined: frozenset[str]

    def _init_allowlist(self, allow_undefined: list[str] | None = None) -> None:
        cfg = _get_config()
        base = DEFAULT_ALLOWLIST | frozenset(cfg.get("allowlist", []))
        extra = frozenset(allow_undefined or [])
        self._allow_undefined = base | extra

    def _strict_resolve(self, key: str) -> Any:
        if key in self._allow_undefined:
            return ""
        cfg = _get_config()
        warn_only = cfg.get("warn_only", False)
        if not getattr(settings, "DEBUG", False) and warn_only:
            logger.warning("Undefined template variable: %s", key)
            return ""
        raise UndefinedVariableError(key)


class StrictContext(_StrictLookupMixin, Context):
    """Template context that raises on undefined variables."""

    def __init__(
        self,
        dict_: dict[str, Any] | None = None,
        *args: Any,
        allow_undefined: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(dict_, *args, **kwargs)
        self._init_allowlist(allow_undefined)

    def __missing__(self, key: str) -> Any:
        return self._strict_resolve(key)

    def __getitem__(self, key: str) -> Any:
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.__missing__(key)


class StrictRequestContext(_StrictLookupMixin, RequestContext):
    """Request-aware template context that raises on undefined variables."""

    def __init__(
        self,
        request: Any,
        dict_: dict[str, Any] | None = None,
        *args: Any,
        allow_undefined: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(request, dict_, *args, **kwargs)
        self._init_allowlist(allow_undefined)

    def __missing__(self, key: str) -> Any:
        return self._strict_resolve(key)

    def __getitem__(self, key: str) -> Any:
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.__missing__(key)


class StrictEngine(DjangoTemplates):
    """Template engine backend that enforces strict variable resolution."""

    def get_templatetag_libraries(self, custom_libraries: dict[str, str]) -> dict[str, str]:
        libraries = super().get_templatetag_libraries(custom_libraries)
        libraries["strict_tags"] = "django_matt.templates.templatetags.strict_tags"
        return libraries


class StrictTemplateMixin:
    """Mixin for CBVs — renders templates with strict context."""

    allow_undefined: list[str] = []

    def render_to_response(self, context: dict[str, Any], **kwargs: Any) -> Any:
        from django.template.loader import get_template

        template = get_template(self.template_name)  # type: ignore[attr-defined]
        request = getattr(self, "request", None)
        if request is not None:
            strict_ctx = StrictRequestContext(
                request, context, allow_undefined=self.allow_undefined
            )
        else:
            strict_ctx = StrictContext(context, allow_undefined=self.allow_undefined)
        from django.http import HttpResponse

        return HttpResponse(template.template.render(strict_ctx))


def strict_template(
    allow_undefined: list[str] | None = None,
) -> Any:
    """Decorator for FBVs to enforce strict template rendering."""
    extra = allow_undefined or []

    def decorator(view_func: Any) -> Any:
        @functools.wraps(view_func)
        def wrapper(request: Any, *args: Any, **kwargs: Any) -> Any:
            response = view_func(request, *args, **kwargs)
            # Only intercept TemplateResponse (lazy rendering)
            from django.template.response import TemplateResponse

            if isinstance(response, TemplateResponse) and not response.is_rendered:
                ctx_data = response.context_data or {}
                strict_ctx = StrictRequestContext(
                    request, ctx_data, allow_undefined=extra
                )
                response.content = response.template.render(strict_ctx)
                return response
            return response

        return wrapper

    return decorator
