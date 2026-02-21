"""
Serving utilities for backend-served components.

Provides views, middleware, and helpers for serving component-based
UIs from Django.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views import View

import orjson

from django_matt.components.base import Component, registry
from django_matt.components.renderers.base import BaseRenderer, RenderContext
from django_matt.components.renderers.html import HTMLRenderer
from django_matt.components.renderers.react import ReactRenderer
from django_matt.components.theming import Theme, get_theme

# =============================================================================
# Response Classes
# =============================================================================


class ComponentResponse(HttpResponse):
    """
    HTTP response containing rendered components.

    Usage:
        def my_view(request):
            card = Card(title="Hello", children=[Text(content="World")])
            return ComponentResponse(card)
    """

    def __init__(
        self,
        component: Component | list[Component],
        renderer: BaseRenderer | None = None,
        context: RenderContext | None = None,
        **kwargs,
    ):
        if renderer is None:
            renderer = ReactRenderer()

        if context is None:
            context = RenderContext()

        output = renderer.render(component, context)

        super().__init__(
            content=output.content,
            content_type=output.content_type,
            **kwargs,
        )

        self.render_output = output


class JsonComponentResponse(JsonResponse):
    """
    JSON response containing component data.

    Usage:
        def my_api(request):
            table = DataTable(columns=[...], data=[...])
            return JsonComponentResponse(table)
    """

    def __init__(
        self,
        component: Component | list[Component],
        context: RenderContext | None = None,
        **kwargs,
    ):
        if context is None:
            context = RenderContext()

        if isinstance(component, list):
            data = [c.model_dump(exclude_none=True) for c in component]
        else:
            data = component.model_dump(exclude_none=True)

        # Process enums
        data = self._process_enums(data)

        super().__init__(data, **kwargs)

    def _process_enums(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._process_enums(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._process_enums(item) for item in data]
        if hasattr(data, "value"):
            return data.value
        return data


class HtmlComponentResponse(HttpResponse):
    """
    HTML response with rendered components.

    Usage:
        def my_view(request):
            page = Container(children=[...])
            return HtmlComponentResponse(page, title="My Page")
    """

    def __init__(
        self,
        component: Component | list[Component],
        title: str = "",
        context: RenderContext | None = None,
        renderer: HTMLRenderer | None = None,
        **kwargs,
    ):
        if renderer is None:
            renderer = HTMLRenderer()

        if context is None:
            context = RenderContext()

        output = renderer.render(component, context)

        super().__init__(
            content=output.content,
            content_type="text/html",
            **kwargs,
        )


# =============================================================================
# Decorators
# =============================================================================


def component_view(
    renderer: BaseRenderer | None = None,
    theme: Theme | None = None,
):
    """
    Decorator that renders component return values.

    Usage:
        @component_view()
        def my_view(request):
            return Card(title="Hello")

        @component_view(renderer=HTMLRenderer())
        def html_view(request):
            return Container(children=[...])
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            result = func(request, *args, **kwargs)

            # If already an HttpResponse, return as-is
            if isinstance(result, HttpResponse):
                return result

            # If a component or list of components, render
            if isinstance(result, (Component, list)):
                context = RenderContext(
                    theme=theme or get_theme(),
                    request=request,
                    user=getattr(request, "user", None),
                )
                return ComponentResponse(
                    result,
                    renderer=renderer or ReactRenderer(),
                    context=context,
                )

            # Otherwise return as-is (might be a dict for JsonResponse, etc.)
            return result

        return wrapper

    return decorator


def json_component_view(func: Callable) -> Callable:
    """
    Decorator that returns components as JSON.

    Usage:
        @json_component_view
        def api_view(request):
            return DataTable(columns=[...], data=[...])
    """

    @wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        result = func(request, *args, **kwargs)

        if isinstance(result, HttpResponse):
            return result

        if isinstance(result, (Component, list)):
            context = RenderContext(
                request=request,
                user=getattr(request, "user", None),
            )
            return JsonComponentResponse(result, context=context)

        return JsonResponse(result)

    return wrapper


def html_component_view(
    title: str = "",
    renderer: HTMLRenderer | None = None,
):
    """
    Decorator that renders components as HTML.

    Usage:
        @html_component_view(title="Dashboard")
        def dashboard(request):
            return Container(children=[...])
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            result = func(request, *args, **kwargs)

            if isinstance(result, HttpResponse):
                return result

            if isinstance(result, (Component, list)):
                context = RenderContext(
                    request=request,
                    user=getattr(request, "user", None),
                )
                return HtmlComponentResponse(
                    result,
                    title=title,
                    context=context,
                    renderer=renderer,
                )

            return result

        return wrapper

    return decorator


# =============================================================================
# Class-Based Views
# =============================================================================


class ComponentView(View):
    """
    Base class-based view for component-based UIs.

    Usage:
        class DashboardView(ComponentView):
            def get_component(self, request):
                return Card(
                    title="Dashboard",
                    children=[...],
                )

        # In urls.py
        path('dashboard/', DashboardView.as_view(), name='dashboard'),
    """

    renderer_class: type[BaseRenderer] = ReactRenderer
    theme: Theme | None = None

    def get_renderer(self) -> BaseRenderer:
        """Get the renderer instance."""
        return self.renderer_class()

    def get_context(self, request: HttpRequest) -> RenderContext:
        """Get the render context."""
        return RenderContext(
            theme=self.theme or get_theme(),
            request=request,
            user=getattr(request, "user", None),
        )

    def get_component(self, request: HttpRequest) -> Component | list[Component]:
        """Override this to return the component(s) to render."""
        raise NotImplementedError("Subclasses must implement get_component()")

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle GET requests."""
        component = self.get_component(request)
        context = self.get_context(request)
        renderer = self.get_renderer()

        return ComponentResponse(component, renderer=renderer, context=context)


class JsonComponentView(ComponentView):
    """View that returns components as JSON."""

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        component = self.get_component(request)
        context = self.get_context(request)
        return JsonComponentResponse(component, context=context)


class HtmlComponentView(ComponentView):
    """View that returns components as HTML."""

    renderer_class: type[BaseRenderer] = HTMLRenderer
    title: str = ""

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        component = self.get_component(request)
        context = self.get_context(request)
        return HtmlComponentResponse(
            component,
            title=self.title,
            context=context,
            renderer=self.get_renderer(),
        )


# =============================================================================
# Page Builder
# =============================================================================


class Page:
    """
    Helper for building complete pages with components.

    Usage:
        page = Page(title="Dashboard")
        page.add(Heading(content="Welcome"))
        page.add(Stats(items=[...]))
        page.add(DataTable(columns=[...], data=[...]))

        return page.render(request)
    """

    def __init__(
        self,
        title: str = "",
        description: str = "",
        theme: Theme | None = None,
    ):
        self.title = title
        self.description = description
        self.theme = theme
        self.components: list[Component] = []
        self.head: list[str] = []
        self.scripts: list[str] = []
        self.styles: list[str] = []

    def add(self, component: Component) -> "Page":
        """Add a component to the page."""
        self.components.append(component)
        return self

    def add_head(self, html: str) -> "Page":
        """Add content to the page head."""
        self.head.append(html)
        return self

    def add_script(self, url: str) -> "Page":
        """Add a script to the page."""
        self.scripts.append(url)
        return self

    def add_style(self, url: str) -> "Page":
        """Add a stylesheet to the page."""
        self.styles.append(url)
        return self

    def render(
        self,
        request: HttpRequest | None = None,
        renderer: BaseRenderer | None = None,
        as_json: bool = False,
    ) -> HttpResponse:
        """Render the page."""
        context = RenderContext(
            theme=self.theme or get_theme(),
            request=request,
            user=getattr(request, "user", None) if request else None,
        )

        if as_json:
            return JsonComponentResponse(self.components, context=context)

        if renderer is None:
            renderer = ReactRenderer()

        return ComponentResponse(
            self.components,
            renderer=renderer,
            context=context,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert page to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "components": [c.model_dump(exclude_none=True) for c in self.components],
            "head": self.head,
            "scripts": self.scripts,
            "styles": self.styles,
        }


# =============================================================================
# Component Factory
# =============================================================================


def create_component(
    component_type: str,
    **props,
) -> Component:
    """
    Create a component by type name.

    Usage:
        card = create_component("card", title="Hello", description="World")
        button = create_component("button", label="Click me", variant="primary")
    """
    component_class = registry.get(component_type)
    if component_class is None:
        raise ValueError(f"Unknown component type: {component_type}")

    return component_class(**props)


def create_from_dict(data: dict[str, Any]) -> Component:
    """
    Create a component from a dictionary.

    Usage:
        data = {"type": "card", "title": "Hello", "children": [...]}
        card = create_from_dict(data)
    """
    component_type = data.pop("type", None)
    if component_type is None:
        raise ValueError("Missing 'type' in component data")

    # Handle children recursively
    children_data = data.pop("children", [])
    children = [create_from_dict(c) if isinstance(c, dict) else c for c in children_data]

    component = create_component(component_type, **data)
    component.children = children

    return component


def create_from_json(json_str: str) -> Component | list[Component]:
    """
    Create component(s) from JSON string.

    Usage:
        json_str = '{"type": "card", "title": "Hello"}'
        card = create_from_json(json_str)
    """
    data = orjson.loads(json_str)

    if isinstance(data, list):
        return [create_from_dict(item) for item in data]

    return create_from_dict(data)


# =============================================================================
# Middleware
# =============================================================================


class ComponentMiddleware:
    """
    Middleware that handles component responses.

    Automatically adds theme CSS and scripts to component responses.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # If this is a component response, we could add additional processing here
        if isinstance(response, ComponentResponse):
            # Add any global scripts/styles from the render output
            pass

        return response


__all__ = [
    # Responses
    "ComponentResponse",
    "JsonComponentResponse",
    "HtmlComponentResponse",
    # Decorators
    "component_view",
    "json_component_view",
    "html_component_view",
    # Views
    "ComponentView",
    "JsonComponentView",
    "HtmlComponentView",
    # Page Builder
    "Page",
    # Factories
    "create_component",
    "create_from_dict",
    "create_from_json",
    # Middleware
    "ComponentMiddleware",
]
