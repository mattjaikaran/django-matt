"""
Backend-Served Component System.

A framework-agnostic component system for building UIs from the backend.
Components are defined in Python and can be rendered to JSON for any
frontend framework (React, Vue, etc.) or to plain HTML.

Usage:
    from django_matt.components import (
        Card, Text, Button, DataTable, Form, TextField,
        ComponentResponse, component_view,
    )

    # Create components
    card = Card(
        title="User Profile",
        children=[
            Text(content="Welcome back!"),
            Button(label="Edit Profile", variant="primary"),
        ],
    )

    # In a view
    @component_view()
    def profile_view(request):
        return card

    # Or use the response directly
    def api_view(request):
        table = DataTable(columns=[...], data=[...])
        return ComponentResponse(table)
"""

# Base
from django_matt.components.base import (
    Component,
    ComponentType,
    ComponentTree,
    ComponentRegistry,
    registry,
    ValidationRule,
    EventHandler,
    Slot,
)

# Forms
from django_matt.components.forms import (
    BaseField,
    TextField,
    EmailField,
    PasswordField,
    NumberField,
    Textarea,
    Select,
    SelectOption,
    MultiSelect,
    Checkbox,
    RadioGroup,
    Switch,
    DatePicker,
    FileUpload,
    Button,
    SubmitButton,
    Form,
    LoginForm,
    RegisterForm,
    OAuthButtons,
)

# Layout
from django_matt.components.layout import (
    Container,
    Card,
    Modal,
    Drawer,
    TabItem,
    Tabs,
    AccordionItem,
    Accordion,
    Alert,
    Toast,
    NavItem,
    Nav,
    Text,
    Heading,
    Image,
    Avatar,
    Badge,
    Spinner,
    Progress,
    Divider,
)

# Data
from django_matt.components.data import (
    TableColumn,
    TableAction,
    DataTable,
    List,
    DetailField,
    DetailView,
    Pagination,
    SearchInput,
    StatItem,
    Stats,
    EmptyState,
    Skeleton,
)

# Theming
from django_matt.components.theming import (
    Theme,
    SemanticColors,
    DarkColors,
    Typography,
    ThemeManager,
    theme_manager,
    set_theme,
    get_theme,
    use_preset,
    create_shadcn_theme,
    create_zinc_theme,
    create_blue_theme,
    create_green_theme,
    create_violet_theme,
)

# Renderers
from django_matt.components.renderers import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
    ReactRenderer,
    HTMLRenderer,
    JSONRenderer,
)

# Serving
from django_matt.components.serving import (
    ComponentResponse,
    JsonComponentResponse,
    HtmlComponentResponse,
    component_view,
    json_component_view,
    html_component_view,
    ComponentView,
    JsonComponentView,
    HtmlComponentView,
    Page,
    create_component,
    create_from_dict,
    create_from_json,
    ComponentMiddleware,
)


__all__ = [
    # Base
    "Component",
    "ComponentType",
    "ComponentTree",
    "ComponentRegistry",
    "registry",
    "ValidationRule",
    "EventHandler",
    "Slot",
    # Forms
    "BaseField",
    "TextField",
    "EmailField",
    "PasswordField",
    "NumberField",
    "Textarea",
    "Select",
    "SelectOption",
    "MultiSelect",
    "Checkbox",
    "RadioGroup",
    "Switch",
    "DatePicker",
    "FileUpload",
    "Button",
    "SubmitButton",
    "Form",
    "LoginForm",
    "RegisterForm",
    "OAuthButtons",
    # Layout
    "Container",
    "Card",
    "Modal",
    "Drawer",
    "TabItem",
    "Tabs",
    "AccordionItem",
    "Accordion",
    "Alert",
    "Toast",
    "NavItem",
    "Nav",
    "Text",
    "Heading",
    "Image",
    "Avatar",
    "Badge",
    "Spinner",
    "Progress",
    "Divider",
    # Data
    "TableColumn",
    "TableAction",
    "DataTable",
    "List",
    "DetailField",
    "DetailView",
    "Pagination",
    "SearchInput",
    "StatItem",
    "Stats",
    "EmptyState",
    "Skeleton",
    # Theming
    "Theme",
    "SemanticColors",
    "DarkColors",
    "Typography",
    "ThemeManager",
    "theme_manager",
    "set_theme",
    "get_theme",
    "use_preset",
    "create_shadcn_theme",
    "create_zinc_theme",
    "create_blue_theme",
    "create_green_theme",
    "create_violet_theme",
    # Renderers
    "BaseRenderer",
    "RenderContext",
    "RenderOutput",
    "ReactRenderer",
    "HTMLRenderer",
    "JSONRenderer",
    # Serving
    "ComponentResponse",
    "JsonComponentResponse",
    "HtmlComponentResponse",
    "component_view",
    "json_component_view",
    "html_component_view",
    "ComponentView",
    "JsonComponentView",
    "HtmlComponentView",
    "Page",
    "create_component",
    "create_from_dict",
    "create_from_json",
    "ComponentMiddleware",
]
