# Installation

This guide covers how to install django-matt and configure it for different use cases.

## Requirements

- **Python**: 3.12 or higher (3.13 recommended)
- **Django**: 5.2 or higher
- **Database**: PostgreSQL recommended (SQLite works for development)

## Package Manager Options

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is the recommended package manager for Python projects.

```bash
# Install with core dependencies
uv add django-matt

# Install with authentication extras
uv add "django-matt[auth]"

# Install with all extras
uv add "django-matt[all]"
```

## Installation Extras

django-matt provides optional extras for specific features:

| Extra | Description | Dependencies |
|-------|-------------|--------------|
| `auth` | JWT and session auth | `PyJWT`, `passlib`, `argon2-cffi` |
| `oauth` | OAuth providers | `httpx`, `authlib` |
| `passkeys` | WebAuthn support | `webauthn` |
| `sso` | Enterprise SSO | `python-saml`, `oic` |
| `billing` | Payment providers | `stripe`, `paypal-sdk` |
| `websockets` | Real-time features | `channels`, `daphne` |
| `tasks` | Background tasks | `celery` or `dramatiq` |
| `postgres` | PostgreSQL features | `psycopg[binary]`, `pgvector` |
| `performance` | Fast serialization | `orjson`, `ujson`, `redis` |
| `files` | File uploads, S3 | `boto3`, `python-multipart` |
| `testing` | Test utilities | `factory-boy`, `faker`, `pytest` |
| `docs` | Documentation | `mkdocs`, `mkdocs-material` |
| `full` | Common features | auth, performance, files |
| `all` | Everything | All of the above |

### Common Installation Combinations

```bash
# API with authentication
uv add "django-matt[auth,oauth]"

# B2B SaaS application
uv add "django-matt[auth,oauth,sso,billing]"

# Real-time application
uv add "django-matt[auth,websockets]"

# High-performance API
uv add "django-matt[auth,postgres,performance]"
```

## Django Configuration

After installation, add django-matt to your Django settings.

### Basic Configuration

```python
# settings.py

INSTALLED_APPS = [
    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # django-matt
    "django_matt",

    # Your apps
    "myapp",
]
```

### Full Configuration with All Features

```python
# settings.py

INSTALLED_APPS = [
    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # django-matt core
    "django_matt",

    # Optional: Multi-tenancy models
    "django_matt.multitenancy",

    # Optional: Billing models
    "django_matt.billing",

    # Optional: WebSockets (requires channels)
    "channels",

    # Your apps
    "myapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Optional: JWT authentication
    "django_matt.auth.JWTAuthenticationMiddleware",

    # Optional: Content negotiation
    "django_matt.negotiation.ContentNegotiationMiddleware",

    # Optional: Dependency injection
    "django_matt.di.DependencyInjectionMiddleware",

    # Optional: Multi-tenancy
    "django_matt.multitenancy.TenantMiddleware",
]
```

## Feature-Specific Configuration

### JWT Authentication

```python
# settings.py

DJANGO_MATT_JWT = {
    # Required: Secret key for signing tokens
    "SECRET_KEY": "your-secret-key-here",  # Use Django's SECRET_KEY in production

    # Token lifetimes (in seconds)
    "ACCESS_TOKEN_LIFETIME": 3600,  # 1 hour
    "REFRESH_TOKEN_LIFETIME": 604800,  # 7 days

    # Token settings
    "ALGORITHM": "HS256",
    "TOKEN_TYPE": "Bearer",

    # Optional: Audience and issuer
    "AUDIENCE": None,
    "ISSUER": None,

    # Token rotation
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

### OAuth Providers

```python
# settings.py

DJANGO_MATT_OAUTH = {
    "google": {
        "client_id": "your-google-client-id",
        "client_secret": "your-google-client-secret",
        "redirect_uri": "https://yourapp.com/auth/google/callback",
    },
    "github": {
        "client_id": "your-github-client-id",
        "client_secret": "your-github-client-secret",
        "redirect_uri": "https://yourapp.com/auth/github/callback",
    },
}
```

### Billing

```python
# settings.py

DJANGO_MATT_BILLING = {
    "default_provider": "stripe",

    "stripe": {
        "api_key": "sk_test_...",
        "webhook_secret": "whsec_...",
        "publishable_key": "pk_test_...",
    },

    "paypal": {
        "client_id": "your-paypal-client-id",
        "client_secret": "your-paypal-client-secret",
        "mode": "sandbox",  # or "live"
    },
}
```

### Multi-Tenancy

```python
# settings.py

DJANGO_MATT_MULTITENANCY = {
    "enabled": True,
    "tenant_model": "multitenancy.Organization",
    "tenant_header": "X-Tenant-ID",
    "auto_create_tenant": False,
}
```

## Database Setup

### PostgreSQL (Recommended)

```python
# settings.py

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myproject",
        "USER": "postgres",
        "PASSWORD": "password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# Optional: pgvector for AI/ML features
DJANGO_MATT_DATABASE = {
    "pgvector": True,
}
```

### SQLite (Development Only)

```python
# settings.py

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

## Running Migrations

After configuration, run migrations to create the necessary database tables:

```bash
# Create migrations for your app
python manage.py makemigrations

# Apply all migrations
python manage.py migrate
```

## Verifying Installation

Create a simple test to verify the installation:

```python
# test_installation.py
from django_matt import DjangoMattAPI, __version__

api = DjangoMattAPI(title="Test API", version="1.0.0")

@api.get("/test")
async def test(request):
    return {"status": "ok", "version": __version__}

print(f"django-matt {__version__} installed successfully!")
```

Run with:

```bash
python manage.py shell < test_installation.py
```

## Version Compatibility Matrix

| django-matt | Python | Django |
|-------------|--------|--------|
| 0.1.x | 3.12, 3.13 | 5.2 |
| 0.2.x | 3.12, 3.13, 3.14 | 6.0 |

!!! warning "Django 6.0 requires Python 3.12+"
    Django 6.0 dropped support for Python 3.10 and 3.11. If you need Python 3.11 support, stay on Django 5.2.

## Next Steps

- [Quick Start](quickstart.md) - Create your first API
- [Configuration](configuration.md) - Detailed configuration options
- [Authentication](../auth/overview.md) - Set up authentication
