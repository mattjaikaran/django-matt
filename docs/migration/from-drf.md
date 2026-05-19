# Migrating from Django REST Framework (Legacy)

> **This is a legacy guide.** The current, authoritative version is [`docs/migrations/from-drf.md`](../migrations/from-drf.md). This file is preserved for historical reference.

This guide helps you migrate an existing Django REST Framework (DRF) application to django-matt. We cover the key differences and show equivalent patterns side-by-side.

## Why Migrate?

| Feature | DRF | django-matt |
|---------|-----|-------------|
| Async support | Limited (DRF 3.14+) | Full async-first |
| Type hints | Partial | Complete, every signature |
| Schema validation | DRF Serializers | Pydantic v2 |
| Performance | Good | Better (orjson, Rust-accelerated router) |
| Auto-generated types | Via drf-spectacular | Built-in TS/Swift codegen |
| Auth | simplejwt + dj-rest-auth | Built-in JWT, OAuth, SSO, Passkeys, Magic Links |
| Billing | None | Built-in Stripe/PayPal/Polar |
| Real-time | None | Built-in WebSocket support |
| Feature flags | None | Built-in (DB, Redis, LaunchDarkly) |
| OpenAPI | Via drf-spectacular | Built-in Swagger + ReDoc |
| Dependency injection | None | Built-in DI container |

## Installation

Install django-matt alongside DRF for gradual migration:

```bash
uv add django-matt
```

Add to `INSTALLED_APPS` (keep DRF during migration):

```python
INSTALLED_APPS = [
    ...
    'rest_framework',  # Keep during migration
    'django_matt',
]
```

---

## Serializers to Schemas

### DRF Serializer

```python
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'full_name', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'username', 'password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
```

### django-matt Schema

```python
from django_matt import ModelSchema
from pydantic import field_validator, computed_field


class UserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'created_at']

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class UserCreateSchema(ModelSchema):
    password: str

    class Meta:
        model = User
        fields = ['email', 'username']

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    @field_validator('email')
    @classmethod
    def validate_email_unique(cls, v: str) -> str:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(email=v).exists():
            raise ValueError('Email already exists')
        return v
```

**Key differences:**
- `ModelSchema` uses `Meta` with `fields` list (no `read_only_fields` needed -- use separate schemas for read/write)
- Computed fields use Pydantic's `@computed_field` decorator
- Validation uses `@field_validator` with `@classmethod`
- No `create()` method on the schema -- creation logic lives in the controller

---

## Views to Controllers

### DRF APIView

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = UserSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

### django-matt Controller

```python
from django_matt import MattAPI, APIController, IsAuthenticated
from django_matt.core.errors import NotFoundError

api = MattAPI()


@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/{user_id}", response_model=UserSchema)
    async def get_user(self, user_id: int) -> UserSchema:
        try:
            user = await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError("User not found")
        return UserSchema.from_orm(user)

    @api.put("/{user_id}", response_model=UserSchema)
    async def update_user(self, user_id: int, data: UserUpdateSchema) -> UserSchema:
        try:
            user = await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError("User not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await user.asave()

        return UserSchema.from_orm(user)

    @api.delete("/{user_id}")
    async def delete_user(self, user_id: int):
        try:
            user = await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError("User not found")

        await user.adelete()
        return {"deleted": True}
```

**Key differences:**
- Async by default -- use `aget()`, `asave()`, `adelete()`
- Errors are exceptions, not manual `Response` objects
- Pydantic schema parameter auto-parses the request body
- No manual `is_valid()` calls -- Pydantic validates on construction
- Route decorators on the `api` instance, not HTTP method names as function names

---

## ViewSets to APIViewSet

### DRF ModelViewSet

```python
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response


class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return ProductCreateSerializer
        return ProductSerializer

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.is_active = False
        product.save()
        return Response({'status': 'archived'})
```

### django-matt APIViewSet

```python
from django_matt.views import (
    APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView,
)
from django_matt import IsAuthenticated


class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    permission_classes = [IsAuthenticated]

    list = ListView(
        filterset_fields=['category', 'is_active'],
        search_fields=['name', 'description'],
        ordering_fields=['price', 'created_at'],
    )
    create = CreateView(request_schema=ProductCreateSchema)
    read = ReadView()
    update = UpdateView(request_schema=ProductUpdateSchema)
    delete = DeleteView()


# Custom actions as standalone endpoints
@api.post("/products/{product_id}/archive")
@jwt_required
async def archive_product(request, product_id: int):
    try:
        product = await Product.objects.aget(id=product_id)
    except Product.DoesNotExist:
        raise NotFoundError("Product not found")

    product.is_active = False
    await product.asave()
    return {"status": "archived"}
```

**Key differences:**
- Each CRUD operation is a composable view object, not implicit from the base class
- Different schemas per operation via `request_schema` parameter
- Filtering/search/ordering configured on `ListView` directly
- Custom actions are standalone endpoints (no `@action` decorator)
- Lifecycle hooks available: `before_create`, `after_create`, `on_error`, etc.

---

## Authentication

### DRF JWT (djangorestframework-simplejwt)

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# urls.py
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
]
```

### django-matt JWT

```python
# settings.py
DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": 3600,       # 60 minutes in seconds
    "REFRESH_TOKEN_LIFETIME": 604800,    # 7 days in seconds
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]

# api.py
from django_matt.auth import AuthController

api.register_controller(AuthController)
# Provides: POST /auth/login, /auth/register, /auth/refresh, /auth/logout
# Plus:     GET  /auth/me
```

django-matt also includes OAuth (Google, GitHub, Apple, Microsoft), SSO (SAML, OIDC), Passkeys/WebAuthn, Magic Links, API Keys, and RBAC -- all built in.

---

## Permissions

### DRF Permissions

```python
from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.is_staff
```

### django-matt Permissions

```python
from django_matt.permissions import BasePermission


class IsOwner(BasePermission):
    async def has_permission(self, request, view) -> bool:
        return True

    async def has_object_permission(self, request, view, obj) -> bool:
        return obj.owner_id == request.user.id


class IsAdminOrReadOnly(BasePermission):
    async def has_permission(self, request, view) -> bool:
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.is_staff
```

You can also use decorators for one-off permission checks:

```python
from django_matt.auth import jwt_required, with_roles, with_permission

@api.delete("/users/{user_id}")
@jwt_required
@with_roles("admin")
async def delete_user(request, user_id: int):
    ...
```

Built-in permission classes: `AllowAny`, `IsAuthenticated`, `IsAdmin`, `IsStaff`, `IsSuperUser`, `IsOwner`, `HasRole`, `HasPermission`.

---

## Pagination

### DRF Pagination

```python
from rest_framework.pagination import PageNumberPagination, CursorPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductViewSet(ModelViewSet):
    pagination_class = StandardPagination
```

### django-matt Pagination

```python
from django_matt.pagination import PageNumberPagination, CursorPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductViewSet(APIViewSet):
    list = ListView(pagination_class=StandardPagination)
```

Available pagination classes: `PageNumberPagination`, `LimitOffsetPagination`, `CursorPagination`.

---

## Filtering

### DRF Filtering (django-filter)

```python
from django_filters import rest_framework as filters


class ProductFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = ['category', 'is_active']


class ProductViewSet(ModelViewSet):
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']
```

### django-matt Filtering

```python
from django_matt.filtering import FilterSet, IntegerFilter


class ProductFilter(FilterSet):
    min_price = IntegerFilter(field_name="price", lookup_expr="gte")
    max_price = IntegerFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = ['category', 'is_active']


class ProductViewSet(APIViewSet):
    list = ListView(
        filterset_class=ProductFilter,
        search_fields=['name', 'description'],
        ordering_fields=['price', 'created_at'],
    )
```

Built-in filter types: `CharFilter`, `IntegerFilter`, `BooleanFilter`, `DateFilter`, `DateTimeFilter`, `InFilter`. Plus `PostgresSearchBackend` for full-text search.

---

## Throttling

### DRF Throttling

```python
from rest_framework.throttling import UserRateThrottle

class BurstRateThrottle(UserRateThrottle):
    rate = '60/min'

class ProductViewSet(ModelViewSet):
    throttle_classes = [BurstRateThrottle]
```

### django-matt Throttling

```python
# settings.py
DJANGO_MATT = {
    "THROTTLE_RATES": {
        "burst": "60/min",
        "sustained": "1000/day",
    }
}

# In views or controllers, throttling is configurable per-route or globally.
```

---

## URL Configuration

### DRF Router

```python
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('products', ProductViewSet)
router.register('users', UserViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
```

### django-matt URLs

```python
from django_matt import MattAPI

api = MattAPI(title="My API", version="1.0.0")

# Controllers auto-register their routes
@api.controller("/products")
class ProductController(APIController):
    ...

@api.controller("/users")
class UserController(APIController):
    ...

# urls.py
urlpatterns = [
    path('api/', api.urls),
]
```

---

## Error Handling

### DRF Exceptions

```python
from rest_framework.exceptions import NotFound, ValidationError

def my_view(request):
    if not user:
        raise NotFound(detail="User not found")
    if invalid_data:
        raise ValidationError({"email": "Invalid email format"})
```

### django-matt Errors

```python
from django_matt.core.errors import (
    NotFoundError,
    ValidationError,
    UnauthorizedError,
    ForbiddenError,
)

async def my_view(request):
    if not user:
        raise NotFoundError("User not found")
    if invalid_data:
        raise ValidationError("Invalid email format", field="email")
```

Errors are automatically converted to JSON responses with appropriate status codes. In debug mode, responses include tracebacks and code snippets.

---

## Testing

### DRF Test Client

```python
from rest_framework.test import APIClient

class TestUserAPI:
    def test_list_users(self):
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get('/api/users/')
        assert response.status_code == 200
        assert len(response.data) == 3
```

### django-matt AsyncAPITestClient

```python
from django_matt.testing import AsyncAPITestClient

class TestUserAPI:
    async def test_list_users(self):
        client = AsyncAPITestClient(api)
        await client.force_authenticate(user)
        response = await client.get('/api/users/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
```

django-matt also provides built-in assertions:

```python
from django_matt.testing import (
    assert_status,
    assert_created,
    assert_not_found,
    assert_validation_error,
    assert_contains_keys,
    assert_query_count,
)

async def test_create_user(self):
    response = await client.post('/api/users/', json=payload)
    assert_created(response)
    assert_contains_keys(response.json(), ['id', 'email'])
```

---

## Complete Before/After Example

Here is a small DRF app converted to django-matt.

### Before: DRF

```python
# serializers.py
from rest_framework import serializers

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'completed', 'created_at']
        read_only_fields = ['id', 'created_at']

class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['title']

# views.py
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        return TaskSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

# urls.py
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('tasks', TaskViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]

# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
```

### After: django-matt

```python
# schemas.py
from django_matt import ModelSchema

class TaskSchema(ModelSchema):
    class Meta:
        model = Task
        fields = ['id', 'title', 'completed', 'created_at']

class TaskCreateSchema(ModelSchema):
    class Meta:
        model = Task
        fields = ['title']

# api.py
from django_matt import MattAPI
from django_matt.auth import AuthController

api = MattAPI(title="Task API", version="1.0.0")
api.register_controller(AuthController)

# views.py
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
from django_matt.views.hooks import before_create

class TaskViewSet(APIViewSet):
    api = api
    model = Task
    default_response_schema = TaskSchema

    list = ListView()
    create = CreateView(request_schema=TaskCreateSchema)
    read = ReadView()
    update = UpdateView(request_schema=TaskCreateSchema)
    delete = DeleteView()

    def get_queryset(self, request):
        return Task.objects.filter(owner=request.user)

    async def before_create(self, request, data):
        data["owner_id"] = request.user.id
        return data

# urls.py
urlpatterns = [
    path('api/', api.urls),
]

# settings.py
DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": 3600,
    "REFRESH_TOKEN_LIFETIME": 604800,
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]
```

---

## Migration Strategy

### Phase 1: Install and Configure

Add `django_matt` to `INSTALLED_APPS` alongside DRF. Configure JWT settings.

### Phase 2: New Endpoints with django-matt

Build new features with django-matt while existing DRF endpoints keep working:

```python
# urls.py
urlpatterns = [
    path('api/v1/', include('old_api.urls')),   # DRF
    path('api/v2/', api.urls),                   # django-matt
]
```

### Phase 3: Migrate Incrementally

Convert one endpoint at a time. Run tests after each conversion.

### Phase 4: Remove DRF

```bash
uv remove djangorestframework djangorestframework-simplejwt django-filter
```

Remove `rest_framework` from `INSTALLED_APPS`.

---

## Common Gotchas

### 1. Async ORM

DRF views are sync. django-matt is async-first. Use Django's async ORM methods:

```python
# DRF (sync)
user = User.objects.get(id=user_id)
user.save()

# django-matt (async)
user = await User.objects.aget(id=user_id)
await user.asave()
```

For querysets: `.all()` returns a lazy queryset (safe in async). Use `async for` to iterate:

```python
async for user in User.objects.filter(is_active=True):
    ...
```

### 2. Request Body Parsing

```python
# DRF -- manual parsing
data = request.data  # Already parsed by DRF

# django-matt -- Pydantic schema as parameter (auto-parsed)
async def create(self, data: CreateSchema):
    ...  # data is already a validated Pydantic model
```

### 3. Response Format

```python
# DRF
return Response({"key": "value"}, status=201)

# django-matt -- return dict or tuple
return {"key": "value"}          # 200 by default
return 201, {"key": "value"}     # explicit status
```

### 4. No `serializer.save()`

django-matt schemas are pure validation/serialization. Object creation is explicit:

```python
# DRF
serializer.save(owner=request.user)

# django-matt
instance = await Task.objects.acreate(**data.model_dump(), owner=request.user)
```

### 5. Nested Serializers

```python
# DRF
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

# django-matt -- use Pydantic model composition
class OrderItemSchema(ModelSchema):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'price']

class OrderSchema(ModelSchema):
    items: list[OrderItemSchema] = []

    class Meta:
        model = Order
        fields = ['id', 'total', 'created_at']
```

---

## Next Steps

- [Authentication Guide](../auth/overview.md) -- Configure JWT, OAuth, SSO, Passkeys
- [CRUD Views](../features/views.md) -- Use APIViewSet for rapid development
- [Testing](../testing/client.md) -- Write async tests with AsyncAPITestClient
- [Migration from Django Ninja](from-django-ninja.md) -- If also using Ninja
- [Framework Comparison](../comparison.md) -- See how django-matt compares
