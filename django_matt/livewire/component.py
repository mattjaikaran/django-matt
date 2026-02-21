"""
Reactive component base class.

Provides the foundation for Livewire-style components with
state management, actions, and lifecycle hooks.
"""

import hashlib
import uuid
from collections.abc import Callable
from functools import wraps
from typing import (
    Any,
    ClassVar,
    TypeVar,
)

import orjson
from pydantic import BaseModel, ConfigDict, PrivateAttr

T = TypeVar("T")


# =============================================================================
# Decorators
# =============================================================================


def reactive(field: T) -> T:
    """
    Mark a field as reactive (triggers re-render on change).

    Usage:
        class Counter(LiveComponent):
            count: int = reactive(0)
    """
    return field


def computed(func: Callable[..., T]) -> property:
    """
    Mark a method as a computed property (cached until dependencies change).

    Usage:
        class Cart(LiveComponent):
            items: List[dict] = []

            @computed
            def total(self) -> float:
                return sum(item['price'] * item['qty'] for item in self.items)
    """
    cache_attr = f"_computed_cache_{func.__name__}"

    @property
    @wraps(func)
    def wrapper(self) -> T:
        # Simple caching - invalidated on any state change
        if not hasattr(self, cache_attr) or self._state_version != getattr(
            self, f"{cache_attr}_version", -1
        ):
            result = func(self)
            setattr(self, cache_attr, result)
            setattr(self, f"{cache_attr}_version", self._state_version)
        return getattr(self, cache_attr)

    wrapper.fget._is_computed = True
    return wrapper


def watch(*fields: str):
    """
    Watch specific fields and call method when they change.

    Usage:
        class Search(LiveComponent):
            query: str = ""

            @watch("query")
            def on_query_change(self, old_value, new_value):
                self.results = self.search(new_value)
    """

    def decorator(func: Callable) -> Callable:
        func._watch_fields = fields
        return func

    return decorator


def action(func: Callable) -> Callable:
    """
    Mark a method as an action that can be called from the frontend.

    Usage:
        class Counter(LiveComponent):
            @action
            def increment(self):
                self.count += 1
    """
    func._is_action = True

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self._mark_dirty()
        return result

    wrapper._is_action = True
    wrapper._original = func
    return wrapper


def on_mount(func: Callable) -> Callable:
    """
    Called when component is first mounted (initial render).

    Usage:
        class UserProfile(LiveComponent):
            @on_mount
            def load_user(self):
                self.user = User.objects.get(pk=self.user_id)
    """
    func._lifecycle = "mount"
    return func


def on_hydrate(func: Callable) -> Callable:
    """
    Called when component state is restored from snapshot.

    Usage:
        class Dashboard(LiveComponent):
            @on_hydrate
            def reconnect_services(self):
                self.ws_client = WebSocketClient()
    """
    func._lifecycle = "hydrate"
    return func


def on_dehydrate(func: Callable) -> Callable:
    """
    Called before component state is serialized to snapshot.

    Usage:
        class Editor(LiveComponent):
            @on_dehydrate
            def cleanup(self):
                self.ws_client.close()
    """
    func._lifecycle = "dehydrate"
    return func


# =============================================================================
# Base Component
# =============================================================================


class LiveComponent(BaseModel):
    """
    Base class for Livewire-style reactive components.

    Components have:
    - Reactive state that triggers re-renders
    - Actions that can be called from the frontend
    - Lifecycle hooks (mount, hydrate, dehydrate)
    - Computed properties with caching
    - Watchers for state changes

    Usage:
        class TodoList(LiveComponent):
            items: List[str] = []
            new_item: str = ""

            @action
            def add_item(self):
                if self.new_item:
                    self.items.append(self.new_item)
                    self.new_item = ""

            @action
            def remove_item(self, index: int):
                self.items.pop(index)

            @computed
            def count(self) -> int:
                return len(self.items)

            def render(self) -> str:
                return '''
                <div wire:id="{{ component_id }}">
                    <input wire:model="new_item" placeholder="New item">
                    <button wire:click="add_item">Add</button>
                    <ul>
                        {% for item in items %}
                        <li>
                            {{ item }}
                            <button wire:click="remove_item({{ loop.index0 }})">×</button>
                        </li>
                        {% endfor %}
                    </ul>
                    <p>Total: {{ count }}</p>
                </div>
                '''
    """

    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    # Component metadata
    _component_id: str = PrivateAttr(default_factory=lambda: str(uuid.uuid4())[:8])
    _component_name: str = PrivateAttr(default="")
    _state_version: int = PrivateAttr(default=0)
    _dirty: bool = PrivateAttr(default=False)
    _mounted: bool = PrivateAttr(default=False)
    _request: Any | None = PrivateAttr(default=None)
    _old_state: dict[str, Any] = PrivateAttr(default_factory=dict)

    # Class-level configuration
    _actions: ClassVar[set[str]] = set()
    _watchers: ClassVar[dict[str, list[str]]] = {}
    _lifecycle_hooks: ClassVar[dict[str, list[str]]] = {}

    def __init__(self, **data):
        super().__init__(**data)
        self._component_name = self.__class__.__name__
        self._discover_methods()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._actions = set()
        cls._watchers = {}
        cls._lifecycle_hooks = {"mount": [], "hydrate": [], "dehydrate": []}

        # Discover decorated methods
        for name in dir(cls):
            if name.startswith("_"):
                continue
            try:
                attr = getattr(cls, name)
            except AttributeError:
                continue

            if callable(attr):
                if getattr(attr, "_is_action", False):
                    cls._actions.add(name)
                if hasattr(attr, "_watch_fields"):
                    for field in attr._watch_fields:
                        if field not in cls._watchers:
                            cls._watchers[field] = []
                        cls._watchers[field].append(name)
                if hasattr(attr, "_lifecycle"):
                    cls._lifecycle_hooks[attr._lifecycle].append(name)

    def _discover_methods(self):
        """Discover action methods at runtime."""

    def _mark_dirty(self):
        """Mark component as needing re-render."""
        self._dirty = True
        self._state_version += 1

    def __setattr__(self, name: str, value: Any):
        """Track state changes for watchers."""
        if not name.startswith("_") and hasattr(self, "_old_state"):
            old_value = getattr(self, name, None)
            super().__setattr__(name, value)

            # Call watchers
            if name in self._watchers and old_value != value:
                for watcher_name in self._watchers[name]:
                    watcher = getattr(self, watcher_name)
                    watcher(old_value, value)

            self._mark_dirty()
        else:
            super().__setattr__(name, value)

    @property
    def component_id(self) -> str:
        """Get the unique component ID."""
        return self._component_id

    def get_state(self) -> dict[str, Any]:
        """Get the current component state."""
        return self.model_dump(exclude={"_*"})

    def set_state(self, state: dict[str, Any]):
        """Set component state from dictionary."""
        for key, value in state.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def call_action(self, action_name: str, *args, **kwargs) -> Any:
        """Call an action method by name."""
        if action_name not in self._actions:
            raise ValueError(f"Unknown action: {action_name}")

        method = getattr(self, action_name)
        return method(*args, **kwargs)

    def mount(self):
        """Called when component is first created."""
        if not self._mounted:
            self._mounted = True
            for hook_name in self._lifecycle_hooks.get("mount", []):
                getattr(self, hook_name)()

    def hydrate(self, state: dict[str, Any]):
        """Restore component from serialized state."""
        self.set_state(state)
        for hook_name in self._lifecycle_hooks.get("hydrate", []):
            getattr(self, hook_name)()

    def dehydrate(self) -> dict[str, Any]:
        """Serialize component state for storage."""
        for hook_name in self._lifecycle_hooks.get("dehydrate", []):
            getattr(self, hook_name)()
        return self.get_state()

    def render(self) -> str:
        """
        Render the component to HTML.

        Override this method to define the component's template.
        """
        raise NotImplementedError("Subclasses must implement render()")

    def get_render_context(self) -> dict[str, Any]:
        """Get the context for rendering."""
        context = self.get_state()
        context["component_id"] = self._component_id
        context["component_name"] = self._component_name

        # Add computed properties
        for name in dir(self.__class__):
            attr = getattr(self.__class__, name, None)
            if isinstance(attr, property) and hasattr(attr.fget, "_is_computed"):
                context[name] = getattr(self, name)

        return context

    def to_html(self) -> str:
        """Render component to HTML with wire attributes."""
        from django.template import Context, Template

        template_str = self.render()
        context = self.get_render_context()

        # Use Django template engine for rendering
        template = Template(template_str)
        html = template.render(Context(context))

        return html

    def get_checksum(self) -> str:
        """Get a checksum of the current state for change detection."""
        state_json = orjson.dumps(self.get_state(), option=orjson.OPT_SORT_KEYS).decode()
        return hashlib.md5(state_json.encode()).hexdigest()[:8]


# =============================================================================
# Component with Validation
# =============================================================================


class ValidatedComponent(LiveComponent):
    """
    Live component with built-in form validation.

    Usage:
        class ContactForm(ValidatedComponent):
            name: str = ""
            email: str = ""
            message: str = ""

            class Validation:
                name = {"required": True, "min_length": 2}
                email = {"required": True, "email": True}
                message = {"required": True, "min_length": 10}

            @action
            def submit(self):
                if self.validate():
                    send_contact_email(self.name, self.email, self.message)
                    self.reset()
    """

    _errors: dict[str, list[str]] = PrivateAttr(default_factory=dict)

    class Validation:
        """Override to define field validation rules."""

    @property
    def errors(self) -> dict[str, list[str]]:
        """Get current validation errors."""
        return self._errors

    def validate(self, fields: list[str] | None = None) -> bool:
        """
        Validate component state.

        Args:
            fields: Specific fields to validate (all if None)

        Returns:
            True if validation passes
        """
        self._errors = {}
        validation_class = getattr(self, "Validation", None)

        if not validation_class:
            return True

        fields_to_validate = fields or [
            name for name in dir(validation_class) if not name.startswith("_")
        ]

        for field_name in fields_to_validate:
            rules = getattr(validation_class, field_name, None)
            if not rules:
                continue

            value = getattr(self, field_name, None)
            field_errors = self._validate_field(field_name, value, rules)

            if field_errors:
                self._errors[field_name] = field_errors

        return len(self._errors) == 0

    def _validate_field(
        self,
        field_name: str,
        value: Any,
        rules: dict[str, Any],
    ) -> list[str]:
        """Validate a single field against rules."""
        errors = []

        # Required
        if rules.get("required") and not value:
            errors.append(f"{field_name} is required")
            return errors  # Skip other validations if empty

        if value is None:
            return errors

        # String validations
        if isinstance(value, str):
            if "min_length" in rules and len(value) < rules["min_length"]:
                errors.append(f"{field_name} must be at least {rules['min_length']} characters")

            if "max_length" in rules and len(value) > rules["max_length"]:
                errors.append(f"{field_name} must be at most {rules['max_length']} characters")

            if rules.get("email"):
                import re

                if not re.match(r"^[^@]+@[^@]+\.[^@]+$", value):
                    errors.append(f"{field_name} must be a valid email")

            if "pattern" in rules:
                import re

                if not re.match(rules["pattern"], value):
                    errors.append(rules.get("pattern_message", f"{field_name} format is invalid"))

        # Numeric validations
        if isinstance(value, (int, float)):
            if "min" in rules and value < rules["min"]:
                errors.append(f"{field_name} must be at least {rules['min']}")

            if "max" in rules and value > rules["max"]:
                errors.append(f"{field_name} must be at most {rules['max']}")

        # Custom validator
        if "validator" in rules:
            custom_errors = rules["validator"](value)
            if custom_errors:
                errors.extend(custom_errors if isinstance(custom_errors, list) else [custom_errors])

        return errors

    def validate_field(self, field_name: str) -> bool:
        """Validate a single field (for real-time validation)."""
        return self.validate(fields=[field_name])

    def reset(self):
        """Reset form to initial state."""
        self._errors = {}
        # Reset to default values
        for field_name, field_info in self.model_fields.items():
            if field_info.default is not None:
                setattr(self, field_name, field_info.default)
            elif field_info.default_factory is not None:
                setattr(self, field_name, field_info.default_factory())

    def get_render_context(self) -> dict[str, Any]:
        """Include errors in render context."""
        context = super().get_render_context()
        context["errors"] = self._errors
        return context


__all__ = [
    "LiveComponent",
    "ValidatedComponent",
    "action",
    "computed",
    "on_dehydrate",
    "on_hydrate",
    "on_mount",
    "reactive",
    "watch",
]
