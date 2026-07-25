# Getting Started

Welcome to django-matt! This section will help you get up and running quickly.

## Quick Links

<div class="grid cards" markdown>

-   :material-download: **Installation**

    ---

    Install django-matt and configure your Django project.

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-rocket-launch: **Quick Start**

    ---

    Create your first API in 5 minutes.

    [:octicons-arrow-right-24: Quick Start](quickstart.md)

-   :material-cog: **Configuration**

    ---

    Configure authentication, billing, and more.

    [:octicons-arrow-right-24: Configuration](configuration.md)

</div>

## Prerequisites

Before you begin, ensure you have:

- **Python 3.12+** (3.13 recommended)
- **Django 5.2+** installed
- A Django project created

## Installation Overview

```bash
# Install with uv (recommended)
uv add django-matt
```

Add to your Django settings:

```python
INSTALLED_APPS = [
    ...
    'django_matt',
]
```

## Your First API

```python
# api.py
from django_matt import MattAPI

api = MattAPI(title="My API", version="0.9.0")

@api.get("/hello")
async def hello(request):
    return {"message": "Hello, World!"}
```

```python
# urls.py
from django.urls import path
from .api import api

urlpatterns = [
    path("api/", api.urls),
]
```

Visit `http://localhost:8000/api/docs` to see your API documentation.

## What's Next?

After completing the quick start, explore:

- [Core Concepts](../core/routing.md) - Learn about routing and controllers
- [Authentication](../auth/overview.md) - Add JWT, OAuth, or other auth methods
- [CRUD Views](../features/views.md) - Build CRUD endpoints quickly
- [Testing](../testing/client.md) - Write tests for your API
