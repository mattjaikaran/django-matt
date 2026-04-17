# Content Negotiation

Automatic multi-format API responses based on Accept headers, query parameters, or URL suffixes. Supports JSON, XML, CSV, YAML, MessagePack, and HTML.

## Quick Start

```python
# Using middleware (automatic for all API responses)
# settings.py
MIDDLEWARE = [
    ...
    "django_matt.negotiation.ContentNegotiationMiddleware",
]

# Using decorators
from django_matt.negotiation import renders, render_as, content_negotiated

@renders("json", "xml", "csv")
def list_users(request):
    return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

@render_as("csv")
def export_users(request):
    return [{"id": 1, "name": "Alice"}]

# Using the negotiator directly
from django_matt.negotiation import render

def my_view(request):
    data = {"users": [{"id": 1, "name": "Alice"}]}
    return render(request, data)
```

Clients request formats via:

- **Query parameter**: `GET /users?format=xml`
- **URL suffix**: `GET /users.csv`
- **Accept header**: `Accept: application/xml`

## Configuration

```python
# settings.py
DJANGO_MATT_NEGOTIATION = {
    "DEFAULT_FORMAT": "json",
    "FORMAT_QUERY_PARAM": "format",
    "STRICT_ACCEPT": False,  # Return 406 if format not supported

    # Enabled formats in priority order
    "FORMATS": ["json", "xml", "csv", "yaml", "msgpack"],

    # Format aliases
    "FORMAT_ALIASES": {
        "javascript": "json",
        "yml": "yaml",
    },

    # Per-format settings
    "JSON": {
        "INDENT": None,
        "ENSURE_ASCII": False,
        "SORT_KEYS": False,
    },
    "XML": {
        "ROOT_TAG": "response",
        "ITEM_TAG": "item",
        "DECLARATION": True,
        "ENCODING": "utf-8",
        "PRETTY_PRINT": False,
    },
    "CSV": {
        "DELIMITER": ",",
        "INCLUDE_HEADER": True,
    },
    "YAML": {
        "DEFAULT_FLOW_STYLE": False,
        "ALLOW_UNICODE": True,
        "INDENT": 2,
    },
    "HTML": {
        "TEMPLATE_NAME": None,  # Auto-generates HTML table
        "BASE_TEMPLATE": "base.html",
    },
}
```

Optional dependencies for non-JSON formats:

```bash
uv add pyyaml    # YAML support
uv add msgpack   # MessagePack support
```

## Key Features

### Renderers

Six built-in renderers convert Python data to response formats:

| Renderer | Media Type | Notes |
|----------|-----------|-------|
| `JSONRenderer` | `application/json` | Uses orjson for performance |
| `XMLRenderer` | `application/xml` | Nested dict/list to XML |
| `CSVRenderer` | `text/csv` | Flattens nested dicts |
| `YAMLRenderer` | `application/yaml` | Requires `pyyaml` |
| `MessagePackRenderer` | `application/msgpack` | Requires `msgpack` |
| `HTMLRenderer` | `text/html` | Template or auto-table |

All renderers handle Pydantic models, datetime, Decimal, UUID, and Enum serialization.

### Parsers

Six built-in parsers handle incoming request bodies:

| Parser | Media Type |
|--------|-----------|
| `JSONParser` | `application/json` |
| `XMLParser` | `application/xml` |
| `FormParser` | `application/x-www-form-urlencoded` |
| `MultiPartParser` | `multipart/form-data` |
| `YAMLParser` | `application/yaml` |
| `MessagePackParser` | `application/msgpack` |

### Decorators

```python
from django_matt.negotiation import renders, render_as, content_negotiated, with_template

# Restrict formats
@renders("json", "xml")
async def list_items(request):
    return items

# Force a specific format
@render_as("csv")
async def export_items(request):
    return items

# Auto-negotiate all formats
@content_negotiated
async def get_data(request):
    return data

# Use template for HTML, negotiate for other formats
@with_template("items/list.html")
async def list_items(request):
    return {"items": items}
```

### NegotiatedResponse Builder

Fluent API for building negotiated responses:

```python
from django_matt.negotiation import NegotiatedResponse

def create_item(request):
    item = create(request.parsed_data)
    return (
        NegotiatedResponse(item)
        .with_status(201)
        .render(request)
    )

# Force specific format
def export(request):
    return (
        NegotiatedResponse(data)
        .as_format("csv")
        .render()
    )
```

### Middleware

The middleware automatically negotiates format and parses request bodies:

```python
# Sync middleware
MIDDLEWARE = ["django_matt.negotiation.ContentNegotiationMiddleware"]

# Async middleware (for ASGI)
MIDDLEWARE = ["django_matt.negotiation.AsyncContentNegotiationMiddleware"]
```

The middleware sets `request.negotiated_format` and `request.parsed_data` on every request, and transforms JSON responses to the negotiated format on the way out.

### ContentNegotiator

Use the negotiator directly for full control:

```python
from django_matt.negotiation import ContentNegotiator

negotiator = ContentNegotiator()

# Negotiate format from request
negotiated = negotiator.negotiate(request)
print(negotiated.format)      # "xml"
print(negotiated.media_type)  # "application/xml"

# Render data
response = negotiated.renderer.to_response(data, status=200)

# Parse request body
parsed = negotiator.parse(request)
```

## Practical Example

An API endpoint that supports JSON, XML, and CSV export:

```python
from django_matt.negotiation import renders, NegotiatedResponse

@renders("json", "xml", "csv")
async def list_products(request):
    products = await Product.objects.all().values("id", "name", "price", "category")
    return list(products)

@renders("json", "xml")
async def get_product(request, pk: int):
    product = await Product.objects.filter(pk=pk).values().afirst()
    if not product:
        return NegotiatedResponse({"error": "Not found"}).with_status(404).render(request)
    return product
```

```bash
# JSON (default)
curl http://localhost:8000/products/

# XML via query param
curl http://localhost:8000/products/?format=xml

# CSV via Accept header
curl -H "Accept: text/csv" http://localhost:8000/products/

# XML via URL suffix
curl http://localhost:8000/products.xml
```
