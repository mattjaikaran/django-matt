"""
React/JSX renderer for components.

Generates React component props as JSON that can be consumed by
a React frontend library (like @django-matt/react).
"""

import json
from typing import Any, Dict, List, Optional, Union

from django_matt.components.base import Component, ComponentType
from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)


class ReactRenderer(BaseRenderer):
    """
    Renders components as JSON props for React consumption.

    The output is a JSON structure that React components can use
    to render the UI. This follows the backend-served UI pattern
    where the server defines the component tree and the frontend
    renders it.

    Usage:
        from django_matt.components import Card, Text
        from django_matt.components.renderers import ReactRenderer

        renderer = ReactRenderer()
        card = Card(
            title="Welcome",
            children=[Text(content="Hello, World!")],
        )
        output = renderer.render(card)
        # output.content is JSON that React can render
    """

    def __init__(self, include_metadata: bool = True):
        self.include_metadata = include_metadata
        super().__init__()

    def _register_default_renderers(self) -> None:
        """No special per-component renderers needed for JSON output."""
        pass

    def render_component(
        self,
        component: Component,
        context: Optional[RenderContext] = None,
    ) -> RenderOutput:
        """Render a component to React-consumable JSON."""
        if context is None:
            context = RenderContext()

        props = self._component_to_props(component, context)

        content = json.dumps(props, default=str, ensure_ascii=False)

        return RenderOutput(
            content=content,
            content_type="application/json",
            metadata={
                "component_type": component.type.value,
                "component_id": component.id,
            } if self.include_metadata else {},
        )

    def _component_to_props(
        self,
        component: Component,
        context: RenderContext,
    ) -> Dict[str, Any]:
        """Convert a component to React props dictionary."""
        # Get all component data
        data = component.model_dump(exclude_none=True)

        # Convert ComponentType enum to string
        if "type" in data:
            data["type"] = data["type"].value if hasattr(data["type"], "value") else data["type"]

        # Process children recursively
        if "children" in data and data["children"]:
            data["children"] = [
                self._component_to_props(child, context.child_context(child.id))
                for child in component.children
            ]

        # Process nested components in other fields
        data = self._process_nested_components(data, context)

        return data

    def _process_nested_components(
        self,
        data: Dict[str, Any],
        context: RenderContext,
    ) -> Dict[str, Any]:
        """Process any nested components in the data."""
        result = {}

        for key, value in data.items():
            if isinstance(value, Component):
                result[key] = self._component_to_props(value, context)
            elif isinstance(value, list):
                result[key] = [
                    self._component_to_props(item, context) if isinstance(item, Component)
                    else self._process_value(item, context)
                    for item in value
                ]
            elif isinstance(value, dict):
                result[key] = self._process_nested_components(value, context)
            else:
                result[key] = self._process_value(value, context)

        return result

    def _process_value(self, value: Any, context: RenderContext) -> Any:
        """Process a single value, handling special types."""
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        elif hasattr(value, "value"):  # Enum
            return value.value
        return value

    def render_page(
        self,
        components: Union[Component, List[Component]],
        context: Optional[RenderContext] = None,
        title: str = "",
        description: str = "",
    ) -> RenderOutput:
        """
        Render a complete page structure.

        Returns JSON with page metadata and component tree.
        """
        if context is None:
            context = RenderContext()

        if isinstance(components, Component):
            components = [components]

        page_data = {
            "page": {
                "title": title,
                "description": description,
            },
            "components": [
                self._component_to_props(c, context) for c in components
            ],
            "theme": {
                "name": context.theme.name,
                "dark_mode": context.dark_mode,
            },
        }

        return RenderOutput(
            content=json.dumps(page_data, default=str, ensure_ascii=False),
            content_type="application/json",
            metadata={"type": "page"},
        )


class ReactHtmlRenderer(BaseRenderer):
    """
    Renders components as HTML with embedded React hydration data.

    This renderer generates server-rendered HTML that can be hydrated
    by React on the client side. Useful for SSR scenarios.

    Usage:
        renderer = ReactHtmlRenderer(
            root_id="app",
            bundle_url="/static/js/components.js",
        )
        output = renderer.render(component)
        # output.content is HTML with embedded props
    """

    def __init__(
        self,
        root_id: str = "root",
        bundle_url: str = "/static/js/components.js",
        css_url: Optional[str] = None,
    ):
        self.root_id = root_id
        self.bundle_url = bundle_url
        self.css_url = css_url
        self._json_renderer = ReactRenderer(include_metadata=False)
        super().__init__()

    def _register_default_renderers(self) -> None:
        pass

    def render_component(
        self,
        component: Component,
        context: Optional[RenderContext] = None,
    ) -> RenderOutput:
        """Render component as HTML with React bootstrap."""
        if context is None:
            context = RenderContext()

        # Get JSON props
        json_output = self._json_renderer.render_component(component, context)

        # Generate HTML
        html = self._generate_html(json_output.content, context)

        scripts = [self.bundle_url]
        styles = []
        if self.css_url:
            styles.append(self.css_url)

        return RenderOutput(
            content=html,
            content_type="text/html",
            scripts=scripts,
            styles=styles,
        )

    def _generate_html(self, props_json: str, context: RenderContext) -> str:
        """Generate HTML with embedded props and hydration script."""
        # Escape JSON for embedding in script tag
        escaped_props = props_json.replace("</", "<\\/").replace("<!--", "<\\!--")

        return f'''<div id="{self.root_id}"></div>
<script type="application/json" id="{self.root_id}-props">
{escaped_props}
</script>
<script>
  window.__DJANGO_MATT_PROPS__ = window.__DJANGO_MATT_PROPS__ || {{}};
  window.__DJANGO_MATT_PROPS__["{self.root_id}"] = JSON.parse(
    document.getElementById("{self.root_id}-props").textContent
  );
</script>'''

    def render_page(
        self,
        components: Union[Component, List[Component]],
        context: Optional[RenderContext] = None,
        title: str = "",
        include_doctype: bool = True,
    ) -> RenderOutput:
        """Render a complete HTML page with React components."""
        if context is None:
            context = RenderContext()

        if isinstance(components, Component):
            components = [components]

        # Get page JSON
        json_output = self._json_renderer.render_page(
            components, context, title=title
        )

        # Generate full HTML page
        css_link = f'<link rel="stylesheet" href="{self.css_url}">' if self.css_url else ""
        theme_css = context.theme.get_full_css() if hasattr(context.theme, 'get_full_css') else ""

        html = f'''{"<!DOCTYPE html>" if include_doctype else ""}
<html lang="{context.locale}"{' class="dark"' if context.dark_mode else ""}>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  {css_link}
  <style>
{theme_css}
  </style>
</head>
<body>
  <div id="{self.root_id}"></div>
  <script type="application/json" id="{self.root_id}-props">
{json_output.content}
  </script>
  <script src="{self.bundle_url}"></script>
  <script>
    window.DjangoMatt.hydrate("{self.root_id}");
  </script>
</body>
</html>'''

        return RenderOutput(
            content=html,
            content_type="text/html",
            scripts=[self.bundle_url],
            styles=[self.css_url] if self.css_url else [],
        )


# Component mapping for shadcn/ui
SHADCN_COMPONENT_MAP = {
    ComponentType.BUTTON: "Button",
    ComponentType.CARD: "Card",
    ComponentType.MODAL: "Dialog",
    ComponentType.DRAWER: "Sheet",
    ComponentType.TABS: "Tabs",
    ComponentType.ACCORDION: "Accordion",
    ComponentType.ALERT: "Alert",
    ComponentType.TEXT_FIELD: "Input",
    ComponentType.EMAIL_FIELD: "Input",
    ComponentType.PASSWORD_FIELD: "Input",
    ComponentType.NUMBER_FIELD: "Input",
    ComponentType.TEXTAREA: "Textarea",
    ComponentType.SELECT: "Select",
    ComponentType.MULTI_SELECT: "MultiSelect",
    ComponentType.CHECKBOX: "Checkbox",
    ComponentType.RADIO: "RadioGroup",
    ComponentType.SWITCH: "Switch",
    ComponentType.DATE_PICKER: "DatePicker",
    ComponentType.FILE_UPLOAD: "FileInput",
    ComponentType.DATA_TABLE: "DataTable",
    ComponentType.PAGINATION: "Pagination",
    ComponentType.AVATAR: "Avatar",
    ComponentType.BADGE: "Badge",
    ComponentType.SPINNER: "Spinner",
    ComponentType.PROGRESS: "Progress",
    ComponentType.FORM: "Form",
    ComponentType.LOGIN_FORM: "LoginForm",
    ComponentType.REGISTER_FORM: "RegisterForm",
    ComponentType.OAUTH_BUTTONS: "OAuthButtons",
}


def get_shadcn_component_name(component_type: ComponentType) -> str:
    """Get the shadcn/ui component name for a component type."""
    return SHADCN_COMPONENT_MAP.get(component_type, "div")
