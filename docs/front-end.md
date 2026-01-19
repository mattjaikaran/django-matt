# Frontend Integration

Django Matt provides multiple approaches for frontend integration.

## Code Generation

Generate TypeScript types, hooks, and components from Django models:

```bash
# Generate TypeScript types
python manage.py sync_types --target typescript --output frontend/types

# Generate React components with shadcn/ui
python manage.py sync_types --target react --output frontend/src/generated

# Generate Svelte components
python manage.py sync_types --target svelte --output frontend/src/lib
```

See [Code Generation](./codegen/overview.md) for full documentation.

## UI Libraries

### shadcn/ui (Recommended)

Generated React components use shadcn/ui by default:

- Form components with react-hook-form
- Data tables with sorting/filtering
- Modals, toasts, and more

### Tailwind CSS

Django Matt's component system supports Tailwind:

```python
from django_matt.tailwind import cn, button_class

# Smart class merging
classes = cn("px-4 py-2", conditional_class if condition else "")

# Pre-built component classes
button = button_class(variant="primary", size="lg")
```

## HTMX Integration

Build dynamic UIs with minimal JavaScript:

```python
from django_matt.htmx import htmx_view

@htmx_view(
    template="products/list.html",
    partial_template="products/partials/list.html"
)
def product_list(request):
    return {"products": Product.objects.all()}
```

See [HTMX](./htmx/overview.md) for full documentation.

## Livewire-Style Components

Reactive server-side components:

```python
from django_matt.livewire import LiveComponent, action

class Counter(LiveComponent):
    count: int = 0

    @action
    def increment(self):
        self.count += 1
```

See [Livewire](./livewire/overview.md) for full documentation.

## Backend Components

Serve UI components from Python:

```python
from django_matt.components import Form, TextField, SubmitButton

form = Form(
    fields=[TextField(name="email", label="Email")],
    submit=SubmitButton(label="Submit"),
)
```

See [Components](./components/overview.md) for full documentation.

## Django Matt Pages

Server-driven SPA with end-to-end type safety:

```python
from django_matt.pages import PageResponse, page

@page("Dashboard")
def dashboard(request):
    return {"stats": get_stats()}
```

See the design document at `docs/design/pages-system.md`.

## Related Documentation

- [Code Generation](./codegen/overview.md) - TypeScript, React, Svelte
- [HTMX](./htmx/overview.md) - HTMX integration
- [Livewire](./livewire/overview.md) - Reactive components
- [Components](./components/overview.md) - Backend component system
- [Type Generation](./typegen/typescript.md) - TypeScript types
