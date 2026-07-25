"""
Vite template tags for Django templates.

Usage:
    {% load vite %}

    <head>
        {% vite_hmr_client %}
        {% vite_react_refresh %}
        {% vite_asset "src/main.js" %}
        {% vite_preload "src/main.js" %}
    </head>
"""

from __future__ import annotations

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

from django_matt.vite.config import get_vite_config
from django_matt.vite.manifest import get_manifest

register = template.Library()


@register.simple_tag
def vite_asset(entry: str) -> str:
    """
    Render script and CSS tags for a Vite entry point.

    In development: serves from Vite dev server.
    In production: resolves from the build manifest.

    Usage:
        {% vite_asset "src/main.js" %}
        {% vite_asset "src/styles.css" %}
    """
    config = get_vite_config()

    if config.is_dev:
        dev_url = config.dev_server_url.rstrip("/")
        return mark_safe(f'<script type="module" src="{dev_url}/{entry}"></script>')

    # Production: resolve from manifest
    manifest = get_manifest()
    tags: list[str] = []
    tags.extend(manifest.get_css_tags(entry))
    tags.extend(manifest.get_js_tags(entry))

    return mark_safe("\n".join(tags))


@register.simple_tag
def vite_hmr_client() -> str:
    """
    Render the Vite HMR client script tag.

    Only outputs in development (DEBUG=True). Noop in production.

    Usage:
        {% vite_hmr_client %}
    """
    if not getattr(settings, "DEBUG", False):
        return ""

    config = get_vite_config()
    if not config.hmr_enabled:
        return ""

    dev_url = config.dev_server_url.rstrip("/")
    return mark_safe(f'<script type="module" src="{dev_url}/@vite/client"></script>')


@register.simple_tag
def vite_react_refresh() -> str:
    """
    Render the React Fast Refresh preamble.

    Only outputs in development when react_refresh is enabled.
    Must be placed before any other scripts.

    Usage:
        {% vite_react_refresh %}
    """
    if not getattr(settings, "DEBUG", False):
        return ""

    config = get_vite_config()
    if not config.react_refresh:
        return ""

    dev_url = config.dev_server_url.rstrip("/")
    return mark_safe(
        f'<script type="module">\n'
        f'  import RefreshRuntime from "{dev_url}/@react-refresh";\n'
        f"  RefreshRuntime.injectIntoGlobalHook(window);\n"
        f"  window.$RefreshReg$ = () => {{}};\n"
        f"  window.$RefreshSig$ = () => (type) => type;\n"
        f"  window.__vite_plugin_react_preamble_installed__ = true;\n"
        f"</script>"
    )


@register.simple_tag
def vite_preload(entry: str) -> str:
    """
    Render modulepreload link tags for a production entry point.

    Only outputs in production. Noop in development (Vite handles this).

    Usage:
        {% vite_preload "src/main.js" %}
    """
    config = get_vite_config()

    if config.is_dev:
        return ""

    manifest = get_manifest()
    tags = manifest.get_preload_tags(entry)
    return mark_safe("\n".join(tags))
