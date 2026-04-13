"""
Unpoly template tags.

Provides template tags for generating Unpoly attributes and configuration.

Usage:
    {% load unpoly_tags %}

    <nav {% up_nav %}>
        <a href="/" {% up_current "/" %}>Home</a>
        <a href="/about/" {% up_current "/about/" %}>About</a>
    </nav>

    {% up_config %}
"""

from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

import orjson

from django_matt.unpoly.config import get_unpoly_config

register = template.Library()


@register.simple_tag
def up_current(path: str) -> str:
    """
    Output the [up-current] attribute for nav highlighting.

    Unpoly automatically adds .up-current to links matching the
    current URL when inside an [up-nav] container.

    Args:
        path: URL path to match against.

    Usage:
        <a href="/dashboard/" {% up_current "/dashboard/" %}>Dashboard</a>
    """
    return mark_safe(f'[up-current="{path}"]')


@register.tag("up_nav")
def do_up_nav(parser: template.base.Parser, token: template.base.Token) -> UpNavNode:
    """
    Wrap navigation with [up-nav] attribute.

    Content between {% up_nav %} and {% end_up_nav %} is wrapped
    in a <nav up-nav> element.

    Usage:
        {% up_nav %}
            <a href="/">Home</a>
            <a href="/about/">About</a>
        {% end_up_nav %}
    """
    nodelist = parser.parse(("end_up_nav",))
    parser.delete_first_token()
    return UpNavNode(nodelist)


class UpNavNode(template.Node):
    def __init__(self, nodelist: template.NodeList) -> None:
        self.nodelist = nodelist

    def render(self, context: template.Context) -> str:
        inner = self.nodelist.render(context)
        return f"<nav up-nav>{inner}</nav>"


@register.simple_tag
def up_config() -> str:
    """
    Render a <script> tag with Unpoly configuration.

    Reads from Django settings (UNPOLY dict) and outputs an
    up.configure() call.

    Usage:
        <head>
            {% up_config %}
        </head>
    """
    config = get_unpoly_config()

    js_config: dict[str, object] = {}
    if not config.enabled:
        js_config["enabled"] = False
    if config.version:
        js_config["version"] = config.version

    if not js_config:
        return mark_safe("")

    json_str = orjson.dumps(js_config).decode()
    return mark_safe(
        f"<script>if(typeof up !== 'undefined') {{ up.network.config.update({json_str}); }}</script>"
    )


__all__ = [
    "do_up_nav",
    "up_config",
    "up_current",
]
