# Content Negotiation

Django Matt provides automatic content negotiation for multi-format API responses.

## Overview

```mermaid
flowchart LR
    subgraph "Request"
        ACCEPT[Accept Header]
        QUERY[?format=xml]
        SUFFIX[/users.csv]
    end

    subgraph "Negotiator"
        DETECT[Format Detection]
        SELECT[Renderer Selection]
    end

    subgraph "Renderers"
        JSON[JSONRenderer]
        XML[XMLRenderer]
        CSV[CSVRenderer]
        YAML[YAMLRenderer]
        MSG[MessagePackRenderer]
        HTML[HTMLRenderer]
    end

    subgraph "Response"
        OUT[Formatted Output]
    end

    ACCEPT --> DETECT
    QUERY --> DETECT
    SUFFIX --> DETECT
    DETECT --> SELECT
    SELECT --> JSON
    SELECT --> XML
    SELECT --> CSV
    SELECT --> YAML
    SELECT --> MSG
    SELECT --> HTML
    JSON --> OUT
    XML --> OUT
    CSV --> OUT
```

## Quick Start

### Using Middleware (Recommended)

```python
# settings.py
MIDDLEWARE = [
    ...
    'django_matt.negotiation.ContentNegotiationMiddleware',
]

# views.py - all API responses are automatically negotiated
@api.get("/users")
async def list_users(request):
    return [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
```

Clients can then request different formats:

```bash
# JSON (default)
curl http://localhost:8000/api/users

# XML
curl -H "Accept: application/xml" http://localhost:8000/api/users

# CSV
curl http://localhost:8000/api/users?format=csv

# YAML (URL suffix)
curl http://localhost:8000/api/users.yaml
```

### Using Decorators

```python
from django_matt.negotiation import renders, render_as

# Limit to specific formats
@api.get("/users")
@renders("json", "xml", "csv")
async def list_users(request):
    return users

# Force a specific format
@api.get("/export")
@render_as("csv")
async def export_data(request):
    return data  # Always returns CSV
```

### Manual Negotiation

```python
from django_matt.negotiation import negotiate, render, render_format

@api.get("/data")
async def get_data(request):
    data = {"users": get_users()}

    # Auto-negotiate based on request
    return render(request, data)

@api.get("/export")
async def export(request):
    data = get_export_data()

    # Force specific format
    return render_format(data, "csv")
```

## Configuration

```python
# settings.py
DJANGO_MATT_NEGOTIATION = {
    # Default format when none specified
    "DEFAULT_FORMAT": "json",

    # Query parameter name for format
    "FORMAT_QUERY_PARAM": "format",

    # Raise 406 if Accept header can't be satisfied
    "STRICT_ACCEPT": False,

    # Enabled formats
    "FORMATS": ["json", "xml", "csv", "yaml", "msgpack"],

    # JSON configuration
    "JSON": {
        "indent": None,  # None for compact, 2 for pretty
        "ensure_ascii": False,
    },

    # XML configuration
    "XML": {
        "root_element": "response",
        "item_element": "item",
        "encoding": "utf-8",
    },

    # CSV configuration
    "CSV": {
        "delimiter": ",",
        "include_header": True,
    },
}
```

## Supported Formats

### JSON

```python
from django_matt.negotiation import JSONRenderer

# Automatically used for application/json
# Supports orjson/ujson for performance

@api.get("/users")
@renders("json")
async def list_users(request):
    return [{"id": 1, "name": "John"}]

# Response:
# [{"id": 1, "name": "John"}]
```

### XML

```python
from django_matt.negotiation import XMLRenderer

@api.get("/users")
@renders("xml")
async def list_users(request):
    return {"users": [{"id": 1, "name": "John"}]}

# Response:
# <?xml version="1.0" encoding="utf-8"?>
# <response>
#   <users>
#     <item>
#       <id>1</id>
#       <name>John</name>
#     </item>
#   </users>
# </response>
```

### CSV

```python
from django_matt.negotiation import CSVRenderer

@api.get("/export")
@renders("csv")
async def export_users(request):
    return [
        {"id": 1, "name": "John", "email": "john@example.com"},
        {"id": 2, "name": "Jane", "email": "jane@example.com"},
    ]

# Response:
# id,name,email
# 1,John,john@example.com
# 2,Jane,jane@example.com
```

### YAML

```python
from django_matt.negotiation import YAMLRenderer

@api.get("/config")
@renders("yaml")
async def get_config(request):
    return {"database": {"host": "localhost", "port": 5432}}

# Response:
# database:
#   host: localhost
#   port: 5432
```

### MessagePack

Binary format for high-performance scenarios:

```python
from django_matt.negotiation import MessagePackRenderer

@api.get("/data")
@renders("json", "msgpack")
async def get_data(request):
    return large_dataset  # More efficient as MessagePack
```

### HTML (Templates)

```python
from django_matt.negotiation import with_template

@api.get("/users")
@with_template("users/list.html")
@renders("json", "html")
async def list_users(request):
    return {"users": User.objects.all()}

# JSON request: returns JSON
# HTML request: renders template with context
```

## Parsers

Content negotiation also handles request body parsing:

```python
from django_matt.negotiation import parse_request_body

@api.post("/users")
async def create_user(request):
    # Automatically parses based on Content-Type
    data = parse_request_body(request)

    # Works with JSON, XML, YAML, MessagePack, Form data
    return User.objects.create(**data)
```

### Available Parsers

| Content-Type | Parser |
|-------------|--------|
| application/json | JSONParser |
| application/xml, text/xml | XMLParser |
| application/x-yaml, text/yaml | YAMLParser |
| application/msgpack | MessagePackParser |
| application/x-www-form-urlencoded | FormParser |
| multipart/form-data | MultiPartParser |

## Custom Renderers

Create custom renderers for specialized formats:

```python
from django_matt.negotiation import BaseRenderer

class MarkdownTableRenderer(BaseRenderer):
    media_type = "text/markdown"
    format = "md"

    def render(self, data, **kwargs):
        if not isinstance(data, list):
            data = [data]

        if not data:
            return ""

        # Build markdown table
        headers = data[0].keys()
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]

        for row in data:
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")

        return "\n".join(lines)

# Register the renderer
from django_matt.negotiation import RENDERERS
RENDERERS["md"] = MarkdownTableRenderer()
```

## Format Detection Priority

The negotiator detects format in this order:

1. **URL suffix** - `/users.xml` -> XML
2. **Query parameter** - `?format=csv` -> CSV
3. **Accept header** - `Accept: application/xml` -> XML
4. **Default format** - JSON

```python
# These all return XML:
GET /users.xml
GET /users?format=xml
GET /users (with Accept: application/xml header)
```

## Error Handling

### NotAcceptable (406)

When strict mode is enabled and the requested format isn't available:

```python
# settings.py
DJANGO_MATT_NEGOTIATION = {
    "STRICT_ACCEPT": True,
}

# views.py
@api.get("/users")
@renders("json", "xml")  # Only JSON and XML
async def list_users(request):
    return users

# Request with Accept: text/csv will return 406 Not Acceptable
```

### ParseError

When request body parsing fails:

```python
from django_matt.negotiation import ParseError

@api.post("/users")
async def create_user(request):
    try:
        data = parse_request_body(request)
    except ParseError as e:
        return {"error": str(e)}, 400
```

## Middleware vs Decorators

### Use Middleware When

- You want automatic negotiation for all API endpoints
- You have a consistent API format strategy
- You want minimal code changes

### Use Decorators When

- Different endpoints need different format support
- You want explicit control over formats
- You need to force specific formats for exports

```python
# Middleware handles most endpoints automatically
MIDDLEWARE = ['django_matt.negotiation.ContentNegotiationMiddleware']

# But decorators override for specific needs
@api.get("/export")
@render_as("csv")  # Always CSV, ignores Accept header
async def export(request):
    return data
```

## Integration with Views

### Class-Based Views

```python
from django_matt.negotiation import content_negotiated

@content_negotiated
class UserViewSet(APIViewSet):
    model = User

    # All methods automatically support content negotiation
    list = ListView()
    create = CreateView()
    read = ReadView()
```

### Function-Based Views

```python
from django_matt.negotiation import renders, render

@api.get("/users")
@renders("json", "xml", "csv")
async def list_users(request):
    users = await User.objects.all()
    return users  # Automatically rendered based on Accept header
```

## Performance Tips

1. **Use MessagePack for large payloads** - Binary format is more efficient
2. **Enable orjson** - Install `orjson` for faster JSON serialization
3. **Limit formats** - Only enable formats you actually need
4. **Cache rendered responses** - Use `@cache_response()` for expensive renders

```python
from django_matt.utils import cache_response

@api.get("/report")
@cache_response(timeout=300)
@renders("json", "csv")
async def get_report(request):
    return expensive_report_generation()
```
