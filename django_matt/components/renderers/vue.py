# file-length-max: 2100
"""
Vue.js renderer for components.

Generates Vue Single File Components (SFCs) with Composition API (Vue 3),
TypeScript support, and Tailwind CSS integration.
"""

import re
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
# Vue Component Mapping
# =============================================================================

# Map django-matt components to Vue/shadcn-vue equivalents
VUE_COMPONENT_MAP: dict[ComponentType, str] = {
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
    ComponentType.CONTAINER: "div",
    ComponentType.TEXT: "p",
    ComponentType.HEADING: "h1",
    ComponentType.IMAGE: "img",
    ComponentType.LINK: "RouterLink",
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


def get_vue_component_name(component_type: ComponentType) -> str:
    """Get the Vue component name for a component type."""
    return VUE_COMPONENT_MAP.get(component_type, "div")


# =============================================================================
# Vue Renderer
# =============================================================================


class VueRenderer(BaseRenderer):
    """
    Renders components as Vue Single File Components (SFCs).

    Generates Vue 3 components with Composition API, TypeScript support,
    and scoped CSS/Tailwind styling.

    Usage:
        from django_matt.components import Card, Text
        from django_matt.components.renderers import VueRenderer

        renderer = VueRenderer()
        card = Card(
            title="Welcome",
            children=[Text(content="Hello, World!")],
        )
        output = renderer.render(card)
        # output.content is a Vue SFC string

        # With TypeScript
        renderer = VueRenderer(typescript=True)
        output = renderer.render(card)
    """

    def __init__(
        self,
        typescript: bool = True,
        use_tailwind: bool = True,
        component_library: Literal["shadcn-vue", "primevue", "naive-ui", "none"] = "shadcn-vue",
        include_metadata: bool = False,
    ):
        """
        Initialize Vue renderer.

        Args:
            typescript: Generate TypeScript code (default True)
            use_tailwind: Use Tailwind CSS classes (default True)
            component_library: UI component library to target
            include_metadata: Include component metadata in output
        """
        self.typescript = typescript
        self.use_tailwind = use_tailwind
        self.component_library = component_library
        self.include_metadata = include_metadata
        super().__init__()

    def _register_default_renderers(self) -> None:
        """Register component-specific Vue renderers."""
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
            ComponentType.LOGIN_FORM: self._render_login_form,
            ComponentType.REGISTER_FORM: self._render_register_form,
            ComponentType.OAUTH_BUTTONS: self._render_oauth_buttons,
        }

    def render_component(
        self,
        component: Component,
        context: RenderContext | None = None,
    ) -> RenderOutput:
        """Render a component to Vue SFC template syntax."""
        if context is None:
            context = RenderContext()

        # Get component-specific renderer
        renderer = self._component_renderers.get(component.type)

        if renderer:
            template = renderer(component, context)
        else:
            template = self._render_default(component, context)

        return RenderOutput(
            content=template,
            content_type="text/x-vue",
            metadata={
                "component_type": component.type.value,
                "component_id": component.id,
            }
            if self.include_metadata
            else {},
        )

    def render_to_string(
        self,
        component: Component,
        context: RenderContext | None = None,
        component_name: str = "GeneratedComponent",
    ) -> str:
        """
        Render a complete Vue SFC file.

        Args:
            component: The component to render
            context: Render context
            component_name: Name for the Vue component

        Returns:
            Complete Vue SFC string with template, script, and style sections
        """
        if context is None:
            context = RenderContext()

        # Generate template
        template_content = self.render_component(component, context).content

        # Collect imports
        imports = self._collect_imports(component)

        # Generate script setup
        script_content = self._generate_script_setup(component, imports, component_name)

        # Generate styles
        style_content = self._generate_styles(component, context)

        # Combine into SFC
        sfc_parts = [
            f"<template>\n  {template_content}\n</template>",
            "",
            script_content,
        ]

        if style_content:
            sfc_parts.append("")
            sfc_parts.append(style_content)

        return "\n".join(sfc_parts)

    def render(
        self,
        component: Component | list[Component],
        context: RenderContext | None = None,
    ) -> RenderOutput:
        """
        Render one or more components.

        Returns a complete Vue SFC for a single component,
        or combined template for multiple components.
        """
        if context is None:
            context = RenderContext()

        if isinstance(component, list):
            outputs = [self.render_component(c, context) for c in component]
            combined = self._combine_outputs(outputs)
            return combined

        # Single component - return full SFC
        sfc_content = self.render_to_string(component, context)
        return RenderOutput(
            content=sfc_content,
            content_type="text/x-vue",
            metadata={
                "component_type": component.type.value,
                "component_id": component.id,
            }
            if self.include_metadata
            else {},
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_class(self, component: Component, *additional: str) -> str:
        """Build class attribute string."""
        classes = list(additional)
        if component.class_name:
            classes.append(component.class_name)
        if not component.visible:
            classes.append("hidden")
        return " ".join(filter(None, classes))

    def _get_attrs(
        self,
        component: Component,
        skip_class: bool = False,
        **extra: Any,
    ) -> str:
        """Build Vue attribute string."""
        attrs = []

        if component.id:
            attrs.append(f'id="{self._escape(component.id)}"')

        if not skip_class:
            classes = self._get_class(component, *extra.pop("classes", []))
            if classes:
                attrs.append(f'class="{self._escape(classes)}"')

        if component.style:
            style = "; ".join(f"{k}: {v}" for k, v in component.style.items())
            attrs.append(f':style="{{ {self._to_vue_object(component.style)} }}"')

        if component.disabled:
            attrs.append(':disabled="true"')

        if component.aria_label:
            attrs.append(f'aria-label="{self._escape(component.aria_label)}"')

        if component.aria_describedby:
            attrs.append(f'aria-describedby="{self._escape(component.aria_describedby)}"')

        # Handle Vue-specific attributes
        for key, value in extra.items():
            if key.startswith("v_"):
                # Convert v_model to v-model, v_if to v-if, etc.
                vue_directive = key.replace("_", "-")
                if value is True:
                    attrs.append(vue_directive)
                elif value is not None and value is not False:
                    attrs.append(f'{vue_directive}="{self._escape(str(value))}"')
            elif key.startswith("@"):
                # Event handlers
                attrs.append(f'{key}="{self._escape(str(value))}"')
            elif key.startswith(":"):
                # Bound props
                attrs.append(f'{key}="{self._escape(str(value))}"')
            elif value is True:
                attrs.append(key.replace("_", "-"))
            elif value is not None and value is not False:
                attrs.append(f'{key.replace("_", "-")}="{self._escape(str(value))}"')

        return " ".join(attrs)

    def _escape(self, value: str) -> str:
        """Escape string for Vue template."""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _to_vue_object(self, obj: dict) -> str:
        """Convert Python dict to Vue object literal."""
        items = []
        for k, v in obj.items():
            key = f"'{k}'" if "-" in k else k
            if isinstance(v, str):
                items.append(f"{key}: '{v}'")
            elif isinstance(v, bool):
                items.append(f"{key}: {'true' if v else 'false'}")
            else:
                items.append(f"{key}: {v}")
        return "{ " + ", ".join(items) + " }"

    def _collect_imports(self, component: Component) -> dict[str, set[str]]:
        """Collect required imports from component tree."""
        imports: dict[str, set[str]] = {
            "vue": set(),
            "components": set(),
            "composables": set(),
            "stores": set(),
        }

        def traverse(comp: Component):
            # Add component import
            vue_name = get_vue_component_name(comp.type)
            if vue_name not in ("div", "p", "span", "h1", "h2", "h3", "h4", "h5", "h6", "img"):
                imports["components"].add(vue_name)

            # Check for reactive needs
            if comp.bind:
                imports["vue"].add("ref")
                imports["vue"].add("computed")

            if comp.on:
                imports["vue"].add("ref")

            # Check children
            for child in comp.children:
                traverse(child)

        traverse(component)
        return imports

    def _generate_script_setup(
        self,
        component: Component,
        imports: dict[str, set[str]],
        component_name: str,
    ) -> str:
        """Generate <script setup> section."""
        lines = []

        # Script tag
        lang = ' lang="ts"' if self.typescript else ""
        lines.append(f"<script setup{lang}>")

        # Vue imports
        if imports["vue"]:
            vue_imports = ", ".join(sorted(imports["vue"]))
            lines.append(f"import {{ {vue_imports} }} from 'vue'")

        # Component imports (shadcn-vue style)
        if imports["components"]:
            for comp in sorted(imports["components"]):
                lines.append(f"import {{ {comp} }} from '@/components/ui/{self._to_kebab(comp)}'")

        # Composable imports
        if imports["composables"]:
            for comp in sorted(imports["composables"]):
                lines.append(f"import {{ {comp} }} from '@/composables/{self._to_kebab(comp)}'")

        # Store imports
        if imports["stores"]:
            for store in sorted(imports["stores"]):
                lines.append(f"import {{ {store} }} from '@/stores/{self._to_kebab(store)}'")

        # Props interface (TypeScript)
        if self.typescript:
            lines.append("")
            lines.append("interface Props {")
            lines.append("  // Add your props here")
            lines.append("}")
            lines.append("")
            lines.append("const props = defineProps<Props>()")

        # Emits
        lines.append("")
        if self.typescript:
            lines.append("const emit = defineEmits<{")
            lines.append("  // Add your events here")
            lines.append("}>()")
        else:
            lines.append("const emit = defineEmits([])")

        # State from component bindings
        bindings = self._extract_bindings(component)
        if bindings:
            lines.append("")
            lines.append("// State")
            for name, default_value in bindings.items():
                if self.typescript:
                    type_hint = self._infer_ts_type(default_value)
                    lines.append(
                        f"const {name} = ref<{type_hint}>({orjson.dumps(default_value).decode()})"
                    )
                else:
                    lines.append(f"const {name} = ref({orjson.dumps(default_value).decode()})")

        # Event handlers
        handlers = self._extract_event_handlers(component)
        if handlers:
            lines.append("")
            lines.append("// Event handlers")
            for handler_name, handler_info in handlers.items():
                if self.typescript:
                    lines.append(f"const {handler_name} = async () => {{")
                else:
                    lines.append(f"const {handler_name} = async () => {{")
                lines.append(f"  // TODO: Implement {handler_info['action']}")
                lines.append("}")

        lines.append("</script>")
        return "\n".join(lines)

    def _generate_styles(self, component: Component, context: RenderContext) -> str:
        """Generate <style> section."""
        if self.use_tailwind:
            # With Tailwind, we typically don't need many custom styles
            return "<style scoped>\n/* Add custom styles here */\n</style>"

        # Generate CSS from theme
        css_vars = []
        if hasattr(context.theme, "get_css_variables"):
            for name, value in context.theme.get_css_variables().items():
                css_vars.append(f"  --{name}: {value};")

        if css_vars:
            return f"<style scoped>\n:root {{\n{chr(10).join(css_vars)}\n}}\n</style>"

        return "<style scoped>\n/* Add custom styles here */\n</style>"

    def _extract_bindings(self, component: Component) -> dict[str, Any]:
        """Extract data bindings from component tree."""
        bindings: dict[str, Any] = {}

        def traverse(comp: Component):
            if comp.bind:
                bindings[comp.bind] = getattr(comp, "default_value", None)
            for child in comp.children:
                traverse(child)

        traverse(component)
        return bindings

    def _extract_event_handlers(self, component: Component) -> dict[str, dict]:
        """Extract event handlers from component tree."""
        handlers: dict[str, dict] = {}

        def traverse(comp: Component):
            if comp.on:
                for event, handler in comp.on.items():
                    handler_name = f"handle{event.title().replace('_', '')}"
                    handlers[handler_name] = {
                        "event": event,
                        "action": handler.action,
                        "method": handler.method,
                    }
            for child in comp.children:
                traverse(child)

        traverse(component)
        return handlers

    def _infer_ts_type(self, value: Any) -> str:
        """Infer TypeScript type from Python value."""
        if value is None:
            return "unknown"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "number"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            if value:
                inner_type = self._infer_ts_type(value[0])
                return f"{inner_type}[]"
            return "unknown[]"
        if isinstance(value, dict):
            return "Record<string, unknown>"
        return "unknown"

    def _to_kebab(self, name: str) -> str:
        """Convert PascalCase or camelCase to kebab-case."""
        return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()

    def _render_default(self, component: Component, context: RenderContext) -> str:
        """Default renderer for unknown components."""
        attrs = self._get_attrs(component)
        children = self.render_children(component.children, context)
        return f"<div {attrs}>{children}</div>"

    # =========================================================================
    # Layout Components
    # =========================================================================

    def _render_container(self, component: Component, context: RenderContext) -> str:
        tag = getattr(component, "tag", "div")
        attrs = self._get_attrs(component)
        children = self.render_children(component.children, context)
        return f"<{tag} {attrs}>{children}</{tag}>"

    def _render_card(self, component: Component, context: RenderContext) -> str:
        title = getattr(component, "title", None)
        description = getattr(component, "description", None)
        footer = getattr(component, "footer", None)
        children = self.render_children(component.children, context)

        classes = ["rounded-lg", "border", "bg-card", "text-card-foreground", "shadow-sm"]
        if component.class_name:
            classes.append(component.class_name)

        parts = [f'<Card class="{" ".join(classes)}">']

        if title or description:
            parts.append("  <CardHeader>")
            if title:
                parts.append(f"    <CardTitle>{self._escape(title)}</CardTitle>")
            if description:
                parts.append(f"    <CardDescription>{self._escape(description)}</CardDescription>")
            parts.append("  </CardHeader>")

        parts.append(f"  <CardContent>{children}</CardContent>")

        if footer:
            footer_content = self.render_children(
                footer if isinstance(footer, list) else [footer], context
            )
            parts.append(f"  <CardFooter>{footer_content}</CardFooter>")

        parts.append("</Card>")
        return "\n".join(parts)

    def _render_modal(self, component: Component, context: RenderContext) -> str:
        is_open = getattr(component, "open", False)
        title = getattr(component, "title", "")
        description = getattr(component, "description", "")
        footer = getattr(component, "footer", None)
        children = self.render_children(component.children, context)

        # Use v-model for open state
        model_binding = component.bind or "isDialogOpen"

        parts = [
            f'<Dialog v-model:open="{model_binding}">',
            "  <DialogContent>",
            "    <DialogHeader>",
        ]

        if title:
            parts.append(f"      <DialogTitle>{self._escape(title)}</DialogTitle>")
        if description:
            parts.append(
                f"      <DialogDescription>{self._escape(description)}</DialogDescription>"
            )

        parts.append("    </DialogHeader>")
        parts.append(f"    <div>{children}</div>")

        if footer:
            footer_content = self.render_children(
                footer if isinstance(footer, list) else [footer], context
            )
            parts.append(f"    <DialogFooter>{footer_content}</DialogFooter>")

        parts.append("  </DialogContent>")
        parts.append("</Dialog>")

        return "\n".join(parts)

    def _render_drawer(self, component: Component, context: RenderContext) -> str:
        title = getattr(component, "title", "")
        description = getattr(component, "description", "")
        position = getattr(component, "position", "right")
        footer = getattr(component, "footer", None)
        children = self.render_children(component.children, context)

        model_binding = component.bind or "isSheetOpen"
        side_map = {"left": "left", "right": "right", "top": "top", "bottom": "bottom"}
        side = side_map.get(position, "right")

        parts = [
            f'<Sheet v-model:open="{model_binding}">',
            f'  <SheetContent side="{side}">',
            "    <SheetHeader>",
        ]

        if title:
            parts.append(f"      <SheetTitle>{self._escape(title)}</SheetTitle>")
        if description:
            parts.append(f"      <SheetDescription>{self._escape(description)}</SheetDescription>")

        parts.append("    </SheetHeader>")
        parts.append(f'    <div class="py-4">{children}</div>')

        if footer:
            footer_content = self.render_children(
                footer if isinstance(footer, list) else [footer], context
            )
            parts.append(f"    <SheetFooter>{footer_content}</SheetFooter>")

        parts.append("  </SheetContent>")
        parts.append("</Sheet>")

        return "\n".join(parts)

    def _render_tabs(self, component: Component, context: RenderContext) -> str:
        items = getattr(component, "items", [])
        default_value = getattr(component, "default_value", None) or (
            items[0].value if items else ""
        )

        model_binding = component.bind or "activeTab"

        parts = [f'<Tabs v-model="{model_binding}" default-value="{default_value}">']
        parts.append("  <TabsList>")

        for item in items:
            disabled = ':disabled="true"' if item.disabled else ""
            parts.append(
                f'    <TabsTrigger value="{item.value}" {disabled}>{self._escape(item.label)}</TabsTrigger>'
            )

        parts.append("  </TabsList>")

        for item in items:
            content = self.render_children(item.children, context) if item.children else ""
            parts.append(f'  <TabsContent value="{item.value}">{content}</TabsContent>')

        parts.append("</Tabs>")
        return "\n".join(parts)

    def _render_accordion(self, component: Component, context: RenderContext) -> str:
        items = getattr(component, "items", [])
        accordion_type = getattr(component, "accordion_type", "single")
        collapsible = getattr(component, "collapsible", True)

        type_attr = f'type="{accordion_type}"'
        collapsible_attr = "collapsible" if collapsible and accordion_type == "single" else ""

        parts = [f"<Accordion {type_attr} {collapsible_attr}>"]

        for item in items:
            content = self.render_children(item.children, context) if item.children else ""
            parts.append(f'  <AccordionItem value="{item.value}">')
            parts.append(f"    <AccordionTrigger>{self._escape(item.title)}</AccordionTrigger>")
            parts.append(f"    <AccordionContent>{content}</AccordionContent>")
            parts.append("  </AccordionItem>")

        parts.append("</Accordion>")
        return "\n".join(parts)

    def _render_alert(self, component: Component, context: RenderContext) -> str:
        variant = getattr(component, "variant", "default")
        title = getattr(component, "title", "")
        message = getattr(component, "message", "")
        dismissible = getattr(component, "dismissible", False)

        variant_attr = f'variant="{variant}"' if variant != "default" else ""

        parts = [f"<Alert {variant_attr}>"]
        if title:
            parts.append(f"  <AlertTitle>{self._escape(title)}</AlertTitle>")
        parts.append(f"  <AlertDescription>{self._escape(message)}</AlertDescription>")

        if dismissible:
            parts.insert(
                1, '  <button class="absolute right-2 top-2" @click="$emit(\'dismiss\')">x</button>'
            )

        parts.append("</Alert>")
        return "\n".join(parts)

    # =========================================================================
    # Display Components
    # =========================================================================

    def _render_text(self, component: Component, context: RenderContext) -> str:
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
        classes = [variant_classes.get(variant, "")]
        if component.class_name:
            classes.append(component.class_name)

        class_str = " ".join(filter(None, classes))
        return f'<{tag} class="{class_str}">{self._escape(content)}</{tag}>'

    def _render_heading(self, component: Component, context: RenderContext) -> str:
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

        class_str = level_classes.get(level, "")
        html = f'<h{level} class="{class_str}">{self._escape(content)}</h{level}>'

        if subtitle:
            html += f'\n<p class="text-muted-foreground">{self._escape(subtitle)}</p>'

        return html

    def _render_image(self, component: Component, context: RenderContext) -> str:
        src = getattr(component, "src", "")
        alt = getattr(component, "alt", "")
        width = getattr(component, "width", None)
        height = getattr(component, "height", None)
        loading = getattr(component, "loading", "lazy")

        attrs = [f'src="{self._escape(src)}"', f'alt="{self._escape(alt)}"', f'loading="{loading}"']

        if width:
            attrs.append(f':width="{width}"')
        if height:
            attrs.append(f':height="{height}"')

        if component.class_name:
            attrs.append(f'class="{component.class_name}"')

        return f"<img {' '.join(attrs)} />"

    def _render_avatar(self, component: Component, context: RenderContext) -> str:
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
        size_class = size_classes.get(size, size_classes["md"])

        parts = [f'<Avatar class="{size_class}">']
        if src:
            parts.append(f'  <AvatarImage src="{self._escape(src)}" alt="{self._escape(alt)}" />')
        parts.append(f"  <AvatarFallback>{self._escape(fallback)}</AvatarFallback>")
        parts.append("</Avatar>")

        return "\n".join(parts)

    def _render_badge(self, component: Component, context: RenderContext) -> str:
        content = getattr(component, "content", "")
        variant = getattr(component, "variant", "default")

        variant_attr = f'variant="{variant}"' if variant != "default" else ""
        return f"<Badge {variant_attr}>{self._escape(content)}</Badge>"

    def _render_spinner(self, component: Component, context: RenderContext) -> str:
        size = getattr(component, "size", "md")
        label = getattr(component, "label", None)

        size_classes = {
            "xs": "h-3 w-3",
            "sm": "h-4 w-4",
            "md": "h-6 w-6",
            "lg": "h-8 w-8",
            "xl": "h-10 w-10",
        }
        size_class = size_classes.get(size, size_classes["md"])

        spinner = f'<Loader2 class="animate-spin {size_class}" />'
        if label:
            return f'<div class="flex items-center gap-2">{spinner}<span>{self._escape(label)}</span></div>'
        return spinner

    def _render_progress(self, component: Component, context: RenderContext) -> str:
        value = getattr(component, "value", 0)
        max_value = getattr(component, "max_value", 100)
        indeterminate = getattr(component, "indeterminate", False)

        if indeterminate:
            return '<Progress :model-value="undefined" />'
        return f'<Progress :model-value="{value}" :max="{max_value}" />'

    # =========================================================================
    # Button & Link
    # =========================================================================

    def _render_button(self, component: Component, context: RenderContext) -> str:
        label = getattr(component, "label", "")
        button_type = getattr(component, "button_type", "button")
        variant = getattr(component, "variant", "primary")
        size = getattr(component, "size", "md")
        icon = getattr(component, "icon", None)
        icon_position = getattr(component, "icon_position", "left")
        full_width = getattr(component, "full_width", False)

        # Map variants to shadcn-vue
        variant_map = {
            "primary": "default",
            "secondary": "secondary",
            "destructive": "destructive",
            "outline": "outline",
            "ghost": "ghost",
            "link": "link",
        }
        vue_variant = variant_map.get(variant, "default")

        # Map sizes
        size_map = {"sm": "sm", "md": "default", "lg": "lg", "icon": "icon"}
        vue_size = size_map.get(size, "default")

        attrs = [f'type="{button_type}"', f'variant="{vue_variant}"', f'size="{vue_size}"']

        if component.disabled:
            attrs.append(':disabled="true"')

        if full_width:
            attrs.append('class="w-full"')

        # Handle click event
        if component.on and "click" in component.on:
            handler = component.on["click"]
            handler_name = "handleClick"
            attrs.append(f'@click="{handler_name}"')

        content_parts = []
        if icon and icon_position == "left":
            content_parts.append(f'<{icon} class="mr-2 h-4 w-4" />')
        content_parts.append(self._escape(label))
        if icon and icon_position == "right":
            content_parts.append(f'<{icon} class="ml-2 h-4 w-4" />')

        return f"<Button {' '.join(attrs)}>{''.join(content_parts)}</Button>"

    def _render_link(self, component: Component, context: RenderContext) -> str:
        label = getattr(component, "label", "")
        href = getattr(component, "href", "#")

        # Use Vue Router for internal links
        if href.startswith("/"):
            return f'<RouterLink to="{self._escape(href)}">{self._escape(label)}</RouterLink>'

        # External link
        return f'<a href="{self._escape(href)}" target="_blank" rel="noopener noreferrer">{self._escape(label)}</a>'

    # =========================================================================
    # Form Components
    # =========================================================================

    def _render_form(self, component: Component, context: RenderContext) -> str:
        action = getattr(component, "action", "")
        method = getattr(component, "method", "POST")
        fields = getattr(component, "fields", [])
        submit = getattr(component, "submit", None)

        parts = ['<form @submit.prevent="handleSubmit">']

        for field in fields:
            output = self.render_component(field, context)
            parts.append(f'  <div class="mb-4">{output.content}</div>')

        if submit:
            output = self.render_component(submit, context)
            parts.append(f"  {output.content}")

        parts.append("</form>")
        return "\n".join(parts)

    def _render_field_wrapper(
        self,
        component: Component,
        input_html: str,
        context: RenderContext,
    ) -> str:
        """Wrap a form field with label and error in Vue FormField."""
        label = getattr(component, "label", "")
        name = getattr(component, "name", "")
        help_text = getattr(component, "help_text", "")
        error = getattr(component, "error", "")
        required = getattr(component, "required", False)

        parts = ["<FormField>"]

        if label:
            req = '<span class="text-destructive">*</span>' if required else ""
            parts.append(f"  <FormLabel>{self._escape(label)}{req}</FormLabel>")

        parts.append(f"  <FormControl>{input_html}</FormControl>")

        if help_text and not error:
            parts.append(f"  <FormDescription>{self._escape(help_text)}</FormDescription>")

        if error:
            parts.append(f"  <FormMessage>{self._escape(error)}</FormMessage>")

        parts.append("</FormField>")
        return "\n".join(parts)

    def _render_text_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        default_value = getattr(component, "default_value", "")

        model_binding = component.bind or name
        input_html = f'<Input v-model="{model_binding}" type="text" placeholder="{self._escape(placeholder or "")}" />'
        return self._render_field_wrapper(component, input_html, context)

    def _render_email_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")

        model_binding = component.bind or name
        input_html = f'<Input v-model="{model_binding}" type="email" placeholder="{self._escape(placeholder or "")}" autocomplete="email" />'
        return self._render_field_wrapper(component, input_html, context)

    def _render_password_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        show_toggle = getattr(component, "show_toggle", True)

        model_binding = component.bind or name

        if show_toggle:
            input_html = f'''<div class="relative">
    <Input v-model="{model_binding}" :type="showPassword ? 'text' : 'password'" placeholder="{self._escape(placeholder or "")}" class="pr-10" />
    <button type="button" class="absolute inset-y-0 right-0 flex items-center pr-3" @click="showPassword = !showPassword">
      <Eye v-if="!showPassword" class="h-4 w-4" />
      <EyeOff v-else class="h-4 w-4" />
    </button>
  </div>'''
        else:
            input_html = f'<Input v-model="{model_binding}" type="password" placeholder="{self._escape(placeholder or "")}" />'

        return self._render_field_wrapper(component, input_html, context)

    def _render_number_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        min_value = getattr(component, "min_value", None)
        max_value = getattr(component, "max_value", None)
        step = getattr(component, "step", None)

        model_binding = component.bind or name
        attrs = [f'v-model.number="{model_binding}"', 'type="number"']

        if min_value is not None:
            attrs.append(f':min="{min_value}"')
        if max_value is not None:
            attrs.append(f':max="{max_value}"')
        if step is not None:
            attrs.append(f':step="{step}"')

        input_html = f"<Input {' '.join(attrs)} />"
        return self._render_field_wrapper(component, input_html, context)

    def _render_textarea(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        rows = getattr(component, "rows", 3)

        model_binding = component.bind or name
        input_html = f'<Textarea v-model="{model_binding}" placeholder="{self._escape(placeholder or "")}" :rows="{rows}" />'
        return self._render_field_wrapper(component, input_html, context)

    def _render_select(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        options = getattr(component, "options", [])
        empty_label = getattr(component, "empty_label", "Select...")

        model_binding = component.bind or name

        parts = [
            f'<Select v-model="{model_binding}">',
            "  <SelectTrigger>",
            f'    <SelectValue placeholder="{self._escape(empty_label)}" />',
            "  </SelectTrigger>",
            "  <SelectContent>",
        ]

        for opt in options:
            disabled = ':disabled="true"' if opt.disabled else ""
            parts.append(
                f'    <SelectItem value="{opt.value}" {disabled}>{self._escape(opt.label)}</SelectItem>'
            )

        parts.append("  </SelectContent>")
        parts.append("</Select>")

        select_html = "\n".join(parts)
        return self._render_field_wrapper(component, select_html, context)

    def _render_checkbox(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        label = getattr(component, "label", "")
        checked = getattr(component, "checked", False)

        model_binding = component.bind or name

        return f'''<div class="flex items-center space-x-2">
  <Checkbox id="{name}" v-model:checked="{model_binding}" />
  <label for="{name}" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">{self._escape(label)}</label>
</div>'''

    def _render_radio(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        options = getattr(component, "options", [])
        direction = getattr(component, "direction", "vertical")

        model_binding = component.bind or name
        flex_class = "flex-col space-y-2" if direction == "vertical" else "flex-row space-x-4"

        parts = [f'<RadioGroup v-model="{model_binding}" class="flex {flex_class}">']

        for opt in options:
            parts.append('  <div class="flex items-center space-x-2">')
            parts.append(f'    <RadioGroupItem id="{name}_{opt.value}" value="{opt.value}" />')
            parts.append(f'    <Label for="{name}_{opt.value}">{self._escape(opt.label)}</Label>')
            parts.append("  </div>")

        parts.append("</RadioGroup>")

        radio_html = "\n".join(parts)
        return self._render_field_wrapper(component, radio_html, context)

    def _render_switch(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        label = getattr(component, "label", "")
        checked = getattr(component, "checked", False)

        model_binding = component.bind or name

        return f'''<div class="flex items-center space-x-2">
  <Switch id="{name}" v-model:checked="{model_binding}" />
  <Label for="{name}">{self._escape(label)}</Label>
</div>'''

    # =========================================================================
    # Data Components
    # =========================================================================

    def _render_data_table(self, component: Component, context: RenderContext) -> str:
        columns = getattr(component, "columns", [])
        data_url = getattr(component, "data_url", None)
        empty_message = getattr(component, "empty_message", "No data available")
        selectable = getattr(component, "selectable", False)

        # For shadcn-vue DataTable with TanStack Table
        parts = [
            "<DataTable",
            '  :columns="columns"',
            '  :data="data"',
        ]

        if selectable:
            parts.append('  :row-selection="rowSelection"')
            parts.append('  @update:row-selection="rowSelection = $event"')

        parts.append(">")
        parts.append(f"  <template #empty>{self._escape(empty_message)}</template>")
        parts.append("</DataTable>")

        return "\n".join(parts)

    def _render_pagination(self, component: Component, context: RenderContext) -> str:
        current_page = getattr(component, "current_page", 1)
        total_pages = getattr(component, "total_pages", 1)

        model_binding = component.bind or "currentPage"

        return f'''<Pagination v-model:page="{model_binding}" :total="{total_pages * 10}" :sibling-count="1" show-edges>
  <PaginationList class="flex items-center gap-1">
    <PaginationFirst />
    <PaginationPrev />
    <template v-for="(item, index) in items" :key="index">
      <PaginationListItem v-if="item.type === 'page'" :value="item.value" as-child>
        <Button class="w-10 h-10 p-0" :variant="item.value === page ? 'default' : 'outline'">
          {{{{ item.value }}}}
        </Button>
      </PaginationListItem>
      <PaginationEllipsis v-else :index="index" />
    </template>
    <PaginationNext />
    <PaginationLast />
  </PaginationList>
</Pagination>'''

    # =========================================================================
    # Auth Components
    # =========================================================================

    def _render_login_form(self, component: Component, context: RenderContext) -> str:
        action = getattr(component, "action", "/api/auth/login")
        email_label = getattr(component, "email_label", "Email")
        password_label = getattr(component, "password_label", "Password")
        submit_label = getattr(component, "submit_label", "Sign In")
        show_remember_me = getattr(component, "show_remember_me", True)
        show_forgot_password = getattr(component, "show_forgot_password", True)
        forgot_password_url = getattr(component, "forgot_password_url", "/forgot-password")
        oauth_providers = getattr(component, "oauth_providers", [])

        parts = ['<form @submit.prevent="handleLogin" class="space-y-4">']

        # Email field
        parts.append("  <FormField>")
        parts.append(f"    <FormLabel>{email_label}</FormLabel>")
        parts.append("    <FormControl>")
        parts.append(
            '      <Input v-model="email" type="email" placeholder="name@example.com" required />'
        )
        parts.append("    </FormControl>")
        parts.append("  </FormField>")

        # Password field
        parts.append("  <FormField>")
        parts.append(f"    <FormLabel>{password_label}</FormLabel>")
        parts.append("    <FormControl>")
        parts.append('      <Input v-model="password" type="password" required />')
        parts.append("    </FormControl>")
        parts.append("  </FormField>")

        # Remember me and forgot password
        if show_remember_me or show_forgot_password:
            parts.append('  <div class="flex items-center justify-between">')
            if show_remember_me:
                parts.append('    <div class="flex items-center space-x-2">')
                parts.append('      <Checkbox id="remember" v-model:checked="rememberMe" />')
                parts.append('      <label for="remember" class="text-sm">Remember me</label>')
                parts.append("    </div>")
            if show_forgot_password:
                parts.append(
                    f'    <RouterLink to="{forgot_password_url}" class="text-sm text-primary hover:underline">Forgot password?</RouterLink>'
                )
            parts.append("  </div>")

        # Submit button
        parts.append('  <Button type="submit" class="w-full" :disabled="isLoading">')
        parts.append('    <Loader2 v-if="isLoading" class="mr-2 h-4 w-4 animate-spin" />')
        parts.append(f"    {submit_label}")
        parts.append("  </Button>")

        # OAuth providers
        if oauth_providers:
            parts.append('  <div class="relative">')
            parts.append('    <div class="absolute inset-0 flex items-center">')
            parts.append('      <span class="w-full border-t" />')
            parts.append("    </div>")
            parts.append('    <div class="relative flex justify-center text-xs uppercase">')
            parts.append(
                '      <span class="bg-background px-2 text-muted-foreground">Or continue with</span>'
            )
            parts.append("    </div>")
            parts.append("  </div>")
            parts.append('  <div class="grid gap-2">')
            for provider in oauth_providers:
                parts.append(f'    <Button variant="outline" @click="handleOAuth(\'{provider}\')">')
                parts.append(f"      {provider.title()}")
                parts.append("    </Button>")
            parts.append("  </div>")

        parts.append("</form>")
        return "\n".join(parts)

    def _render_register_form(self, component: Component, context: RenderContext) -> str:
        action = getattr(component, "action", "/api/auth/register")
        email_label = getattr(component, "email_label", "Email")
        password_label = getattr(component, "password_label", "Password")
        confirm_password_label = getattr(component, "confirm_password_label", "Confirm Password")
        submit_label = getattr(component, "submit_label", "Create Account")
        require_password_confirm = getattr(component, "require_password_confirm", True)
        show_terms_checkbox = getattr(component, "show_terms_checkbox", True)
        terms_url = getattr(component, "terms_url", "/terms")
        privacy_url = getattr(component, "privacy_url", "/privacy")

        parts = ['<form @submit.prevent="handleRegister" class="space-y-4">']

        # Email field
        parts.append("  <FormField>")
        parts.append(f"    <FormLabel>{email_label}</FormLabel>")
        parts.append("    <FormControl>")
        parts.append(
            '      <Input v-model="email" type="email" placeholder="name@example.com" required />'
        )
        parts.append("    </FormControl>")
        parts.append("  </FormField>")

        # Password field
        parts.append("  <FormField>")
        parts.append(f"    <FormLabel>{password_label}</FormLabel>")
        parts.append("    <FormControl>")
        parts.append('      <Input v-model="password" type="password" required />')
        parts.append("    </FormControl>")
        parts.append("  </FormField>")

        # Confirm password
        if require_password_confirm:
            parts.append("  <FormField>")
            parts.append(f"    <FormLabel>{confirm_password_label}</FormLabel>")
            parts.append("    <FormControl>")
            parts.append('      <Input v-model="confirmPassword" type="password" required />')
            parts.append("    </FormControl>")
            parts.append("  </FormField>")

        # Terms checkbox
        if show_terms_checkbox:
            parts.append('  <div class="flex items-center space-x-2">')
            parts.append('    <Checkbox id="terms" v-model:checked="acceptTerms" required />')
            parts.append('    <label for="terms" class="text-sm">')
            parts.append(
                f'      I agree to the <RouterLink to="{terms_url}" class="text-primary hover:underline">Terms of Service</RouterLink>'
            )
            parts.append(
                f'      and <RouterLink to="{privacy_url}" class="text-primary hover:underline">Privacy Policy</RouterLink>'
            )
            parts.append("    </label>")
            parts.append("  </div>")

        # Submit button
        parts.append('  <Button type="submit" class="w-full" :disabled="isLoading">')
        parts.append('    <Loader2 v-if="isLoading" class="mr-2 h-4 w-4 animate-spin" />')
        parts.append(f"    {submit_label}")
        parts.append("  </Button>")

        parts.append("</form>")
        return "\n".join(parts)

    def _render_oauth_buttons(self, component: Component, context: RenderContext) -> str:
        providers = getattr(component, "providers", [])
        layout = getattr(component, "layout", "vertical")
        button_variant = getattr(component, "button_variant", "outline")

        layout_class = "flex-col space-y-2" if layout == "vertical" else "flex-row space-x-2"

        parts = [f'<div class="flex {layout_class}">']

        provider_icons = {
            "google": "Google",
            "github": "Github",
            "apple": "Apple",
            "microsoft": "Microsoft",
        }

        for provider in providers:
            icon = provider_icons.get(provider, provider.title())
            parts.append(
                f'  <Button variant="{button_variant}" @click="handleOAuth(\'{provider}\')">'
            )
            parts.append(f"    {icon}")
            parts.append("  </Button>")

        parts.append("</div>")
        return "\n".join(parts)


# =============================================================================
# Vue SFC Renderer (Full File Generation)
# =============================================================================


class VueSFCRenderer(VueRenderer):
    """
    Extended Vue renderer that generates complete Vue SFC files.

    Includes support for:
    - Composables generation
    - Pinia store integration
    - Vue Router handling
    - Teleport for modals
    """

    def render_to_file(
        self,
        component: Component,
        output_path: str,
        component_name: str | None = None,
        context: RenderContext | None = None,
    ) -> None:
        """
        Render component to a Vue SFC file.

        Args:
            component: Component to render
            output_path: Path to write the .vue file
            component_name: Optional component name (derived from filename if not provided)
            context: Render context
        """
        if component_name is None:
            component_name = Path(output_path).stem
            # Convert to PascalCase
            component_name = "".join(
                word.title() for word in component_name.replace("-", "_").split("_")
            )

        sfc_content = self.render_to_string(component, context, component_name)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(sfc_content)


# =============================================================================
# Code Generation Utilities
# =============================================================================


def generate_vue_project(
    output_dir: str,
    project_name: str = "frontend",
    include_pinia: bool = True,
    include_router: bool = True,
    include_tailwind: bool = True,
) -> dict[str, str]:
    """
    Generate a Vue project structure with essential configuration.

    Args:
        output_dir: Base directory for the project
        project_name: Name of the Vue project
        include_pinia: Include Pinia store setup
        include_router: Include Vue Router setup
        include_tailwind: Include Tailwind CSS configuration

    Returns:
        Dictionary of generated file paths and their contents
    """
    files: dict[str, str] = {}
    base_path = Path(output_dir) / project_name

    # package.json
    dependencies = {
        "vue": "^3.4.0",
        "@vueuse/core": "^10.7.0",
    }
    dev_dependencies = {
        "typescript": "~5.3.0",
        "vite": "^5.0.0",
        "@vitejs/plugin-vue": "^4.5.0",
        "vue-tsc": "^1.8.25",
    }

    if include_pinia:
        dependencies["pinia"] = "^2.1.0"
    if include_router:
        dependencies["vue-router"] = "^4.2.0"
    if include_tailwind:
        dev_dependencies["tailwindcss"] = "^3.4.0"
        dev_dependencies["autoprefixer"] = "^10.4.0"
        dev_dependencies["postcss"] = "^8.4.0"

    package_json = {
        "name": project_name,
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vue-tsc && vite build",
            "preview": "vite preview",
        },
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
    }
    files[str(base_path / "package.json")] = orjson.dumps(
        package_json, option=orjson.OPT_INDENT_2
    ).decode()

    # vite.config.ts
    vite_config = """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
})
"""
    files[str(base_path / "vite.config.ts")] = vite_config

    # tsconfig.json
    tsconfig = {
        "compilerOptions": {
            "target": "ES2020",
            "useDefineForClassFields": True,
            "module": "ESNext",
            "lib": ["ES2020", "DOM", "DOM.Iterable"],
            "skipLibCheck": True,
            "moduleResolution": "bundler",
            "allowImportingTsExtensions": True,
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True,
            "jsx": "preserve",
            "strict": True,
            "noUnusedLocals": True,
            "noUnusedParameters": True,
            "noFallthroughCasesInSwitch": True,
            "paths": {
                "@/*": ["./src/*"],
            },
        },
        "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue"],
        "references": [{"path": "./tsconfig.node.json"}],
    }
    files[str(base_path / "tsconfig.json")] = orjson.dumps(
        tsconfig, option=orjson.OPT_INDENT_2
    ).decode()

    # src/main.ts
    main_ts_imports = ["import { createApp } from 'vue'", "import App from './App.vue'"]
    main_ts_uses = []

    if include_pinia:
        main_ts_imports.append("import { createPinia } from 'pinia'")
        main_ts_uses.append("app.use(createPinia())")
    if include_router:
        main_ts_imports.append("import router from './router'")
        main_ts_uses.append("app.use(router)")
    if include_tailwind:
        main_ts_imports.append("import './assets/main.css'")

    main_ts = "\n".join(main_ts_imports) + "\n\nconst app = createApp(App)\n\n"
    main_ts += "\n".join(main_ts_uses) + "\n\napp.mount('#app')\n"
    files[str(base_path / "src" / "main.ts")] = main_ts

    # src/App.vue
    app_vue = """<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView />
</template>
"""
    files[str(base_path / "src" / "App.vue")] = app_vue

    # Tailwind config
    if include_tailwind:
        tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
"""
        files[str(base_path / "tailwind.config.js")] = tailwind_config

        main_css = """@tailwind base;
@tailwind components;
@tailwind utilities;
"""
        files[str(base_path / "src" / "assets" / "main.css")] = main_css

    # Router setup
    if include_router:
        router_ts = """import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
"""
        files[str(base_path / "src" / "router" / "index.ts")] = router_ts

    # Pinia store example
    if include_pinia:
        store_ts = """import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const setLoading = (loading: boolean) => {
    isLoading.value = loading
  }

  const setError = (err: string | null) => {
    error.value = err
  }

  return {
    isLoading,
    error,
    setLoading,
    setError,
  }
})
"""
        files[str(base_path / "src" / "stores" / "app.ts")] = store_ts

    return files


def generate_vue_types(
    schemas: list[dict[str, Any]],
    output_path: str | None = None,
) -> str:
    """
    Generate TypeScript interfaces from Pydantic-like schema definitions.

    Args:
        schemas: List of schema definitions (typically from Pydantic models)
        output_path: Optional path to write the types file

    Returns:
        TypeScript type definitions as a string
    """
    lines = [
        "// Auto-generated TypeScript types",
        "// Do not edit manually",
        "",
    ]

    for schema in schemas:
        name = schema.get("name", "Unknown")
        fields = schema.get("fields", [])

        lines.append(f"export interface {name} {{")

        for field in fields:
            field_name = field.get("name", "unknown")
            field_type = _python_to_ts_type(field.get("type", "any"))
            optional = "?" if not field.get("required", False) else ""
            lines.append(f"  {field_name}{optional}: {field_type}")

        lines.append("}")
        lines.append("")

    content = "\n".join(lines)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    return content


def _python_to_ts_type(python_type: str) -> str:
    """Convert Python type annotation to TypeScript type."""
    type_map = {
        "str": "string",
        "int": "number",
        "float": "number",
        "bool": "boolean",
        "None": "null",
        "Any": "unknown",
        "dict": "Record<string, unknown>",
        "list": "unknown[]",
        "datetime": "string",
        "date": "string",
        "UUID": "string",
    }

    # Handle Optional, List, etc.
    if python_type.startswith("Optional["):
        inner = python_type[9:-1]
        return f"{_python_to_ts_type(inner)} | null"

    if python_type.startswith("List["):
        inner = python_type[5:-1]
        return f"{_python_to_ts_type(inner)}[]"

    if python_type.startswith("Dict["):
        # Dict[str, X] -> Record<string, X>
        return "Record<string, unknown>"

    return type_map.get(python_type, python_type)


def generate_composables(
    components: list[Component],
    output_dir: str,
) -> dict[str, str]:
    """
    Generate Vue composables for shared component logic.

    Extracts common patterns like form handling, data fetching,
    and state management into reusable composables.

    Args:
        components: List of components to analyze
        output_dir: Directory to output composable files

    Returns:
        Dictionary of file paths to generated content
    """
    files: dict[str, str] = {}

    # Analyze components for patterns
    has_forms = any(c.type == ComponentType.FORM for c in components)
    has_data_table = any(c.type == ComponentType.DATA_TABLE for c in components)
    has_modals = any(c.type == ComponentType.MODAL for c in components)
    has_auth = any(
        c.type in (ComponentType.LOGIN_FORM, ComponentType.REGISTER_FORM) for c in components
    )

    # Form composable
    if has_forms:
        form_composable = """import { ref, reactive, computed } from 'vue'
import type { Ref } from 'vue'

export interface FormField {
  value: unknown
  error: string | null
  touched: boolean
}

export interface FormOptions<T> {
  initialValues: T
  onSubmit: (values: T) => Promise<void>
  validate?: (values: T) => Record<string, string>
}

export function useForm<T extends Record<string, unknown>>(options: FormOptions<T>) {
  const values = reactive({ ...options.initialValues }) as T
  const errors = ref<Record<string, string>>({})
  const isSubmitting = ref(false)
  const isValid = computed(() => Object.keys(errors.value).length === 0)

  const setFieldValue = (field: keyof T, value: unknown) => {
    (values as Record<string, unknown>)[field as string] = value
  }

  const setFieldError = (field: string, error: string) => {
    errors.value[field] = error
  }

  const clearErrors = () => {
    errors.value = {}
  }

  const handleSubmit = async () => {
    clearErrors()

    if (options.validate) {
      const validationErrors = options.validate(values)
      if (Object.keys(validationErrors).length > 0) {
        errors.value = validationErrors
        return
      }
    }

    isSubmitting.value = true
    try {
      await options.onSubmit(values)
    } finally {
      isSubmitting.value = false
    }
  }

  const reset = () => {
    Object.assign(values, options.initialValues)
    clearErrors()
  }

  return {
    values,
    errors,
    isSubmitting,
    isValid,
    setFieldValue,
    setFieldError,
    clearErrors,
    handleSubmit,
    reset,
  }
}
"""
        files[str(Path(output_dir) / "useForm.ts")] = form_composable

    # Data table composable
    if has_data_table:
        table_composable = """import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'

export interface PaginationState {
  page: number
  pageSize: number
  total: number
}

export interface SortState {
  field: string | null
  direction: 'asc' | 'desc'
}

export interface TableOptions<T> {
  fetchData: (params: { page: number; pageSize: number; sort?: SortState }) => Promise<{ data: T[]; total: number }>
  pageSize?: number
}

export function useDataTable<T>(options: TableOptions<T>) {
  const data = ref<T[]>([]) as Ref<T[]>
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const pagination = ref<PaginationState>({
    page: 1,
    pageSize: options.pageSize || 10,
    total: 0,
  })

  const sort = ref<SortState>({
    field: null,
    direction: 'asc',
  })

  const totalPages = computed(() =>
    Math.ceil(pagination.value.total / pagination.value.pageSize)
  )

  const fetchData = async () => {
    isLoading.value = true
    error.value = null

    try {
      const result = await options.fetchData({
        page: pagination.value.page,
        pageSize: pagination.value.pageSize,
        sort: sort.value.field ? sort.value : undefined,
      })
      data.value = result.data
      pagination.value.total = result.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch data'
    } finally {
      isLoading.value = false
    }
  }

  const setPage = (page: number) => {
    pagination.value.page = page
  }

  const setPageSize = (size: number) => {
    pagination.value.pageSize = size
    pagination.value.page = 1
  }

  const setSort = (field: string, direction: 'asc' | 'desc' = 'asc') => {
    sort.value = { field, direction }
  }

  // Auto-fetch when pagination or sort changes
  watch(
    [() => pagination.value.page, () => pagination.value.pageSize, () => sort.value],
    () => fetchData(),
    { immediate: true }
  )

  return {
    data,
    isLoading,
    error,
    pagination,
    sort,
    totalPages,
    fetchData,
    setPage,
    setPageSize,
    setSort,
  }
}
"""
        files[str(Path(output_dir) / "useDataTable.ts")] = table_composable

    # Modal composable
    if has_modals:
        modal_composable = """import { ref } from 'vue'

export function useModal() {
  const isOpen = ref(false)

  const open = () => {
    isOpen.value = true
  }

  const close = () => {
    isOpen.value = false
  }

  const toggle = () => {
    isOpen.value = !isOpen.value
  }

  return {
    isOpen,
    open,
    close,
    toggle,
  }
}

export function useConfirmModal() {
  const isOpen = ref(false)
  const resolveRef = ref<((value: boolean) => void) | null>(null)

  const confirm = (): Promise<boolean> => {
    isOpen.value = true
    return new Promise((resolve) => {
      resolveRef.value = resolve
    })
  }

  const handleConfirm = () => {
    isOpen.value = false
    resolveRef.value?.(true)
  }

  const handleCancel = () => {
    isOpen.value = false
    resolveRef.value?.(false)
  }

  return {
    isOpen,
    confirm,
    handleConfirm,
    handleCancel,
  }
}
"""
        files[str(Path(output_dir) / "useModal.ts")] = modal_composable

    # Auth composable
    if has_auth:
        auth_composable = """import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

export interface User {
  id: string
  email: string
  name?: string
}

export interface AuthState {
  user: User | null
  token: string | null
}

const authState = ref<AuthState>({
  user: null,
  token: null,
})

export function useAuth() {
  const router = useRouter()

  const isAuthenticated = computed(() => authState.value.token !== null)
  const user = computed(() => authState.value.user)

  const login = async (email: string, password: string) => {
    // Implement your login logic
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })

    if (!response.ok) {
      throw new Error('Login failed')
    }

    const data = await response.json()
    authState.value = {
      user: data.user,
      token: data.token,
    }

    localStorage.setItem('token', data.token)
  }

  const logout = () => {
    authState.value = { user: null, token: null }
    localStorage.removeItem('token')
    router.push('/login')
  }

  const register = async (email: string, password: string) => {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })

    if (!response.ok) {
      throw new Error('Registration failed')
    }

    return response.json()
  }

  const initAuth = () => {
    const token = localStorage.getItem('token')
    if (token) {
      authState.value.token = token
      // Fetch user profile
    }
  }

  return {
    isAuthenticated,
    user,
    login,
    logout,
    register,
    initAuth,
  }
}
"""
        files[str(Path(output_dir) / "useAuth.ts")] = auth_composable

    # Write files
    for path, content in files.items():
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    return files


__all__ = [
    "VueRenderer",
    "VueSFCRenderer",
    "VUE_COMPONENT_MAP",
    "get_vue_component_name",
    "generate_vue_project",
    "generate_vue_types",
    "generate_composables",
]
