# Component Renderers

Transform Python component definitions into framework-specific output for React, Vue, Svelte, Astro, and Remix. Renderers are lazy-loaded -- only the renderer you use gets imported.

## Quick Start

```python
from django_matt.components.layout import Card, Text
from django_matt.components.renderers import ReactRenderer

renderer = ReactRenderer()
card = Card(title="Welcome", children=[Text(content="Hello!")])
output = renderer.render(card)
# output.content is JSON consumable by React
```

## Available Renderers

| Renderer | Output | Content Type | Lazy |
|----------|--------|-------------|------|
| `ReactRenderer` | JSON props | `application/json` | No |
| `ReactHtmlRenderer` | HTML + hydration data | `text/html` | No |
| `HTMLRenderer` | Server-rendered HTML | `text/html` | No |
| `JSONRenderer` | Raw JSON | `application/json` | No |
| `VueRenderer` | Vue SFC templates | `text/x-vue` | Yes |
| `VueSFCRenderer` | Complete .vue files | `text/x-vue` | Yes |
| `SvelteRenderer` | Svelte 5 components | `text/x-svelte` | Yes |
| `AstroRenderer` | Astro components | `text/astro` | Yes |
| `RemixRenderer` | Remix route modules | `text/typescript` | Yes |

## React

```python
from django_matt.components.renderers import ReactRenderer, ReactHtmlRenderer

# JSON props for client-side rendering
renderer = ReactRenderer(include_metadata=True)
output = renderer.render(card)
# Returns JSON with component tree

# Full page with multiple components
output = renderer.render_page(
    components=[card, table],
    title="Dashboard",
    description="Admin dashboard",
)

# Server-rendered HTML with hydration
html_renderer = ReactHtmlRenderer(
    root_id="app",
    bundle_url="/static/js/components.js",
    css_url="/static/css/styles.css",
)
output = html_renderer.render(card)
# Returns HTML with embedded props and hydration script
```

The React renderer maps component types to shadcn/ui names (e.g., `CARD` -> `Card`, `MODAL` -> `Dialog`, `DRAWER` -> `Sheet`).

## Vue

```python
from django_matt.components.renderers import VueRenderer, VueSFCRenderer

renderer = VueRenderer(
    typescript=True,
    use_tailwind=True,
    component_library="shadcn-vue",  # shadcn-vue | primevue | naive-ui | none
)

# Render a complete Vue SFC
sfc_content = renderer.render_to_string(card, component_name="UserCard")

# Write to file
sfc_renderer = VueSFCRenderer()
sfc_renderer.render_to_file(card, "frontend/src/components/UserCard.vue")

# Generate a Vue project scaffold
from django_matt.components.renderers import generate_vue_project
files = generate_vue_project(
    output_dir="frontend",
    project_name="my-app",
    include_pinia=True,
    include_router=True,
    include_tailwind=True,
)

# Generate TypeScript types from schemas
from django_matt.components.renderers import generate_vue_types
types = generate_vue_types(schemas, output_path="frontend/src/types.ts")

# Generate composables (useForm, useDataTable, useModal, useAuth)
from django_matt.components.renderers import generate_composables
generate_composables(components, output_dir="frontend/src/composables")
```

## Svelte

```python
from django_matt.components.renderers import SvelteRenderer

renderer = SvelteRenderer(
    use_typescript=True,
    use_runes=True,          # Svelte 5 $state, $derived, $effect
    use_tailwind=True,
    component_library="bits-ui",  # bits-ui | skeleton | melt-ui
)

output = renderer.render(card)
# output.content is a complete .svelte component

# Generate a SvelteKit project
from django_matt.components.renderers import generate_svelte_project
generate_svelte_project(
    output_dir="frontend",
    project_name="my-app",
    use_sveltekit=True,
    use_typescript=True,
    use_tailwind=True,
)

# Generate TypeScript types
from django_matt.components.renderers import generate_svelte_types
generate_svelte_types(components, output_path="frontend/src/lib/types.ts")

# Generate Svelte stores
from django_matt.components.renderers import SvelteStoreDefinition, generate_stores
stores = [
    SvelteStoreDefinition(name="userStore", type="writable", initial_value=None, typescript_type="User | null"),
]
generate_stores(stores, output_path="frontend/src/lib/stores.ts")
```

## Astro

```python
from django_matt.components.renderers.astro import AstroRenderer, generate_astro_page

renderer = AstroRenderer(
    use_tailwind=True,
    island_framework="react",  # react | vue | svelte | solid | preact
    default_directive="client:load",  # client:load | client:idle | client:visible
)

output = renderer.render(card)
# output.content is an .astro component with frontmatter

# Generate a full page
page = generate_astro_page(
    components=[card, table],
    layout="@/layouts/Layout.astro",
    title="Dashboard",
    island_framework="react",
)

# Generate project scaffold
from django_matt.components.renderers.astro import generate_astro_project
generate_astro_project(
    components=[card],
    output_dir="frontend",
    island_framework="react",
    use_tailwind=True,
)
```

Interactive components (modals, forms, selects) automatically get client directives for partial hydration. Static components render as zero-JS Astro templates.

## Remix

```python
from django_matt.components.renderers.remix import RemixRenderer, generate_remix_route

renderer = RemixRenderer(
    use_tailwind=True,
    component_library="shadcn",  # shadcn | radix | none
    api_base_url="http://localhost:8000/api",
)

output = renderer.render(card)
# output.content is a Remix route module (.tsx)

# Generate a route with loader and action
route = generate_remix_route(
    components=[card, form],
    route_path="/users",
    title="Users",
    api_endpoint="/users",
    api_base_url="http://localhost:8000/api",
)

# Generate project scaffold
from django_matt.components.renderers.remix import generate_remix_project
generate_remix_project(
    components=[card],
    output_dir="frontend",
    api_base_url="http://localhost:8000/api",
)
```

Form components automatically get Remix `Form` wrappers with `action()` functions that POST to your Django API.

## Custom Renderers

Extend `BaseRenderer` to create your own:

```python
from django_matt.components.renderers.base import BaseRenderer, RenderContext, RenderOutput
from django_matt.components.base import Component

class MyRenderer(BaseRenderer):
    def _register_default_renderers(self) -> None:
        # Register per-component-type render functions
        pass

    def render_component(
        self,
        component: Component,
        context: RenderContext | None = None,
    ) -> RenderOutput:
        if context is None:
            context = RenderContext()

        # Transform component to your format
        html = f"<div>{component.type.value}</div>"
        return RenderOutput(content=html, content_type="text/html")
```

The `RenderContext` carries theme, locale, dark mode, user, and request data through the component tree. Use `context.child_context(component_id)` to create nested contexts.
