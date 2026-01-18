# Controllers

Controllers are class-based API handlers that group related endpoints together.

## APIController

The base class for all controllers:

```python
from django_matt import MattAPI, APIController, get, post, put, delete

api = MattAPI()

@api.controller("/users", tags=["Users"])
class UserController(APIController):
    """User management endpoints."""

    @get("/")
    async def list_users(self, request):
        users = await User.objects.all()
        return {"users": [u.email for u in users]}

    @get("/{user_id}")
    async def get_user(self, request, user_id: int):
        user = await User.objects.aget(id=user_id)
        return {"user": user.email}

    @post("/")
    async def create_user(self, request, data: UserCreate):
        user = await User.objects.acreate(**data.model_dump())
        return {"user": user.email}

    @delete("/{user_id}")
    async def delete_user(self, request, user_id: int):
        await User.objects.filter(id=user_id).adelete()
        return {"deleted": True}
```

## CRUDController

Pre-built CRUD operations with async ORM support and query optimization:

```python
from django_matt import MattAPI, CRUDController
from django_matt.permissions import IsAuthenticated

api = MattAPI()

@api.controller("/products", tags=["Products"])
class ProductController(CRUDController):
    model = Product
    permission_classes = [IsAuthenticated]

    # Query optimization (auto-detected by default)
    auto_optimize = True
    select_related_fields = ["category", "brand"]
    prefetch_related_fields = ["tags", "images"]

    # Optional: customize response schemas
    list_schema = ProductListSchema
    detail_schema = ProductDetailSchema
    create_schema = ProductCreateSchema
    update_schema = ProductUpdateSchema
```

### Built-in Methods

CRUDController provides these async methods:

| Method | HTTP | Path | Description |
|--------|------|------|-------------|
| `list()` | GET | `/` | List with pagination |
| `create()` | POST | `/` | Create new resource |
| `read()` | GET | `/{id}` | Get single resource |
| `update()` | PUT | `/{id}` | Full update |
| `partial_update()` | PATCH | `/{id}` | Partial update |
| `delete()` | DELETE | `/{id}` | Delete resource |
| `exists()` | GET | `/{id}/exists` | Check if exists |
| `count()` | GET | `/count` | Count resources |
| `bulk_create()` | POST | `/bulk` | Create multiple |
| `bulk_update()` | PUT | `/bulk` | Update multiple |

### Query Optimization

CRUDController automatically optimizes queries:

```python
class OrderController(CRUDController):
    model = Order

    # Auto-detect relations (default behavior)
    auto_optimize = True

    # Or manually specify
    select_related_fields = ["customer", "shipping_address"]
    prefetch_related_fields = ["items", "items__product"]

    # Debug optimization
    async def list(self, request):
        info = self.get_query_optimization_info()
        print(f"select_related: {info['select_related']}")
        print(f"prefetch_related: {info['prefetch_related']}")
        return await super().list(request)
```

### Customizing Behavior

Override methods to customize behavior:

```python
class ProductController(CRUDController):
    model = Product

    def get_queryset(self):
        """Filter by user's organization."""
        qs = super().get_queryset()
        if hasattr(self.request, 'org'):
            qs = qs.filter(organization=self.request.org)
        return qs

    async def pre_create(self, request, data):
        """Add user before creation."""
        data['created_by'] = request.user
        return data

    async def post_create(self, request, instance):
        """Send notification after creation."""
        await send_notification(f"Product {instance.name} created")
```

## Controller Options

### Prefix and Tags

```python
@api.controller("/api/v1/users", tags=["Users", "V1"])
class UserController(APIController):
    ...
```

### Permission Classes

```python
from django_matt.permissions import IsAuthenticated, IsAdmin

@api.controller("/admin", tags=["Admin"])
class AdminController(APIController):
    permission_classes = [IsAuthenticated, IsAdmin]
```

### Per-Method Permissions

```python
from django_matt.auth import jwt_required, admin_required

class UserController(APIController):
    @get("/")
    async def list_users(self, request):
        # Public endpoint
        ...

    @get("/me")
    @jwt_required
    async def get_me(self, request):
        # Requires authentication
        ...

    @delete("/{user_id}")
    @admin_required
    async def delete_user(self, request, user_id: int):
        # Requires admin
        ...
```

## Dependency Injection

Controllers support dependency injection:

```python
from django_matt.di import Depends, CurrentUser, inject

class UserService:
    async def get_profile(self, user_id: int):
        return await User.objects.aget(id=user_id)

@api.controller("/users")
class UserController(APIController):
    def __init__(self, service: UserService = Depends()):
        self.service = service

    @get("/me")
    @inject
    async def get_me(self, request, user: CurrentUser):
        return await self.service.get_profile(user.id)
```

## Django Version Compatibility

CRUDController automatically adapts to your Django version:

```python
from django_matt.core import DJANGO_5_2_PLUS, DJANGO_6_0_PLUS

# Check version at runtime
if DJANGO_5_2_PLUS:
    print("Using Django 5.2+ features")

if DJANGO_6_0_PLUS:
    print("Using Django 6.0+ features")
```

Features by version:

| Feature | Django 4.1+ | Django 5.2+ | Django 6.0+ |
|---------|-------------|-------------|-------------|
| Async ORM | ✅ | ✅ | ✅ |
| Connection pooling | ❌ | ✅ | ✅ |
| Health checks | ❌ | ✅ | ✅ |
