# file-length-max: 650
"""
Astro renderer for components.

Generates Astro components (.astro) with island architecture support,
TypeScript, and Tailwind CSS integration. Supports client directives
for partial hydration (client:load, client:visible, client:idle).
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
# Astro Component Mapping
# =============================================================================

ASTRO_COMPONENT_MAP: dict[ComponentType, str] = {
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
    ComponentType.LINK: "a",
    ComponentType.LIST: "div",
    ComponentType.DETAIL_VIEW: "div",
    ComponentType.ICON_BUTTON: "Button",
}

# Input types for text-based fields
INPUT_TYPE_MAP: dict[ComponentType, str] = {
    ComponentType.TEXT_FIELD: "text",
    ComponentType.EMAIL_FIELD: "email",
    ComponentType.PASSWORD_FIELD: "password",
    ComponentType.NUMBER_FIELD: "number",
}

# Interactive components that need hydration
INTERACTIVE_COMPONENTS: set[ComponentType] = {
    ComponentType.MODAL,
    ComponentType.DRAWER,
    ComponentType.TABS,
    ComponentType.ACCORDION,
    ComponentType.SELECT,
    ComponentType.MULTI_SELECT,
    ComponentType.DATE_PICKER,
    ComponentType.FILE_UPLOAD,
    ComponentType.DATA_TABLE,
    ComponentType.FORM,
    ComponentType.LOGIN_FORM,
    ComponentType.REGISTER_FORM,
    ComponentType.SWITCH,
    ComponentType.CHECKBOX,
    ComponentType.RADIO,
}


def get_astro_component_name(component_type: ComponentType) -> str:
    """Get the Astro component name for a component type."""
    return ASTRO_COMPONENT_MAP.get(component_type, "div")


# =============================================================================
# Astro Renderer
# =============================================================================

ClientDirective = Literal[
    "client:load",
    "client:idle",
    "client:visible",
    "client:media",
    "client:only",
]


class AstroRenderer(BaseRenderer):
    """
    Renders components as Astro components (.astro files).

    Astro's island architecture means interactive components get
    client directives for partial hydration, while static components
    render as pure HTML with zero JavaScript.

    Usage:
        from django_matt.components import Card, Text
        from django_matt.components.renderers.astro import AstroRenderer

        renderer = AstroRenderer()
        card = Card(
            title="Welcome",
            children=[Text(content="Hello, World!")],
        )
        output = renderer.render(card)
        # output.content is an .astro component string

        # With specific island framework
        renderer = AstroRenderer(island_framework="react")
    """

    def __init__(
        self,
        use_tailwind: bool = True,
        island_framework: Literal["react", "vue", "svelte", "solid", "preact"] = "react",
        default_directive: ClientDirective = "client:load",
        include_metadata: bool = False,
    ) -> None:
        self.use_tailwind = use_tailwind
        self.island_framework = island_framework
        self.default_directive = default_directive
        self.include_metadata = include_metadata
        super().__init__()

    def _register_default_renderers(self) -> None:
        """No special per-component renderers needed."""

    def render_component(
        self,
        component: Component,
        context: RenderContext | None = None,
    ) -> RenderOutput:
        """Render a component to an Astro component."""
        if context is None:
            context = RenderContext()

        imports = set[str]()
        body = self._render_node(component, context, imports)
        frontmatter = self._build_frontmatter(component, imports)

        content = f"---\n{frontmatter}---\n\n{body}\n"

        return RenderOutput(
            content=content,
            content_type="text/astro",
            metadata={
                "component_type": component.type.value,
                "island_framework": self.island_framework,
            }
            if self.include_metadata
            else {},
        )

    def _build_frontmatter(
        self,
        component: Component,
        imports: set[str],
    ) -> str:
        """Build the Astro frontmatter (TypeScript section)."""
        lines: list[str] = []

        # Props interface
        lines.append("interface Props {")
        lines.append("  class?: string;")

        props = self._extract_props(component)
        for prop_name, prop_type in props.items():
            lines.append(f"  {prop_name}?: {prop_type};")
        lines.append("}")
        lines.append("")

        # Destructure props
        prop_names = list(props.keys())
        if prop_names:
            lines.append(f"const {{ class: className, {', '.join(prop_names)} }} = Astro.props;")
        else:
            lines.append("const { class: className } = Astro.props;")
        lines.append("")

        # Component imports
        for imp in sorted(imports):
            lines.append(imp)
        if imports:
            lines.append("")

        return "\n".join(lines) + "\n"

    def _render_node(
        self,
        component: Component,
        context: RenderContext,
        imports: set[str],
    ) -> str:
        """Render a single component node to Astro markup."""
        comp_name = get_astro_component_name(component.type)
        is_interactive = component.type in INTERACTIVE_COMPONENTS
        is_html = comp_name in {"div", "p", "h1", "h2", "h3", "img", "a", "span"}

        # Collect attributes
        attrs = self._build_attrs(component)
        children_html = self._render_children(component, context, imports)

        if is_html:
            return self._render_html_element(comp_name, attrs, children_html, component)

        # Island component — needs import and client directive
        if is_interactive:
            ext = self._framework_extension()
            imports.add(f'import {comp_name} from "@/components/{comp_name}.{ext}";')
            directive = self.default_directive
            attr_str = self._attrs_to_string(attrs)
            if children_html:
                return f"<{comp_name} {directive} {attr_str}>\n{children_html}\n</{comp_name}>"
            return f"<{comp_name} {directive} {attr_str} />"

        # Static component (Astro-native, no JS)
        imports.add(f'import {comp_name} from "@/components/{comp_name}.astro";')
        attr_str = self._attrs_to_string(attrs)
        if children_html:
            return f"<{comp_name} {attr_str}>\n{children_html}\n</{comp_name}>"
        return f"<{comp_name} {attr_str} />"

    def _render_html_element(
        self,
        tag: str,
        attrs: dict[str, Any],
        children: str,
        component: Component,
    ) -> str:
        """Render a plain HTML element."""
        # Special handling for headings
        if component.type == ComponentType.HEADING:
            level = getattr(component, "level", 1)
            tag = f"h{min(max(level, 1), 6)}"

        attr_str = self._attrs_to_string(attrs)

        # Self-closing elements
        if tag == "img":
            src = getattr(component, "src", "")
            alt = getattr(component, "alt", "")
            return f'<img src="{src}" alt="{alt}" {attr_str} />'

        # Text content
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
        """Extract component attributes for rendering."""
        attrs: dict[str, Any] = {}

        css_class = getattr(component, "css_class", "")
        if css_class:
            attrs["class"] = css_class

        # Common props
        for prop in ("disabled", "required", "placeholder", "name", "value"):
            val = getattr(component, prop, None)
            if val is not None:
                attrs[prop] = val

        # Variant/size
        variant = getattr(component, "variant", None)
        if variant:
            attrs["variant"] = variant
        size = getattr(component, "size", None)
        if size:
            attrs["size"] = size

        return attrs

    def _attrs_to_string(self, attrs: dict[str, Any]) -> str:
        """Convert attributes dict to HTML attribute string."""
        parts = []
        for key, value in attrs.items():
            if isinstance(value, bool):
                if value:
                    parts.append(key)
            elif isinstance(value, str):
                parts.append(f'{key}="{value}"')
            else:
                parts.append(f"{key}={{{orjson.dumps(value).decode()}}}")
        return " ".join(parts)

    def _extract_props(self, component: Component) -> dict[str, str]:
        """Extract TypeScript prop types from component."""
        props: dict[str, str] = {}
        data = component.model_dump(exclude_none=True)
        skip = {"id", "type", "children", "css_class"}

        for key, value in data.items():
            if key in skip:
                continue
            if isinstance(value, bool):
                props[key] = "boolean"
            elif isinstance(value, int):
                props[key] = "number"
            elif isinstance(value, str):
                props[key] = "string"
            elif isinstance(value, list):
                props[key] = "any[]"
            elif isinstance(value, dict):
                props[key] = "Record<string, any>"

        return props

    def _framework_extension(self) -> str:
        """Get file extension for the island framework."""
        ext_map = {
            "react": "tsx",
            "vue": "vue",
            "svelte": "svelte",
            "solid": "tsx",
            "preact": "tsx",
        }
        return ext_map.get(self.island_framework, "tsx")


# =============================================================================
# Astro Page Generator
# =============================================================================


def generate_astro_page(
    components: list[Component],
    *,
    layout: str = "@/layouts/Layout.astro",
    title: str = "Page",
    description: str = "",
    island_framework: str = "react",
) -> str:
    """
    Generate a full Astro page from components.

    Args:
        components: Components to render in the page
        layout: Layout component path
        title: Page title
        description: Meta description
        island_framework: Framework for interactive islands

    Returns:
        Full .astro page content
    """
    renderer = AstroRenderer(island_framework=island_framework)

    imports = set[str]()
    imports.add(f'import Layout from "{layout}";')

    body_parts = []
    for comp in components:
        ctx = RenderContext()
        inner_imports = set[str]()
        body = renderer._render_node(comp, ctx, inner_imports)
        imports.update(inner_imports)
        body_parts.append(body)

    frontmatter_lines = sorted(imports)
    frontmatter = "\n".join(frontmatter_lines)

    body = "\n\n".join(body_parts)

    return f"""---
{frontmatter}
---

<Layout title="{title}">
{body}
</Layout>
"""


def generate_astro_project(
    components: list[Component],
    output_dir: str | Path,
    *,
    island_framework: str = "react",
    use_tailwind: bool = True,
) -> list[str]:
    """
    Generate a full Astro project scaffold with components.

    Args:
        components: Components to generate
        output_dir: Directory to write files
        island_framework: Framework for interactive islands
        use_tailwind: Include Tailwind CSS config

    Returns:
        List of created file paths
    """
    base = Path(output_dir)
    created: list[str] = []

    renderer = AstroRenderer(
        island_framework=island_framework,
        use_tailwind=use_tailwind,
    )

    # Generate component files
    components_dir = base / "src" / "components"
    components_dir.mkdir(parents=True, exist_ok=True)

    for comp in components:
        output = renderer.render(comp)
        comp_name = get_astro_component_name(comp.type)
        is_interactive = comp.type in INTERACTIVE_COMPONENTS

        if is_interactive:
            ext = renderer._framework_extension()
            filename = f"{comp_name}.{ext}"
        else:
            filename = f"{comp_name}.astro"

        filepath = components_dir / filename
        filepath.write_text(output.content)
        created.append(str(filepath))

    # Generate astro.config.mjs
    config_path = base / "astro.config.mjs"
    config_path.write_text(_astro_config(island_framework, use_tailwind))
    created.append(str(config_path))

    # Generate tsconfig.json
    tsconfig_path = base / "tsconfig.json"
    tsconfig_path.write_text(_tsconfig())
    created.append(str(tsconfig_path))

    # Generate package.json
    pkg_path = base / "package.json"
    pkg_path.write_text(_package_json(island_framework))
    created.append(str(pkg_path))

    return created


def _astro_config(framework: str, tailwind: bool) -> str:
    """Generate astro.config.mjs."""
    integrations = []
    imports = ['import { defineConfig } from "astro/config";']

    fw_map = {
        "react": ("@astrojs/react", "react()"),
        "vue": ("@astrojs/vue", "vue()"),
        "svelte": ("@astrojs/svelte", "svelte()"),
        "solid": ("@astrojs/solid-js", "solidJs()"),
        "preact": ("@astrojs/preact", "preact()"),
    }

    if framework in fw_map:
        pkg, call = fw_map[framework]
        func_name = call.split("(")[0]
        imports.append(f'import {func_name} from "{pkg}";')
        integrations.append(call)

    if tailwind:
        imports.append('import tailwind from "@astrojs/tailwind";')
        integrations.append("tailwind()")

    imports_str = "\n".join(imports)
    integrations_str = ", ".join(integrations)

    return f"""{imports_str}

export default defineConfig({{
  integrations: [{integrations_str}],
  output: "server",
  vite: {{
    server: {{
      proxy: {{
        "/api": "http://localhost:8000",
      }},
    }},
  }},
}});
"""


def _tsconfig() -> str:
    return """{
  "extends": "astro/tsconfigs/strict",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
"""


def _package_json(framework: str) -> str:
    fw_deps = {
        "react": {"react": "^19.0.0", "react-dom": "^19.0.0", "@astrojs/react": "^4.0.0"},
        "vue": {"vue": "^3.5.0", "@astrojs/vue": "^5.0.0"},
        "svelte": {"svelte": "^5.0.0", "@astrojs/svelte": "^6.0.0"},
        "solid": {"solid-js": "^1.9.0", "@astrojs/solid-js": "^4.0.0"},
        "preact": {"preact": "^10.0.0", "@astrojs/preact": "^4.0.0"},
    }

    deps = {
        "astro": "^5.0.0",
        "@astrojs/tailwind": "^6.0.0",
        **fw_deps.get(framework, {}),
    }

    pkg = {
        "name": "django-matt-astro-frontend",
        "type": "module",
        "scripts": {
            "dev": "astro dev",
            "build": "astro build",
            "preview": "astro preview",
        },
        "dependencies": deps,
        "devDependencies": {
            "typescript": "^5.7.0",
            "tailwindcss": "^4.0.0",
        },
    }

    return orjson.dumps(pkg, option=orjson.OPT_INDENT_2).decode()


__all__ = [
    "ASTRO_COMPONENT_MAP",
    "AstroRenderer",
    "INTERACTIVE_COMPONENTS",
    "generate_astro_page",
    "generate_astro_project",
    "get_astro_component_name",
]
