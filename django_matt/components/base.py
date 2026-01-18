"""
Base component classes for the backend-served component system.

Provides the foundation for defining UI components in Python that
can be serialized to JSON and rendered by any frontend framework.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, Type, Union
from pydantic import BaseModel, Field, ConfigDict
import uuid


class ComponentType(str, Enum):
    """Component type identifiers."""
    # Layout
    CONTAINER = "container"
    CARD = "card"
    MODAL = "modal"
    DRAWER = "drawer"
    TABS = "tabs"
    ACCORDION = "accordion"
    ALERT = "alert"

    # Form
    FORM = "form"
    TEXT_FIELD = "text_field"
    EMAIL_FIELD = "email_field"
    PASSWORD_FIELD = "password_field"
    NUMBER_FIELD = "number_field"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SWITCH = "switch"
    DATE_PICKER = "date_picker"
    FILE_UPLOAD = "file_upload"

    # Data
    DATA_TABLE = "data_table"
    LIST = "list"
    DETAIL_VIEW = "detail_view"
    PAGINATION = "pagination"

    # Actions
    BUTTON = "button"
    LINK = "link"
    ICON_BUTTON = "icon_button"

    # Display
    TEXT = "text"
    HEADING = "heading"
    IMAGE = "image"
    AVATAR = "avatar"
    BADGE = "badge"
    SPINNER = "spinner"
    PROGRESS = "progress"

    # Auth
    LOGIN_FORM = "login_form"
    REGISTER_FORM = "register_form"
    OAUTH_BUTTONS = "oauth_buttons"


class ValidationRule(BaseModel):
    """Validation rule for form fields."""
    type: Literal["required", "min", "max", "minLength", "maxLength", "pattern", "email", "url", "custom"]
    value: Optional[Any] = None
    message: str = ""


class EventHandler(BaseModel):
    """Event handler definition."""
    event: str  # click, submit, change, etc.
    action: str  # URL or action name
    method: str = "POST"
    confirm: Optional[str] = None  # Confirmation message
    optimistic: bool = False  # Optimistic UI update


class Component(BaseModel):
    """
    Base class for all UI components.

    Components are Pydantic models that serialize to JSON and can be
    rendered by frontend framework adapters.

    Usage:
        from django_matt.components import Component, Text

        # Create a component
        greeting = Text(content="Hello, World!", variant="h1")

        # Serialize to JSON
        json_data = greeting.model_dump()

        # Render with a specific renderer
        from django_matt.components.renderers import ReactRenderer
        html = ReactRenderer().render(greeting)
    """
    model_config = ConfigDict(extra="allow")

    # Core properties
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ComponentType

    # Styling
    class_name: Optional[str] = None
    style: Optional[Dict[str, str]] = None

    # Visibility & state
    visible: bool = True
    disabled: bool = False
    loading: bool = False

    # Children
    children: List["Component"] = Field(default_factory=list)

    # Events
    on: Optional[Dict[str, EventHandler]] = None

    # Data binding
    bind: Optional[str] = None  # Bind to a data path

    # Accessibility
    aria_label: Optional[str] = None
    aria_describedby: Optional[str] = None

    # Custom props (passed through to renderer)
    props: Dict[str, Any] = Field(default_factory=dict)

    def add_child(self, child: "Component") -> "Component":
        """Add a child component."""
        self.children.append(child)
        return self

    def with_class(self, class_name: str) -> "Component":
        """Add CSS class."""
        if self.class_name:
            self.class_name = f"{self.class_name} {class_name}"
        else:
            self.class_name = class_name
        return self

    def with_style(self, **styles) -> "Component":
        """Add inline styles."""
        if self.style is None:
            self.style = {}
        self.style.update(styles)
        return self

    def on_click(self, action: str, **kwargs) -> "Component":
        """Add click handler."""
        if self.on is None:
            self.on = {}
        self.on["click"] = EventHandler(event="click", action=action, **kwargs)
        return self

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return self.model_dump(exclude_none=True)


# Component type alias for nested components
ComponentTree = Union[Component, List[Component]]


class ComponentRegistry:
    """
    Registry for component types and custom components.

    Allows registering custom components and retrieving them by name.

    Usage:
        from django_matt.components import registry, Component

        @registry.register("custom_card")
        class CustomCard(Component):
            type: ComponentType = ComponentType.CARD
            title: str
            description: str

        # Later, retrieve by name
        CardClass = registry.get("custom_card")
    """

    def __init__(self):
        self._components: Dict[str, Type[Component]] = {}
        self._aliases: Dict[str, str] = {}

    def register(self, name: str, aliases: Optional[List[str]] = None):
        """
        Decorator to register a component class.

        Usage:
            @registry.register("my_component", aliases=["mycomp"])
            class MyComponent(Component):
                ...
        """
        def decorator(cls: Type[Component]) -> Type[Component]:
            self._components[name] = cls
            if aliases:
                for alias in aliases:
                    self._aliases[alias] = name
            return cls
        return decorator

    def register_class(
        self,
        name: str,
        cls: Type[Component],
        aliases: Optional[List[str]] = None,
    ) -> None:
        """Register a component class directly."""
        self._components[name] = cls
        if aliases:
            for alias in aliases:
                self._aliases[alias] = name

    def get(self, name: str) -> Optional[Type[Component]]:
        """Get a component class by name."""
        if name in self._aliases:
            name = self._aliases[name]
        return self._components.get(name)

    def list(self) -> List[str]:
        """List all registered component names."""
        return list(self._components.keys())

    def unregister(self, name: str) -> None:
        """Unregister a component."""
        if name in self._components:
            del self._components[name]
        # Remove aliases
        self._aliases = {k: v for k, v in self._aliases.items() if v != name}


# Global registry instance
registry = ComponentRegistry()


class Slot(BaseModel):
    """
    Named slot for component composition.

    Slots allow placing child components in specific locations.

    Usage:
        card = Card(
            slots={
                "header": Text(content="Title"),
                "footer": Button(label="Submit"),
            }
        )
    """
    name: str
    content: Optional[ComponentTree] = None
    fallback: Optional[ComponentTree] = None


__all__ = [
    "ComponentType",
    "ValidationRule",
    "EventHandler",
    "Component",
    "ComponentTree",
    "ComponentRegistry",
    "registry",
    "Slot",
]
