# Migrating from Django REST Framework

This guide helps you migrate an existing Django REST Framework (DRF) application to django-matt. We'll cover the key differences and show equivalent patterns.

## Why Migrate?

| Feature | DRF | django-matt |
|---------|-----|-------------|
| Async support | Limited | Full async-first |
| Type hints | Partial | Complete |
| Schema validation | DRF Serializers | Pydantic v2 |
| Performance | Good | Better (orjson, streaming) |
| Auto-generated types | Via drf-spectacular | Built-in TS/Swift |
| Bundle size | Large | Smaller |
| Learning curve | Steep | Gentler |

## Installation

First, install django-matt alongside DRF for gradual migration:

```bash
uv add django-matt
```

Add to `INSTALLED_APPS` (you can keep DRF during migration):

```python
INSTALLED_APPS = [
    ...
    'rest_framework',  # Keep during migration
    'django_matt',
]
```

## Serializers to Schemas

### DRF Serializer

```python
# DRF way
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
# django-matt way
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
    def validate_email(cls, v: str) -> str:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(email=v).exists():
            raise ValueError('Email already exists')
        return v
```

## Views to Controllers

### DRF APIView

```python
# DRF way
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
# django-matt way
from django_matt import MattAPI, APIController, IsAuthenticated
from django_matt.core.errors import NotFoundError

api = MattAPI()


@api.controller("/users", tags=["Users"])
class UserController(APIController):
    permission_classes = [IsAuthenticated]

    @api.get("/{user_id}", response=UserSchema)
    async def get_user(self, user_id: int) -> UserSchema:
        try:
            user = await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError("User not found")
        return UserSchema.from_orm(user)

    @api.put("/{user_id}", response=UserSchema)
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

## ViewSets to APIViewSet

### DRF ModelViewSet

```python
# DRF way
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
# django-matt way
from django_matt.views import APIViewSet, ListView, CreateView, ReadView, UpdateView, DeleteView
from django_matt import IsAuthenticated


class ProductViewSet(APIViewSet):
    api = api
    model = Product
    default_response_schema = ProductSchema
    permission_classes = [IsAuthenticated]

    # List with filtering
    list = ListView(
        filterset_fields=['category', 'is_active'],
        search_fields=['name', 'description'],
        ordering_fields=['price', 'created_at'],
    )

    # Create with different schema
    create = CreateView(request_schema=ProductCreateSchema)

    # Read single item
    read = ReadView()

    # Update
    update = UpdateView(request_schema=ProductUpdateSchema)

    # Delete
    delete = DeleteView()


# Custom action as separate endpoint
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

## Authentication

### DRF JWT (via djangorestframework-simplejwt)

```python
# DRF way - settings.py
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
# django-matt way - settings.py
DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": 3600,  # 60 minutes
    "REFRESH_TOKEN_LIFETIME": 604800,  # 7 days
}

MIDDLEWARE = [
    ...
    "django_matt.auth.JWTAuthenticationMiddleware",
]

# api.py
from django_matt.auth import AuthController

# Register the built-in auth controller
api.register_controller(AuthController, prefix="/auth")
# Provides: /auth/login, /auth/register, /auth/refresh, /auth/logout, /auth/me
```

## Permissions

### DRF Permissions

```python
# DRF way
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
# django-matt way
from django_matt.permissions import BasePermission


class IsOwner(BasePermission):
    async def has_permission(self, request, view) -> bool:
        return True  # Object-level check

    async def has_object_permission(self, request, view, obj) -> bool:
        return obj.owner_id == request.user.id


class IsAdminOrReadOnly(BasePermission):
    async def has_permission(self, request, view) -> bool:
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user.is_staff
```

## Pagination

### DRF Pagination

```python
# DRF way
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# In ViewSet
class ProductViewSet(ModelViewSet):
    pagination_class = StandardPagination
```

### django-matt Pagination

```python
# django-matt way
from django_matt.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# In ViewSet
class ProductViewSet(APIViewSet):
    list = ListView(pagination_class=StandardPagination)
```

## URL Configuration

### DRF URLs with Router

```python
# DRF way
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
# django-matt way
from django_matt import MattAPI

api = MattAPI(title="My API", version="1.0.0")

# Register controllers
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

## Error Handling

### DRF Exceptions

```python
# DRF way
from rest_framework.exceptions import APIException, NotFound, ValidationError

def my_view(request):
    if not user:
        raise NotFound(detail="User not found")

    if invalid_data:
        raise ValidationError({"email": "Invalid email format"})
```

### django-matt Errors

```python
# django-matt way
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

## Migration Strategy

### Phase 1: Install and Configure

```python
# settings.py
INSTALLED_APPS = [
    ...
    'rest_framework',  # Keep existing
    'django_matt',     # Add new
]
```

### Phase 2: Create New Endpoints with django-matt

Build new features with django-matt while keeping existing DRF endpoints working.

```python
# old_api/urls.py (DRF - keep working)
urlpatterns = [
    path('api/v1/', include(router.urls)),
]

# new_api/api.py (django-matt)
api = MattAPI(title="My API v2", version="2.0.0")

# urls.py
urlpatterns = [
    path('api/v1/', include('old_api.urls')),  # DRF
    path('api/v2/', api.urls),                  # django-matt
]
```

### Phase 3: Migrate Endpoints Incrementally

Convert one endpoint at a time, test thoroughly.

### Phase 4: Remove DRF

Once all endpoints are migrated:

```bash
uv remove djangorestframework
uv remove djangorestframework-simplejwt
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    # 'rest_framework',  # Removed
    'django_matt',
]
```

## Common Gotchas

### 1. Async Views

DRF views are sync by default. django-matt is async-first:

```python
# DRF (sync)
def get(self, request):
    users = User.objects.all()
    return Response(UserSerializer(users, many=True).data)

# django-matt (async)
async def list_users(self):
    users = await User.objects.all().aiterator()
    return [UserSchema.from_orm(u) async for u in users]
```

### 2. Request Data Access

```python
# DRF
data = request.data  # Already parsed

# django-matt - use Pydantic schema parameter
async def create(self, data: CreateSchema):  # Automatically parsed
    ...
```

### 3. Response Format

```python
# DRF
return Response({"key": "value"}, status=201)

# django-matt
return 201, {"key": "value"}
# or
return {"key": "value"}  # 200 by default
```

## Next Steps

- [Authentication Guide](../auth/overview.md) - Configure JWT, OAuth, etc.
- [CRUD Views](../features/views.md) - Use APIViewSet for rapid development
- [Testing](../testing/client.md) - Write tests for your migrated endpoints
