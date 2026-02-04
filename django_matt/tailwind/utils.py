"""
Tailwind CSS class utilities.

Provides utilities for merging, deduplicating, and conditionally
applying Tailwind CSS classes.
"""

from __future__ import annotations

from typing import Any

# Tailwind class categories for smart merging
# Maps class prefix to category for conflict resolution
CLASS_CATEGORIES = {
    # Spacing
    "p-": "padding",
    "px-": "padding-x",
    "py-": "padding-y",
    "pt-": "padding-top",
    "pr-": "padding-right",
    "pb-": "padding-bottom",
    "pl-": "padding-left",
    "ps-": "padding-start",
    "pe-": "padding-end",
    "m-": "margin",
    "mx-": "margin-x",
    "my-": "margin-y",
    "mt-": "margin-top",
    "mr-": "margin-right",
    "mb-": "margin-bottom",
    "ml-": "margin-left",
    "ms-": "margin-start",
    "me-": "margin-end",
    # Sizing
    "w-": "width",
    "h-": "height",
    "min-w-": "min-width",
    "min-h-": "min-height",
    "max-w-": "max-width",
    "max-h-": "max-height",
    "size-": "size",
    # Layout
    "flex": "display",
    "grid": "display",
    "block": "display",
    "inline": "display",
    "hidden": "display",
    "justify-": "justify",
    "items-": "items",
    "content-": "content",
    "gap-": "gap",
    "gap-x-": "gap-x",
    "gap-y-": "gap-y",
    # Colors
    "bg-": "background",
    "text-": "text-color",
    "border-": "border-color",
    # Typography
    "font-": "font",
    "text-xs": "text-size",
    "text-sm": "text-size",
    "text-base": "text-size",
    "text-lg": "text-size",
    "text-xl": "text-size",
    "text-2xl": "text-size",
    "text-3xl": "text-size",
    "text-4xl": "text-size",
    "leading-": "leading",
    "tracking-": "tracking",
    # Borders
    "rounded": "rounded",
    "rounded-": "rounded",
    "border": "border-width",
    "border-0": "border-width",
    "border-2": "border-width",
    "border-4": "border-width",
    "border-8": "border-width",
    # Effects
    "shadow": "shadow",
    "shadow-": "shadow",
    "opacity-": "opacity",
    # Transitions
    "duration-": "duration",
    "ease-": "ease",
    "transition": "transition",
    "transition-": "transition",
}


def cn(*args: Any) -> str:
    """
    Merge class names intelligently.

    Combines multiple class strings, handling:
    - Falsy values (None, False, "")
    - Conditional classes
    - Tailwind class conflicts (later classes override earlier ones)

    Args:
        *args: Class strings or falsy values to merge

    Returns:
        Merged class string

    Examples:
        >>> cn("px-4", "py-2")
        "px-4 py-2"

        >>> cn("px-4", None, "py-2")
        "px-4 py-2"

        >>> cn("px-4", False and "hidden")
        "px-4"

        >>> cn("px-4", "px-8")  # Later overrides earlier
        "px-8"
    """
    return merge_classes(*args)


def merge_classes(*args: Any) -> str:
    """
    Merge class names with intelligent conflict resolution.

    When the same Tailwind utility category appears multiple times,
    the later value takes precedence (similar to CSS cascade).

    Args:
        *args: Class strings or falsy values

    Returns:
        Merged and deduplicated class string
    """
    all_classes = []

    for arg in args:
        if not arg:
            continue

        if isinstance(arg, str):
            all_classes.extend(arg.split())
        elif isinstance(arg, (list, tuple)):
            for item in arg:
                if item:
                    all_classes.extend(str(item).split())

    # Track categories to handle conflicts
    category_map: dict[str, int] = {}
    result_classes: list[str] = []

    for cls in all_classes:
        # Get the base class (without variants like hover:, md:, etc.)
        base_class = _get_base_class(cls)
        category = _get_class_category(base_class)

        if category:
            # Check if we already have this category
            if category in category_map:
                # Remove the previous class of this category
                prev_index = category_map[category]
                result_classes[prev_index] = None  # type: ignore

            category_map[category] = len(result_classes)

        result_classes.append(cls)

    # Filter out None values and deduplicate
    return " ".join(c for c in result_classes if c)


def _get_base_class(cls: str) -> str:
    """Get the base class without variants (hover:, md:, etc.)."""
    parts = cls.split(":")
    return parts[-1]


def _get_class_category(cls: str) -> str | None:
    """Get the category for a Tailwind class."""
    for prefix, category in CLASS_CATEGORIES.items():
        if cls == prefix.rstrip("-") or cls.startswith(prefix):
            return category
    return None


def classes(*args: Any) -> str:
    """
    Simple class list builder without conflict resolution.

    Joins class strings, filtering out falsy values.

    Args:
        *args: Class strings or falsy values

    Returns:
        Joined class string

    Examples:
        >>> classes("px-4", "py-2", None, "bg-blue-500")
        "px-4 py-2 bg-blue-500"
    """
    result = []
    for arg in args:
        if not arg:
            continue
        if isinstance(arg, str):
            result.append(arg)
        elif isinstance(arg, (list, tuple)):
            result.extend(str(item) for item in arg if item)
    return " ".join(result)


class ClassList:
    """
    Builder for constructing class lists with method chaining.

    Examples:
        >>> ClassList().add("px-4").add("py-2").when(True, "bg-blue-500").build()
        "px-4 py-2 bg-blue-500"
    """

    def __init__(self, *initial: str):
        self._classes: list[str] = list(initial)

    def add(self, *classes: str) -> ClassList:
        """Add classes to the list."""
        for cls in classes:
            if cls:
                self._classes.extend(cls.split())
        return self

    def when(self, condition: Any, *classes: str) -> ClassList:
        """Add classes if condition is truthy."""
        if condition:
            return self.add(*classes)
        return self

    def unless(self, condition: Any, *classes: str) -> ClassList:
        """Add classes if condition is falsy."""
        if not condition:
            return self.add(*classes)
        return self

    def remove(self, *classes: str) -> ClassList:
        """Remove classes from the list."""
        for cls in classes:
            while cls in self._classes:
                self._classes.remove(cls)
        return self

    def toggle(self, condition: Any, on_class: str, off_class: str = "") -> ClassList:
        """Add on_class if condition is truthy, off_class otherwise."""
        if condition:
            self.add(on_class)
        elif off_class:
            self.add(off_class)
        return self

    def build(self) -> str:
        """Build the final class string."""
        return merge_classes(*self._classes)

    def __str__(self) -> str:
        return self.build()


class ClassBuilder:
    """
    Advanced class builder with variant support.

    Examples:
        >>> (
        ...     ClassBuilder()
        ...     .base("px-4 py-2")
        ...     .variant("hover", "bg-blue-600")
        ...     .variant("focus", "ring-2 ring-blue-500")
        ...     .build()
        ... )
        "px-4 py-2 hover:bg-blue-600 focus:ring-2 focus:ring-blue-500"
    """

    def __init__(self):
        self._base: list[str] = []
        self._variants: dict[str, list[str]] = {}

    def base(self, *classes: str) -> ClassBuilder:
        """Add base classes."""
        for cls in classes:
            if cls:
                self._base.extend(cls.split())
        return self

    def variant(self, variant: str, *classes: str) -> ClassBuilder:
        """Add variant classes (e.g., hover:, focus:, md:)."""
        if variant not in self._variants:
            self._variants[variant] = []
        for cls in classes:
            if cls:
                self._variants[variant].extend(cls.split())
        return self

    def hover(self, *classes: str) -> ClassBuilder:
        """Add hover: variant classes."""
        return self.variant("hover", *classes)

    def focus(self, *classes: str) -> ClassBuilder:
        """Add focus: variant classes."""
        return self.variant("focus", *classes)

    def active(self, *classes: str) -> ClassBuilder:
        """Add active: variant classes."""
        return self.variant("active", *classes)

    def disabled(self, *classes: str) -> ClassBuilder:
        """Add disabled: variant classes."""
        return self.variant("disabled", *classes)

    def dark(self, *classes: str) -> ClassBuilder:
        """Add dark: variant classes."""
        return self.variant("dark", *classes)

    def sm(self, *classes: str) -> ClassBuilder:
        """Add sm: responsive variant classes."""
        return self.variant("sm", *classes)

    def md(self, *classes: str) -> ClassBuilder:
        """Add md: responsive variant classes."""
        return self.variant("md", *classes)

    def lg(self, *classes: str) -> ClassBuilder:
        """Add lg: responsive variant classes."""
        return self.variant("lg", *classes)

    def xl(self, *classes: str) -> ClassBuilder:
        """Add xl: responsive variant classes."""
        return self.variant("xl", *classes)

    def build(self) -> str:
        """Build the final class string."""
        result = list(self._base)

        for variant, classes in self._variants.items():
            for cls in classes:
                result.append(f"{variant}:{cls}")

        return " ".join(result)

    def __str__(self) -> str:
        return self.build()


# Convenience instance
tw = ClassBuilder()


__all__ = [
    "cn",
    "merge_classes",
    "classes",
    "ClassList",
    "ClassBuilder",
    "tw",
]
