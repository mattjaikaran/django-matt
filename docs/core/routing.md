# API & Routing

Django Matt provides a clean, decorator-based routing system for defining API endpoints.

## DjangoMattAPI

The main entry point for creating a Django Matt API.

```python
from django_matt import DjangoMattAPI

api = DjangoMattAPI(
    title="My API",
    version="1.0.0",
    description="A modern Django API",
)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | `str` | `"Django Matt API"` | API title for OpenAPI docs |
| `version` | `str` | `"1.0.0"` | API version |
| `description` | `str` | `""` | API description |
| `docs_url` | `str` | `"/docs"` | Swagger UI URL |
| `redoc_url` | `str` | `"/redoc"` | ReDoc URL |
| `openapi_url` | `str` | `"/openapi.json"` | OpenAPI schema URL |

## Route Decorators

### Function-Based Endpoints (via APIRouter)

Use `api.get/post/put/patch/delete` as decorators on standalone async functions:

```python
from django_matt import DjangoMattAPI
from pydantic import BaseModel

api = DjangoMattAPI()

class UserCreate(BaseModel):
    email: str
    name: str

@api.get("/users")
async def list_users(request):
    return {"users": []}

@api.post("/users")
async def create_user(request, body: UserCreate):
    return {"email": body.email}

@api.get("/users/<int:user_id>")
async def get_user(request, user_id: int):
    return {"user_id": user_id}

@api.put("/users/<int:user_id>")
async def update_user(request, user_id: int, body: UserCreate):
    return {"updated": True}

@api.patch("/users/<int:user_id>")
async def patch_user(request, user_id: int):
    return {"patched": True}

@api.delete("/users/<int:user_id>")
async def delete_user(request, user_id: int):
    return {"deleted": True}
```

### Controller-Based Endpoints

Inside an `APIController` subclass, use the module-level decorators imported from `django_matt.core.router`:

```python
from django_matt.core.router import get, post, put, patch, delete
from django_matt.core.controller import APIController

class UserController(APIController):
    prefix = "/users"

    @get("/")
    async def list_users(self, request):
        return {"users": []}

    @post("/")
    async def create_user(self, request, data: UserCreate):
        return {"email": data.email}
```

The `_route_info` attribute set by these decorators is what `APIRouter.get_urls()` reads to generate Django URL patterns.

### Path Parameters

```python
@api.get("/users/{user_id}/posts/{post_id}")
async def get_user_post(request, user_id: int, post_id: int):
    # Parameters are automatically parsed from the path
    return {"user_id": user_id, "post_id": post_id}
```

### Query Parameters

```python
from typing import Optional

@api.get("/users")
async def list_users(
    request,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
):
    # Query params: /users?page=2&limit=20&search=john
    return {"page": page, "limit": limit, "search": search}
```

### Request Body

For function-based routes, use the `body` parameter name — the router automatically detects it as the request body and validates it with Pydantic:

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

@api.post("/users")
async def create_user(request, body: UserCreate):
    # body is automatically parsed and validated from the JSON request
    return {"email": body.email, "name": body.name}
```

For controller methods, any parameter typed as a `BaseModel` subclass (other than `request`) is injected from the parsed JSON body:

```python
class UserController(APIController):
    prefix = "/users"

    @post("/")
    async def create_user(self, request, data: UserCreate):
        # data is parsed from request body
        ...
```

## Router Groups

Group related endpoints with a sub-router and include it in the main API:

```python
from django_matt.core.router import APIRouter

users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.get("/")
async def list_users(request):
    return {"users": []}

@users_router.get("/<int:user_id>")
async def get_user(request, user_id: int):
    return {"user_id": user_id}

# Include in main API
api.include_router(users_router)
```

## Registering Controllers

```python
from django_matt import DjangoMattAPI
from myapp.controllers import UserController, ProductController

api = DjangoMattAPI()
api.register_controller(UserController)
api.register_controller(ProductController)

# Register multiple at once
api.register_controllers(UserController, ProductController)
```

## URL Configuration

Expose the API URLs in Django's `urls.py`:

```python
# urls.py
from django.urls import path, include
from myapp.api import api

urlpatterns = [
    path("api/", include(api.urls)),
]
```

`api.urls` calls `get_urls()` internally, which merges routes with the same path, sorts static patterns before parameterized ones, and optionally builds a Rust radix-tree router for O(path-length) dispatch.

## Response Types

### Dict Response

Return a plain dict — the router serializes it with `orjson` into a `JsonResponse`:

```python
@api.get("/status")
async def status(request):
    return {"status": "ok"}
```

### Pydantic Model Response

Return a Pydantic model instance — it is serialized via `model_dump()`:

```python
from pydantic import BaseModel

class StatusResponse(BaseModel):
    status: str
    version: str

@api.get("/status")
async def status(request) -> StatusResponse:
    return StatusResponse(status="ok", version="1.0.0")
```

### Django HttpResponse

Return any `HttpResponse` subclass directly (e.g. `StreamingHttpResponse`, `FileResponse`):

```python
from django.http import HttpResponse

@api.get("/ping")
async def ping(request):
    return HttpResponse("pong", content_type="text/plain")
```

### Default Status Codes

| Method | Default status |
|--------|---------------|
| GET | 200 |
| POST | 201 |
| PUT | 200 |
| PATCH | 200 |
| DELETE | 204 |

Override via `status_code` kwarg on the decorator:

```python
@api.post("/users", status_code=200)
async def create_user(request, body: UserCreate):
    ...
```

## Async Support

All handlers are async by default. Sync handlers are also supported — the router detects coroutines at registration time:

```python
# Async (recommended)
@api.get("/users")
async def list_users(request):
    count = await User.objects.acount()
    return {"count": count}

# Sync (also works)
@api.get("/sync-users")
def list_users_sync(request):
    count = User.objects.count()
    return {"count": count}
```
