# Templates

django-matt includes project scaffolding templates and code generation templates for controllers, schemas, services, and tests.

## Project Templates

The `startapi` management command generates a full project structure from a template:

```bash
python manage.py startapi myproject --template starter
python manage.py startapi myproject --template b2b --auth jwt --docker
python manage.py startapi myproject --template saas --frontend react-vite
```

### Available Templates

| Template | Description | Includes |
|----------|-------------|----------|
| `starter` | Minimal API project | Core setup, basic auth, single app |
| `b2b` | Multi-tenant business app | Organizations, teams, memberships, RBAC |
| `b2c` | Consumer-facing app | User profiles, social auth, notifications |
| `saas` | SaaS starter | Billing (Stripe), feature flags, multi-tenancy |

### Options

| Flag | Description |
|------|-------------|
| `--template`, `-t` | Project template (`starter`, `b2b`, `b2c`, `saas`) |
| `--auth`, `-a` | Auth strategy (`jwt`, `session`, `api-key`) |
| `--db` | Database (`postgres`, `mysql`, `sqlite`) |
| `--frontend` | Frontend scaffolding (`react-vite`, `swift`, `none`) |
| `--docker` | Include Docker and docker-compose files |
| `--api-app` | Name of the API app (default: `api`) |

## Code Generation Templates

The `generate_crud` command and the CLI template system generate individual files from templates.

### Controller Template

Generated via `generate_controller_template(name, crud=True)`:

```python
# Output for: generate_controller_template("Product", crud=True)
class ProductController(APIController):
    prefix = "/products"
    tags = ["Product"]
    permission_classes = [IsAuthenticated]

    @get("/")
    async def list_products(self, request, page: int = 1, page_size: int = 20):
        queryset = Product.objects.all()
        total = await queryset.acount()
        offset = (page - 1) * page_size
        items = [item async for item in queryset[offset:offset + page_size]]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    @get("/{id}")
    async def get_product(self, request, id: int) -> ProductSchema:
        ...

    @post("/")
    async def create_product(self, request, data: ProductCreateSchema) -> ProductSchema:
        ...

    @put("/{id}")
    async def update_product(self, request, id: int, data: ProductUpdateSchema) -> ProductSchema:
        ...

    @delete("/{id}")
    async def delete_product(self, request, id: int) -> dict:
        ...
```

### Schema Template

Generates `ModelSchema` classes for a model with Create, Update, and Response variants.

### Service Template

Generates a service layer class with async CRUD methods that wrap ORM operations.

### Test Template

Generates pytest-based async test scaffolding with factory fixtures.

### Running Code Generation

```bash
# Generate all CRUD files for a model
python manage.py generate_crud myapp.Product --full

# Generate specific parts
python manage.py generate_crud myapp.Product --controller --schema
```

The `--full` flag generates: controller, schemas, service, admin config, and tests.

## Tailwind Integration

django-matt includes a Tailwind CSS integration module for server-rendered templates.

### Setup

The `django_matt.tailwind` module provides template tags and a component system:

```python
# settings.py
INSTALLED_APPS = [
    ...
    "django_matt.tailwind",
]
```

### Template Components

The `django_matt.tailwind.components` module provides server-rendered UI components:

```python
from django_matt.tailwind.components import render_component

# Render a component to HTML
html = render_component("button", {"variant": "primary", "text": "Submit"})
```

### Template Tags

```html
{% load matt_tailwind %}

{% matt_component "alert" variant="warning" %}
  This is a warning message.
{% endmatt_component %}
```

## Template Customization

### Override Scaffolding Templates

The code generation templates are Python functions in `django_matt.cli.templates`. To customize, create your own template functions and pass them to the generator:

```python
from django_matt.cli.templates import generate_controller_template

# The default generates async controllers with IsAuthenticated
# Customize by modifying the output or writing your own generator
template = generate_controller_template("Order", crud=True)
```

### Project Template Structure

Each project template generates a standard Django project layout:

```
myproject/
    manage.py
    config/
        __init__.py
        settings.py
        urls.py
        asgi.py
        wsgi.py
    api/
        __init__.py
        models.py
        controllers.py
        schemas.py
        services.py
        tests/
```

The `b2b` and `saas` templates add additional apps and configuration for multi-tenancy, billing, and team management.
