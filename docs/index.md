# django-matt

A modern Django API framework with async support and developer experience tools.

## Overview

**django-matt** consolidates features from multiple packages into one cohesive library:

| Package | Feature | django-matt Module |
|---------|---------|-------------------|
| django-ninja | Core routing, OpenAPI | `django_matt.core` |
| django-ninja-extra | Class controllers, permissions, DI | `django_matt.core.controller` |
| django-ninja-jwt | JWT authentication | `django_matt.auth` |
| ninja-schema | ModelSchema for Django ORM | `django_matt.core.schema` |
| django-ninja-crud | Composable CRUD views | `django_matt.views` |

## Features

- **Async-first design** - Built for Python 3.11+ with full async/await support
- **Type-safe** - Pydantic schemas for request/response validation
- **Multiple auth methods** - JWT, Session, API Keys, OAuth, Passkeys, SSO
- **Automatic OpenAPI** - Swagger UI and ReDoc documentation
- **Type generation** - Generate TypeScript and Swift types from your schemas
- **Multi-tenancy** - Built-in B2B support with organizations and teams
- **Background tasks** - Celery, Dramatiq, or Django-Q2 backends
- **Billing integration** - Stripe, PayPal, and Polar support

## Quick Start

```python
from django_matt import MattAPI
from django_matt.auth import jwt_required

api = MattAPI()

@api.get("/hello")
async def hello(request):
    return {"message": "Hello, World!"}

@api.get("/protected")
@jwt_required
async def protected(request):
    return {"user": request.user.email}
```

## Installation

```bash
# Using uv (recommended)
uv add django-matt

# Using pip
pip install django-matt

# With all extras
uv add "django-matt[all]"
```

## Version Compatibility

| django-matt | Python | Django |
|-------------|--------|--------|
| 0.1.x | 3.11+ | 5.2+ |
| 0.2.x (planned) | 3.12+ | 6.0+ |

!!! note "Django 6.0 Support"
    Django 6.0 requires Python 3.12+. If you need Python 3.11 support, use Django 5.2.

## License

MIT License - see [LICENSE](https://github.com/mattjaikaran/django-matt/blob/main/LICENSE) for details.
