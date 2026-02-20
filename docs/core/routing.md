# API & Routing

Django Matt provides a clean, decorator-based routing system for defining API endpoints.

## MattAPI

The main entry point for creating a Django Matt API.

```python
from django_matt import MattAPI

api = MattAPI(
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

### Basic Decorators

```python
from django_matt import api, get, post, put, patch, delete

@api.get("/users")
async def list_users(request):
    return {"users": [...]}

@api.post("/users")
async def create_user(request, data: UserCreate):
    return {"user": {...}}

@api.get("/users/{user_id}")
async def get_user(request, user_id: int):
    return {"user": {...}}

@api.put("/users/{user_id}")
async def update_user(request, user_id: int, data: UserUpdate):
    return {"user": {...}}

@api.patch("/users/{user_id}")
async def patch_user(request, user_id: int, data: UserPatch):
    return {"user": {...}}

@api.delete("/users/{user_id}")
async def delete_user(request, user_id: int):
    return {"deleted": True}
```

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

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

@api.post("/users")
async def create_user(request, data: UserCreate):
    # Request body is automatically validated
    return {"email": data.email, "name": data.name}
```

## Router Groups

Group related endpoints with a router:

```python
from django_matt import APIRouter

users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.get("/")
async def list_users(request):
    return {"users": [...]}

@users_router.get("/{user_id}")
async def get_user(request, user_id: int):
    return {"user": {...}}

# Register the router
api.include_router(users_router)
```

## URL Configuration

Add the API to your Django URLs:

```python
# urls.py
from django.urls import path
from myapp.api import api

urlpatterns = [
    path("api/", api.urls),
]
```

## Response Types

### Dict Response

```python
@api.get("/status")
async def status(request):
    return {"status": "ok"}
```

### Pydantic Model Response

```python
from pydantic import BaseModel

class StatusResponse(BaseModel):
    status: str
    version: str

@api.get("/status", response=StatusResponse)
async def status(request) -> StatusResponse:
    return StatusResponse(status="ok", version="1.0.0")
```

### HTTP Status Codes

```python
from django.http import HttpResponse

@api.post("/users", response={201: UserResponse})
async def create_user(request, data: UserCreate):
    user = await User.objects.acreate(**data.model_dump())
    return 201, UserResponse.from_orm(user)
```

## Async Support

Django Matt is async-first. All handlers support both sync and async:

```python
# Async (recommended)
@api.get("/users")
async def list_users(request):
    users = [u async for u in User.objects.all()].acount()
    return {"count": users}

# Sync (also supported)
@api.get("/sync-users")
def list_users_sync(request):
    users = User.objects.count()
    return {"count": users}
```
