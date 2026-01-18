# Quick Start

This guide will help you create your first API with django-matt in 5 minutes.

## 1. Create a Django Project

```bash
# Create a new project
django-admin startproject myproject
cd myproject

# Install django-matt
uv add "django-matt[auth]"
```

## 2. Configure Django

Edit `myproject/settings.py`:

```python
INSTALLED_APPS = [
    ...
    'django_matt',
]

# JWT Configuration (optional)
DJANGO_MATT_JWT = {
    "SECRET_KEY": "your-secret-key",  # Use Django's SECRET_KEY in production
    "ACCESS_TOKEN_LIFETIME": 3600,     # 1 hour
    "REFRESH_TOKEN_LIFETIME": 86400 * 7,  # 7 days
}
```

## 3. Create Your API

Create `myproject/api.py`:

```python
from django_matt import MattAPI
from django_matt.auth import jwt_required
from pydantic import BaseModel

api = MattAPI(title="My API", version="1.0.0")


# Simple endpoint
@api.get("/hello")
async def hello(request):
    return {"message": "Hello, World!"}


# With request validation
class CreateUserSchema(BaseModel):
    email: str
    name: str


@api.post("/users")
async def create_user(request, data: CreateUserSchema):
    # data is validated automatically
    return {"email": data.email, "name": data.name}


# Protected endpoint
@api.get("/me")
@jwt_required
async def get_current_user(request):
    return {"user": request.user.email}
```

## 4. Add URL Configuration

Edit `myproject/urls.py`:

```python
from django.urls import path
from .api import api

urlpatterns = [
    path("api/", api.urls),
]
```

## 5. Run the Server

```bash
python manage.py runserver
```

Visit:

- **API**: http://localhost:8000/api/hello
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## Next Steps

- [Authentication](../auth/overview.md) - Set up JWT, sessions, or API keys
- [Controllers](../core/controllers.md) - Organize endpoints into classes
- [CRUD Views](../features/views.md) - Auto-generate CRUD endpoints
- [Type Generation](../typegen/typescript.md) - Generate TypeScript types
