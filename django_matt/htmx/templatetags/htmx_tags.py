"""
HTMX template tags.

Provides template tags for generating HTMX attributes and components.

Usage:
    {% load htmx_tags %}

    {% htmx_script %}
    {% htmx_attrs "get" "/api/users" target="#results" %}
    {% if htmx %}This is an HTMX request{% endif %}
"""

from typing import Any

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def htmx_script(
    version: str = "1.9.10",
    extensions: str | None = None,
    integrity: str | None = None,
) -> str:
    """
    Include the HTMX script tag.

    Usage:
        {% htmx_script %}
        {% htmx_script version="1.9.10" %}
        {% htmx_script extensions="sse,ws" %}
    """
    base_url = f"https://unpkg.com/htmx.org@{version}"

    integrity_attr = ""
    if integrity:
        integrity_attr = f' integrity="{integrity}" crossorigin="anonymous"'

    script = f'<script src="{base_url}"{integrity_attr}></script>'

    # Add extensions if specified
    if extensions:
        ext_scripts = []
        for ext in extensions.split(","):
            ext = ext.strip()
            ext_scripts.append(f'<script src="{base_url}/dist/ext/{ext}.js"></script>')
        script += "\n" + "\n".join(ext_scripts)

    return mark_safe(script)


@register.simple_tag
def htmx_attrs(
    method: str,
    url: str,
    target: str | None = None,
    swap: str | None = None,
    trigger: str | None = None,
    indicator: str | None = None,
    confirm: str | None = None,
    boost: bool = False,
    push_url: str | None = None,
    select: str | None = None,
    vals: str | None = None,
    headers: str | None = None,
    **kwargs,
) -> str:
    """
    Generate HTMX attributes.

    Usage:
        <button {% htmx_attrs "post" "/api/items" target="#list" swap="beforeend" %}>
            Add Item
        </button>

        <a {% htmx_attrs "get" "/page" boost=True %}>Link</a>
    """
    attrs = []

    # Method and URL
    method = method.lower()
    if method in ("get", "post", "put", "patch", "delete"):
        attrs.append(f'hx-{method}="{url}"')
    else:
        raise ValueError(f"Invalid HTMX method: {method}")

    # Common attributes
    if target:
        attrs.append(f'hx-target="{target}"')
    if swap:
        attrs.append(f'hx-swap="{swap}"')
    if trigger:
        attrs.append(f'hx-trigger="{trigger}"')
    if indicator:
        attrs.append(f'hx-indicator="{indicator}"')
    if confirm:
        attrs.append(f'hx-confirm="{confirm}"')
    if boost:
        attrs.append('hx-boost="true"')
    if push_url:
        attrs.append(f'hx-push-url="{push_url}"')
    if select:
        attrs.append(f'hx-select="{select}"')
    if vals:
        attrs.append(f"hx-vals='{vals}'")
    if headers:
        attrs.append(f"hx-headers='{headers}'")

    # Extra kwargs as hx-* attributes
    for key, value in kwargs.items():
        key = key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                attrs.append(f'hx-{key}="true"')
        else:
            attrs.append(f'hx-{key}="{value}"')

    return mark_safe(" ".join(attrs))


@register.simple_tag
def hx_get(url: str, **kwargs) -> str:
    """Shortcut for hx-get attribute."""
    return htmx_attrs("get", url, **kwargs)


@register.simple_tag
def hx_post(url: str, **kwargs) -> str:
    """Shortcut for hx-post attribute."""
    return htmx_attrs("post", url, **kwargs)


@register.simple_tag
def hx_put(url: str, **kwargs) -> str:
    """Shortcut for hx-put attribute."""
    return htmx_attrs("put", url, **kwargs)


@register.simple_tag
def hx_patch(url: str, **kwargs) -> str:
    """Shortcut for hx-patch attribute."""
    return htmx_attrs("patch", url, **kwargs)


@register.simple_tag
def hx_delete(url: str, **kwargs) -> str:
    """Shortcut for hx-delete attribute."""
    return htmx_attrs("delete", url, **kwargs)


@register.simple_tag
def hx_trigger(
    event: str,
    modifiers: str | None = None,
) -> str:
    """
    Generate hx-trigger attribute.

    Usage:
        <input {% hx_trigger "keyup" "changed delay:500ms" %} ...>
        <div {% hx_trigger "intersect" "once" %} ...>
    """
    value = event
    if modifiers:
        value = f"{event} {modifiers}"
    return mark_safe(f'hx-trigger="{value}"')


@register.simple_tag
def hx_vals(values: dict[str, Any]) -> str:
    """
    Generate hx-vals attribute from a dictionary.

    Usage:
        <button {% hx_vals my_dict %} hx-post="/api">Submit</button>
    """
    import orjson

    json_str = orjson.dumps(values).decode()
    return mark_safe(f"hx-vals='{json_str}'")


@register.simple_tag
def hx_headers(headers: dict[str, str]) -> str:
    """
    Generate hx-headers attribute from a dictionary.

    Usage:
        <button {% hx_headers my_headers %} hx-post="/api">Submit</button>
    """
    import orjson

    json_str = orjson.dumps(headers).decode()
    return mark_safe(f"hx-headers='{json_str}'")


@register.inclusion_tag("htmx/loading_indicator.html")
def htmx_loading(
    id: str = "loading",
    text: str = "Loading...",
    spinner: bool = True,
) -> dict[str, Any]:
    """
    Render a loading indicator.

    Usage:
        {% htmx_loading id="my-loader" text="Please wait..." %}

        <!-- Use with hx-indicator -->
        <button hx-get="/api" hx-indicator="#my-loader">Load</button>
    """
    return {
        "id": id,
        "text": text,
        "spinner": spinner,
    }


@register.simple_tag(takes_context=True)
def htmx_csrf(context) -> str:
    """
    Generate HTMX-compatible CSRF token header.

    Usage:
        <body {% htmx_csrf %}>
            ...
        </body>

    This sets hx-headers with the CSRF token for all HTMX requests.
    """
    request = context.get("request")
    if request:
        from django.middleware.csrf import get_token

        token = get_token(request)
        return mark_safe(f'hx-headers=\'{{"X-CSRFToken": "{token}"}}\'')
    return ""


@register.tag
def htmx_fragment(parser, token):
    """
    Define a template fragment that can be rendered independently.

    Usage:
        {% htmx_fragment "user-list" %}
            <ul>
                {% for user in users %}
                    <li>{{ user.name }}</li>
                {% endfor %}
            </ul>
        {% end_htmx_fragment %}

    In your view, you can render just this fragment:
        from django_matt.htmx import render_fragment
        return render_fragment(request, "users/list.html", "user-list", context)
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(f"'{bits[0]}' tag requires exactly one argument")
    fragment_name = bits[1].strip("\"'")
    nodelist = parser.parse(("end_htmx_fragment",))
    parser.delete_first_token()
    return HtmxFragmentNode(fragment_name, nodelist)


class HtmxFragmentNode(template.Node):
    def __init__(self, name: str, nodelist):
        self.name = name
        self.nodelist = nodelist

    def render(self, context):
        # Check if we should render only this fragment
        target_fragment = context.get("_htmx_fragment")
        if target_fragment and target_fragment != self.name:
            return ""

        # Wrap in a div with the fragment name as ID
        content = self.nodelist.render(context)
        return f'<div id="{self.name}">{content}</div>'


@register.simple_tag
def htmx_oob(target_id: str, swap: str = "innerHTML") -> str:
    """
    Generate OOB swap attribute.

    Usage:
        <div id="sidebar" {% htmx_oob "sidebar" %}>
            Updated sidebar content
        </div>
    """
    return mark_safe(f'hx-swap-oob="{swap}"')


@register.filter
def htmx_safe_id(value: Any) -> str:
    """
    Convert a value to a safe HTML ID for HTMX targeting.

    Usage:
        <div id="item-{{ item.pk|htmx_safe_id }}">...</div>
    """
    return str(value).replace(" ", "-").replace(".", "_")


__all__ = [
    "htmx_attrs",
    "htmx_csrf",
    "htmx_fragment",
    "htmx_loading",
    "htmx_oob",
    "htmx_safe_id",
    "htmx_script",
    "hx_delete",
    "hx_get",
    "hx_headers",
    "hx_patch",
    "hx_post",
    "hx_put",
    "hx_trigger",
    "hx_vals",
]
