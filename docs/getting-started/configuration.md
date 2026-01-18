# Configuration

django-matt uses Django settings for configuration. All settings are optional with sensible defaults.

## Core Settings

```python
# settings.py

# API Configuration
DJANGO_MATT = {
    "TITLE": "My API",
    "VERSION": "1.0.0",
    "DESCRIPTION": "My awesome API",
    "DOCS_URL": "/docs",
    "REDOC_URL": "/redoc",
    "OPENAPI_URL": "/openapi.json",
}
```

## Authentication Settings

### JWT Configuration

```python
DJANGO_MATT_JWT = {
    "SECRET_KEY": SECRET_KEY,  # Required
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": 3600,  # 1 hour
    "REFRESH_TOKEN_LIFETIME": 604800,  # 7 days
    "ISSUER": "my-app",
    "AUDIENCE": None,
}
```

### Session Configuration

```python
DJANGO_MATT_SESSION = {
    "COOKIE_NAME": "sessionid",
    "COOKIE_AGE": 1209600,  # 14 days
    "COOKIE_SECURE": True,
    "COOKIE_HTTPONLY": True,
    "COOKIE_SAMESITE": "Lax",
    "CSRF_ENABLED": True,
}
```

### API Key Configuration

```python
DJANGO_MATT_API_KEYS = {
    "HEADER_NAME": "X-API-Key",
    "QUERY_PARAM": "api_key",
    "RATE_LIMITS": {
        "free": "100/hour",
        "pro": "1000/hour",
        "enterprise": "10000/hour",
    },
}
```

## Background Tasks

```python
DJANGO_MATT_TASKS = {
    "BACKEND": "celery",  # "celery", "dramatiq", "django_q", "sync"
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
}
```

## File Storage

```python
DJANGO_MATT_FILES = {
    "STORAGE": "s3",  # "local", "s3", "r2", "minio"
    "S3_BUCKET": "my-bucket",
    "S3_REGION": "us-east-1",
    "MAX_UPLOAD_SIZE": 10 * 1024 * 1024,  # 10MB
}
```

## Performance

```python
DJANGO_MATT_PERFORMANCE = {
    "JSON_RENDERER": "orjson",  # "orjson", "ujson", "json"
    "CACHE_BACKEND": "redis",
    "CACHE_TTL": 300,
}
```

## Environment Variables

All settings can be overridden with environment variables:

```bash
DJANGO_MATT_JWT_SECRET_KEY=your-secret
DJANGO_MATT_JWT_ACCESS_TOKEN_LIFETIME=3600
DJANGO_MATT_TASKS_BACKEND=celery
```
