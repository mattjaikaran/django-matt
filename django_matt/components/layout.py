"""
Layout components for structuring UI.

Provides containers, cards, modals, tabs, and other
structural components.
"""

from typing import Literal

from pydantic import Field

from django_matt.components.base import (
    Component,
    ComponentTree,
    ComponentType,
    registry,
)

# =============================================================================
# Containers
# =============================================================================


@registry.register("container", aliases=["div", "box"])
class Container(Component):
    """
    Generic container component.

    Usage:
        content = Container(
            children=[Text(content="Hello"), Text(content="World")],
            class_name="flex gap-4",
        )
    """

    type: ComponentType = ComponentType.CONTAINER
    tag: str = "div"  # HTML tag to render
    flex: bool = False
    flex_direction: Literal["row", "column", "row-reverse", "column-reverse"] = "row"
    justify: Literal["start", "end", "center", "between", "around", "evenly"] = "start"
    align: Literal["start", "end", "center", "stretch", "baseline"] = "start"
    gap: str | None = None  # CSS gap value
    padding: str | None = None
    margin: str | None = None


@registry.register("card")
class Card(Component):
    """
    Card component with header, body, and footer.

    Usage:
        user_card = Card(
            title="User Profile",
            description="View and edit your profile",
            children=[...],
            footer=[Button(label="Save")],
        )
    """

    type: ComponentType = ComponentType.CARD
    title: str | None = None
    description: str | None = None
    header: ComponentTree | None = None
    footer: ComponentTree | None = None
    image: str | None = None  # Header image URL
    image_alt: str | None = None
    variant: Literal["default", "outline", "elevated", "filled"] = "default"
    hoverable: bool = False
    clickable: bool = False


@registry.register("modal", aliases=["dialog"])
class Modal(Component):
    """
    Modal dialog component.

    Usage:
        confirm_modal = Modal(
            id="confirm-delete",
            title="Confirm Delete",
            description="Are you sure you want to delete this item?",
            children=[...],
            footer=[
                Button(label="Cancel", variant="outline"),
                Button(label="Delete", variant="destructive"),
            ],
        )
    """

    type: ComponentType = ComponentType.MODAL
    title: str | None = None
    description: str | None = None
    footer: ComponentTree | None = None
    open: bool = False
    size: Literal["sm", "md", "lg", "xl", "full"] = "md"
    closable: bool = True
    close_on_overlay: bool = True
    close_on_escape: bool = True
    prevent_scroll: bool = True


@registry.register("drawer", aliases=["side_panel"])
class Drawer(Component):
    """
    Slide-out drawer component.

    Usage:
        menu_drawer = Drawer(
            id="menu",
            title="Menu",
            position="left",
            children=[...],
        )
    """

    type: ComponentType = ComponentType.DRAWER
    title: str | None = None
    description: str | None = None
    footer: ComponentTree | None = None
    open: bool = False
    position: Literal["left", "right", "top", "bottom"] = "right"
    size: Literal["sm", "md", "lg", "xl", "full"] = "md"
    closable: bool = True
    close_on_overlay: bool = True


# =============================================================================
# Tabs & Accordion
# =============================================================================


class TabItem(Component):
    """Individual tab item."""

    type: ComponentType = ComponentType.CONTAINER
    value: str
    label: str
    icon: str | None = None
    disabled: bool = False
    badge: str | None = None


@registry.register("tabs")
class Tabs(Component):
    """
    Tabbed interface component.

    Usage:
        settings_tabs = Tabs(
            items=[
                TabItem(value="general", label="General", children=[...]),
                TabItem(value="security", label="Security", children=[...]),
                TabItem(value="notifications", label="Notifications", children=[...]),
            ],
            default_value="general",
        )
    """

    type: ComponentType = ComponentType.TABS
    items: list[TabItem] = Field(default_factory=list)
    default_value: str | None = None
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    variant: Literal["default", "outline", "pills"] = "default"

    def add_tab(self, value: str, label: str, content: ComponentTree = None, **kwargs) -> "Tabs":
        """Add a tab."""
        tab = TabItem(value=value, label=label, **kwargs)
        if content:
            if isinstance(content, list):
                tab.children = content
            else:
                tab.children = [content]
        self.items.append(tab)
        return self


class AccordionItem(Component):
    """Individual accordion item."""

    type: ComponentType = ComponentType.CONTAINER
    value: str
    title: str
    subtitle: str | None = None
    icon: str | None = None
    disabled: bool = False


@registry.register("accordion")
class Accordion(Component):
    """
    Accordion component.

    Usage:
        faq = Accordion(
            items=[
                AccordionItem(value="q1", title="What is this?", children=[...]),
                AccordionItem(value="q2", title="How does it work?", children=[...]),
            ],
            type="single",
        )
    """

    type: ComponentType = ComponentType.ACCORDION
    items: list[AccordionItem] = Field(default_factory=list)
    accordion_type: Literal["single", "multiple"] = "single"
    collapsible: bool = True
    default_value: str | list[str] | None = None

    def add_item(
        self, value: str, title: str, content: ComponentTree = None, **kwargs
    ) -> "Accordion":
        """Add an accordion item."""
        item = AccordionItem(value=value, title=title, **kwargs)
        if content:
            if isinstance(content, list):
                item.children = content
            else:
                item.children = [content]
        self.items.append(item)
        return self


# =============================================================================
# Alerts & Notifications
# =============================================================================


@registry.register("alert")
class Alert(Component):
    """
    Alert component for notifications.

    Usage:
        error_alert = Alert(
            title="Error",
            message="Something went wrong",
            variant="destructive",
            dismissible=True,
        )
    """

    type: ComponentType = ComponentType.ALERT
    title: str | None = None
    message: str = ""
    variant: Literal["default", "success", "warning", "error", "info", "destructive"] = "default"
    icon: str | None = None
    dismissible: bool = False
    action: Component | None = None  # Action button


@registry.register("toast")
class Toast(Component):
    """
    Toast notification component.

    Usage:
        success_toast = Toast(
            title="Saved",
            message="Your changes have been saved",
            variant="success",
            duration=5000,
        )
    """

    type: ComponentType = ComponentType.ALERT  # Reuse alert type
    title: str | None = None
    message: str = ""
    variant: Literal["default", "success", "warning", "error", "info"] = "default"
    duration: int = 5000  # Auto-dismiss in ms (0 = no auto-dismiss)
    position: Literal[
        "top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"
    ] = "bottom-right"
    action: Component | None = None


# =============================================================================
# Navigation
# =============================================================================


class NavItem(Component):
    """Navigation item."""

    type: ComponentType = ComponentType.LINK
    label: str
    href: str
    icon: str | None = None
    active: bool = False
    badge: str | None = None
    children: list["NavItem"] = Field(default_factory=list)  # Nested items


@registry.register("nav", aliases=["navigation"])
class Nav(Component):
    """
    Navigation component.

    Usage:
        sidebar = Nav(
            items=[
                NavItem(label="Dashboard", href="/", icon="home"),
                NavItem(label="Users", href="/users", icon="users"),
                NavItem(label="Settings", href="/settings", icon="settings"),
            ],
            orientation="vertical",
        )
    """

    type: ComponentType = ComponentType.CONTAINER
    items: list[NavItem] = Field(default_factory=list)
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    variant: Literal["default", "pills", "underline"] = "default"


# =============================================================================
# Display Components
# =============================================================================


@registry.register("text", aliases=["p", "span"])
class Text(Component):
    """
    Text display component.

    Usage:
        title = Text(content="Hello World", variant="h1")
        paragraph = Text(content="Some content here", variant="p")
    """

    type: ComponentType = ComponentType.TEXT
    content: str
    variant: Literal["h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "small", "lead", "muted"] = (
        "p"
    )
    truncate: bool = False
    max_lines: int | None = None


@registry.register("heading", aliases=["h1", "h2", "h3"])
class Heading(Component):
    """
    Heading component.

    Usage:
        title = Heading(content="Page Title", level=1)
    """

    type: ComponentType = ComponentType.HEADING
    content: str
    level: Literal[1, 2, 3, 4, 5, 6] = 1
    subtitle: str | None = None


@registry.register("image", aliases=["img"])
class Image(Component):
    """
    Image component.

    Usage:
        avatar = Image(
            src="/images/user.jpg",
            alt="User avatar",
            width=100,
            height=100,
            rounded=True,
        )
    """

    type: ComponentType = ComponentType.IMAGE
    src: str
    alt: str = ""
    width: int | None = None
    height: int | None = None
    rounded: bool = False
    aspect_ratio: str | None = None  # e.g., "16/9", "1/1"
    object_fit: Literal["contain", "cover", "fill", "none", "scale-down"] = "cover"
    loading: Literal["lazy", "eager"] = "lazy"
    fallback: str | None = None  # Fallback image URL


@registry.register("avatar")
class Avatar(Component):
    """
    Avatar component.

    Usage:
        user_avatar = Avatar(
            src="/images/user.jpg",
            alt="John Doe",
            fallback="JD",
            size="md",
        )
    """

    type: ComponentType = ComponentType.AVATAR
    src: str | None = None
    alt: str = ""
    fallback: str | None = None  # Initials or icon
    size: Literal["xs", "sm", "md", "lg", "xl"] = "md"
    status: Literal["online", "offline", "away", "busy"] | None = None


@registry.register("badge")
class Badge(Component):
    """
    Badge component.

    Usage:
        status = Badge(content="Active", variant="success")
    """

    type: ComponentType = ComponentType.BADGE
    content: str
    variant: Literal["default", "secondary", "success", "warning", "error", "outline"] = "default"
    size: Literal["sm", "md", "lg"] = "md"
    dot: bool = False  # Show as dot instead of text


@registry.register("spinner", aliases=["loading"])
class Spinner(Component):
    """
    Loading spinner component.

    Usage:
        loading = Spinner(size="md", label="Loading...")
    """

    type: ComponentType = ComponentType.SPINNER
    size: Literal["xs", "sm", "md", "lg", "xl"] = "md"
    label: str | None = None


@registry.register("progress")
class Progress(Component):
    """
    Progress bar component.

    Usage:
        upload_progress = Progress(value=65, max_value=100, show_label=True)
    """

    type: ComponentType = ComponentType.PROGRESS
    value: float = 0
    max_value: float = 100
    show_label: bool = False
    label_format: str = "{value}%"
    variant: Literal["default", "success", "warning", "error"] = "default"
    size: Literal["sm", "md", "lg"] = "md"
    indeterminate: bool = False


@registry.register("divider", aliases=["separator", "hr"])
class Divider(Component):
    """
    Divider/separator component.

    Usage:
        sep = Divider(orientation="horizontal", label="OR")
    """

    type: ComponentType = ComponentType.CONTAINER
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    label: str | None = None


__all__ = [
    # Containers
    "Container",
    "Card",
    "Modal",
    "Drawer",
    # Tabs & Accordion
    "TabItem",
    "Tabs",
    "AccordionItem",
    "Accordion",
    # Alerts
    "Alert",
    "Toast",
    # Navigation
    "NavItem",
    "Nav",
    # Display
    "Text",
    "Heading",
    "Image",
    "Avatar",
    "Badge",
    "Spinner",
    "Progress",
    "Divider",
]
