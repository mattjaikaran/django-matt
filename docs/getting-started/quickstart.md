# Quick Start

This guide will help you create your first API with django-matt in under 5 minutes.

## Prerequisites

- Python 3.12+
- Django 5.2+
- django-matt installed (`uv add django-matt`)

## Option 1: Using the startapi Command (Recommended)

The fastest way to get started is using the built-in `startapi` command:

```bash
# Create a new API project with all the essentials
python manage.py startapi myapi --template minimal --auth jwt

# Or create a full B2B SaaS project
python manage.py startapi myapi --template b2b --auth jwt --docker
```

This generates:
- API module with basic endpoints
- Authentication configured
- Schemas for User and common models
- Tests boilerplate
- Docker setup (if `--docker` flag used)

## Option 2: Manual Setup

### Step 1: Create a Django Project

```bash
# Create a new Django project
django-admin startproject myproject
cd myproject

# Install django-matt
uv add "django-matt[auth]"
```

### Step 2: Configure Django

Edit `myproject/settings.py`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Add django-matt
    "django_matt",
]

# JWT Configuration (optional but recommended)
DJANGO_MATT_JWT = {
    "SECRET_KEY": "your-secret-key",  # Use Django's SECRET_KEY in production
    "ACCESS_TOKEN_LIFETIME": 3600,     # 1 hour
    "REFRESH_TOKEN_LIFETIME": 86400 * 7,  # 7 days
}
```

### Step 3: Create Your API

Create `myproject/api.py`:

```python
from django_matt import MattAPI
from django_matt.auth import jwt_required
from pydantic import BaseModel

# Initialize the API
api = MattAPI(
    title="My First API",
    version="1.0.0",
    description="A modern Django API built with django-matt",
)


# =============================================================================
# Basic Endpoints
# =============================================================================

@api.get("/")
async def root(request):
    """Welcome endpoint"""
    return {"message": "Welcome to My API!"}


@api.get("/health")
async def health_check(request):
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}


# =============================================================================
# Request Validation with Pydantic
# =============================================================================

class MessageSchema(BaseModel):
    """Schema for message requests"""
    content: str
    recipient: str


class MessageResponse(BaseModel):
    """Schema for message responses"""
    id: int
    content: str
    recipient: str
    sent: bool


@api.post("/messages", response=MessageResponse)
async def send_message(request, data: MessageSchema):
    """Send a message - demonstrates request validation"""
    return MessageResponse(
        id=1,
        content=data.content,
        recipient=data.recipient,
        sent=True,
    )


# =============================================================================
# Path Parameters
# =============================================================================

@api.get("/users/{user_id}")
async def get_user(request, user_id: int):
    """Get a user by ID"""
    return {"user_id": user_id, "name": f"User {user_id}"}


# =============================================================================
# Query Parameters
# =============================================================================

@api.get("/search")
async def search(
    request,
    q: str,
    page: int = 1,
    limit: int = 10,
):
    """Search with pagination - query params: ?q=term&page=1&limit=10"""
    return {
        "query": q,
        "page": page,
        "limit": limit,
        "results": [],
    }


# =============================================================================
# Protected Endpoints
# =============================================================================

@api.get("/me")
@jwt_required
async def get_current_user(request):
    """Get current user - requires authentication"""
    return {
        "id": request.user.id,
        "email": request.user.email,
        "username": request.user.username,
    }
```

### Step 4: Add URL Configuration

Edit `myproject/urls.py`:

```python
from django.contrib import admin
from django.urls import path
from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

### Step 5: Run the Server

```bash
# Apply migrations first
python manage.py migrate

# Run the development server
python manage.py runserver
```

## Explore Your API

Visit these URLs in your browser:

| URL | Description |
|-----|-------------|
| http://localhost:8000/api/ | Root endpoint |
| http://localhost:8000/api/health | Health check |
| http://localhost:8000/api/docs | Swagger UI (interactive docs) |
| http://localhost:8000/api/redoc | ReDoc (alternative docs) |
| http://localhost:8000/api/openapi.json | OpenAPI schema |

## Test Your Endpoints

### Using curl

```bash
# Root endpoint
curl http://localhost:8000/api/

# Health check
curl http://localhost:8000/api/health

# Send a message (POST with JSON body)
curl -X POST http://localhost:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello!", "recipient": "john@example.com"}'

# Get user by ID
curl http://localhost:8000/api/users/123

# Search with query params
curl "http://localhost:8000/api/search?q=django&page=1&limit=20"
```

### Using httpie

```bash
# Root endpoint
http GET localhost:8000/api/

# Send a message
http POST localhost:8000/api/messages content="Hello!" recipient="john@example.com"

# Search
http GET localhost:8000/api/search q==django page==1 limit==20
```

### Using Python

```python
import httpx

# Sync client
client = httpx.Client(base_url="http://localhost:8000/api")

# GET request
response = client.get("/health")
print(response.json())

# POST request
response = client.post("/messages", json={
    "content": "Hello!",
    "recipient": "john@example.com"
})
print(response.json())

# Async client
async with httpx.AsyncClient(base_url="http://localhost:8000/api") as client:
    response = await client.get("/health")
    print(response.json())
```

## Adding Authentication

### Register a User

First, let's add registration and login endpoints:

```python
# myproject/api.py

from django.contrib.auth.models import User
from django_matt.auth import create_token_pair
from pydantic import BaseModel, EmailStr


class RegisterSchema(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginSchema(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@api.post("/auth/register", response=TokenResponse)
async def register(request, data: RegisterSchema):
    """Register a new user"""
    user = await User.objects.acreate_user(
        username=data.username,
        email=data.email,
        password=data.password,
    )
    tokens = create_token_pair(user)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@api.post("/auth/login", response=TokenResponse)
async def login(request, data: LoginSchema):
    """Login and get tokens"""
    from asgiref.sync import sync_to_async
    from django.contrib.auth import authenticate

    user = await sync_to_async(authenticate)(
        username=data.username,
        password=data.password,
    )
    if not user:
        from django_matt.core.errors import UnauthorizedError
        raise UnauthorizedError("Invalid credentials")

    tokens = create_token_pair(user)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
```

### Using Authentication

```bash
# Register a user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "username": "testuser", "password": "securepass123"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "securepass123"}'

# Use the access token for protected endpoints
curl http://localhost:8000/api/me \
  -H "Authorization: Bearer <your-access-token>"
```

## Adding CRUD Operations

Use `APIViewSet` for rapid CRUD endpoint creation:

```python
# myproject/models.py
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

```python
# myproject/schemas.py
from django_matt import ModelSchema
from .models import Product


class ProductSchema(ModelSchema):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "created_at"]


class ProductCreateSchema(ModelSchema):
    class Meta:
        model = Product
        fields = ["name", "description", "price"]
```

```python
# myproject/api.py (add to existing)
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
from django_matt.permissions import IsAuthenticated
from .models import Product
from .schemas import ProductSchema, ProductCreateSchema


class ProductViewSet(APIViewSet):
    """CRUD endpoints for products"""
    api = api
    model = Product
    default_response_schema = ProductSchema

    # GET /api/products/
    list = ListView()

    # POST /api/products/
    create = CreateView(
        request_schema=ProductCreateSchema,
        permission_classes=[IsAuthenticated],
    )

    # GET /api/products/{id}/
    read = ReadView()

    # PUT /api/products/{id}/
    update = UpdateView(
        request_schema=ProductCreateSchema,
        permission_classes=[IsAuthenticated],
    )

    # DELETE /api/products/{id}/
    delete = DeleteView(permission_classes=[IsAuthenticated])
```

This creates:

| Method | URL | Description |
|--------|-----|-------------|
| GET | /api/products/ | List all products |
| POST | /api/products/ | Create a product (auth required) |
| GET | /api/products/{id}/ | Get a product |
| PUT | /api/products/{id}/ | Update a product (auth required) |
| DELETE | /api/products/{id}/ | Delete a product (auth required) |

## Project Structure

Your project should now look like this:

```
myproject/
    manage.py
    myproject/
        __init__.py
        settings.py
        urls.py
        api.py          # Your API endpoints
        models.py       # Django models
        schemas.py      # Pydantic schemas
```

## What's New

Recent additions to the framework:

- **Auto-Instrumentation** - Zero-config observability via `setup_observability()`. Automatically traces controllers, DB queries, cache operations, and outbound HTTP. See [Observability > Auto-Instrumentation](../observability/auto-instrumentation.md).
- **Lightweight Spans** - Dependency-free span system (`span()`, `aspan()`, `@traced`) with nested parent-child tracking. See [Observability > Spans](../observability/spans.md).
- **Metrics Collectors** - Built-in request, database, and cache collectors with percentile tracking and slow query detection. See [Observability > Collectors](../observability/collectors.md).
- **Span Exporters** - Console, JSON, Prometheus, and OpenTelemetry exporters for span data. See [Observability > Exporters](../observability/exporters.md).
- **Config Validation** - Pydantic-based `ConfigNamespace` with typed namespaces (Auth, Cache, Database, etc.) and startup validation. See [Config > Validation](../config/validation.md).
- **Route-Scoped Middleware** - Per-route middleware with `@use_middleware` / `@skip_middleware` and built-ins for CORS, rate limiting, caching, and auth. See [Middleware > Scoped](../middleware/scoped.md).

## Next Steps

Now that you have a working API, explore these features:

<div class="grid cards" markdown>

-   :material-shield-account: **Authentication**

    ---

    Add JWT, OAuth, Passkeys, or SSO

    [:octicons-arrow-right-24: Authentication Guide](../auth/overview.md)

-   :material-database: **CRUD Views**

    ---

    Automatic CRUD with `APIViewSet`

    [:octicons-arrow-right-24: CRUD Views](../features/views.md)

-   :material-office-building: **Multi-Tenancy**

    ---

    Add organizations and teams

    [:octicons-arrow-right-24: Multi-Tenancy](../multitenancy/overview.md)

-   :material-credit-card: **Billing**

    ---

    Integrate Stripe, PayPal, or Polar

    [:octicons-arrow-right-24: Billing](../billing/overview.md)

-   :material-language-typescript: **Type Generation**

    ---

    Generate TypeScript types

    [:octicons-arrow-right-24: Type Generation](../typegen/typescript.md)

-   :material-test-tube: **Testing**

    ---

    Write tests with the test client

    [:octicons-arrow-right-24: Testing](../testing/client.md)

</div>
