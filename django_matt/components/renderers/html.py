"""
HTML renderer for components.

Generates plain HTML that can be used without JavaScript,
or as a fallback for non-JS environments.
"""

from html import escape
from typing import Any

from django_matt.components.base import Component, ComponentType
from django_matt.components.renderers.base import (
    BaseRenderer,
    RenderContext,
    RenderOutput,
)


class HTMLRenderer(BaseRenderer):
    """
    Renders components as plain HTML.

    This renderer generates semantic HTML that works without JavaScript.
    Useful for:
    - Server-side rendering without JS
    - Email templates
    - Print views
    - Progressive enhancement base

    Usage:
        from django_matt.components import Card, Text
        from django_matt.components.renderers import HTMLRenderer

        renderer = HTMLRenderer()
        card = Card(
            title="Welcome",
            children=[Text(content="Hello, World!")],
        )
        output = renderer.render(card)
        # output.content is plain HTML
    """

    def __init__(self, css_framework: str = "tailwind"):
        """
        Initialize HTML renderer.

        Args:
            css_framework: CSS framework for class names ("tailwind", "bootstrap", "none")
        """
        self.css_framework = css_framework
        super().__init__()

    def _register_default_renderers(self) -> None:
        """Register component-specific HTML renderers."""
        self._component_renderers = {
            ComponentType.CONTAINER: self._render_container,
            ComponentType.CARD: self._render_card,
            ComponentType.MODAL: self._render_modal,
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
        """Render a component to HTML."""
        if context is None:
            context = RenderContext()

        # Get component-specific renderer
        renderer = self._component_renderers.get(component.type)

        if renderer:
            html = renderer(component, context)
        else:
            # Default: render as div with children
            html = self._render_default(component, context)

        return RenderOutput(
            content=html,
            content_type="text/html",
        )

    def _get_class(self, component: Component, *additional: str) -> str:
        """Build class attribute string."""
        classes = list(additional)
        if component.class_name:
            classes.append(component.class_name)
        if not component.visible:
            classes.append("hidden")
        return " ".join(classes)

    def _get_attrs(self, component: Component, **extra: Any) -> str:
        """Build attribute string."""
        attrs = []

        if component.id:
            attrs.append(f'id="{escape(component.id)}"')

        classes = self._get_class(component, *extra.pop("classes", []))
        if classes:
            attrs.append(f'class="{escape(classes)}"')

        if component.style:
            style = "; ".join(f"{k}: {v}" for k, v in component.style.items())
            attrs.append(f'style="{escape(style)}"')

        if component.disabled:
            attrs.append("disabled")

        if component.aria_label:
            attrs.append(f'aria-label="{escape(component.aria_label)}"')

        if component.aria_describedby:
            attrs.append(f'aria-describedby="{escape(component.aria_describedby)}"')

        for key, value in extra.items():
            if value is True:
                attrs.append(key.replace("_", "-"))
            elif value is not None and value is not False:
                attrs.append(f'{key.replace("_", "-")}="{escape(str(value))}"')

        return " ".join(attrs)

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
        classes = ["rounded-lg", "border", "bg-card", "text-card-foreground", "shadow-sm"]
        attrs = self._get_attrs(component, classes=classes)
        children = self.render_children(component.children, context)

        parts = [f"<div {attrs}>"]

        title = getattr(component, "title", None)
        description = getattr(component, "description", None)
        if title or description:
            parts.append('<div class="flex flex-col space-y-1.5 p-6">')
            if title:
                parts.append(
                    f'<h3 class="text-2xl font-semibold leading-none tracking-tight">{escape(title)}</h3>'
                )
            if description:
                parts.append(f'<p class="text-sm text-muted-foreground">{escape(description)}</p>')
            parts.append("</div>")

        parts.append(f'<div class="p-6 pt-0">{children}</div>')

        footer = getattr(component, "footer", None)
        if footer:
            footer_html = self.render_children(
                footer if isinstance(footer, list) else [footer], context
            )
            parts.append(f'<div class="flex items-center p-6 pt-0">{footer_html}</div>')

        parts.append("</div>")
        return "\n".join(parts)

    def _render_modal(self, component: Component, context: RenderContext) -> str:
        is_open = getattr(component, "open", False)
        if not is_open:
            return ""

        title = getattr(component, "title", "")
        description = getattr(component, "description", "")
        children = self.render_children(component.children, context)

        return f"""
<div class="fixed inset-0 z-50 bg-black/80" aria-hidden="true"></div>
<div class="fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg sm:rounded-lg">
  <div class="flex flex-col space-y-1.5 text-center sm:text-left">
    <h2 class="text-lg font-semibold leading-none tracking-tight">{escape(title)}</h2>
    <p class="text-sm text-muted-foreground">{escape(description)}</p>
  </div>
  <div>{children}</div>
</div>
"""

    def _render_tabs(self, component: Component, context: RenderContext) -> str:
        items = getattr(component, "items", [])
        default_value = getattr(component, "default_value", None) or (
            items[0].value if items else ""
        )

        tabs_html = [
            '<div class="inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">'
        ]
        for item in items:
            active = item.value == default_value
            active_class = "bg-background text-foreground shadow-sm" if active else ""
            tabs_html.append(
                f'<button class="inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all {active_class}"'
                f' data-value="{escape(item.value)}">{escape(item.label)}</button>'
            )
        tabs_html.append("</div>")

        # Render content for active tab
        for item in items:
            if item.value == default_value and item.children:
                content = self.render_children(item.children, context)
                tabs_html.append(f'<div class="mt-2">{content}</div>')
                break

        return "\n".join(tabs_html)

    def _render_accordion(self, component: Component, context: RenderContext) -> str:
        items = getattr(component, "items", [])
        html_parts = ['<div class="divide-y">']

        for item in items:
            content = self.render_children(item.children, context) if item.children else ""
            html_parts.append(f"""
<div class="border-b">
  <button class="flex w-full items-center justify-between py-4 font-medium transition-all hover:underline">
    {escape(item.title)}
    <svg class="h-4 w-4 shrink-0 transition-transform duration-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
    </svg>
  </button>
  <div class="overflow-hidden text-sm transition-all">
    <div class="pb-4 pt-0">{content}</div>
  </div>
</div>
""")

        html_parts.append("</div>")
        return "\n".join(html_parts)

    def _render_alert(self, component: Component, context: RenderContext) -> str:
        variant = getattr(component, "variant", "default")
        title = getattr(component, "title", "")
        message = getattr(component, "message", "")

        variant_classes = {
            "default": "bg-background text-foreground",
            "destructive": "border-destructive/50 text-destructive dark:border-destructive",
            "success": "border-green-500/50 text-green-700 dark:text-green-400",
            "warning": "border-yellow-500/50 text-yellow-700 dark:text-yellow-400",
            "info": "border-blue-500/50 text-blue-700 dark:text-blue-400",
        }

        classes = ["relative", "w-full", "rounded-lg", "border", "p-4"] + [
            variant_classes.get(variant, "")
        ]
        attrs = self._get_attrs(component, classes=classes, role="alert")

        return f"""
<div {attrs}>
  {f'<h5 class="mb-1 font-medium leading-none tracking-tight">{escape(title)}</h5>' if title else ""}
  <div class="text-sm">{escape(message)}</div>
</div>
"""

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
        attrs = self._get_attrs(component, classes=classes)

        return f"<{tag} {attrs}>{escape(content)}</{tag}>"

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

        classes = [level_classes.get(level, "")]
        attrs = self._get_attrs(component, classes=classes)

        html = f"<h{level} {attrs}>{escape(content)}</h{level}>"
        if subtitle:
            html += f'<p class="text-muted-foreground">{escape(subtitle)}</p>'

        return html

    def _render_image(self, component: Component, context: RenderContext) -> str:
        src = getattr(component, "src", "")
        alt = getattr(component, "alt", "")
        width = getattr(component, "width", None)
        height = getattr(component, "height", None)
        loading = getattr(component, "loading", "lazy")

        attrs = self._get_attrs(
            component,
            src=src,
            alt=alt,
            width=width,
            height=height,
            loading=loading,
        )

        return f"<img {attrs} />"

    def _render_avatar(self, component: Component, context: RenderContext) -> str:
        src = getattr(component, "src", "")
        alt = getattr(component, "alt", "")
        fallback = getattr(component, "fallback", "")

        size_classes = {
            "xs": "h-6 w-6",
            "sm": "h-8 w-8",
            "md": "h-10 w-10",
            "lg": "h-12 w-12",
            "xl": "h-14 w-14",
        }
        size = getattr(component, "size", "md")
        size_class = size_classes.get(size, size_classes["md"])

        classes = ["relative", "flex", "shrink-0", "overflow-hidden", "rounded-full", size_class]
        attrs = self._get_attrs(component, classes=classes)

        if src:
            return f'<span {attrs}><img class="aspect-square h-full w-full" src="{escape(src)}" alt="{escape(alt)}" /></span>'
        return f'<span {attrs}><span class="flex h-full w-full items-center justify-center rounded-full bg-muted">{escape(fallback)}</span></span>'

    def _render_badge(self, component: Component, context: RenderContext) -> str:
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

        classes = [
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
        ]
        attrs = self._get_attrs(component, classes=classes)

        return f"<span {attrs}>{escape(content)}</span>"

    def _render_spinner(self, component: Component, context: RenderContext) -> str:
        size_classes = {
            "xs": "h-3 w-3",
            "sm": "h-4 w-4",
            "md": "h-6 w-6",
            "lg": "h-8 w-8",
            "xl": "h-10 w-10",
        }
        size = getattr(component, "size", "md")
        size_class = size_classes.get(size, size_classes["md"])

        return f"""
<svg class="animate-spin {size_class}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
</svg>
"""

    def _render_progress(self, component: Component, context: RenderContext) -> str:
        value = getattr(component, "value", 0)
        max_value = getattr(component, "max_value", 100)
        percent = (value / max_value * 100) if max_value > 0 else 0

        classes = ["relative", "h-4", "w-full", "overflow-hidden", "rounded-full", "bg-secondary"]
        attrs = self._get_attrs(component, classes=classes)

        return f"""
<div {attrs}>
  <div class="h-full w-full flex-1 bg-primary transition-all" style="transform: translateX(-{100 - percent}%)"></div>
</div>
"""

    # =========================================================================
    # Button & Link
    # =========================================================================

    def _render_button(self, component: Component, context: RenderContext) -> str:
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

        classes = [
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
        ]
        attrs = self._get_attrs(component, classes=classes, type=button_type)

        return f"<button {attrs}>{escape(label)}</button>"

    def _render_link(self, component: Component, context: RenderContext) -> str:
        label = getattr(component, "label", "")
        href = getattr(component, "href", "#")
        attrs = self._get_attrs(component, href=href)
        return f"<a {attrs}>{escape(label)}</a>"

    # =========================================================================
    # Form Components
    # =========================================================================

    def _render_form(self, component: Component, context: RenderContext) -> str:
        action = getattr(component, "action", "")
        method = getattr(component, "method", "POST")
        enctype = getattr(component, "enctype", "application/x-www-form-urlencoded")

        fields = getattr(component, "fields", [])
        submit = getattr(component, "submit", None)

        attrs = self._get_attrs(component, action=action, method=method, enctype=enctype)

        parts = [f"<form {attrs}>"]

        for field in fields:
            output = self.render_component(field, context)
            parts.append(f'<div class="mb-4">{output.content}</div>')

        if submit:
            output = self.render_component(submit, context)
            parts.append(output.content)

        parts.append("</form>")
        return "\n".join(parts)

    def _render_field_wrapper(self, component: Component, input_html: str) -> str:
        """Wrap a form field with label and error."""
        label = getattr(component, "label", "")
        name = getattr(component, "name", "")
        help_text = getattr(component, "help_text", "")
        error = getattr(component, "error", "")
        required = getattr(component, "required", False)

        parts = []

        if label:
            req = '<span class="text-destructive">*</span>' if required else ""
            parts.append(
                f'<label for="{escape(name)}" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">'
                f"{escape(label)}{req}</label>"
            )

        parts.append(input_html)

        if help_text and not error:
            parts.append(f'<p class="text-sm text-muted-foreground">{escape(help_text)}</p>')

        if error:
            parts.append(f'<p class="text-sm text-destructive">{escape(error)}</p>')

        return "\n".join(parts)

    def _render_text_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        default_value = getattr(component, "default_value", "")
        required = getattr(component, "required", False)
        readonly = getattr(component, "readonly", False)

        classes = [
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
            "file:border-0",
            "file:bg-transparent",
            "file:text-sm",
            "file:font-medium",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none",
            "focus-visible:ring-2",
            "focus-visible:ring-ring",
            "focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed",
            "disabled:opacity-50",
        ]

        input_html = f'<input type="text" {self._get_attrs(component, classes=classes, name=name, placeholder=placeholder, value=default_value, required=required, readonly=readonly)} />'
        return self._render_field_wrapper(component, input_html)

    def _render_email_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        default_value = getattr(component, "default_value", "")

        classes = [
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

        input_html = f'<input type="email" {self._get_attrs(component, classes=classes, name=name, placeholder=placeholder, value=default_value)} />'
        return self._render_field_wrapper(component, input_html)

    def _render_password_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")

        classes = [
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

        input_html = f'<input type="password" {self._get_attrs(component, classes=classes, name=name, placeholder=placeholder)} />'
        return self._render_field_wrapper(component, input_html)

    def _render_number_field(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        min_value = getattr(component, "min_value", None)
        max_value = getattr(component, "max_value", None)
        step = getattr(component, "step", None)

        classes = [
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

        input_html = f'<input type="number" {self._get_attrs(component, classes=classes, name=name, min=min_value, max=max_value, step=step)} />'
        return self._render_field_wrapper(component, input_html)

    def _render_textarea(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        placeholder = getattr(component, "placeholder", "")
        rows = getattr(component, "rows", 3)
        default_value = getattr(component, "default_value", "")

        classes = [
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
        ]

        input_html = f"<textarea {self._get_attrs(component, classes=classes, name=name, placeholder=placeholder, rows=rows)}>{escape(default_value or '')}</textarea>"
        return self._render_field_wrapper(component, input_html)

    def _render_select(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        options = getattr(component, "options", [])
        empty_label = getattr(component, "empty_label", "Select...")

        classes = [
            "flex",
            "h-10",
            "w-full",
            "items-center",
            "justify-between",
            "rounded-md",
            "border",
            "border-input",
            "bg-background",
            "px-3",
            "py-2",
            "text-sm",
        ]

        options_html = [f'<option value="">{escape(empty_label)}</option>']
        for opt in options:
            disabled = "disabled" if opt.disabled else ""
            options_html.append(
                f'<option value="{escape(opt.value)}" {disabled}>{escape(opt.label)}</option>'
            )

        select_html = f"<select {self._get_attrs(component, classes=classes, name=name)}>{''.join(options_html)}</select>"
        return self._render_field_wrapper(component, select_html)

    def _render_checkbox(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        label = getattr(component, "label", "")
        checked = getattr(component, "checked", False)

        input_html = f'''
<div class="flex items-center space-x-2">
  <input type="checkbox" {self._get_attrs(component, name=name, checked=checked)} class="h-4 w-4 rounded border-gray-300" />
  <label for="{escape(name)}" class="text-sm font-medium leading-none">{escape(label)}</label>
</div>
'''
        return input_html

    def _render_radio(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        options = getattr(component, "options", [])
        direction = getattr(component, "direction", "vertical")

        flex_class = "flex-col space-y-2" if direction == "vertical" else "flex-row space-x-4"

        items_html = []
        for opt in options:
            items_html.append(f'''
<div class="flex items-center space-x-2">
  <input type="radio" id="{escape(name)}_{escape(opt.value)}" name="{escape(name)}" value="{escape(opt.value)}" class="h-4 w-4" />
  <label for="{escape(name)}_{escape(opt.value)}" class="text-sm font-medium leading-none">{escape(opt.label)}</label>
</div>
''')

        return self._render_field_wrapper(
            component, f'<div class="flex {flex_class}">{"".join(items_html)}</div>'
        )

    def _render_switch(self, component: Component, context: RenderContext) -> str:
        name = getattr(component, "name", "")
        label = getattr(component, "label", "")
        checked = getattr(component, "checked", False)

        checked_attr = "checked" if checked else ""

        return f'''
<div class="flex items-center space-x-2">
  <button type="button" role="switch" aria-checked="{str(checked).lower()}"
    class="peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 {"bg-primary" if checked else "bg-input"}">
    <span class="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform {"translate-x-5" if checked else "translate-x-0"}"></span>
  </button>
  <input type="checkbox" name="{escape(name)}" class="hidden" {checked_attr} />
  <label class="text-sm font-medium leading-none">{escape(label)}</label>
</div>
'''

    # =========================================================================
    # Data Components
    # =========================================================================

    def _render_data_table(self, component: Component, context: RenderContext) -> str:
        columns = getattr(component, "columns", [])
        data = getattr(component, "data", [])
        empty_message = getattr(component, "empty_message", "No data available")

        parts = [
            '<div class="relative w-full overflow-auto">',
            '<table class="w-full caption-bottom text-sm">',
        ]

        # Header
        parts.append("<thead>")
        parts.append('<tr class="border-b transition-colors hover:bg-muted/50">')
        for col in columns:
            if not col.hidden:
                align_class = f"text-{col.align}" if col.align != "left" else ""
                parts.append(
                    f'<th class="h-12 px-4 text-left align-middle font-medium text-muted-foreground {align_class}">{escape(col.label)}</th>'
                )
        parts.append("</tr>")
        parts.append("</thead>")

        # Body
        parts.append("<tbody>")
        if data:
            for row in data:
                parts.append('<tr class="border-b transition-colors hover:bg-muted/50">')
                for col in columns:
                    if not col.hidden:
                        value = row.get(col.key, "")
                        parts.append(f'<td class="p-4 align-middle">{escape(str(value))}</td>')
                parts.append("</tr>")
        else:
            col_count = len([c for c in columns if not c.hidden])
            parts.append(
                f'<tr><td colspan="{col_count}" class="h-24 text-center">{escape(empty_message)}</td></tr>'
            )
        parts.append("</tbody>")

        parts.append("</table>")
        parts.append("</div>")

        return "\n".join(parts)

    def _render_pagination(self, component: Component, context: RenderContext) -> str:
        current_page = getattr(component, "current_page", 1)
        total_pages = getattr(component, "total_pages", 1)
        on_change = getattr(component, "on_change", "?page={page}")

        parts = ['<nav class="flex items-center justify-center space-x-2">']

        # Previous
        prev_disabled = current_page <= 1
        prev_url = on_change.replace("{page}", str(current_page - 1)) if not prev_disabled else "#"
        prev_class = "opacity-50 cursor-not-allowed" if prev_disabled else ""
        parts.append(
            f'<a href="{prev_url}" class="inline-flex items-center justify-center h-10 px-4 py-2 rounded-md border {prev_class}">Previous</a>'
        )

        # Page numbers
        for page in range(1, total_pages + 1):
            if page == current_page:
                parts.append(
                    f'<span class="inline-flex items-center justify-center h-10 w-10 rounded-md bg-primary text-primary-foreground">{page}</span>'
                )
            else:
                url = on_change.replace("{page}", str(page))
                parts.append(
                    f'<a href="{url}" class="inline-flex items-center justify-center h-10 w-10 rounded-md border hover:bg-accent">{page}</a>'
                )

        # Next
        next_disabled = current_page >= total_pages
        next_url = on_change.replace("{page}", str(current_page + 1)) if not next_disabled else "#"
        next_class = "opacity-50 cursor-not-allowed" if next_disabled else ""
        parts.append(
            f'<a href="{next_url}" class="inline-flex items-center justify-center h-10 px-4 py-2 rounded-md border {next_class}">Next</a>'
        )

        parts.append("</nav>")

        return "\n".join(parts)
