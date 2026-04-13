"""
Template tags for rendering django-matt forms in Django templates.

Usage:
    {% load matt_forms %}
    {% render_form form %}
    {% render_form form theme="bootstrap" %}
    {% render_field form.email class="custom-class" %}
    {% form_errors form %}
"""

from __future__ import annotations

from html import escape
from typing import Any

from django import template
from django.utils.safestring import mark_safe

from django_matt.forms.bridge import THEME_CLASSES, render_form

register = template.Library()


@register.simple_tag
def render_matt_form(
    form: Any,
    theme: str = "shadcn",
    method: str = "post",
    action: str = "",
) -> str:
    """
    Render an entire Django form using the matt component system.

    Usage:
        {% load matt_forms %}
        {% render_matt_form form %}
        {% render_matt_form form theme="bootstrap" action="/submit/" %}
    """
    html = render_form(form, theme=theme, method=method, action=action)
    return mark_safe(html)


@register.simple_tag
def render_field(bound_field: Any, **kwargs: str) -> str:
    """
    Render a single bound form field with optional extra attributes.

    Usage:
        {% load matt_forms %}
        {% render_field form.name class="my-class" placeholder="Enter name" %}
    """
    if not hasattr(bound_field, "field"):
        return ""

    theme = kwargs.pop("theme", "shadcn")
    classes = THEME_CLASSES.get(theme, THEME_CLASSES["shadcn"])

    # Merge extra classes
    extra_class = kwargs.pop("class", "")
    base_class = classes.get("input", "")

    from django.forms import BooleanField, ChoiceField, Textarea

    field = bound_field.field
    widget = field.widget

    if isinstance(field, BooleanField):
        base_class = classes.get("checkbox", "")
    elif isinstance(widget, Textarea):
        base_class = classes.get("textarea", "")
    elif isinstance(field, ChoiceField):
        base_class = classes.get("select", "")

    final_class = f"{base_class} {extra_class}".strip()

    # Build attrs dict
    attrs: dict[str, str] = {"class": final_class}
    attrs.update(kwargs)

    # Use Django's built-in rendering with our attrs
    rendered = bound_field.as_widget(attrs=attrs)

    # Wrap with label and help text
    parts: list[str] = []
    parts.append(f'<div class="{escape(classes["field_wrapper"])}">')

    label_text = bound_field.label or bound_field.name
    required_mark = ' <span class="text-destructive">*</span>' if field.required else ""
    parts.append(
        f'  <label for="{escape(bound_field.id_for_label)}"'
        f' class="{escape(classes["label"])}">{escape(str(label_text))}{required_mark}</label>'
    )
    parts.append(f"  {rendered}")

    if field.help_text:
        parts.append(
            f'  <p class="{escape(classes["help_text"])}">{escape(str(field.help_text))}</p>'
        )

    if bound_field.errors:
        for error in bound_field.errors:
            parts.append(f'  <p class="{escape(classes["error"])}">{escape(str(error))}</p>')

    parts.append("</div>")
    return mark_safe("\n".join(parts))


@register.simple_tag
def form_errors(form: Any, theme: str = "shadcn") -> str:
    """
    Render form-level (non-field) errors with styling.

    Usage:
        {% load matt_forms %}
        {% form_errors form %}
        {% form_errors form theme="bootstrap" %}
    """
    if not hasattr(form, "errors"):
        return ""

    non_field_errors = form.non_field_errors()
    if not non_field_errors:
        return ""

    classes = THEME_CLASSES.get(theme, THEME_CLASSES["shadcn"])
    parts: list[str] = []
    parts.append(f'<div class="{escape(classes["error_list"])}">')
    parts.append("  <ul>")
    for error in non_field_errors:
        parts.append(f"    <li>{escape(str(error))}</li>")
    parts.append("  </ul>")
    parts.append("</div>")

    return mark_safe("\n".join(parts))
