# startapi Command

Generate a new Django project with django-matt API configuration.

## Synopsis

```bash
python manage.py startapi NAME [OPTIONS]
```

Or use as a standalone command:

```bash
python -m django_matt startapi NAME [OPTIONS]
```

## Description

The `startapi` command creates a complete Django Matt API project with:

- Pre-configured Django settings
- API app structure with controllers, schemas, and models
- Authentication setup (JWT, OAuth, magic links)
- Optional Docker configuration
- Optional frontend scaffolding (React, Swift)
- Makefile with common commands
- README with getting started instructions

## Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Name of the project to create |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--directory` | Current directory | Directory to create the project in |
| `--api-app` | `api` | Name of the API app to create |
| `--db` | `postgres` | Database: `postgres`, `mysql`, `sqlite` |
| `--template`, `-t` | `starter` | Template: `starter`, `b2b`, `b2c` |
| `--auth`, `-a` | `jwt` | Auth: `none`, `jwt`, `magic-link`, `oauth`, `all` |
| `--frontend`, `-f` | `none` | Frontend: `none`, `react-vite`, `swift` |
| `--docker` | `false` | Include Docker configuration |
| `--with-example` | `false` | Include example models and controllers |
| `--force` | `false` | Overwrite existing files |

## Templates

### starter

Basic API template with minimal setup:

- Single `api` app
- Basic URL routing
- Health check endpoint

Best for: Learning, small projects, APIs without complex requirements.

### b2b

Multi-tenant B2B template with organizations and teams:

- Multi-tenancy middleware
- Organization model
- Team model with memberships
- Invitation system
- Role-based access control

Best for: SaaS applications, enterprise software, team collaboration tools.

### b2c

Consumer-facing template with user features:

- User profiles
- Email verification
- Password reset
- Social login ready

Best for: Consumer apps, social platforms, marketplaces.

## Examples

### Basic Project

```bash
python manage.py startapi myproject
```

Creates a minimal API project with JWT authentication.

### B2B SaaS Project

```bash
python manage.py startapi saasapp \
  --template b2b \
  --auth all \
  --docker
```

Creates a multi-tenant SaaS project with all authentication methods and Docker support.

### Full-Stack Project with React

```bash
python manage.py startapi fullstack \
  --template b2c \
  --auth jwt \
  --frontend react-vite \
  --docker
```

Creates a full-stack project with React frontend and Docker.

### iOS Backend

```bash
python manage.py startapi iosbackend \
  --auth jwt \
  --frontend swift
```

Creates a backend ready for iOS app development with Swift type generation.

### Learning/Development

```bash
python manage.py startapi playground \
  --db sqlite \
  --with-example
```

Creates a simple project with SQLite and example code for learning.

## Generated Project Structure

=== "Basic (starter)"

    ```
    myproject/
    ├── myproject/
    │   ├── __init__.py
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── api/
    │   ├── __init__.py
    │   ├── apps.py
    │   ├── urls.py
    │   ├── controllers/
    │   ├── models/
    │   └── schemas/
    ├── manage.py
    ├── Makefile
    └── README.md
    ```

=== "With Docker"

    ```
    myproject/
    ├── myproject/
    ├── api/
    ├── manage.py
    ├── Dockerfile
    ├── docker-compose.yml
    ├── .env.example
    ├── .dockerignore
    ├── Makefile
    └── README.md
    ```

=== "With React Frontend"

    ```
    myproject/
    ├── myproject/
    ├── api/
    ├── frontend/
    │   ├── src/
    │   │   ├── api/
    │   │   │   └── client.ts
    │   │   ├── types/
    │   │   │   └── api.ts
    │   │   ├── App.tsx
    │   │   └── main.tsx
    │   ├── package.json
    │   ├── vite.config.ts
    │   └── tsconfig.json
    ├── manage.py
    ├── Makefile
    └── README.md
    ```

=== "With Swift"

    ```
    myproject/
    ├── myproject/
    ├── api/
    ├── ios/
    │   ├── Sources/
    │   │   └── API/
    │   │       ├── APIClient.swift
    │   │       └── Models.swift
    │   └── Package.swift
    ├── manage.py
    ├── Makefile
    └── README.md
    ```

## Generated Settings

The command configures Django settings with django-matt:

```python
# settings.py

INSTALLED_APPS = [
    "django_matt",
    "api",
    # ... Django apps
]

# JWT Configuration
DJANGO_MATT_JWT = {
    "SECRET_KEY": "change-me-in-production",
    "ACCESS_TOKEN_LIFETIME": 60 * 15,  # 15 minutes
    "REFRESH_TOKEN_LIFETIME": 60 * 60 * 24 * 7,  # 7 days
    "ALGORITHM": "HS256",
}
```

For B2B template, additional settings:

```python
# B2B Multi-Tenant Configuration
DJANGO_MATT_MULTITENANCY = {
    "ENABLED": True,
    "TENANT_HEADER": "X-Organization-ID",
    "TENANT_URL_KWARG": "org_slug",
    "REQUIRE_TENANT": True,
    "EXEMPT_PATHS": ["/auth/", "/health/", "/docs/"],
}
```

## Generated Example Code

When using `--with-example` or non-starter templates, the command generates example code:

### Example Model

```python
# api/models/task.py
import uuid
from django.db import models

class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
```

### Example Schema

```python
# api/schemas/task.py
from pydantic import Field
from django_matt.core.schema import Schema

class TaskBase(Schema):
    title: str
    description: str | None = None
    completed: bool = False

class TaskCreate(TaskBase):
    pass

class Task(TaskBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
```

### Example Controller

```python
# api/controllers/task.py
from django_matt.core.controller import CRUDController
from django_matt.core.router import get, post, put, delete

class TaskController(CRUDController):
    prefix = "tasks/"
    model = Task
    schema = TaskSchema
    create_schema = TaskCreate

    @get("")
    async def get_tasks(self, request):
        return await self.list(request)

    @post("")
    async def create_task(self, request, data: TaskCreate):
        return await self.create(request, data)
```

## Next Steps After Creation

The command prints next steps:

```
Successfully created django-matt API project myproject

Next steps:
  cd myproject
  python manage.py migrate
  python manage.py runserver_hot

For the frontend:
  cd frontend && bun install && bun dev
```

### With Docker

```bash
cd myproject
make up          # Start with Docker
make migrate     # Run migrations
```

### Without Docker

```bash
cd myproject
python manage.py migrate
python manage.py runserver_hot
```

## Tips and Best Practices

!!! tip "Start Simple"
    Start with `--template starter` and add complexity as needed.
    You can always add multi-tenancy or authentication later.

!!! tip "Use Docker for Production"
    Always use `--docker` for production deployments.
    The generated Docker configuration is production-ready.

!!! tip "Environment Variables"
    After creation, copy `.env.example` to `.env` and configure:
    ```bash
    cp .env.example .env
    # Edit .env with your settings
    ```

!!! warning "Change Secrets"
    Always change the default `SECRET_KEY` and `JWT_SECRET_KEY` before deployment:
    ```bash
    python -c "import secrets; print(secrets.token_hex(32))"
    ```

## See Also

- [CLI: matt new api](../cli/generate.md#matt-new-api)
- [Templates Documentation](../templates.md)
- [Authentication Setup](../auth/overview.md)
- [Multi-tenancy Guide](../multitenancy/overview.md)
