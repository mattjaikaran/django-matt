"""
Svelte renderer for components.

Generates Svelte 5 components with runes ($state, $derived, $effect),
TypeScript support, and modern Svelte features.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django_matt.components.base import Component, ComponentType
from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)

# =============================================================================
# Svelte Component Mapping
# =============================================================================

SVELTE_COMPONENT_MAP: dict[ComponentType, str] = {
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
    ComponentType.CONTAINER: "Container",
    ComponentType.TEXT: "Text",
    ComponentType.HEADING: "Heading",
    ComponentType.IMAGE: "Image",
    ComponentType.LINK: "Link",
    ComponentType.LIST: "List",
    ComponentType.DETAIL_VIEW: "DetailView",
    ComponentType.ICON_BUTTON: "IconButton",
}


def get_svelte_component_name(component_type: ComponentType) -> str:
    """Get the Svelte component name for a component type."""
    return SVELTE_COMPONENT_MAP.get(component_type, "div")


# =============================================================================
# Svelte Transitions and Actions
# =============================================================================

SVELTE_TRANSITIONS = {
    "fade": "fade",
    "blur": "blur",
    "fly": "fly",
    "slide": "slide",
    "scale": "scale",
    "draw": "draw",
    "crossfade": "crossfade",
}

SVELTE_EASING = {
    "linear": "linear",
    "backIn": "backIn",
    "backOut": "backOut",
    "backInOut": "backInOut",
    "bounceIn": "bounceIn",
    "bounceOut": "bounceOut",
    "bounceInOut": "bounceInOut",
    "circIn": "circIn",
    "circOut": "circOut",
    "circInOut": "circInOut",
    "cubicIn": "cubicIn",
    "cubicOut": "cubicOut",
    "cubicInOut": "cubicInOut",
    "elasticIn": "elasticIn",
    "elasticOut": "elasticOut",
    "elasticInOut": "elasticInOut",
    "expoIn": "expoIn",
    "expoOut": "expoOut",
    "expoInOut": "expoInOut",
    "quadIn": "quadIn",
    "quadOut": "quadOut",
    "quadInOut": "quadInOut",
    "quartIn": "quartIn",
    "quartOut": "quartOut",
    "quartInOut": "quartInOut",
    "quintIn": "quintIn",
    "quintOut": "quintOut",
    "quintInOut": "quintInOut",
    "sineIn": "sineIn",
    "sineOut": "sineOut",
    "sineInOut": "sineInOut",
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SvelteComponentOutput:
    """Output from Svelte component generation."""

    name: str
    script: str
    template: str
    style: str
    imports: list[str] = field(default_factory=list)
    props: list[str] = field(default_factory=list)
    stores: list[str] = field(default_factory=list)

    def to_svelte(self) -> str:
        """Combine into a complete .svelte file."""
        parts = []

        # Script section
        script_content = self._build_script()
        if script_content:
            parts.append(f'<script lang="ts">\n{script_content}\n</script>')

        # Template
        parts.append(self.template)

        # Style section
        if self.style:
            parts.append(f"<style>\n{self.style}\n</style>")

        return "\n\n".join(parts)

    def _build_script(self) -> str:
        """Build the script section content."""
        lines = []

        # Imports
        if self.imports:
            for imp in sorted(set(self.imports)):
                lines.append(imp)
            lines.append("")

        # Props using $props() rune (Svelte 5)
        if self.props:
            props_str = ", ".join(self.props)
            lines.append(f"let {{ {props_str} }} = $props();")
            lines.append("")

        # Additional script content
        if self.script:
            lines.append(self.script)

        return "\n".join(lines)


@dataclass
class SvelteStoreDefinition:
    """Definition for a Svelte store."""

    name: str
    type: str = "writable"  # writable, readable, derived
    initial_value: Any = None
    derive_from: list[str] = field(default_factory=list)
    typescript_type: str = "any"

    def to_code(self) -> str:
        """Generate store definition code."""
        if self.type == "writable":
            value = json.dumps(self.initial_value) if self.initial_value is not None else "null"
            return f"export const {self.name} = writable<{self.typescript_type}>({value});"
        if self.type == "readable":
            value = json.dumps(self.initial_value) if self.initial_value is not None else "null"
            return f"export const {self.name} = readable<{self.typescript_type}>({value});"
        if self.type == "derived":
            stores = ", ".join(self.derive_from)
            return f"export const {self.name} = derived([{stores}], ([$values]) => {{ /* derive logic */ }});"
        return ""


# =============================================================================
# Svelte Renderer
# =============================================================================


class SvelteRenderer(BaseRenderer):
    """
    Renders components as Svelte 5 components with TypeScript support.

    Features:
    - Svelte 5 runes ($state, $derived, $effect)
    - TypeScript support in script sections
    - Scoped CSS with Tailwind classes
    - Store integration
    - Transitions and animations
    - Two-way binding support
    - Named slots

    Usage:
        from django_matt.components import Card, Text
        from django_matt.components.renderers import SvelteRenderer

        renderer = SvelteRenderer()
        card = Card(
            title="Welcome",
            children=[Text(content="Hello, World!")],
        )
        output = renderer.render(card)
        # output.content is Svelte component code
    """

    def __init__(
        self,
        use_typescript: bool = True,
        use_runes: bool = True,
        use_tailwind: bool = True,
        component_library: str = "bits-ui",  # bits-ui, skeleton, melt-ui
    ):
        """
        Initialize Svelte renderer.

        Args:
            use_typescript: Generate TypeScript in script sections
            use_runes: Use Svelte 5 runes ($state, $derived, $effect)
            use_tailwind: Use Tailwind CSS classes
            component_library: Target UI library (bits-ui, skeleton, melt-ui)
        """
        self.use_typescript = use_typescript
        self.use_runes = use_runes
        self.use_tailwind = use_tailwind
        self.component_library = component_library
        super().__init__()

    def _register_default_renderers(self) -> None:
        """Register component-specific Svelte renderers."""
        self._component_renderers = {
            ComponentType.CONTAINER: self._render_container,
            ComponentType.CARD: self._render_card,
            ComponentType.MODAL: self._render_modal,
            ComponentType.DRAWER: self._render_drawer,
            ComponentType.TABS: self._render_tabs,
            ComponentType.ACCORDION: self._render_accordion,
            ComponentType.ALERT: self._render_alert,
            ComponentType.TEXT: self._render_text,
            ComponentType.HEADING: self._render_heading,
            ComponentType.BUTTON: self._render_button,
            ComponentType.LINK: self._render_link,
            ComponentType.IMAGE: self._render_image,
            ComponentType.AVATAR: self._render_avatar,
            ComponentType.BADGE: self._render_badge,
            ComponentType.SPINNER: self._render_spinner,
            ComponentType.PROGRESS: self._render_progress,
            ComponentType.FORM: self._render_form,
            ComponentType.TEXT_FIELD: self._render_text_field,
            ComponentType.EMAIL_FIELD: self._render_email_field,
            ComponentType.PASSWORD_FIELD: self._render_password_field,
            ComponentType.NUMBER_FIELD: self._render_number_field,
            ComponentType.TEXTAREA: self._render_textarea,
            ComponentType.SELECT: self._render_select,
            ComponentType.CHECKBOX: self._render_checkbox,
            ComponentType.RADIO: self._render_radio,
            ComponentType.SWITCH: self._render_switch,
            ComponentType.DATA_TABLE: self._render_data_table,
            ComponentType.PAGINATION: self._render_pagination,
        }

    def render_component(
        self,
        component: Component,
        context: RenderContext | None = None,
    ) -> RenderOutput:
        """Render a component to Svelte format."""
        if context is None:
            context = RenderContext()

        # Get component-specific renderer
        renderer = self._component_renderers.get(component.type)

        if renderer:
            svelte_output = renderer(component, context)
        else:
            svelte_output = self._render_default(component, context)

        return RenderOutput(
            content=svelte_output.to_svelte(),
            content_type="text/x-svelte",
            metadata={
                "component_name": svelte_output.name,
                "imports": svelte_output.imports,
                "props": svelte_output.props,
            },
        )

    def render_to_string(
        self,
        component: Component,
        context: RenderContext | None = None,
    ) -> str:
        """Render component directly to Svelte string."""
        output = self.render_component(component, context)
        return output.content

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _escape(self, text: str) -> str:
        """Escape text for Svelte template."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
            .replace("{", "&#123;")
            .replace("}", "&#125;")
        )

    def _get_classes(self, component: Component, *additional: str) -> str:
        """Build class string for component."""
        classes = list(additional)
        if component.class_name:
            classes.append(component.class_name)
        if not component.visible:
            classes.append("hidden")
        return " ".join(classes)

    def _get_attrs(self, component: Component, **extra: Any) -> str:
        """Build attribute string for Svelte template."""
        attrs = []

        if component.id:
            attrs.append(f'id="{self._escape(component.id)}"')

        if component.disabled:
            attrs.append("disabled")

        if component.aria_label:
            attrs.append(f'aria-label="{self._escape(component.aria_label)}"')

        if component.aria_describedby:
            attrs.append(f'aria-describedby="{self._escape(component.aria_describedby)}"')

        # Handle style as object for Svelte
        if component.style:
            style_str = "; ".join(f"{k}: {v}" for k, v in component.style.items())
            attrs.append(f'style="{self._escape(style_str)}"')

        # Extra attributes
        for key, value in extra.items():
            key = key.replace("_", "-")
            if value is True:
                attrs.append(key)
            elif value is not None and value is not False:
                # Handle Svelte-specific binding syntax
                if key.startswith("bind:") or key.startswith("on:") or key.startswith("use:"):
                    attrs.append(f"{key}={{{value}}}")
                else:
                    attrs.append(f'{key}="{self._escape(str(value))}"')

        return " ".join(attrs)

    def _render_children_template(
        self,
        children: list[Component],
        context: RenderContext,
    ) -> str:
        """Render children to Svelte template format."""
        if not children:
            return ""

        parts = []
        for child in children:
            output = self.render_component(child, context)
            # Extract just the template part
            content = output.content
            # Simple extraction - in real use, would parse properly
            if "<script" in content:
                # Extract template between script and style
                match = re.search(r"</script>\s*\n\n(.+?)(?:\n\n<style|$)", content, re.DOTALL)
                if match:
                    parts.append(match.group(1).strip())
            else:
                parts.append(content)

        return "\n".join(parts)

    def _create_output(
        self,
        name: str,
        template: str,
        script: str = "",
        style: str = "",
        imports: list[str] | None = None,
        props: list[str] | None = None,
    ) -> SvelteComponentOutput:
        """Create a SvelteComponentOutput with defaults."""
        return SvelteComponentOutput(
            name=name,
            script=script,
            template=template,
            style=style,
            imports=imports or [],
            props=props or [],
        )

    # =========================================================================
    # Default Renderer
    # =========================================================================

    def _render_default(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        """Default renderer for unknown components."""
        classes = self._get_classes(component)
        attrs = self._get_attrs(component)
        children = self._render_children_template(component.children, context)

        class_attr = f'class="{classes}"' if classes else ""
        template = f"<div {class_attr} {attrs}>\n  {children}\n</div>"

        return self._create_output(
            name="Component",
            template=template,
        )

    # =========================================================================
    # Layout Components
    # =========================================================================

    def _render_container(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        tag = getattr(component, "tag", "div")
        classes = self._get_classes(component)
        attrs = self._get_attrs(component)
        children = self._render_children_template(component.children, context)

        class_attr = f'class="{classes}"' if classes else ""
        template = f"<{tag} {class_attr} {attrs}>\n  {children}\n</{tag}>"

        return self._create_output(
            name="Container",
            template=template,
        )

    def _render_card(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        title = getattr(component, "title", "")
        description = getattr(component, "description", "")
        footer = getattr(component, "footer", None)

        classes = self._get_classes(
            component,
            "rounded-lg",
            "border",
            "bg-card",
            "text-card-foreground",
            "shadow-sm",
        )
        children = self._render_children_template(component.children, context)

        # Build template
        header_section = ""
        if title or description:
            title_html = (
                f'    <h3 class="text-2xl font-semibold leading-none tracking-tight">{self._escape(title)}</h3>\n'
                if title
                else ""
            )
            desc_html = (
                f'    <p class="text-sm text-muted-foreground">{self._escape(description)}</p>\n'
                if description
                else ""
            )
            header_section = (
                f'  <div class="flex flex-col space-y-1.5 p-6">\n{title_html}{desc_html}  </div>\n'
            )

        footer_section = ""
        if footer:
            footer_children = (
                self._render_children_template([footer], context)
                if isinstance(footer, Component)
                else self._render_children_template(footer, context)
            )
            footer_section = (
                f'  <div class="flex items-center p-6 pt-0">\n    {footer_children}\n  </div>\n'
            )

        template = f"""<div class="{classes}">
{header_section}  <div class="p-6 pt-0">
    {children}
  </div>
{footer_section}</div>"""

        # Script with props
        script = """// Card state
let isExpanded = $state(true);"""

        return self._create_output(
            name="Card",
            template=template,
            script=script,
            props=["title", "description", "class: className"],
        )

    def _render_modal(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        title = getattr(component, "title", "")
        description = getattr(component, "description", "")
        is_open = getattr(component, "open", False)
        children = self._render_children_template(component.children, context)

        imports = [
            "import { Dialog } from 'bits-ui';",
            "import { fade, scale } from 'svelte/transition';",
        ]

        script = f"""let open = $state({str(is_open).lower()});

function close() {{
  open = false;
}}"""

        template = f"""<Dialog.Root bind:open>
  <Dialog.Trigger asChild let:builder>
    <slot name="trigger" {{builder}} />
  </Dialog.Trigger>
  <Dialog.Portal>
    <Dialog.Overlay
      transition={{fade}}
      transitionConfig={{{{ duration: 150 }}}}
      class="fixed inset-0 z-50 bg-black/80"
    />
    <Dialog.Content
      transition={{scale}}
      transitionConfig={{{{ duration: 150, start: 0.95 }}}}
      class="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 border bg-background p-6 shadow-lg sm:rounded-lg"
    >
      {{#if "{title}"}}
        <Dialog.Title class="text-lg font-semibold">{self._escape(title)}</Dialog.Title>
      {{/if}}
      {{#if "{description}"}}
        <Dialog.Description class="text-sm text-muted-foreground">
          {self._escape(description)}
        </Dialog.Description>
      {{/if}}
      <div class="mt-4">
        {children}
      </div>
      <Dialog.Close
        class="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100"
      >
        <span class="sr-only">Close</span>
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>"""

        return self._create_output(
            name="Modal",
            template=template,
            script=script,
            imports=imports,
            props=["open", "title", "description", "onClose"],
        )

    def _render_drawer(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        title = getattr(component, "title", "")
        description = getattr(component, "description", "")
        side = getattr(component, "side", "right")
        is_open = getattr(component, "open", False)
        children = self._render_children_template(component.children, context)

        imports = [
            "import { fly } from 'svelte/transition';",
            "import { cubicOut } from 'svelte/easing';",
        ]

        side_classes = {
            "left": "left-0 h-full w-3/4 sm:max-w-sm",
            "right": "right-0 h-full w-3/4 sm:max-w-sm",
            "top": "top-0 w-full",
            "bottom": "bottom-0 w-full",
        }

        fly_config = {
            "left": "{{ x: -300, duration: 300, easing: cubicOut }}",
            "right": "{{ x: 300, duration: 300, easing: cubicOut }}",
            "top": "{{ y: -300, duration: 300, easing: cubicOut }}",
            "bottom": "{{ y: 300, duration: 300, easing: cubicOut }}",
        }

        script = f"""let open = $state({str(is_open).lower()});

function close() {{
  open = false;
}}"""

        template = f"""{{#if open}}
  <!-- Backdrop -->
  <button
    type="button"
    class="fixed inset-0 z-50 bg-black/80"
    on:click={{close}}
    transition:fade={{{{ duration: 200 }}}}
    aria-label="Close drawer"
  />

  <!-- Drawer -->
  <div
    class="fixed z-50 gap-4 bg-background p-6 shadow-lg {side_classes.get(side, side_classes["right"])}"
    transition:fly={fly_config.get(side, fly_config["right"])}
  >
    <div class="flex flex-col space-y-2">
      {{#if "{title}"}}
        <h2 class="text-lg font-semibold">{self._escape(title)}</h2>
      {{/if}}
      {{#if "{description}"}}
        <p class="text-sm text-muted-foreground">{self._escape(description)}</p>
      {{/if}}
    </div>
    <div class="mt-4">
      {children}
    </div>
    <button
      type="button"
      class="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100"
      on:click={{close}}
    >
      <span class="sr-only">Close</span>
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
{{/if}}"""

        return self._create_output(
            name="Drawer",
            template=template,
            script=script,
            imports=imports,
            props=["open", "side", "title", "description", "onClose"],
        )

    def _render_tabs(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        items = getattr(component, "items", [])
        default_value = getattr(component, "default_value", None)

        if not default_value and items:
            default_value = items[0].value if hasattr(items[0], "value") else ""

        imports = ["import { Tabs } from 'bits-ui';"]

        script = f'let value = $state("{default_value}");'

        # Build tabs list
        triggers = []
        contents = []

        for item in items:
            item_value = getattr(item, "value", "")
            item_label = getattr(item, "label", item_value)
            item_children = (
                self._render_children_template(item.children, context)
                if hasattr(item, "children") and item.children
                else ""
            )

            triggers.append(
                f'    <Tabs.Trigger value="{item_value}" '
                f'class="inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm">'
                f"{self._escape(item_label)}</Tabs.Trigger>"
            )

            contents.append(
                f'  <Tabs.Content value="{item_value}" class="mt-2">\n    {item_children}\n  </Tabs.Content>'
            )

        template = f"""<Tabs.Root bind:value class="w-full">
  <Tabs.List class="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
{chr(10).join(triggers)}
  </Tabs.List>
{chr(10).join(contents)}
</Tabs.Root>"""

        return self._create_output(
            name="Tabs",
            template=template,
            script=script,
            imports=imports,
            props=["value", "items"],
        )

    def _render_accordion(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        items = getattr(component, "items", [])
        multiple = getattr(component, "multiple", False)

        imports = [
            "import { Accordion } from 'bits-ui';",
            "import { slide } from 'svelte/transition';",
        ]

        accordion_type = "multiple" if multiple else "single"
        script = f"let value = $state<string{'[]' if multiple else ' | undefined'}>({[] if multiple else 'undefined'});"

        # Build accordion items
        accordion_items = []
        for idx, item in enumerate(items):
            item_value = getattr(item, "value", f"item-{idx}")
            item_title = getattr(item, "title", f"Item {idx + 1}")
            item_children = (
                self._render_children_template(item.children, context)
                if hasattr(item, "children") and item.children
                else ""
            )

            accordion_items.append(f"""  <Accordion.Item value="{item_value}" class="border-b">
    <Accordion.Header>
      <Accordion.Trigger
        class="flex flex-1 items-center justify-between py-4 font-medium transition-all hover:underline [&[data-state=open]>svg]:rotate-180"
      >
        {self._escape(item_title)}
        <svg
          class="h-4 w-4 shrink-0 transition-transform duration-200"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </Accordion.Trigger>
    </Accordion.Header>
    <Accordion.Content
      transition={{slide}}
      transitionConfig={{{{ duration: 200 }}}}
      class="overflow-hidden text-sm"
    >
      <div class="pb-4 pt-0">
        {item_children}
      </div>
    </Accordion.Content>
  </Accordion.Item>""")

        template = f"""<Accordion.Root type="{accordion_type}" bind:value class="w-full">
{chr(10).join(accordion_items)}
</Accordion.Root>"""

        return self._create_output(
            name="Accordion",
            template=template,
            script=script,
            imports=imports,
            props=["value", "items", "multiple"],
        )

    def _render_alert(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        title = getattr(component, "title", "")
        message = getattr(component, "message", "")
        variant = getattr(component, "variant", "default")

        variant_classes = {
            "default": "bg-background text-foreground",
            "destructive": "border-destructive/50 text-destructive dark:border-destructive",
            "success": "border-green-500/50 text-green-700 dark:text-green-400",
            "warning": "border-yellow-500/50 text-yellow-700 dark:text-yellow-400",
            "info": "border-blue-500/50 text-blue-700 dark:text-blue-400",
        }

        classes = self._get_classes(
            component,
            "relative",
            "w-full",
            "rounded-lg",
            "border",
            "p-4",
            variant_classes.get(variant, ""),
        )

        title_html = (
            f'  <h5 class="mb-1 font-medium leading-none tracking-tight">{self._escape(title)}</h5>\n'
            if title
            else ""
        )

        template = f"""<div class="{classes}" role="alert">
{title_html}  <div class="text-sm">{self._escape(message)}</div>
</div>"""

        return self._create_output(
            name="Alert",
            template=template,
            props=["variant", "title", "message"],
        )

    # =========================================================================
    # Display Components
    # =========================================================================

    def _render_text(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        content = getattr(component, "content", "")
        variant = getattr(component, "variant", "p")

        variant_classes = {
            "h1": "scroll-m-20 text-4xl font-extrabold tracking-tight lg:text-5xl",
            "h2": "scroll-m-20 text-3xl font-semibold tracking-tight",
            "h3": "scroll-m-20 text-2xl font-semibold tracking-tight",
            "h4": "scroll-m-20 text-xl font-semibold tracking-tight",
            "p": "leading-7",
            "lead": "text-xl text-muted-foreground",
            "muted": "text-sm text-muted-foreground",
            "small": "text-sm font-medium leading-none",
        }

        tag = variant if variant in ["h1", "h2", "h3", "h4", "h5", "h6", "p", "span"] else "p"
        classes = self._get_classes(component, variant_classes.get(variant, ""))

        template = f'<{tag} class="{classes}">{self._escape(content)}</{tag}>'

        return self._create_output(
            name="Text",
            template=template,
            props=["content", "variant"],
        )

    def _render_heading(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        content = getattr(component, "content", "")
        level = getattr(component, "level", 1)
        subtitle = getattr(component, "subtitle", "")

        level_classes = {
            1: "scroll-m-20 text-4xl font-extrabold tracking-tight lg:text-5xl",
            2: "scroll-m-20 text-3xl font-semibold tracking-tight",
            3: "scroll-m-20 text-2xl font-semibold tracking-tight",
            4: "scroll-m-20 text-xl font-semibold tracking-tight",
            5: "scroll-m-20 text-lg font-semibold tracking-tight",
            6: "scroll-m-20 text-base font-semibold tracking-tight",
        }

        classes = self._get_classes(component, level_classes.get(level, ""))

        subtitle_html = (
            f'\n<p class="text-muted-foreground">{self._escape(subtitle)}</p>' if subtitle else ""
        )

        template = f'<h{level} class="{classes}">{self._escape(content)}</h{level}>{subtitle_html}'

        return self._create_output(
            name="Heading",
            template=template,
            props=["content", "level", "subtitle"],
        )

    def _render_image(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        src = getattr(component, "src", "")
        alt = getattr(component, "alt", "")
        width = getattr(component, "width", None)
        height = getattr(component, "height", None)
        loading = getattr(component, "loading", "lazy")

        classes = self._get_classes(component)

        attrs_parts = [f'class="{classes}"' if classes else ""]
        if width:
            attrs_parts.append(f'width="{width}"')
        if height:
            attrs_parts.append(f'height="{height}"')

        attrs = " ".join(filter(None, attrs_parts))

        template = f'<img src="{self._escape(src)}" alt="{self._escape(alt)}" loading="{loading}" {attrs} />'

        return self._create_output(
            name="Image",
            template=template,
            props=["src", "alt", "width", "height", "loading"],
        )

    def _render_avatar(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        src = getattr(component, "src", "")
        alt = getattr(component, "alt", "")
        fallback = getattr(component, "fallback", "")
        size = getattr(component, "size", "md")

        size_classes = {
            "xs": "h-6 w-6",
            "sm": "h-8 w-8",
            "md": "h-10 w-10",
            "lg": "h-12 w-12",
            "xl": "h-14 w-14",
        }

        classes = self._get_classes(
            component,
            "relative",
            "flex",
            "shrink-0",
            "overflow-hidden",
            "rounded-full",
            size_classes.get(size, size_classes["md"]),
        )

        script = """let imageError = $state(false);

function handleError() {
  imageError = true;
}"""

        template = f"""<span class="{classes}">
  {{#if !imageError && "{src}"}}
    <img
      class="aspect-square h-full w-full"
      src="{self._escape(src)}"
      alt="{self._escape(alt)}"
      on:error={{handleError}}
    />
  {{:else}}
    <span class="flex h-full w-full items-center justify-center rounded-full bg-muted">
      {self._escape(fallback)}
    </span>
  {{/if}}
</span>"""

        return self._create_output(
            name="Avatar",
            template=template,
            script=script,
            props=["src", "alt", "fallback", "size"],
        )

    def _render_badge(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        content = getattr(component, "content", "")
        variant = getattr(component, "variant", "default")

        variant_classes = {
            "default": "bg-primary text-primary-foreground hover:bg-primary/80",
            "secondary": "bg-secondary text-secondary-foreground hover:bg-secondary/80",
            "destructive": "bg-destructive text-destructive-foreground hover:bg-destructive/80",
            "outline": "text-foreground border",
            "success": "bg-green-500 text-white",
            "warning": "bg-yellow-500 text-white",
        }

        classes = self._get_classes(
            component,
            "inline-flex",
            "items-center",
            "rounded-full",
            "border",
            "px-2.5",
            "py-0.5",
            "text-xs",
            "font-semibold",
            "transition-colors",
            variant_classes.get(variant, ""),
        )

        template = f'<span class="{classes}">{self._escape(content)}</span>'

        return self._create_output(
            name="Badge",
            template=template,
            props=["content", "variant"],
        )

    def _render_spinner(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        size = getattr(component, "size", "md")

        size_classes = {
            "xs": "h-3 w-3",
            "sm": "h-4 w-4",
            "md": "h-6 w-6",
            "lg": "h-8 w-8",
            "xl": "h-10 w-10",
        }

        classes = self._get_classes(
            component, "animate-spin", size_classes.get(size, size_classes["md"])
        )

        template = f"""<svg class="{classes}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
</svg>"""

        return self._create_output(
            name="Spinner",
            template=template,
            props=["size"],
        )

    def _render_progress(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        value = getattr(component, "value", 0)
        max_value = getattr(component, "max_value", 100)

        classes = self._get_classes(
            component,
            "relative",
            "h-4",
            "w-full",
            "overflow-hidden",
            "rounded-full",
            "bg-secondary",
        )

        script = f"""let value = $state({value});
let max = $state({max_value});

let percent = $derived((value / max) * 100);"""

        template = f"""<div class="{classes}">
  <div
    class="h-full w-full flex-1 bg-primary transition-all"
    style="transform: translateX(-{{100 - percent}}%)"
  />
</div>"""

        return self._create_output(
            name="Progress",
            template=template,
            script=script,
            props=["value", "max"],
        )

    # =========================================================================
    # Button & Link
    # =========================================================================

    def _render_button(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        label = getattr(component, "label", "")
        button_type = getattr(component, "button_type", "button")
        variant = getattr(component, "variant", "primary")
        size = getattr(component, "size", "md")

        variant_classes = {
            "primary": "bg-primary text-primary-foreground hover:bg-primary/90",
            "secondary": "bg-secondary text-secondary-foreground hover:bg-secondary/80",
            "destructive": "bg-destructive text-destructive-foreground hover:bg-destructive/90",
            "outline": "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
            "ghost": "hover:bg-accent hover:text-accent-foreground",
            "link": "text-primary underline-offset-4 hover:underline",
        }

        size_classes = {
            "sm": "h-9 rounded-md px-3",
            "md": "h-10 px-4 py-2",
            "lg": "h-11 rounded-md px-8",
            "icon": "h-10 w-10",
        }

        classes = self._get_classes(
            component,
            "inline-flex",
            "items-center",
            "justify-center",
            "whitespace-nowrap",
            "rounded-md",
            "text-sm",
            "font-medium",
            "ring-offset-background",
            "transition-colors",
            "focus-visible:outline-none",
            "focus-visible:ring-2",
            "focus-visible:ring-ring",
            "focus-visible:ring-offset-2",
            "disabled:pointer-events-none",
            "disabled:opacity-50",
            variant_classes.get(variant, ""),
            size_classes.get(size, ""),
        )

        disabled = "disabled" if component.disabled else ""

        script = """let loading = $state(false);

async function handleClick(event: MouseEvent) {
  if (onclick) {
    loading = true;
    try {
      await onclick(event);
    } finally {
      loading = false;
    }
  }
}"""

        template = f"""<button
  type="{button_type}"
  class="{classes}"
  {disabled}
  on:click={{handleClick}}
>
  {{#if loading}}
    <svg class="mr-2 h-4 w-4 animate-spin" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  {{/if}}
  {self._escape(label)}
</button>"""

        return self._create_output(
            name="Button",
            template=template,
            script=script,
            props=["label", "variant", "size", "disabled", "loading", "onclick"],
        )

    def _render_link(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        label = getattr(component, "label", "")
        href = getattr(component, "href", "#")
        target = getattr(component, "target", None)

        classes = self._get_classes(component)
        target_attr = f'target="{target}"' if target else ""

        template = f'<a href="{self._escape(href)}" class="{classes}" {target_attr}>{self._escape(label)}</a>'

        return self._create_output(
            name="Link",
            template=template,
            props=["href", "label", "target"],
        )

    # =========================================================================
    # Form Components
    # =========================================================================

    def _render_form(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        action = getattr(component, "action", "")
        method = getattr(component, "method", "POST")
        fields = getattr(component, "fields", [])
        submit = getattr(component, "submit", None)

        classes = self._get_classes(component)

        # Render fields
        fields_html = ""
        for field in fields:
            output = self.render_component(field, context)
            fields_html += f'    <div class="mb-4">\n      {output.content}\n    </div>\n'

        # Render submit button
        submit_html = ""
        if submit:
            output = self.render_component(submit, context)
            submit_html = f"    {output.content}\n"

        imports = ["import { enhance } from '$app/forms';"]

        script = """let submitting = $state(false);
let errors = $state<Record<string, string>>({});

function handleSubmit() {
  return async ({ result, update }) => {
    submitting = true;
    try {
      if (result.type === 'failure') {
        errors = result.data?.errors ?? {};
      } else {
        await update();
      }
    } finally {
      submitting = false;
    }
  };
}"""

        template = f"""<form
  action="{self._escape(action)}"
  method="{method}"
  class="{classes}"
  use:enhance={{handleSubmit}}
>
{fields_html}{submit_html}</form>"""

        return self._create_output(
            name="Form",
            template=template,
            script=script,
            imports=imports,
            props=["action", "method", "onSubmit"],
        )

    def _render_field_wrapper(
        self,
        component: Component,
        input_html: str,
        name: str,
    ) -> str:
        """Wrap a form field with label and error."""
        label = getattr(component, "label", "")
        help_text = getattr(component, "help_text", "")
        error = getattr(component, "error", "")
        required = getattr(component, "required", False)

        parts = []

        if label:
            req = '<span class="text-destructive">*</span>' if required else ""
            parts.append(
                f'<label for="{self._escape(name)}" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">'
                f"{self._escape(label)}{req}</label>"
            )

        parts.append(input_html)

        if help_text:
            parts.append(
                f'{{#if !errors["{name}"]}}\n'
                f'  <p class="text-sm text-muted-foreground">{self._escape(help_text)}</p>\n'
                f"{{/if}}"
            )

        parts.append(
            f'{{#if errors["{name}"]}}\n'
            f'  <p class="text-sm text-destructive">{{errors["{name}"]}}</p>\n'
            f"{{/if}}"
        )

        return "\n".join(parts)

    def _render_text_field(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        default_value = getattr(component, "default_value", "")
        required = getattr(component, "required", False)
        readonly = getattr(component, "readonly", False)

        classes = " ".join(
            [
                "flex",
                "h-10",
                "w-full",
                "rounded-md",
                "border",
                "border-input",
                "bg-background",
                "px-3",
                "py-2",
                "text-sm",
                "ring-offset-background",
                "placeholder:text-muted-foreground",
                "focus-visible:outline-none",
                "focus-visible:ring-2",
                "focus-visible:ring-ring",
                "focus-visible:ring-offset-2",
                "disabled:cursor-not-allowed",
                "disabled:opacity-50",
            ]
        )

        required_attr = "required" if required else ""
        readonly_attr = "readonly" if readonly else ""
        disabled_attr = "disabled" if component.disabled else ""

        script = f'let value = $state("{default_value}");'

        input_html = f"""<input
  type="text"
  id="{self._escape(name)}"
  name="{self._escape(name)}"
  class="{classes}"
  placeholder="{self._escape(placeholder)}"
  bind:value
  {required_attr}
  {readonly_attr}
  {disabled_attr}
/>"""

        template = self._render_field_wrapper(component, input_html, name)

        return self._create_output(
            name="TextField",
            template=template,
            script=script,
            props=["name", "value", "placeholder", "required", "readonly", "disabled"],
        )

    def _render_email_field(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        default_value = getattr(component, "default_value", "")

        classes = " ".join(
            [
                "flex",
                "h-10",
                "w-full",
                "rounded-md",
                "border",
                "border-input",
                "bg-background",
                "px-3",
                "py-2",
                "text-sm",
            ]
        )

        script = f'let value = $state("{default_value}");'

        input_html = f"""<input
  type="email"
  id="{self._escape(name)}"
  name="{self._escape(name)}"
  class="{classes}"
  placeholder="{self._escape(placeholder)}"
  bind:value
/>"""

        template = self._render_field_wrapper(component, input_html, name)

        return self._create_output(
            name="EmailField",
            template=template,
            script=script,
            props=["name", "value", "placeholder"],
        )

    def _render_password_field(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")

        classes = " ".join(
            [
                "flex",
                "h-10",
                "w-full",
                "rounded-md",
                "border",
                "border-input",
                "bg-background",
                "px-3",
                "py-2",
                "text-sm",
            ]
        )

        script = """let value = $state("");
let showPassword = $state(false);"""

        input_html = f"""<div class="relative">
  <input
    type={{showPassword ? "text" : "password"}}
    id="{self._escape(name)}"
    name="{self._escape(name)}"
    class="{classes} pr-10"
    placeholder="{self._escape(placeholder)}"
    bind:value
  />
  <button
    type="button"
    class="absolute right-3 top-1/2 -translate-y-1/2"
    on:click={{() => showPassword = !showPassword}}
  >
    {{#if showPassword}}
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
      </svg>
    {{:else}}
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
    {{/if}}
  </button>
</div>"""

        template = self._render_field_wrapper(component, input_html, name)

        return self._create_output(
            name="PasswordField",
            template=template,
            script=script,
            props=["name", "value", "placeholder"],
        )

    def _render_number_field(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        min_value = getattr(component, "min_value", None)
        max_value = getattr(component, "max_value", None)
        step = getattr(component, "step", None)
        default_value = getattr(component, "default_value", "")

        classes = " ".join(
            [
                "flex",
                "h-10",
                "w-full",
                "rounded-md",
                "border",
                "border-input",
                "bg-background",
                "px-3",
                "py-2",
                "text-sm",
            ]
        )

        min_attr = f'min="{min_value}"' if min_value is not None else ""
        max_attr = f'max="{max_value}"' if max_value is not None else ""
        step_attr = f'step="{step}"' if step is not None else ""

        script = f"let value = $state({default_value if default_value else 0});"

        input_html = f"""<input
  type="number"
  id="{self._escape(name)}"
  name="{self._escape(name)}"
  class="{classes}"
  bind:value
  {min_attr}
  {max_attr}
  {step_attr}
/>"""

        template = self._render_field_wrapper(component, input_html, name)

        return self._create_output(
            name="NumberField",
            template=template,
            script=script,
            props=["name", "value", "min", "max", "step"],
        )

    def _render_textarea(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        rows = getattr(component, "rows", 3)
        default_value = getattr(component, "default_value", "")

        classes = " ".join(
            [
                "flex",
                "min-h-[80px]",
                "w-full",
                "rounded-md",
                "border",
                "border-input",
                "bg-background",
                "px-3",
                "py-2",
                "text-sm",
                "ring-offset-background",
                "placeholder:text-muted-foreground",
                "focus-visible:outline-none",
                "focus-visible:ring-2",
                "focus-visible:ring-ring",
                "focus-visible:ring-offset-2",
                "disabled:cursor-not-allowed",
                "disabled:opacity-50",
            ]
        )

        script = f'let value = $state("{default_value}");'

        input_html = f"""<textarea
  id="{self._escape(name)}"
  name="{self._escape(name)}"
  class="{classes}"
  placeholder="{self._escape(placeholder)}"
  rows="{rows}"
  bind:value
></textarea>"""

        template = self._render_field_wrapper(component, input_html, name)

        return self._create_output(
            name="Textarea",
            template=template,
            script=script,
            props=["name", "value", "placeholder", "rows"],
        )

    def _render_select(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        options = getattr(component, "options", [])
        empty_label = getattr(component, "empty_label", "Select...")

        imports = ["import { Select } from 'bits-ui';"]

        script = "let selected = $state<{ value: string; label: string } | undefined>(undefined);"

        options_json = []
        for opt in options:
            options_json.append(
                f'{{ value: "{getattr(opt, "value", "")}", label: "{getattr(opt, "label", "")}", disabled: {str(getattr(opt, "disabled", False)).lower()} }}'
            )

        template = f"""<Select.Root bind:selected>
  <Select.Trigger
    class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
  >
    <Select.Value placeholder="{self._escape(empty_label)}" />
    <svg class="h-4 w-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </Select.Trigger>
  <Select.Content
    class="relative z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md"
  >
    {{#each [{", ".join(options_json)}] as option}}
      <Select.Item
        value={{option.value}}
        label={{option.label}}
        disabled={{option.disabled}}
        class="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
      >
        {{option.label}}
      </Select.Item>
    {{/each}}
  </Select.Content>
  <input type="hidden" name="{self._escape(name)}" value={{selected?.value ?? ""}} />
</Select.Root>"""

        wrapped = self._render_field_wrapper(component, template, name)

        return self._create_output(
            name="Select",
            template=wrapped,
            script=script,
            imports=imports,
            props=["name", "value", "options", "placeholder"],
        )

    def _render_checkbox(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        label = getattr(component, "label", "")
        checked = getattr(component, "checked", False)

        imports = ["import { Checkbox } from 'bits-ui';"]

        script = f"let checked = $state({str(checked).lower()});"

        template = f"""<div class="flex items-center space-x-2">
  <Checkbox.Root
    id="{self._escape(name)}"
    bind:checked
    class="peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
  >
    <Checkbox.Indicator class="flex items-center justify-center text-current">
      <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </Checkbox.Indicator>
  </Checkbox.Root>
  <label
    for="{self._escape(name)}"
    class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
  >
    {self._escape(label)}
  </label>
  <input type="hidden" name="{self._escape(name)}" value={{checked ? "true" : "false"}} />
</div>"""

        return self._create_output(
            name="Checkbox",
            template=template,
            script=script,
            imports=imports,
            props=["name", "checked", "label", "disabled"],
        )

    def _render_radio(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        options = getattr(component, "options", [])
        direction = getattr(component, "direction", "vertical")

        imports = ["import { RadioGroup } from 'bits-ui';"]

        flex_class = "flex-col space-y-2" if direction == "vertical" else "flex-row space-x-4"

        script = 'let value = $state("");'

        items_html = []
        for opt in options:
            opt_value = getattr(opt, "value", "")
            opt_label = getattr(opt, "label", "")
            items_html.append(f"""    <div class="flex items-center space-x-2">
      <RadioGroup.Item
        id="{self._escape(name)}_{self._escape(opt_value)}"
        value="{self._escape(opt_value)}"
        class="aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RadioGroup.ItemIndicator class="flex items-center justify-center">
          <div class="h-2.5 w-2.5 rounded-full bg-current" />
        </RadioGroup.ItemIndicator>
      </RadioGroup.Item>
      <label
        for="{self._escape(name)}_{self._escape(opt_value)}"
        class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
      >
        {self._escape(opt_label)}
      </label>
    </div>""")

        template = f"""<RadioGroup.Root bind:value class="flex {flex_class}">
{chr(10).join(items_html)}
  <input type="hidden" name="{self._escape(name)}" {{value}} />
</RadioGroup.Root>"""

        wrapped = self._render_field_wrapper(component, template, name)

        return self._create_output(
            name="RadioGroup",
            template=wrapped,
            script=script,
            imports=imports,
            props=["name", "value", "options", "direction"],
        )

    def _render_switch(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        name = getattr(component, "name", "")
        label = getattr(component, "label", "")
        checked = getattr(component, "checked", False)

        imports = ["import { Switch } from 'bits-ui';"]

        script = f"let checked = $state({str(checked).lower()});"

        template = f"""<div class="flex items-center space-x-2">
  <Switch.Root
    id="{self._escape(name)}"
    bind:checked
    class="peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input"
  >
    <Switch.Thumb
      class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0"
    />
  </Switch.Root>
  <label
    for="{self._escape(name)}"
    class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
  >
    {self._escape(label)}
  </label>
  <input type="hidden" name="{self._escape(name)}" value={{checked ? "true" : "false"}} />
</div>"""

        return self._create_output(
            name="Switch",
            template=template,
            script=script,
            imports=imports,
            props=["name", "checked", "label", "disabled"],
        )

    # =========================================================================
    # Data Components
    # =========================================================================

    def _render_data_table(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        columns = getattr(component, "columns", [])
        data = getattr(component, "data", [])
        empty_message = getattr(component, "empty_message", "No data available")

        script = """let sortColumn = $state<string | null>(null);
let sortDirection = $state<'asc' | 'desc'>('asc');

function handleSort(column: string) {
  if (sortColumn === column) {
    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
  } else {
    sortColumn = column;
    sortDirection = 'asc';
  }
}

let sortedData = $derived(
  sortColumn
    ? [...data].sort((a, b) => {
        const aVal = a[sortColumn] ?? '';
        const bVal = b[sortColumn] ?? '';
        const cmp = String(aVal).localeCompare(String(bVal));
        return sortDirection === 'asc' ? cmp : -cmp;
      })
    : data
);"""

        # Build header
        header_cells = []
        for col in columns:
            if not getattr(col, "hidden", False):
                col_key = getattr(col, "key", "")
                col_label = getattr(col, "label", "")
                col_sortable = getattr(col, "sortable", False)
                align = getattr(col, "align", "left")
                align_class = f"text-{align}" if align != "left" else ""

                if col_sortable:
                    header_cells.append(f"""      <th
        class="h-12 px-4 text-left align-middle font-medium text-muted-foreground {align_class} cursor-pointer hover:bg-muted/50"
        on:click={{() => handleSort('{col_key}')}}
      >
        <div class="flex items-center gap-2">
          {self._escape(col_label)}
          {{#if sortColumn === '{col_key}'}}
            <svg class="h-4 w-4 {{sortDirection === 'desc' ? 'rotate-180' : ''}}" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
            </svg>
          {{/if}}
        </div>
      </th>""")
                else:
                    header_cells.append(
                        f'      <th class="h-12 px-4 text-left align-middle font-medium text-muted-foreground {align_class}">{self._escape(col_label)}</th>'
                    )

        # Build body template
        body_cells = []
        for col in columns:
            if not getattr(col, "hidden", False):
                col_key = getattr(col, "key", "")
                body_cells.append(
                    f'        <td class="p-4 align-middle">{{row.{col_key} ?? ""}}</td>'
                )

        col_count = len([c for c in columns if not getattr(c, "hidden", False)])

        template = f"""<div class="relative w-full overflow-auto">
  <table class="w-full caption-bottom text-sm">
    <thead>
      <tr class="border-b transition-colors hover:bg-muted/50">
{chr(10).join(header_cells)}
      </tr>
    </thead>
    <tbody>
      {{#if sortedData.length > 0}}
        {{#each sortedData as row, i (i)}}
          <tr class="border-b transition-colors hover:bg-muted/50">
{chr(10).join(body_cells)}
          </tr>
        {{/each}}
      {{:else}}
        <tr>
          <td colspan="{col_count}" class="h-24 text-center">
            {self._escape(empty_message)}
          </td>
        </tr>
      {{/if}}
    </tbody>
  </table>
</div>"""

        return self._create_output(
            name="DataTable",
            template=template,
            script=script,
            props=["columns", "data", "emptyMessage"],
        )

    def _render_pagination(
        self,
        component: Component,
        context: RenderContext,
    ) -> SvelteComponentOutput:
        current_page = getattr(component, "current_page", 1)
        total_pages = getattr(component, "total_pages", 1)

        script = f"""let currentPage = $state({current_page});
let totalPages = $state({total_pages});

function goToPage(page: number) {{
  if (page >= 1 && page <= totalPages) {{
    currentPage = page;
    onPageChange?.(page);
  }}
}}

let visiblePages = $derived(() => {{
  const pages: number[] = [];
  const delta = 2;
  const left = Math.max(1, currentPage - delta);
  const right = Math.min(totalPages, currentPage + delta);

  for (let i = left; i <= right; i++) {{
    pages.push(i);
  }}

  return pages;
}});"""

        template = """<nav class="flex items-center justify-center space-x-2">
  <button
    class="inline-flex items-center justify-center h-10 px-4 py-2 rounded-md border disabled:opacity-50 disabled:cursor-not-allowed"
    disabled={currentPage <= 1}
    on:click={() => goToPage(currentPage - 1)}
  >
    Previous
  </button>

  {#each visiblePages() as page}
    {#if page === currentPage}
      <span class="inline-flex items-center justify-center h-10 w-10 rounded-md bg-primary text-primary-foreground">
        {page}
      </span>
    {:else}
      <button
        class="inline-flex items-center justify-center h-10 w-10 rounded-md border hover:bg-accent"
        on:click={() => goToPage(page)}
      >
        {page}
      </button>
    {/if}
  {/each}

  <button
    class="inline-flex items-center justify-center h-10 px-4 py-2 rounded-md border disabled:opacity-50 disabled:cursor-not-allowed"
    disabled={currentPage >= totalPages}
    on:click={() => goToPage(currentPage + 1)}
  >
    Next
  </button>
</nav>"""

        return self._create_output(
            name="Pagination",
            template=template,
            script=script,
            props=["currentPage", "totalPages", "onPageChange"],
        )


# =============================================================================
# Code Generation Utilities
# =============================================================================


def generate_svelte_project(
    output_dir: str | Path,
    project_name: str = "django-matt-ui",
    use_sveltekit: bool = True,
    use_typescript: bool = True,
    use_tailwind: bool = True,
) -> None:
    """
    Generate a SvelteKit project structure with components.

    Args:
        output_dir: Directory to create the project in
        project_name: Name of the project
        use_sveltekit: Generate SvelteKit project (vs plain Svelte)
        use_typescript: Include TypeScript configuration
        use_tailwind: Include Tailwind CSS configuration
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # package.json
    package_json = {
        "name": project_name,
        "version": "0.0.1",
        "private": True,
        "scripts": {
            "dev": "vite dev",
            "build": "vite build",
            "preview": "vite preview",
            "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
            "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch",
        },
        "devDependencies": {
            "@sveltejs/adapter-auto": "^3.0.0",
            "@sveltejs/kit": "^2.0.0",
            "@sveltejs/vite-plugin-svelte": "^4.0.0",
            "svelte": "^5.0.0",
            "svelte-check": "^4.0.0",
            "typescript": "^5.0.0",
            "vite": "^6.0.0",
        },
        "dependencies": {
            "bits-ui": "^1.0.0",
        },
        "type": "module",
    }

    if use_tailwind:
        package_json["devDependencies"].update(
            {
                "tailwindcss": "^3.4.0",
                "postcss": "^8.4.0",
                "autoprefixer": "^10.4.0",
            }
        )

    (output_path / "package.json").write_text(json.dumps(package_json, indent=2))

    # svelte.config.js
    svelte_config = """import adapter from '@sveltejs/adapter-auto';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter()
  }
};

export default config;
"""
    (output_path / "svelte.config.js").write_text(svelte_config)

    # vite.config.ts
    vite_config = """import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()]
});
"""
    (output_path / "vite.config.ts").write_text(vite_config)

    # tsconfig.json
    if use_typescript:
        tsconfig = {
            "extends": "./.svelte-kit/tsconfig.json",
            "compilerOptions": {
                "allowJs": True,
                "checkJs": True,
                "esModuleInterop": True,
                "forceConsistentCasingInFileNames": True,
                "resolveJsonModule": True,
                "skipLibCheck": True,
                "sourceMap": True,
                "strict": True,
                "moduleResolution": "bundler",
            },
        }
        (output_path / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2))

    # Tailwind config
    if use_tailwind:
        tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))'
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)'
      }
    }
  },
  plugins: []
};
"""
        (output_path / "tailwind.config.js").write_text(tailwind_config)

        postcss_config = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {}
  }
};
"""
        (output_path / "postcss.config.js").write_text(postcss_config)

    # Create src directory structure
    src_path = output_path / "src"
    src_path.mkdir(exist_ok=True)

    # Create app.html
    app_html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
"""
    (src_path / "app.html").write_text(app_html)

    # Create app.css with CSS variables
    app_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
"""
    (src_path / "app.css").write_text(app_css)

    # Create lib directory for components
    lib_path = src_path / "lib"
    lib_path.mkdir(exist_ok=True)

    components_path = lib_path / "components"
    components_path.mkdir(exist_ok=True)

    # Create index.ts for components
    index_ts = """// Auto-generated component exports
// Add your component exports here
export { default as Button } from './Button.svelte';
export { default as Card } from './Card.svelte';
export { default as Input } from './Input.svelte';
"""
    (components_path / "index.ts").write_text(index_ts)

    # Create routes directory
    routes_path = src_path / "routes"
    routes_path.mkdir(exist_ok=True)

    # Create +layout.svelte
    layout_svelte = """<script>
  import '../app.css';
</script>

<slot />
"""
    (routes_path / "+layout.svelte").write_text(layout_svelte)

    # Create +page.svelte
    page_svelte = """<script lang="ts">
  import { Button, Card } from '$lib/components';
</script>

<main class="container mx-auto p-8">
  <h1 class="text-4xl font-bold mb-8">Django Matt UI</h1>

  <Card title="Welcome" description="Components generated from Django Matt">
    <p class="mb-4">Your Svelte components are ready to use!</p>
    <Button label="Get Started" variant="primary" />
  </Card>
</main>
"""
    (routes_path / "+page.svelte").write_text(page_svelte)

    # Create static directory
    static_path = output_path / "static"
    static_path.mkdir(exist_ok=True)


def generate_svelte_types(
    components: list[type],
    output_path: str | Path | None = None,
) -> str:
    """
    Generate TypeScript type definitions for Svelte components.

    Args:
        components: List of component classes to generate types for
        output_path: Optional path to write the output file

    Returns:
        TypeScript code as string
    """
    lines = [
        "// Auto-generated TypeScript types for Svelte components",
        "// Do not edit manually - regenerate with django-matt",
        "",
        "import type { Snippet } from 'svelte';",
        "",
    ]

    for comp in components:
        name = comp.__name__
        fields = comp.model_fields if hasattr(comp, "model_fields") else {}

        lines.append(f"export interface {name}Props {{")

        for field_name, field_info in fields.items():
            # Skip internal fields
            if field_name in ("id", "type", "children"):
                continue

            # Get TypeScript type
            ts_type = _python_to_ts_type(field_info)
            optional = "?" if not field_info.is_required() else ""

            # Add description if available
            if field_info.description:
                lines.append(f"  /** {field_info.description} */")

            lines.append(f"  {field_name}{optional}: {ts_type};")

        # Add children slot
        lines.append("  children?: Snippet;")
        lines.append("}")
        lines.append("")

    code = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code


def _python_to_ts_type(field_info) -> str:
    """Convert Python/Pydantic field info to TypeScript type."""
    annotation = field_info.annotation if hasattr(field_info, "annotation") else None

    if annotation is None:
        return "any"

    # Handle basic types
    type_map = {
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
        list: "any[]",
        dict: "Record<string, any>",
    }

    # Check for direct type match
    for py_type, ts_type in type_map.items():
        if annotation is py_type:
            return ts_type

    # Handle Optional types
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        args = getattr(annotation, "__args__", ())

        # Handle Union types (including Optional)
        if origin.__name__ == "Union" if hasattr(origin, "__name__") else False:
            types = [_python_to_ts_type_annotation(arg) for arg in args if arg is not type(None)]
            if len(types) == 1:
                return types[0]
            return " | ".join(types)

        # Handle List types
        if origin is list:
            if args:
                inner_type = _python_to_ts_type_annotation(args[0])
                return f"{inner_type}[]"
            return "any[]"

        # Handle Dict types
        if origin is dict:
            if len(args) >= 2:
                key_type = _python_to_ts_type_annotation(args[0])
                value_type = _python_to_ts_type_annotation(args[1])
                return f"Record<{key_type}, {value_type}>"
            return "Record<string, any>"

    return "any"


def _python_to_ts_type_annotation(annotation) -> str:
    """Convert a Python type annotation to TypeScript type."""
    type_map = {
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
        list: "any[]",
        dict: "Record<string, any>",
        type(None): "null",
    }

    if annotation in type_map:
        return type_map[annotation]

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return "any"


def generate_stores(
    stores: list[SvelteStoreDefinition],
    output_path: str | Path | None = None,
) -> str:
    """
    Generate Svelte stores file.

    Args:
        stores: List of store definitions
        output_path: Optional path to write the output file

    Returns:
        TypeScript code for stores
    """
    lines = [
        "// Auto-generated Svelte stores",
        "// Do not edit manually - regenerate with django-matt",
        "",
        "import { writable, readable, derived } from 'svelte/store';",
        "import type { Writable, Readable } from 'svelte/store';",
        "",
    ]

    for store in stores:
        lines.append(store.to_code())
        lines.append("")

    code = "\n".join(lines)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code


__all__ = [
    "SvelteRenderer",
    "SvelteComponentOutput",
    "SvelteStoreDefinition",
    "SVELTE_COMPONENT_MAP",
    "SVELTE_TRANSITIONS",
    "SVELTE_EASING",
    "get_svelte_component_name",
    "generate_svelte_project",
    "generate_svelte_types",
    "generate_stores",
]
