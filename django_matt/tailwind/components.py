# file-length-max: 600
"""
Pre-built Tailwind CSS component class helpers.

Provides consistent, customizable component classes for common UI elements.
"""

from __future__ import annotations

from django_matt.tailwind.config import get_tailwind_config


class ButtonClasses:
    """
    Button component classes.

    Examples:
        >>> ButtonClasses.primary()
        "inline-flex items-center justify-center px-4 py-2 ..."

        >>> ButtonClasses.outline(size="sm")
        "inline-flex items-center justify-center px-3 py-1.5 ..."
    """

    BASE = (
        "inline-flex items-center justify-center font-medium "
        "transition-colors focus-visible:outline-none focus-visible:ring-2 "
        "focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
    )

    SIZES = {
        "xs": "h-7 px-2 text-xs rounded",
        "sm": "h-8 px-3 text-sm rounded-md",
        "md": "h-10 px-4 text-sm rounded-md",
        "lg": "h-11 px-6 text-base rounded-lg",
        "xl": "h-12 px-8 text-base rounded-lg",
        "icon-sm": "h-8 w-8 rounded-md",
        "icon-md": "h-10 w-10 rounded-md",
        "icon-lg": "h-11 w-11 rounded-lg",
    }

    VARIANTS = {
        "primary": "bg-{primary}-600 text-white hover:bg-{primary}-700 focus-visible:ring-{primary}-500",
        "secondary": "bg-{secondary}-100 text-{secondary}-900 hover:bg-{secondary}-200 focus-visible:ring-{secondary}-500",
        "outline": "border border-{secondary}-300 bg-transparent hover:bg-{secondary}-100 focus-visible:ring-{secondary}-500",
        "ghost": "hover:bg-{secondary}-100 hover:text-{secondary}-900 focus-visible:ring-{secondary}-500",
        "link": "text-{primary}-600 underline-offset-4 hover:underline focus-visible:ring-{primary}-500",
        "destructive": "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500",
        "success": "bg-green-600 text-white hover:bg-green-700 focus-visible:ring-green-500",
        "warning": "bg-yellow-500 text-white hover:bg-yellow-600 focus-visible:ring-yellow-500",
    }

    @classmethod
    def get(
        cls,
        variant: str = "primary",
        size: str = "md",
    ) -> str:
        """Get button classes for the specified variant and size."""
        config = get_tailwind_config()

        base = cls.BASE
        size_classes = cls.SIZES.get(size, cls.SIZES["md"])
        variant_classes = cls.VARIANTS.get(variant, cls.VARIANTS["primary"])

        # Replace color placeholders
        variant_classes = variant_classes.format(
            primary=config.color_primary,
            secondary=config.color_secondary,
        )

        return f"{base} {size_classes} {variant_classes}"

    @classmethod
    def primary(cls, size: str = "md") -> str:
        """Get primary button classes."""
        return cls.get("primary", size)

    @classmethod
    def secondary(cls, size: str = "md") -> str:
        """Get secondary button classes."""
        return cls.get("secondary", size)

    @classmethod
    def outline(cls, size: str = "md") -> str:
        """Get outline button classes."""
        return cls.get("outline", size)

    @classmethod
    def ghost(cls, size: str = "md") -> str:
        """Get ghost button classes."""
        return cls.get("ghost", size)

    @classmethod
    def destructive(cls, size: str = "md") -> str:
        """Get destructive button classes."""
        return cls.get("destructive", size)


class InputClasses:
    """
    Input/form control component classes.

    Examples:
        >>> InputClasses.text()
        "flex h-10 w-full rounded-md border border-gray-300 ..."

        >>> InputClasses.checkbox()
        "h-4 w-4 rounded border-gray-300 ..."
    """

    BASE = (
        "flex w-full rounded-md border bg-white px-3 py-2 text-sm "
        "placeholder:text-gray-400 focus:outline-none focus:ring-2 "
        "focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    )

    VARIANTS = {
        "default": "border-{secondary}-300 focus:border-{primary}-500 focus:ring-{primary}-500",
        "error": "border-red-500 focus:border-red-500 focus:ring-red-500",
        "success": "border-green-500 focus:border-green-500 focus:ring-green-500",
    }

    SIZES = {
        "sm": "h-8 text-xs",
        "md": "h-10 text-sm",
        "lg": "h-12 text-base",
    }

    @classmethod
    def text(cls, variant: str = "default", size: str = "md") -> str:
        """Get text input classes."""
        config = get_tailwind_config()

        variant_classes = cls.VARIANTS.get(variant, cls.VARIANTS["default"]).format(
            primary=config.color_primary,
            secondary=config.color_secondary,
        )
        size_classes = cls.SIZES.get(size, cls.SIZES["md"])

        return f"{cls.BASE} {variant_classes} {size_classes}"

    @classmethod
    def textarea(cls, variant: str = "default") -> str:
        """Get textarea classes."""
        config = get_tailwind_config()

        variant_classes = cls.VARIANTS.get(variant, cls.VARIANTS["default"]).format(
            primary=config.color_primary,
            secondary=config.color_secondary,
        )

        return f"{cls.BASE} {variant_classes} min-h-[80px] py-2"

    @classmethod
    def select(cls, variant: str = "default", size: str = "md") -> str:
        """Get select classes."""
        base_classes = cls.text(variant, size)
        return f"{base_classes} cursor-pointer appearance-none bg-no-repeat bg-right pr-10"

    @classmethod
    def checkbox(cls) -> str:
        """Get checkbox classes."""
        config = get_tailwind_config()
        return (
            f"h-4 w-4 rounded border-{config.color_secondary}-300 "
            f"text-{config.color_primary}-600 focus:ring-{config.color_primary}-500"
        )

    @classmethod
    def radio(cls) -> str:
        """Get radio button classes."""
        config = get_tailwind_config()
        return (
            f"h-4 w-4 border-{config.color_secondary}-300 "
            f"text-{config.color_primary}-600 focus:ring-{config.color_primary}-500"
        )

    @classmethod
    def file(cls) -> str:
        """Get file input classes."""
        return (
            "flex h-10 w-full cursor-pointer rounded-md border border-gray-300 "
            "bg-white px-3 py-2 text-sm file:border-0 file:bg-transparent "
            "file:text-sm file:font-medium"
        )


class FormClasses:
    """
    Form layout component classes.

    Examples:
        >>> FormClasses.group()
        "space-y-2"

        >>> FormClasses.label()
        "text-sm font-medium leading-none ..."
    """

    @classmethod
    def group(cls, spacing: str = "2") -> str:
        """Get form group classes."""
        return f"space-y-{spacing}"

    @classmethod
    def label(cls, required: bool = False) -> str:
        """Get label classes."""
        base = "block text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        if required:
            base += " after:content-['*'] after:ml-0.5 after:text-red-500"
        return base

    @classmethod
    def helper_text(cls) -> str:
        """Get helper text classes."""
        return "text-sm text-gray-500"

    @classmethod
    def error_text(cls) -> str:
        """Get error text classes."""
        return "text-sm text-red-500"

    @classmethod
    def fieldset(cls) -> str:
        """Get fieldset classes."""
        return "space-y-4 rounded-lg border border-gray-200 p-4"

    @classmethod
    def legend(cls) -> str:
        """Get legend classes."""
        return "px-2 text-lg font-semibold"


class CardClasses:
    """
    Card component classes.

    Examples:
        >>> CardClasses.container()
        "rounded-lg border bg-white shadow-sm"

        >>> CardClasses.header()
        "flex flex-col space-y-1.5 p-6"
    """

    @classmethod
    def container(cls, bordered: bool = True, shadow: bool = True) -> str:
        """Get card container classes."""
        classes = "rounded-lg bg-white"
        if bordered:
            classes += " border border-gray-200"
        if shadow:
            classes += " shadow-sm"
        return classes

    @classmethod
    def header(cls) -> str:
        """Get card header classes."""
        return "flex flex-col space-y-1.5 p-6"

    @classmethod
    def title(cls) -> str:
        """Get card title classes."""
        return "text-lg font-semibold leading-none tracking-tight"

    @classmethod
    def description(cls) -> str:
        """Get card description classes."""
        return "text-sm text-gray-500"

    @classmethod
    def content(cls, padding: bool = True) -> str:
        """Get card content classes."""
        return "p-6 pt-0" if padding else ""

    @classmethod
    def footer(cls) -> str:
        """Get card footer classes."""
        return "flex items-center p-6 pt-0"


class AlertClasses:
    """
    Alert/notification component classes.

    Examples:
        >>> AlertClasses.info()
        "rounded-lg border p-4 bg-blue-50 border-blue-200 text-blue-800"
    """

    VARIANTS = {
        "info": "bg-blue-50 border-blue-200 text-blue-800",
        "success": "bg-green-50 border-green-200 text-green-800",
        "warning": "bg-yellow-50 border-yellow-200 text-yellow-800",
        "error": "bg-red-50 border-red-200 text-red-800",
        "default": "bg-gray-50 border-gray-200 text-gray-800",
    }

    @classmethod
    def get(cls, variant: str = "default") -> str:
        """Get alert classes for the specified variant."""
        variant_classes = cls.VARIANTS.get(variant, cls.VARIANTS["default"])
        return f"rounded-lg border p-4 {variant_classes}"

    @classmethod
    def info(cls) -> str:
        """Get info alert classes."""
        return cls.get("info")

    @classmethod
    def success(cls) -> str:
        """Get success alert classes."""
        return cls.get("success")

    @classmethod
    def warning(cls) -> str:
        """Get warning alert classes."""
        return cls.get("warning")

    @classmethod
    def error(cls) -> str:
        """Get error alert classes."""
        return cls.get("error")

    @classmethod
    def title(cls) -> str:
        """Get alert title classes."""
        return "mb-1 font-medium"

    @classmethod
    def description(cls) -> str:
        """Get alert description classes."""
        return "text-sm opacity-90"


class BadgeClasses:
    """
    Badge/tag component classes.

    Examples:
        >>> BadgeClasses.primary()
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ..."
    """

    BASE = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"

    VARIANTS = {
        "default": "bg-gray-100 text-gray-800",
        "primary": "bg-{primary}-100 text-{primary}-800",
        "secondary": "bg-{secondary}-100 text-{secondary}-800",
        "success": "bg-green-100 text-green-800",
        "warning": "bg-yellow-100 text-yellow-800",
        "error": "bg-red-100 text-red-800",
        "outline": "border border-current bg-transparent",
    }

    @classmethod
    def get(cls, variant: str = "default") -> str:
        """Get badge classes for the specified variant."""
        config = get_tailwind_config()
        variant_classes = cls.VARIANTS.get(variant, cls.VARIANTS["default"]).format(
            primary=config.color_primary,
            secondary=config.color_secondary,
        )
        return f"{cls.BASE} {variant_classes}"

    @classmethod
    def primary(cls) -> str:
        """Get primary badge classes."""
        return cls.get("primary")

    @classmethod
    def secondary(cls) -> str:
        """Get secondary badge classes."""
        return cls.get("secondary")

    @classmethod
    def success(cls) -> str:
        """Get success badge classes."""
        return cls.get("success")

    @classmethod
    def warning(cls) -> str:
        """Get warning badge classes."""
        return cls.get("warning")

    @classmethod
    def error(cls) -> str:
        """Get error badge classes."""
        return cls.get("error")


class ModalClasses:
    """
    Modal/dialog component classes.

    Examples:
        >>> ModalClasses.overlay()
        "fixed inset-0 z-50 bg-black/80"

        >>> ModalClasses.content()
        "fixed left-[50%] top-[50%] z-50 ..."
    """

    @classmethod
    def overlay(cls) -> str:
        """Get modal overlay classes."""
        return "fixed inset-0 z-50 bg-black/80 backdrop-blur-sm"

    @classmethod
    def content(cls, size: str = "md") -> str:
        """Get modal content classes."""
        sizes = {
            "sm": "max-w-sm",
            "md": "max-w-lg",
            "lg": "max-w-2xl",
            "xl": "max-w-4xl",
            "full": "max-w-[95vw]",
        }
        size_class = sizes.get(size, sizes["md"])

        return (
            f"fixed left-[50%] top-[50%] z-50 w-full {size_class} "
            "translate-x-[-50%] translate-y-[-50%] rounded-lg border "
            "bg-white p-6 shadow-lg"
        )

    @classmethod
    def header(cls) -> str:
        """Get modal header classes."""
        return "flex flex-col space-y-1.5 text-center sm:text-left"

    @classmethod
    def title(cls) -> str:
        """Get modal title classes."""
        return "text-lg font-semibold leading-none tracking-tight"

    @classmethod
    def description(cls) -> str:
        """Get modal description classes."""
        return "text-sm text-gray-500"

    @classmethod
    def body(cls) -> str:
        """Get modal body classes."""
        return "py-4"

    @classmethod
    def footer(cls) -> str:
        """Get modal footer classes."""
        return "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2"

    @classmethod
    def close_button(cls) -> str:
        """Get modal close button classes."""
        return (
            "absolute right-4 top-4 rounded-sm opacity-70 ring-offset-white "
            "transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 "
            "focus:ring-gray-400 focus:ring-offset-2"
        )


class TableClasses:
    """
    Table component classes.

    Examples:
        >>> TableClasses.container()
        "w-full overflow-auto"

        >>> TableClasses.header_cell()
        "h-12 px-4 text-left align-middle font-medium ..."
    """

    @classmethod
    def container(cls) -> str:
        """Get table container classes."""
        return "w-full overflow-auto"

    @classmethod
    def table(cls) -> str:
        """Get table classes."""
        return "w-full caption-bottom text-sm"

    @classmethod
    def header(cls) -> str:
        """Get table header (thead) classes."""
        return "border-b"

    @classmethod
    def header_row(cls) -> str:
        """Get table header row classes."""
        return "border-b transition-colors hover:bg-gray-50"

    @classmethod
    def header_cell(cls) -> str:
        """Get table header cell (th) classes."""
        return "h-12 px-4 text-left align-middle font-medium text-gray-500"

    @classmethod
    def body(cls) -> str:
        """Get table body (tbody) classes."""
        return "[&_tr:last-child]:border-0"

    @classmethod
    def row(cls, striped: bool = False) -> str:
        """Get table row classes."""
        base = "border-b transition-colors hover:bg-gray-50"
        if striped:
            base += " even:bg-gray-50"
        return base

    @classmethod
    def cell(cls) -> str:
        """Get table cell (td) classes."""
        return "p-4 align-middle"

    @classmethod
    def footer(cls) -> str:
        """Get table footer (tfoot) classes."""
        return "border-t bg-gray-50 font-medium"

    @classmethod
    def caption(cls) -> str:
        """Get table caption classes."""
        return "mt-4 text-sm text-gray-500"


def component_classes(
    component: str,
    variant: str = "default",
    size: str = "md",
    **kwargs,
) -> str:
    """
    Get component classes by name.

    Args:
        component: Component name (button, input, card, etc.)
        variant: Component variant
        size: Component size
        **kwargs: Additional component-specific options

    Returns:
        CSS class string

    Examples:
        >>> component_classes("button", "primary", "lg")
        "inline-flex items-center ..."

        >>> component_classes("alert", "error")
        "rounded-lg border p-4 ..."
    """
    components = {
        "button": lambda: ButtonClasses.get(variant, size),
        "input": lambda: InputClasses.text(variant, size),
        "textarea": lambda: InputClasses.textarea(variant),
        "select": lambda: InputClasses.select(variant, size),
        "checkbox": lambda: InputClasses.checkbox(),
        "radio": lambda: InputClasses.radio(),
        "card": lambda: CardClasses.container(**kwargs),
        "alert": lambda: AlertClasses.get(variant),
        "badge": lambda: BadgeClasses.get(variant),
        "modal": lambda: ModalClasses.content(size),
    }

    factory = components.get(component)
    if factory:
        return factory()

    return ""


__all__ = [
    "AlertClasses",
    "BadgeClasses",
    "ButtonClasses",
    "CardClasses",
    "FormClasses",
    "InputClasses",
    "ModalClasses",
    "TableClasses",
    "component_classes",
]
