"""
HTML rendering for page responses.

Generates the HTML shell with page data injected as a script tag
(not a data attribute like Inertia) for better performance.
"""

import json
from typing import Any, Dict, Optional

from django.http import HttpRequest
from django.template import Template, Context
from django.template.loader import render_to_string, get_template
from django.conf import settings
from django.utils.safestring import mark_safe

from django_matt.pages.response import PageData

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


# Default HTML template
DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {% if page_data.title %}<title>{{ page_data.title }}</title>{% endif %}
    {% for name, content in page_data.meta.items %}
    <meta name="{{ name }}" content="{{ content }}">
    {% endfor %}
    {{ head_tags|safe }}
</head>
<body>
    <div id="{{ root_id }}"></div>
    <script type="application/json" id="page-data">{{ page_json|safe }}</script>
    {{ body_scripts|safe }}
</body>
</html>"""


def get_pages_config() -> Dict[str, Any]:
    """Get pages configuration from settings."""
    defaults = {
        "root_template": None,  # Use default template
        "root_id": "app",
        "lang": "en",
        "head_tags": "",
        "body_scripts": "",
        "manifest": None,
        "ssr": {
            "enabled": False,
            "server": "http://localhost:3001",
            "timeout": 5000,
        },
    }

    user_config = getattr(settings, "PAGES", {})
    return {**defaults, **user_config}


def render_page_html(request: HttpRequest, page_data: PageData) -> str:
    """
    Render the full HTML document for a page.

    The page data is injected as a JSON script tag for performance.
    This is faster than Inertia's data-page attribute approach because:
    1. No HTML entity encoding/decoding overhead
    2. Direct JSON parsing by JavaScript
    3. No DOM attribute size limits
    """
    config = get_pages_config()

    # Serialize page data to JSON
    page_dict = page_data.to_dict()
    if HAS_ORJSON:
        page_json = orjson.dumps(page_dict).decode("utf-8")
    else:
        page_json = json.dumps(page_dict, separators=(",", ":"))

    # Build context
    context = {
        "page_data": page_data,
        "page_json": page_json,
        "root_id": config["root_id"],
        "lang": config["lang"],
        "head_tags": _get_head_tags(config),
        "body_scripts": _get_body_scripts(config),
        "request": request,
    }

    # Use custom template or default
    template_name = config.get("root_template")
    if template_name:
        try:
            return render_to_string(template_name, context, request=request)
        except Exception:
            # Fall back to default if custom template fails
            pass

    # Use default template
    template = Template(DEFAULT_TEMPLATE)
    return template.render(Context(context))


def _get_head_tags(config: Dict[str, Any]) -> str:
    """Get head tags (CSS, etc.) from config or manifest."""
    head_tags = config.get("head_tags", "")

    # If manifest is configured, add CSS from it
    manifest = _load_manifest(config.get("manifest"))
    if manifest:
        css_files = _get_css_from_manifest(manifest)
        for css_file in css_files:
            head_tags += f'\n    <link rel="stylesheet" href="{css_file}">'

    return head_tags


def _get_body_scripts(config: Dict[str, Any]) -> str:
    """Get body scripts from config or manifest."""
    body_scripts = config.get("body_scripts", "")

    # If manifest is configured, add JS from it
    manifest = _load_manifest(config.get("manifest"))
    if manifest:
        js_files = _get_js_from_manifest(manifest)
        for js_file in js_files:
            body_scripts += f'\n    <script type="module" src="{js_file}"></script>'

    return body_scripts


def _load_manifest(manifest_path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Load Vite/webpack manifest file."""
    if not manifest_path:
        return None

    try:
        import os
        from django.contrib.staticfiles import finders

        # Try to find the manifest file
        if os.path.isabs(manifest_path):
            full_path = manifest_path
        else:
            full_path = finders.find(manifest_path)

        if full_path and os.path.exists(full_path):
            with open(full_path, "r") as f:
                return json.load(f)
    except Exception:
        pass

    return None


def _get_css_from_manifest(manifest: Dict[str, Any]) -> list:
    """Extract CSS files from manifest."""
    css_files = []

    # Vite manifest format
    for key, value in manifest.items():
        if isinstance(value, dict):
            # Entry point CSS
            if value.get("isEntry") and value.get("css"):
                css_files.extend(value["css"])

    return css_files


def _get_js_from_manifest(manifest: Dict[str, Any]) -> list:
    """Extract JS entry files from manifest."""
    js_files = []

    # Vite manifest format
    for key, value in manifest.items():
        if isinstance(value, dict):
            # Entry point JS
            if value.get("isEntry") and value.get("file"):
                js_files.append(value["file"])

    return js_files


def render_page_script_tag(page_data: PageData) -> str:
    """
    Render just the page data script tag.

    Useful for custom templates that want to control HTML structure
    but still use the page system.

    Usage in Django template:
        {% load pages %}
        {{ page_data|page_script_tag }}
    """
    page_dict = page_data.to_dict()
    if HAS_ORJSON:
        page_json = orjson.dumps(page_dict).decode("utf-8")
    else:
        page_json = json.dumps(page_dict, separators=(",", ":"))

    return mark_safe(
        f'<script type="application/json" id="page-data">{page_json}</script>'
    )


__all__ = [
    "render_page_html",
    "render_page_script_tag",
    "get_pages_config",
]
