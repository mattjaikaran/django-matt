"""Tests for django_matt.components module."""

import pytest
from unittest.mock import Mock, patch
import json


# =============================================================================
# COMPONENT TYPE TESTS
# =============================================================================


class TestComponentType:
    """Tests for ComponentType enum."""

    def test_component_type_values(self):
        """Test that ComponentType has expected values."""
        from django_matt.components.base import ComponentType

        # Layout types - enum values
        assert ComponentType.CONTAINER.value == "container"
        assert ComponentType.CARD.value == "card"
        assert ComponentType.MODAL.value == "modal"
        assert ComponentType.TABS.value == "tabs"

        # Form types
        assert ComponentType.FORM.value == "form"
        assert ComponentType.TEXT_FIELD.value == "text_field"
        assert ComponentType.EMAIL_FIELD.value == "email_field"

        # Data types
        assert ComponentType.DATA_TABLE.value == "data_table"
        assert ComponentType.PAGINATION.value == "pagination"

        # Auth types
        assert ComponentType.LOGIN_FORM.value == "login_form"
        assert ComponentType.REGISTER_FORM.value == "register_form"


# =============================================================================
# VALIDATION RULE TESTS
# =============================================================================


class TestValidationRule:
    """Tests for ValidationRule class."""

    def test_validation_rule_creation(self):
        """Test creating a validation rule."""
        from django_matt.components.base import ValidationRule

        rule = ValidationRule(type="required", message="This field is required")
        assert rule.type == "required"
        assert rule.message == "This field is required"
        assert rule.value is None

    def test_validation_rule_with_value(self):
        """Test validation rule with value."""
        from django_matt.components.base import ValidationRule

        rule = ValidationRule(type="minLength", value=5, message="Min 5 characters")
        assert rule.type == "minLength"
        assert rule.value == 5

    def test_validation_rule_types(self):
        """Test all validation rule types."""
        from django_matt.components.base import ValidationRule

        types = ["required", "min", "max", "minLength", "maxLength", "pattern", "email", "url", "custom"]
        for rule_type in types:
            rule = ValidationRule(type=rule_type)
            assert rule.type == rule_type


# =============================================================================
# EVENT HANDLER TESTS
# =============================================================================


class TestEventHandler:
    """Tests for EventHandler class."""

    def test_event_handler_creation(self):
        """Test creating an event handler."""
        from django_matt.components.base import EventHandler

        handler = EventHandler(event="click", action="/api/action")
        assert handler.event == "click"
        assert handler.action == "/api/action"
        assert handler.method == "POST"

    def test_event_handler_with_confirmation(self):
        """Test event handler with confirmation."""
        from django_matt.components.base import EventHandler

        handler = EventHandler(
            event="click",
            action="/api/delete",
            confirm="Are you sure?",
        )
        assert handler.confirm == "Are you sure?"

    def test_event_handler_optimistic(self):
        """Test event handler with optimistic UI."""
        from django_matt.components.base import EventHandler

        handler = EventHandler(
            event="click",
            action="/api/toggle",
            optimistic=True,
        )
        assert handler.optimistic is True


# =============================================================================
# COMPONENT TESTS
# =============================================================================


class TestComponent:
    """Tests for Component base class."""

    def test_component_creation(self):
        """Test creating a component."""
        from django_matt.components.base import Component, ComponentType

        component = Component(type=ComponentType.CONTAINER)
        assert component.type == ComponentType.CONTAINER
        assert component.visible is True
        assert component.disabled is False
        assert component.children == []

    def test_component_has_id(self):
        """Test that components get auto-generated IDs."""
        from django_matt.components.base import Component, ComponentType

        comp1 = Component(type=ComponentType.CONTAINER)
        comp2 = Component(type=ComponentType.CONTAINER)

        assert comp1.id is not None
        assert comp2.id is not None
        assert comp1.id != comp2.id

    def test_component_custom_id(self):
        """Test component with custom ID."""
        from django_matt.components.base import Component, ComponentType

        component = Component(type=ComponentType.CONTAINER, id="my-id")
        assert component.id == "my-id"

    def test_component_add_child(self):
        """Test adding child components."""
        from django_matt.components.base import Component, ComponentType

        parent = Component(type=ComponentType.CONTAINER)
        child = Component(type=ComponentType.TEXT)

        result = parent.add_child(child)

        assert child in parent.children
        assert result is parent  # Returns self for chaining

    def test_component_with_class(self):
        """Test adding CSS classes."""
        from django_matt.components.base import Component, ComponentType

        component = Component(type=ComponentType.CONTAINER)
        result = component.with_class("px-4")
        assert component.class_name == "px-4"
        assert result is component

        component.with_class("py-2")
        assert component.class_name == "px-4 py-2"

    def test_component_with_style(self):
        """Test adding inline styles."""
        from django_matt.components.base import Component, ComponentType

        component = Component(type=ComponentType.CONTAINER)
        result = component.with_style(color="red", fontSize="16px")

        assert component.style == {"color": "red", "fontSize": "16px"}
        assert result is component

    def test_component_on_click(self):
        """Test adding click handler."""
        from django_matt.components.base import Component, ComponentType

        component = Component(type=ComponentType.BUTTON)
        result = component.on_click("/api/submit", method="POST")

        assert "click" in component.on
        assert component.on["click"].action == "/api/submit"
        assert result is component

    def test_component_to_json(self):
        """Test serializing component to JSON."""
        from django_matt.components.base import Component, ComponentType

        component = Component(
            type=ComponentType.CONTAINER,
            id="test-id",
            class_name="container",
        )
        data = component.to_json()

        assert data["type"] == "container"
        assert data["id"] == "test-id"
        assert data["class_name"] == "container"

    def test_component_children_in_json(self):
        """Test that children are included in JSON."""
        from django_matt.components.base import Component, ComponentType

        parent = Component(type=ComponentType.CONTAINER, id="parent")
        child = Component(type=ComponentType.TEXT, id="child")
        parent.add_child(child)

        data = parent.to_json()
        assert len(data["children"]) == 1
        assert data["children"][0]["id"] == "child"


# =============================================================================
# COMPONENT REGISTRY TESTS
# =============================================================================


class TestComponentRegistry:
    """Tests for ComponentRegistry class."""

    def test_registry_creation(self):
        """Test creating a registry."""
        from django_matt.components.base import ComponentRegistry

        registry = ComponentRegistry()
        assert registry is not None
        assert registry._components == {}

    def test_registry_register_decorator(self):
        """Test using registry as decorator."""
        from django_matt.components.base import ComponentRegistry, Component, ComponentType

        registry = ComponentRegistry()

        @registry.register("custom_card")
        class CustomCard(Component):
            type: ComponentType = ComponentType.CARD
            title: str = ""

        assert registry.get("custom_card") == CustomCard

    def test_registry_register_with_aliases(self):
        """Test registering with aliases."""
        from django_matt.components.base import ComponentRegistry, Component, ComponentType

        registry = ComponentRegistry()

        @registry.register("custom_card", aliases=["card", "cc"])
        class CustomCard(Component):
            type: ComponentType = ComponentType.CARD

        assert registry.get("custom_card") == CustomCard
        assert registry.get("card") == CustomCard
        assert registry.get("cc") == CustomCard

    def test_registry_register_class(self):
        """Test registering class directly."""
        from django_matt.components.base import ComponentRegistry, Component, ComponentType

        registry = ComponentRegistry()

        class MyComponent(Component):
            type: ComponentType = ComponentType.CONTAINER

        registry.register_class("my_component", MyComponent)
        assert registry.get("my_component") == MyComponent

    def test_registry_get_nonexistent(self):
        """Test getting non-existent component."""
        from django_matt.components.base import ComponentRegistry

        registry = ComponentRegistry()
        assert registry.get("nonexistent") is None

    def test_registry_list(self):
        """Test listing registered components."""
        from django_matt.components.base import ComponentRegistry, Component, ComponentType

        registry = ComponentRegistry()

        @registry.register("comp1")
        class Comp1(Component):
            type: ComponentType = ComponentType.CONTAINER

        @registry.register("comp2")
        class Comp2(Component):
            type: ComponentType = ComponentType.CARD

        names = registry.list()
        assert "comp1" in names
        assert "comp2" in names

    def test_registry_unregister(self):
        """Test unregistering component."""
        from django_matt.components.base import ComponentRegistry, Component, ComponentType

        registry = ComponentRegistry()

        @registry.register("mycomp", aliases=["mc"])
        class MyComp(Component):
            type: ComponentType = ComponentType.CONTAINER

        registry.unregister("mycomp")
        assert registry.get("mycomp") is None
        assert registry.get("mc") is None


class TestGlobalRegistry:
    """Tests for global component registry."""

    def test_global_registry_exists(self):
        """Test that global registry exists."""
        from django_matt.components.base import registry

        assert registry is not None

    def test_global_registry_is_component_registry(self):
        """Test that global registry is ComponentRegistry."""
        from django_matt.components.base import registry, ComponentRegistry

        assert isinstance(registry, ComponentRegistry)


# =============================================================================
# SLOT TESTS
# =============================================================================


class TestSlot:
    """Tests for Slot class."""

    def test_slot_creation(self):
        """Test creating a slot."""
        from django_matt.components.base import Slot

        slot = Slot(name="header")
        assert slot.name == "header"
        assert slot.content is None
        assert slot.fallback is None

    def test_slot_with_content(self):
        """Test slot with content."""
        from django_matt.components.base import Slot, Component, ComponentType

        content = Component(type=ComponentType.TEXT)
        slot = Slot(name="header", content=content)
        assert slot.content is content

    def test_slot_with_fallback(self):
        """Test slot with fallback content."""
        from django_matt.components.base import Slot, Component, ComponentType

        fallback = Component(type=ComponentType.TEXT)
        slot = Slot(name="header", fallback=fallback)
        assert slot.fallback is fallback


# =============================================================================
# FORM COMPONENT TESTS
# =============================================================================


class TestFormComponents:
    """Tests for form-related components."""

    def test_text_field_import(self):
        """Test TextField can be imported and created."""
        from django_matt.components.forms import TextField

        field = TextField(name="username", label="Username")
        assert field.name == "username"
        assert field.label == "Username"

    def test_email_field_import(self):
        """Test EmailField can be imported and created."""
        from django_matt.components.forms import EmailField

        field = EmailField(name="email", label="Email")
        assert field.name == "email"

    def test_password_field_import(self):
        """Test PasswordField can be imported and created."""
        from django_matt.components.forms import PasswordField

        field = PasswordField(name="password", label="Password")
        assert field.name == "password"

    def test_base_field_validation(self):
        """Test BaseField validation methods."""
        from django_matt.components.forms import TextField

        field = TextField(name="test", label="Test")
        field.required_field("Required")
        assert field.required is True
        assert len(field.validation) == 1


# =============================================================================
# LAYOUT COMPONENT TESTS
# =============================================================================


class TestLayoutComponents:
    """Tests for layout components."""

    def test_container_import(self):
        """Test Container can be imported."""
        from django_matt.components.layout import Container

        container = Container()
        assert container is not None

    def test_card_import(self):
        """Test Card can be imported."""
        from django_matt.components.layout import Card

        card = Card()
        assert card is not None

    def test_modal_import(self):
        """Test Modal can be imported."""
        from django_matt.components.layout import Modal

        modal = Modal()
        assert modal is not None

    def test_alert_import(self):
        """Test Alert can be imported."""
        from django_matt.components.layout import Alert

        alert = Alert()
        assert alert is not None


# =============================================================================
# DATA COMPONENT TESTS
# =============================================================================


class TestDataComponents:
    """Tests for data display components."""

    def test_data_table_import(self):
        """Test DataTable can be imported."""
        from django_matt.components.data import DataTable

        table = DataTable()
        assert table is not None

    def test_pagination_import(self):
        """Test Pagination can be imported."""
        from django_matt.components.data import Pagination

        pagination = Pagination()
        assert pagination is not None


# =============================================================================
# THEMING TESTS
# =============================================================================


class TestTheming:
    """Tests for theming system."""

    def test_theme_module_imports(self):
        """Test theming module can be imported."""
        from django_matt.components import theming

        assert theming is not None

    def test_theme_class_exists(self):
        """Test Theme class exists."""
        from django_matt.components.theming import Theme

        assert Theme is not None


# =============================================================================
# SERVING TESTS
# =============================================================================


class TestServing:
    """Tests for component serving utilities."""

    def test_serving_module_imports(self):
        """Test serving module can be imported."""
        from django_matt.components import serving

        assert serving is not None

    def test_component_view_exists(self):
        """Test component_view function exists."""
        from django_matt.components.serving import component_view

        assert callable(component_view)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestComponentIntegration:
    """Integration tests for component system."""

    def test_build_form_with_fields(self):
        """Test building a form with fields."""
        from django_matt.components.forms import TextField, EmailField, PasswordField

        fields = [
            EmailField(name="email", label="Email", required=True),
            PasswordField(name="password", label="Password", required=True),
        ]

        assert len(fields) == 2
        assert fields[0].name == "email"
        assert fields[1].name == "password"

    def test_component_serialization_roundtrip(self):
        """Test serializing and deserializing component."""
        from django_matt.components.base import Component, ComponentType
        import json

        original = Component(
            type=ComponentType.CONTAINER,
            id="test-container",
            class_name="px-4 py-2",
        )

        # Serialize
        json_str = json.dumps(original.to_json())

        # Deserialize
        data = json.loads(json_str)
        restored = Component(**data)

        assert restored.id == original.id
        assert restored.class_name == original.class_name


# =============================================================================
# Requirement-aligned tests (07-04)
# =============================================================================


class TestComponentRendersToHTML:
    """COMP-01: Verify backend component renders to HTML string."""

    def test_component_to_json_produces_dict(self):
        """Test component renders to serializable dict (HTML generation input)."""
        from django_matt.components.base import Component, ComponentType

        component = Component(
            type=ComponentType.CARD,
            id="test-card",
            class_name="shadow-md",
        )
        data = component.to_json()

        assert isinstance(data, dict)
        assert data["type"] == "card"
        assert data["id"] == "test-card"
        assert data["class_name"] == "shadow-md"

    def test_component_tree_renders_children(self):
        """Test component tree with children serializes correctly."""
        from django_matt.components.base import Component, ComponentType

        parent = Component(type=ComponentType.CONTAINER, id="parent")
        child1 = Component(type=ComponentType.TEXT, id="child1")
        child2 = Component(type=ComponentType.BUTTON, id="child2")

        parent.add_child(child1).add_child(child2)
        data = parent.to_json()

        assert len(data["children"]) == 2
        assert data["children"][0]["id"] == "child1"
        assert data["children"][1]["id"] == "child2"

    def test_html_component_response_returns_html(self):
        """Test HtmlComponentResponse renders component to HTML."""
        from django_matt.components.base import Component, ComponentType
        from django_matt.components.serving import HtmlComponentResponse

        component = Component(type=ComponentType.CONTAINER, id="test-html")

        response = HtmlComponentResponse(component)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/html"
        # Content should be a string (rendered HTML)
        assert len(response.content) > 0

    def test_component_response_returns_response(self):
        """Test ComponentResponse wraps component in HttpResponse."""
        from django_matt.components.base import Component, ComponentType
        from django_matt.components.serving import ComponentResponse
        from django.http import HttpResponse

        component = Component(type=ComponentType.CONTAINER, id="test-resp")

        response = ComponentResponse(component)
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200

    def test_page_builder_renders(self):
        """Test Page builder adds components and renders."""
        from django_matt.components.base import Component, ComponentType
        from django_matt.components.serving import Page
        from django.http import HttpResponse

        page = Page(title="Test Page")
        page.add(Component(type=ComponentType.CONTAINER, id="section1"))
        page.add(Component(type=ComponentType.CARD, id="card1"))

        assert len(page.components) == 2
        assert page.title == "Test Page"

        # Render without request
        response = page.render()
        assert isinstance(response, HttpResponse)

    def test_create_component_factory(self):
        """Test create_component creates component by type name."""
        from django_matt.components.serving import create_component
        from django_matt.components.base import registry, Component, ComponentType

        # Register a test component
        @registry.register("test_widget_07")
        class TestWidget(Component):
            type: ComponentType = ComponentType.CONTAINER
            label: str = ""

        widget = create_component("test_widget_07", label="Hello")
        assert widget.label == "Hello"

        # Clean up
        registry.unregister("test_widget_07")
