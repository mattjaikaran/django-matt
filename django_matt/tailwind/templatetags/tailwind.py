"""
Template tags for Tailwind CSS helpers.

Usage:
    {% load tailwind %}

    <!-- Class merging -->
    <button class="{% cn 'px-4 py-2' button_class %}">Click</button>

    <!-- Component classes -->
    <button class="{% button 'primary' 'lg' %}">Submit</button>
    <input class="{% input 'default' %}" />
    <div class="{% card %}">...</div>

    <!-- Conditional classes -->
    <div class="{% classes 'base-class' is_active|yesno:'active,' %}">...</div>

    <!-- Theme colors -->
    <div class="{% theme_bg 'primary' %}">...</div>
"""

from django import template

from django_matt.tailwind.components import (
    AlertClasses,
    BadgeClasses,
    ButtonClasses,
    CardClasses,
    FormClasses,
    InputClasses,
    TableClasses,
    component_classes,
)
from django_matt.tailwind.config import get_tailwind_config
from django_matt.tailwind.utils import classes as classes_func
from django_matt.tailwind.utils import cn as cn_func

register = template.Library()


@register.simple_tag
def cn(*args):
    """
    Merge class names with intelligent conflict resolution.

    Usage:
        {% cn 'px-4 py-2' extra_class %}
        {% cn 'base' is_active|yesno:'active,' %}
    """
    return cn_func(*args)


@register.simple_tag
def classes(*args):
    """
    Simple class list builder without conflict resolution.

    Usage:
        {% classes 'base' optional_class another_class %}
    """
    return classes_func(*args)


@register.simple_tag
def button(variant="primary", size="md"):
    """
    Get button component classes.

    Usage:
        <button class="{% button %}">Default</button>
        <button class="{% button 'outline' 'sm' %}">Small Outline</button>
    """
    return ButtonClasses.get(variant, size)


@register.simple_tag
def input_field(variant="default", size="md"):
    """
    Get input component classes.

    Usage:
        <input class="{% input_field %}" />
        <input class="{% input_field 'error' %}" />
    """
    return InputClasses.text(variant, size)


@register.simple_tag
def textarea(variant="default"):
    """
    Get textarea component classes.

    Usage:
        <textarea class="{% textarea %}"></textarea>
    """
    return InputClasses.textarea(variant)


@register.simple_tag
def select_field(variant="default", size="md"):
    """
    Get select component classes.

    Usage:
        <select class="{% select_field %}">...</select>
    """
    return InputClasses.select(variant, size)


@register.simple_tag
def checkbox():
    """
    Get checkbox component classes.

    Usage:
        <input type="checkbox" class="{% checkbox %}" />
    """
    return InputClasses.checkbox()


@register.simple_tag
def radio():
    """
    Get radio button component classes.

    Usage:
        <input type="radio" class="{% radio %}" />
    """
    return InputClasses.radio()


@register.simple_tag
def form_group(spacing="2"):
    """
    Get form group classes.

    Usage:
        <div class="{% form_group %}">...</div>
    """
    return FormClasses.group(spacing)


@register.simple_tag
def label(required=False):
    """
    Get label classes.

    Usage:
        <label class="{% label %}">Name</label>
        <label class="{% label True %}">Required Field</label>
    """
    return FormClasses.label(required)


@register.simple_tag
def card(bordered=True, shadow=True):
    """
    Get card container classes.

    Usage:
        <div class="{% card %}">...</div>
        <div class="{% card bordered=False %}">...</div>
    """
    return CardClasses.container(bordered, shadow)


@register.simple_tag
def card_header():
    """Get card header classes."""
    return CardClasses.header()


@register.simple_tag
def card_title():
    """Get card title classes."""
    return CardClasses.title()


@register.simple_tag
def card_content(padding=True):
    """Get card content classes."""
    return CardClasses.content(padding)


@register.simple_tag
def card_footer():
    """Get card footer classes."""
    return CardClasses.footer()


@register.simple_tag
def alert(variant="default"):
    """
    Get alert component classes.

    Usage:
        <div class="{% alert 'success' %}">Success!</div>
        <div class="{% alert 'error' %}">Error!</div>
    """
    return AlertClasses.get(variant)


@register.simple_tag
def badge(variant="default"):
    """
    Get badge component classes.

    Usage:
        <span class="{% badge 'success' %}">Active</span>
    """
    return BadgeClasses.get(variant)


@register.simple_tag
def table():
    """Get table classes."""
    return TableClasses.table()


@register.simple_tag
def table_header():
    """Get table header classes."""
    return TableClasses.header()


@register.simple_tag
def table_row(striped=False):
    """Get table row classes."""
    return TableClasses.row(striped)


@register.simple_tag
def table_cell():
    """Get table cell classes."""
    return TableClasses.cell()


@register.simple_tag
def th():
    """Get table header cell classes."""
    return TableClasses.header_cell()


@register.simple_tag
def theme_bg(color_type="primary", shade=500):
    """
    Get theme background color class.

    Usage:
        <div class="{% theme_bg 'primary' %}">...</div>
        <div class="{% theme_bg 'secondary' 100 %}">...</div>
    """
    config = get_tailwind_config()
    return config.bg(color_type, shade)


@register.simple_tag
def theme_text(color_type="primary", shade=500):
    """
    Get theme text color class.

    Usage:
        <span class="{% theme_text 'primary' %}">...</span>
    """
    config = get_tailwind_config()
    return config.text(color_type, shade)


@register.simple_tag
def theme_border(color_type="primary", shade=500):
    """
    Get theme border color class.

    Usage:
        <div class="border {% theme_border 'primary' %}">...</div>
    """
    config = get_tailwind_config()
    return config.border(color_type, shade)


@register.simple_tag
def component(name, variant="default", size="md", **kwargs):
    """
    Get component classes by name.

    Usage:
        <button class="{% component 'button' 'primary' 'lg' %}">...</button>
        <div class="{% component 'alert' 'error' %}">...</div>
    """
    return component_classes(name, variant, size, **kwargs)


@register.filter
def tw_if(value, classes_str):
    """
    Return classes if value is truthy.

    Usage:
        <div class="{{ is_active|tw_if:'bg-blue-500 text-white' }}">...</div>
    """
    if value:
        return classes_str
    return ""


@register.filter
def tw_unless(value, classes_str):
    """
    Return classes if value is falsy.

    Usage:
        <div class="{{ is_active|tw_unless:'bg-gray-100' }}">...</div>
    """
    if not value:
        return classes_str
    return ""


@register.filter
def tw_toggle(value, classes_str):
    """
    Toggle between two sets of classes.

    Usage:
        <div class="{{ is_active|tw_toggle:'bg-blue-500,bg-gray-100' }}">...</div>
    """
    parts = classes_str.split(",", 1)
    if len(parts) == 2:
        return parts[0] if value else parts[1]
    return parts[0] if value else ""
