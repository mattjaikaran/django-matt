"""Template tags for strict template mode.

Usage::

    {% load strict_tags %}
    {% allow_undefined optional_sidebar debug_info %}
        {{ optional_sidebar }}
    {% end_allow_undefined %}
"""

from __future__ import annotations

from django import template

register = template.Library()


class AllowUndefinedNode(template.Node):
    """Temporarily allows listed variables to be undefined within a block."""

    def __init__(self, nodelist: template.NodeList, var_names: list[str]) -> None:
        self.nodelist = nodelist
        self.var_names = var_names

    def render(self, context: template.Context) -> str:
        allowlist = getattr(context, "_allow_undefined", None)
        if allowlist is not None:
            original = context._allow_undefined
            context._allow_undefined = original | frozenset(self.var_names)
            try:
                return self.nodelist.render(context)
            finally:
                context._allow_undefined = original
        return self.nodelist.render(context)


@register.tag("allow_undefined")
def do_allow_undefined(
    parser: template.base.Parser, token: template.base.Token
) -> AllowUndefinedNode:
    """Block tag that marks variables as intentionally optional.

    Usage::

        {% allow_undefined var1 var2 %}
            {{ var1 }}
        {% end_allow_undefined %}
    """
    bits = token.split_contents()
    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            "'allow_undefined' tag requires at least one variable name"
        )
    var_names = bits[1:]
    nodelist = parser.parse(("end_allow_undefined",))
    parser.delete_first_token()
    return AllowUndefinedNode(nodelist, var_names)
