# file-length-max: 700
"""
Remix renderer for components.

Generates Remix route components with loader/action patterns,
TypeScript, and Tailwind CSS. Follows Remix v2 conventions
with file-based routing and nested layouts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import orjson

from django_matt.components.base import Component, ComponentType
from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)

# =============================================================================
# Remix Component Mapping
# =============================================================================

REMIX_COMPONENT_MAP: dict[ComponentType, str] = {
    ComponentType.BUTTON: "Button",
    ComponentType.CARD: "Card",
    ComponentType.MODAL: "Dialog",
    ComponentType.DRAWER: "Drawer",
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
    ComponentType.FILE_UPLOAD: "FileUpload",
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
    ComponentType.CONTAINER: "div",
    ComponentType.TEXT: "p",
    ComponentType.HEADING: "h1",
    ComponentType.IMAGE: "img",
    ComponentType.LINK: "Link",
    ComponentType.LIST: "div",
    ComponentType.DETAIL_VIEW: "div",
    ComponentType.ICON_BUTTON: "Button",
}

INPUT_TYPE_MAP: dict[ComponentType, str] = {
    ComponentType.TEXT_FIELD: "text",
    ComponentType.EMAIL_FIELD: "email",
    ComponentType.PASSWORD_FIELD: "password",
    ComponentType.NUMBER_FIELD: "number",
}

# Components that need Form integration
FORM_COMPONENTS: set[ComponentType] = {
    ComponentType.FORM,
    ComponentType.LOGIN_FORM,
    ComponentType.REGISTER_FORM,
    ComponentType.TEXT_FIELD,
    ComponentType.EMAIL_FIELD,
    ComponentType.PASSWORD_FIELD,
    ComponentType.NUMBER_FIELD,
    ComponentType.TEXTAREA,
    ComponentType.SELECT,
    ComponentType.CHECKBOX,
    ComponentType.FILE_UPLOAD,
}


def get_remix_component_name(component_type: ComponentType) -> str:
    """Get the Remix component name for a component type."""
    return REMIX_COMPONENT_MAP.get(component_type, "div")


# =============================================================================
# Remix Renderer
# =============================================================================


class RemixRenderer(BaseRenderer):
    """
    Renders components as Remix route modules (.tsx).

    Generates React components with Remix patterns:
    - loader() for data fetching
    - action() for form handling
    - meta() for SEO
    - useLoaderData/useActionData hooks

    Usage:
        from django_matt.components import Card, Text
        from django_matt.components.renderers.remix import RemixRenderer

        renderer = RemixRenderer()
        card = Card(
            title="Welcome",
            children=[Text(content="Hello, World!")],
        )
        output = renderer.render(card)
    """

    def __init__(
        self,
        use_tailwind: bool = True,
        component_library: Literal["shadcn", "radix", "none"] = "shadcn",
        include_metadata: bool = False,
        api_base_url: str = "http://localhost:8000/api",
    ) -> None:
        self.use_tailwind = use_tailwind
        self.component_library = component_library
        self.include_metadata = include_metadata
        self.api_base_url = api_base_url
        super().__init__()

    def _register_default_renderers(self) -> None:
        """No special per-component renderers needed."""

    def render_component(
        self,
        component: Component,
        context: RenderContext | None = None,
    ) -> RenderOutput:
        """Render a component to a Remix route module."""
        if context is None:
            context = RenderContext()

        imports = set[str]()
        imports.add('import type { MetaFunction } from "@remix-run/node";')

        body = self._render_node(component, context, imports)
        has_form = self._has_form_components(component)

        if has_form:
            imports.add('import { Form, useActionData } from "@remix-run/react";')
            imports.add('import type { ActionFunctionArgs } from "@remix-run/node";')

        import_block = "\n".join(sorted(imports))
        component_name = self._to_pascal_case(
            getattr(component, "title", None) or component.type.value
        )

        # Build the route module
        parts = [import_block, ""]

        # Meta function
        title = getattr(component, "title", component_name)
        parts.append(f"""export const meta: MetaFunction = () => {{
  return [
    {{ title: "{title}" }},
    {{ name: "description", content: "{title} page" }},
  ];
}};""")
        parts.append("")

        # Action function (if forms present)
        if has_form:
            parts.append("""export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  const data = Object.fromEntries(formData);

  const response = await fetch(`${process.env.API_BASE_URL}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    return { errors: await response.json() };
  }

  return { success: true };
}""")
            parts.append("")

        # Default export (component)
        parts.append(f"export default function {component_name}Route() {{")
        if has_form:
            parts.append("  const actionData = useActionData<typeof action>();")
            parts.append("")
        parts.append("  return (")
        parts.append(f"    {body}")
        parts.append("  );")
        parts.append("}")
        parts.append("")

        content = "\n".join(parts)

        return RenderOutput(
            content=content,
            content_type="text/typescript",
            metadata={
                "component_type": component.type.value,
                "has_form": has_form,
            }
            if self.include_metadata
            else {},
        )

    def _render_node(
        self,
        component: Component,
        context: RenderContext,
        imports: set[str],
    ) -> str:
        """Render a single component node to JSX."""
        comp_name = get_remix_component_name(component.type)
        is_html = comp_name in {"div", "p", "h1", "h2", "h3", "img", "a", "span"}

        attrs = self._build_attrs(component)
        children_jsx = self._render_children(component, context, imports)

        if is_html:
            return self._render_html_element(comp_name, attrs, children_jsx, component)

        # Link component uses Remix Link
        if component.type == ComponentType.LINK:
            imports.add('import { Link } from "@remix-run/react";')
            href = getattr(component, "href", "#")
            text = getattr(component, "text", "") or getattr(component, "content", "")
            attr_str = self._attrs_to_jsx(attrs)
            return f'<Link to="{href}" {attr_str}>{text}</Link>'

        # Form components use Remix Form
        if component.type in (
            ComponentType.FORM,
            ComponentType.LOGIN_FORM,
            ComponentType.REGISTER_FORM,
        ):
            imports.add('import { Form } from "@remix-run/react";')
            attr_str = self._attrs_to_jsx(attrs)
            return f'<Form method="post" {attr_str}>\n{children_jsx}\n</Form>'

        # UI library component
        if self.component_library == "shadcn":
            imports.add(
                f'import {{ {comp_name} }} from "@/components/ui/{self._to_kebab(comp_name)}";'
            )
        elif self.component_library == "radix":
            imports.add(
                f'import * as {comp_name} from "@radix-ui/react-{self._to_kebab(comp_name)}";'
            )

        attr_str = self._attrs_to_jsx(attrs)
        if children_jsx:
            return f"<{comp_name} {attr_str}>\n{children_jsx}\n</{comp_name}>"
        return f"<{comp_name} {attr_str} />"

    def _render_html_element(
        self,
        tag: str,
        attrs: dict[str, Any],
        children: str,
        component: Component,
    ) -> str:
        """Render a plain HTML element as JSX."""
        if component.type == ComponentType.HEADING:
            level = getattr(component, "level", 1)
            tag = f"h{min(max(level, 1), 6)}"

        attr_str = self._attrs_to_jsx(attrs)

        if tag == "img":
            src = getattr(component, "src", "")
            alt = getattr(component, "alt", "")
            return f'<img src="{src}" alt="{alt}" {attr_str} />'

        text = getattr(component, "content", None) or getattr(component, "text", "")
        if text and not children:
            return f"<{tag} {attr_str}>{text}</{tag}>"

        if children:
            return f"<{tag} {attr_str}>\n{children}\n</{tag}>"

        return f"<{tag} {attr_str} />"

    def _render_children(
        self,
        component: Component,
        context: RenderContext,
        imports: set[str],
    ) -> str:
        """Render child components."""
        children = getattr(component, "children", []) or []
        if not children:
            return ""

        parts = []
        for child in children:
            child_ctx = context.child_context(child.id)
            parts.append(self._render_node(child, child_ctx, imports))
        return "\n".join(parts)

    def _build_attrs(self, component: Component) -> dict[str, Any]:
        """Extract component attributes for JSX rendering."""
        attrs: dict[str, Any] = {}

        css_class = getattr(component, "css_class", "")
        if css_class:
            attrs["className"] = css_class

        for prop in ("disabled", "required", "placeholder", "name", "value"):
            val = getattr(component, prop, None)
            if val is not None:
                attrs[prop] = val

        variant = getattr(component, "variant", None)
        if variant:
            attrs["variant"] = variant
        size = getattr(component, "size", None)
        if size:
            attrs["size"] = size

        # Input type
        if component.type in INPUT_TYPE_MAP:
            attrs["type"] = INPUT_TYPE_MAP[component.type]

        return attrs

    def _attrs_to_jsx(self, attrs: dict[str, Any]) -> str:
        """Convert attributes to JSX string."""
        parts = []
        for key, value in attrs.items():
            if isinstance(value, bool):
                if value:
                    parts.append(f"{key}")
            elif isinstance(value, str):
                parts.append(f'{key}="{value}"')
            else:
                parts.append(f"{key}={{{orjson.dumps(value).decode()}}}")
        return " ".join(parts)

    def _has_form_components(self, component: Component) -> bool:
        """Check if component tree contains form elements."""
        if component.type in FORM_COMPONENTS:
            return True
        for child in getattr(component, "children", []) or []:
            if self._has_form_components(child):
                return True
        return False

    @staticmethod
    def _to_pascal_case(s: str) -> str:
        """Convert string to PascalCase."""
        return "".join(word.capitalize() for word in s.replace("-", " ").replace("_", " ").split())

    @staticmethod
    def _to_kebab(s: str) -> str:
        """Convert PascalCase to kebab-case."""
        result = []
        for i, char in enumerate(s):
            if char.isupper() and i > 0:
                result.append("-")
            result.append(char.lower())
        return "".join(result)


# =============================================================================
# Remix Route Generator
# =============================================================================


def generate_remix_route(
    components: list[Component],
    *,
    route_path: str = "/",
    title: str = "Page",
    api_endpoint: str | None = None,
    api_base_url: str = "http://localhost:8000/api",
) -> str:
    """
    Generate a Remix route module from components.

    Args:
        components: Components to render
        route_path: The route path (for loader data fetching)
        title: Page title for meta
        api_endpoint: API endpoint for loader data
        api_base_url: Base URL for Django API

    Returns:
        Complete Remix route module (.tsx content)
    """
    renderer = RemixRenderer(api_base_url=api_base_url)

    imports = set[str]()
    imports.add('import type { MetaFunction, LoaderFunctionArgs } from "@remix-run/node";')
    imports.add('import { useLoaderData } from "@remix-run/react";')
    imports.add('import { json } from "@remix-run/node";')

    body_parts = []
    has_form = False
    for comp in components:
        ctx = RenderContext()
        inner_imports = set[str]()
        body = renderer._render_node(comp, ctx, inner_imports)
        imports.update(inner_imports)
        body_parts.append(body)
        if renderer._has_form_components(comp):
            has_form = True

    import_block = "\n".join(sorted(imports))
    body = "\n\n".join(body_parts)

    # Loader
    endpoint = api_endpoint or route_path.rstrip("/")
    loader = f"""export async function loader({{ request }}: LoaderFunctionArgs) {{
  const response = await fetch("{api_base_url}{endpoint}", {{
    headers: {{
      Cookie: request.headers.get("Cookie") || "",
    }},
  }});

  if (!response.ok) {{
    throw new Response("API Error", {{ status: response.status }});
  }}

  return json(await response.json());
}}"""

    # Action (if forms)
    action = ""
    if has_form:
        action = f"""
export async function action({{ request }}: ActionFunctionArgs) {{
  const formData = await request.formData();
  const data = Object.fromEntries(formData);

  const response = await fetch("{api_base_url}{endpoint}", {{
    method: "POST",
    headers: {{
      "Content-Type": "application/json",
      Cookie: request.headers.get("Cookie") || "",
    }},
    body: JSON.stringify(data),
  }});

  if (!response.ok) {{
    return json({{ errors: await response.json() }}, {{ status: 422 }});
  }}

  return json({{ success: true }});
}}
"""

    component_name = RemixRenderer._to_pascal_case(title)

    return f"""{import_block}

export const meta: MetaFunction = () => {{
  return [
    {{ title: "{title}" }},
  ];
}};

{loader}
{action}
export default function {component_name}Route() {{
  const data = useLoaderData<typeof loader>();

  return (
    <div>
{body}
    </div>
  );
}}
"""


def generate_remix_project(
    components: list[Component],
    output_dir: str | Path,
    *,
    api_base_url: str = "http://localhost:8000/api",
    use_tailwind: bool = True,
) -> list[str]:
    """
    Generate a Remix project scaffold with components.

    Args:
        components: Components to generate
        output_dir: Directory to write files
        api_base_url: Django API base URL
        use_tailwind: Include Tailwind

    Returns:
        List of created file paths
    """
    base = Path(output_dir)
    created: list[str] = []

    renderer = RemixRenderer(api_base_url=api_base_url, use_tailwind=use_tailwind)

    # Components
    components_dir = base / "app" / "components" / "ui"
    components_dir.mkdir(parents=True, exist_ok=True)

    for comp in components:
        output = renderer.render(comp)
        comp_name = get_remix_component_name(comp.type)
        filepath = components_dir / f"{RemixRenderer._to_kebab(comp_name)}.tsx"
        filepath.write_text(output.content)
        created.append(str(filepath))

    # Root route
    routes_dir = base / "app" / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)

    index_route = generate_remix_route(
        components,
        route_path="/",
        title="Home",
        api_base_url=api_base_url,
    )
    index_path = routes_dir / "_index.tsx"
    index_path.write_text(index_route)
    created.append(str(index_path))

    # Package.json
    pkg = {
        "name": "django-matt-remix-frontend",
        "type": "module",
        "scripts": {
            "dev": "remix vite:dev",
            "build": "remix vite:build",
            "start": "remix-serve ./build/server/index.js",
        },
        "dependencies": {
            "@remix-run/node": "^2.15.0",
            "@remix-run/react": "^2.15.0",
            "@remix-run/serve": "^2.15.0",
            "react": "^19.0.0",
            "react-dom": "^19.0.0",
        },
        "devDependencies": {
            "@remix-run/dev": "^2.15.0",
            "typescript": "^5.7.0",
            "vite": "^6.0.0",
            "tailwindcss": "^4.0.0",
        },
    }
    pkg_path = base / "package.json"
    pkg_path.write_text(orjson.dumps(pkg, option=orjson.OPT_INDENT_2).decode())
    created.append(str(pkg_path))

    # vite.config.ts
    vite_config = base / "vite.config.ts"
    vite_config.write_text("""import { vitePlugin as remix } from "@remix-run/dev";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [remix(), tsconfigPaths()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
""")
    created.append(str(vite_config))

    # tsconfig.json
    tsconfig = base / "tsconfig.json"
    tsconfig.write_text("""{
  "include": ["env.d.ts", "**/*.ts", "**/*.tsx"],
  "compilerOptions": {
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "target": "ES2022",
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["app/*"]
    }
  }
}
""")
    created.append(str(tsconfig))

    return created


__all__ = [
    "REMIX_COMPONENT_MAP",
    "RemixRenderer",
    "generate_remix_project",
    "generate_remix_route",
    "get_remix_component_name",
]
