"""
Inertia.js template tags.

Provides ``{% inertia %}`` and ``{% inertia_head %}`` tags for rendering
the root div and SSR head content respectively.

Usage::

    {% load inertia_tags %}
    <html>
    <head>
        {% inertia_head %}
    </head>
    <body>
        {% inertia %}
        <script src="/static/js/app.js"></script>
    </body>
    </html>
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def inertia(context) -> str:
    """Render the root ``<div id="app">`` with embedded page data.

    The ``page`` context variable (JSON string) is injected by
    :func:`django_matt.inertia.response.inertia` when rendering the
    root template.

    If SSR body content is available it is rendered inside the div.
    """
    page_json = context.get("page", "{}")
    ssr_body = context.get("ssr_body")

    # Escape for HTML attribute (double-quote safe)
    escaped = page_json.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#x27;")

    inner = ssr_body or ""
    return mark_safe(f'<div id="app" data-page="{escaped}">{inner}</div>')


@register.simple_tag(takes_context=True)
def inertia_head(context) -> str:
    """Render SSR head tags if available.

    When SSR is enabled, the SSR server returns ``<title>``, ``<meta>``,
    and other head tags that should be injected into ``<head>``.
    """
    ssr_head: list[str] = context.get("ssr_head", [])
    if not ssr_head:
        return ""
    return mark_safe("\n".join(ssr_head))


__all__ = [
    "inertia",
    "inertia_head",
]
