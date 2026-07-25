# Migrating from DRF to django-matt

Side-by-side reference for developers moving from Django REST Framework. Each section shows DRF on the left/top and django-matt on the right/bottom.

---

## 1. Installation

**DRF**
```bash
uv add djangorestframework djangorestframework-simplejwt django-filter
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    "rest_framework",
    "django_filters",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}
```

**django-matt**
```bash
# Remove DRF packages (or keep during gradual migration)
uv remove djangorestframework djangorestframework-simplejwt django-filter

uv add django-matt
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    "django_matt",
]

DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": 3600,    # seconds
    "REFRESH_TOKEN_LIFETIME": 604800, # 7 days
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]
```

---

## 2. Serializers → Schemas

### ModelSerializer → ModelSchema

**DRF**
```python
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "username", "full_name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
```

**django-matt**
```python
from django_matt import ModelSchema
from pydantic import computed_field

class UserSchema(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name", "created_at"]

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

### Plain Serializer → Pydantic BaseModel

**DRF**
```python
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8)
    remember_me = serializers.BooleanField(default=False)
```

**django-matt**
```python
from pydantic import BaseModel, EmailStr

class LoginSchema(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False
```

### Field declarations

| DRF | django-matt |
|-----|-------------|
| `CharField(max_length=100)` | `name: str` (Pydantic `Field(max_length=100)`) |
| `IntegerField(min_value=0)` | `count: int` (Pydantic `Field(ge=0)`) |
| `BooleanField(default=True)` | `active: bool = True` |
| `SerializerMethodField()` | `@computed_field @property` |
| `write_only=True` | separate request/response schemas |
| `read_only_fields = [...]` | separate read schema (omit fields) |

### Validation

**DRF**
```python
class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "username", "password"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already in use")
        return value

    def validate(self, attrs):
        if attrs["username"] == attrs["email"]:
            raise serializers.ValidationError("Username cannot equal email")
        return attrs
```

**django-matt**
```python
from django_matt import ModelSchema
from pydantic import BaseModel, field_validator, model_validator

class UserCreateSchema(BaseModel):
    email: str
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("email")
    @classmethod
    def email_unique(cls, v: str) -> str:
        if User.objects.filter(email=v).exists():
            raise ValueError("Email already in use")
        return v

    @model_validator(mode="after")
    def username_not_email(self) -> "UserCreateSchema":
        if self.username == self.email:
            raise ValueError("Username cannot equal email")
        return self
```

### Nested serializers

**DRF**
```python
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "quantity", "price"]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "total", "items", "created_at"]
```

**django-matt**
```python
class OrderItemSchema(ModelSchema):
    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "quantity", "price"]

class OrderSchema(ModelSchema):
    items: list[OrderItemSchema] = []

    class Meta:
        model = Order
        fields = ["id", "total", "created_at"]
```

---

## 3. APIView / GenericAPIView → APIController

**DRF**
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response(UserSerializer(user).data)

    def patch(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        serializer = UserSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        user.delete()
        return Response(status=204)
```

**django-matt**
```python
from django_matt import DjangoMattAPI, APIController
from django_matt.permissions import IsAuthenticated
from django_matt.core.errors import NotFoundError

api = DjangoMattAPI()

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

    @api.patch("/{user_id}", response_model=UserSchema)
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
        return 204, {}
```

Key differences:
- Methods are named freely; route is declared via `@api.get/post/patch/delete`
- Errors are raised exceptions, not manual `Response` objects
- `data: Schema` parameter auto-parses and validates the request body — no `is_valid()` call
- All handlers are `async`; use `aget()`, `asave()`, `adelete()`
- Return a dict or `(status_code, dict)` tuple instead of `Response(...)`

---

## 4. ViewSets → APIViewSet

**DRF**
```python
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class ProductViewSet(ModelViewSet):
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return ProductCreateSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.is_active = False
        product.save()
        return Response({"status": "archived"})
```

**django-matt**
```python
from django_matt.views import (
    APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView,
)
from django_matt.permissions import IsAuthenticated

class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    permission_classes = [IsAuthenticated]

    list = ListView(
        filterset_fields=["category", "is_active"],
        search_fields=["name", "description"],
        ordering_fields=["price", "created_at"],
    )
    create = CreateView(request_schema=ProductCreateSchema)
    read = ReadView()
    update = UpdateView(request_schema=ProductUpdateSchema)
    delete = DeleteView()

    def get_queryset(self, request):
        return Product.objects.select_related("category").all()

    async def before_create(self, request, data: dict) -> dict:
        data["owner_id"] = request.user.id
        return data


# Custom action — standalone endpoint
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

Key differences:
- Each CRUD operation is a composable view object (`ListView`, `CreateView`, etc.)
- Per-operation schemas via `request_schema` — no `get_serializer_class()`
- `before_create` / `after_create` lifecycle hooks replace `perform_create`
- Custom actions become standalone `@api.post(...)` endpoints
- `get_queryset(request)` receives the request as an explicit argument

---

## 5. Authentication

**DRF (djangorestframework-simplejwt)**
```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

# urls.py
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view()),
    path("api/token/refresh/", TokenRefreshView.as_view()),
]

# views.py
from rest_framework.permissions import IsAuthenticated
class MyView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({"user": str(request.user)})
```

**django-matt**
```python
# settings.py
DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": 3600,
    "REFRESH_TOKEN_LIFETIME": 604800,
    "ROTATE_REFRESH_TOKENS": True,
}
MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]

# api.py — AuthController provides login, register, refresh, logout, /me
from django_matt.auth import AuthController
api.register_controller(AuthController)
# Registers: POST /auth/login, /auth/register, /auth/refresh, /auth/logout
#            GET  /auth/me

# views.py
from django_matt.auth import jwt_required, jwt_optional

@api.get("/profile")
@jwt_required
async def profile(request):
    return {"user": request.user.email}

@api.get("/public-feed")
@jwt_optional          # request.user may be AnonymousUser
async def public_feed(request):
    ...
```

django-matt also ships OAuth (Google/GitHub/Apple/Microsoft), SSO (SAML/OIDC), Passkeys/WebAuthn, Magic Links, and API Keys out of the box — no extra packages.

---

## 6. Permissions

**DRF**
```python
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser

class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_staff

# Usage
class ArticleViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwner]
```

**django-matt**
```python
from django_matt.permissions import BasePermission, IsAuthenticated, IsAdmin, IsOwner

# Built-ins: AllowAny, IsAuthenticated, IsAdmin, IsStaff, IsSuperUser,
#            IsOwner, HasRole, HasPermission

class IsAdminOrReadOnly(BasePermission):
    async def has_permission(self, request, view) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_staff

# Class-level
class ArticleController(APIController):
    permission_classes = [IsAuthenticated, IsOwner]

# Decorator-level (one-off)
from django_matt.auth import jwt_required, requires_role, requires_permission

@api.delete("/articles/{article_id}")
@jwt_required
@requires_role("admin")
async def delete_article(request, article_id: int):
    ...

@api.post("/articles/{article_id}/publish")
@jwt_required
@requires_permission("articles.publish")
async def publish_article(request, article_id: int):
    ...
```

Permission methods are `async` in django-matt. `IsOwner` is built-in and checks `obj.owner_id == request.user.id` by default.

---

## 7. Pagination

**DRF**
```python
from rest_framework.pagination import (
    PageNumberPagination, LimitOffsetPagination, CursorPagination
)

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

class ProductViewSet(ModelViewSet):
    pagination_class = StandardPagination
```

**django-matt**
```python
from django_matt.pagination import PageNumberPagination, LimitOffsetPagination, CursorPagination

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

class ProductViewSet(APIViewSet):
    list = ListView(pagination_class=StandardPagination)
```

Or configure globally:

```python
# settings.py
DJANGO_MATT = {
    "DEFAULT_PAGINATION_CLASS": "django_matt.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}
```

| DRF class | django-matt class |
|-----------|------------------|
| `PageNumberPagination` | `django_matt.pagination.PageNumberPagination` |
| `LimitOffsetPagination` | `django_matt.pagination.LimitOffsetPagination` |
| `CursorPagination` | `django_matt.pagination.CursorPagination` |

---

## 8. Filtering

**DRF (django-filter)**
```python
import django_filters
from django_filters.rest_framework import DjangoFilterBackend

class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Product
        fields = ["category", "is_active"]

class ProductViewSet(ModelViewSet):
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at"]
    ordering = ["-created_at"]
```

**django-matt**
```python
from django_matt.filtering import FilterSet, NumberFilter, CharFilter

class ProductFilter(FilterSet):
    min_price = NumberFilter(field_name="price", lookup_expr="gte")
    max_price = NumberFilter(field_name="price", lookup_expr="lte")
    name = CharFilter(lookup_expr="icontains")

    class Meta:
        model = Product
        fields = ["category", "is_active"]

class ProductViewSet(APIViewSet):
    list = ListView(
        filterset_class=ProductFilter,
        search_fields=["name", "description"],
        ordering_fields=["price", "created_at"],
        ordering=["-created_at"],
    )
```

Built-in filter types: `CharFilter`, `NumberFilter`, `IntegerFilter`, `BooleanFilter`, `DateFilter`, `DateTimeFilter`, `InFilter`, `UUIDFilter`. Full-text search via `PostgresSearchBackend` (no separate package needed).

---

## 9. Routers

**DRF**
```python
from rest_framework.routers import DefaultRouter, SimpleRouter

router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("users", UserViewSet)
router.register("orders", OrderViewSet, basename="order")

# urls.py
from django.urls import path, include
urlpatterns = [
    path("api/", include(router.urls)),
]
```

**django-matt — APIViewSet (automatic registration)**
```python
# Each APIViewSet registers itself via its `api` attribute
class ProductViewSet(APIViewSet):
    api = api
    model = Product
    ...

class UserViewSet(APIViewSet):
    api = api
    model = User
    ...

# urls.py
from django.urls import path
urlpatterns = [
    path("api/", api.urls),
]
```

**django-matt — APIController (manual registration)**
```python
from django_matt import DjangoMattAPI, APIController

api = DjangoMattAPI(title="My API", version="1.0.0")

@api.controller("/products", tags=["Products"])
class ProductController(APIController):
    @api.get("/")
    async def list_products(self): ...

    @api.post("/")
    async def create_product(self, data: ProductCreateSchema): ...

# Or register explicitly:
api.register_controller(ProductController)
api.register_controller(UserController)
api.register_controller(OrderController)

# urls.py
urlpatterns = [
    path("api/", api.urls),
]
```

No router object — `api.urls` exposes all registered endpoints automatically. OpenAPI docs available at `/api/docs` and `/api/redoc`.

---

## 10. Testing

**DRF**
```python
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

class TestProductAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="secret123"
        )
        self.client.force_authenticate(user=self.user)

    def test_list_products(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_create_product(self):
        payload = {"name": "Widget", "price": "9.99", "category_id": 1}
        response = self.client.post("/api/products/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Widget")

    def test_unauthorized(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 401)
```

**django-matt**
```python
import pytest
from django_matt.testing import AsyncAPITestClient
from django_matt.testing import assert_ok, assert_created, assert_unauthorized

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.fixture
def client(api):
    return AsyncAPITestClient(api)

@pytest.fixture
async def auth_client(client, user):
    await client.force_authenticate(user)
    return client


async def test_list_products(auth_client):
    response = await auth_client.get("/api/products/")
    assert_ok(response)
    assert isinstance(response.json(), list)


async def test_create_product(auth_client):
    payload = {"name": "Widget", "price": "9.99", "category_id": 1}
    response = await auth_client.post("/api/products/", json=payload)
    assert_created(response)
    assert response.json()["name"] == "Widget"


async def test_unauthorized(client):
    response = await client.get("/api/products/")
    assert_unauthorized(response)
```

**Factory pattern**
```python
# DRF — typically django-model-bakery or factory_boy
from model_bakery import baker
product = baker.make("Product", price=9.99)

# django-matt — same libraries work; built-in factories also available
from django_matt.testing import ModelFactory

class ProductFactory(ModelFactory):
    class Meta:
        model = Product

    name = "Widget"
    price = 9.99
    is_active = True

product = await ProductFactory.acreate()
products = await ProductFactory.acreate_batch(5, category=category)
```

**Built-in assertions**

| Assertion | Checks |
|-----------|--------|
| `assert_ok(response)` | status 200 |
| `assert_created(response)` | status 201 |
| `assert_no_content(response)` | status 204 |
| `assert_bad_request(response)` | status 400 |
| `assert_unauthorized(response)` | status 401 |
| `assert_forbidden(response)` | status 403 |
| `assert_not_found(response)` | status 404 |
| `assert_contains_keys(data, keys)` | all keys present |
| `assert_query_count(n)` | context manager — asserts N DB queries |

---

## Migration Strategy

### Gradual migration — run DRF and django-matt side-by-side

```python
# urls.py
urlpatterns = [
    path("api/v1/", include("myapp.drf_urls")),  # existing DRF routes
    path("api/v2/", api.urls),                    # new django-matt routes
]
```

1. Install `django-matt` alongside `djangorestframework`
2. Build all new endpoints with django-matt
3. Migrate existing endpoints one controller at a time
4. Remove DRF when all routes are migrated:

```bash
uv remove djangorestframework djangorestframework-simplejwt django-filter dj-rest-auth
```

Remove `rest_framework` and `django_filters` from `INSTALLED_APPS`.

### Common gotchas

**Async ORM** — All django-matt handlers are async; use async ORM methods:
```python
# DRF (sync)                     # django-matt (async)
User.objects.get(id=pk)          await User.objects.aget(id=pk)
user.save()                      await user.asave()
user.delete()                    await user.adelete()
qs.filter(...).first()           await qs.filter(...).afirst()
```

**No `serializer.save()`** — Schemas validate only; persistence is explicit:
```python
# DRF
serializer.save(owner=request.user)

# django-matt
instance = await Product.objects.acreate(**data.model_dump(), owner=request.user)
```

**Response format** — Return dicts or `(status, dict)` tuples, not `Response` objects:
```python
# DRF
return Response({"key": "value"}, status=201)

# django-matt
return 201, {"key": "value"}
# or just return the schema/dict for 200
return UserSchema.from_orm(user)
```
