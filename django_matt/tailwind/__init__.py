"""
Tailwind CSS integration helpers for Django Matt.

Provides utilities for working with Tailwind CSS in Django templates and views:
- Class utilities: merging, conditional classes, variants
- Component helpers: pre-built Tailwind component classes
- Theme configuration: color schemes, spacing, typography
- Template tags for use in Django templates

Usage:
    # In Python code
    from django_matt.tailwind import cn, classes, tw

    # Merge classes with deduplication
    classes = cn("px-4 py-2", "bg-blue-500", conditional and "hover:bg-blue-600")

    # Build component classes
    button_classes = tw.button(variant="primary", size="lg")

    # In templates
    {% load tailwind %}
    <button class="{% cn 'px-4 py-2' variant_class %}">Click me</button>

Settings:
    DJANGO_MATT_TAILWIND = {
        "THEME": "default",  # or "dark", "custom"
        "COLOR_PRIMARY": "blue",
        "COLOR_SECONDARY": "gray",
        "BORDER_RADIUS": "rounded-lg",
        "COMPONENT_PREFIX": "",  # Optional prefix for component classes
    }
"""

from django_matt.tailwind.components import (
    AlertClasses,
    BadgeClasses,
    ButtonClasses,
    CardClasses,
    FormClasses,
    InputClasses,
    ModalClasses,
    TableClasses,
    component_classes,
)
from django_matt.tailwind.config import (
    TailwindConfig,
    get_tailwind_config,
)
from django_matt.tailwind.utils import (
    ClassBuilder,
    ClassList,
    classes,
    cn,
    merge_classes,
    tw,
)

__all__ = [
    # Utils
    "cn",
    "tw",
    "classes",
    "merge_classes",
    "ClassList",
    "ClassBuilder",
    # Components
    "ButtonClasses",
    "InputClasses",
    "FormClasses",
    "CardClasses",
    "AlertClasses",
    "BadgeClasses",
    "ModalClasses",
    "TableClasses",
    "component_classes",
    # Config
    "TailwindConfig",
    "get_tailwind_config",
]
