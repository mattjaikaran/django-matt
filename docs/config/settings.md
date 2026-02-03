# Settings Reference

Complete reference for all Django Matt configuration settings, including `DJANGO_MATT_*` settings and environment variables.

## DJANGO_MATT Settings

The main `DJANGO_MATT` dictionary in your settings controls framework behavior:

```python
DJANGO_MATT = {
    # Version info
    "VERSION": "0.1.0",

    # Performance settings
    "BENCHMARK_ENABLED": False,
    "BENCHMARK_HEADER": "X-Django-Matt-Timing",

    # Cache settings
    "CACHE_ENABLED": False,
    "CACHE_TIMEOUT": 300,  # 5 minutes
    "CACHE_KEY_PREFIX": "django_matt:",
    "CACHE_LOCK_TIMEOUT": 10,  # For stampede prevention

    # Database settings
    "DB_TYPE": "postgres",
    "DB_POOL_ENABLED": False,

    # Query optimization
    "QUERY_OPTIMIZATION_ENABLED": True,
    "N1_DETECTION_ENABLED": True,
    "QUERY_ANALYSIS_ENABLED": False,

    # Performance suggestions
    "SUGGESTIONS_ENABLED": False,
}
```

## Setting Descriptions

### Performance Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `BENCHMARK_ENABLED` | bool | `False` | Enable request timing and benchmarking |
| `BENCHMARK_HEADER` | str | `"X-Django-Matt-Timing"` | HTTP header name for timing information |

### Cache Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `CACHE_ENABLED` | bool | `False` | Enable response and result caching |
| `CACHE_TIMEOUT` | int | `300` | Default cache timeout in seconds |
| `CACHE_KEY_PREFIX` | str | `"django_matt:"` | Prefix for all cache keys |
| `CACHE_LOCK_TIMEOUT` | int | `10` | Lock timeout for stampede prevention |

### Database Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `DB_TYPE` | str | `"postgres"` | Database type (postgres, mysql, sqlite) |
| `DB_POOL_ENABLED` | bool | `False` | Enable connection pooling (Django 5.2+) |

### Query Optimization Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `QUERY_OPTIMIZATION_ENABLED` | bool | `True` | Enable automatic query optimization |
| `N1_DETECTION_ENABLED` | bool | `True` | Enable N+1 query detection warnings |
| `QUERY_ANALYSIS_ENABLED` | bool | `False` | Enable detailed query analysis logging |
| `SUGGESTIONS_ENABLED` | bool | `False` | Enable runtime performance suggestions |

## Environment Variables

### Core Django Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | None (required) | Django secret key |
| `DJANGO_ENV` | `"development"` | Environment name |
| `ALLOWED_HOSTS` | `""` | Comma-separated list of allowed hosts |
| `DEBUG` | `"False"` | Enable debug mode |

### Database Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_TYPE` | `"postgres"` | Database type |
| `DB_ENGINE` | Auto-detected | Full Django database engine path |
| `DB_NAME` | `"django_matt"` | Database name |
| `DB_USER` | `"postgres"` | Database user |
| `DB_PASSWORD` | `""` | Database password |
| `DB_HOST` | `"localhost"` | Database host |
| `DB_PORT` | `"5432"` | Database port |
| `DB_CONN_MAX_AGE` | `600` / `None` | Connection max age (None=persistent) |
| `DB_CONN_HEALTH_CHECKS` | `"True"` | Enable connection health checks |
| `DB_ATOMIC_REQUESTS` | `"False"` | Wrap requests in transactions |
| `DB_AUTOCOMMIT` | `"True"` | Enable autocommit |
| `DB_TIME_ZONE` | None | Database timezone |
| `DB_TEST_NAME` | None | Test database name |

### Connection Pooling (Django 5.2+)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_ENABLED` | `"False"` | Enable psycopg3 connection pooling |
| `DB_POOL_MIN_SIZE` | `5` | Minimum pool connections |
| `DB_POOL_MAX_SIZE` | `20` | Maximum pool connections |
| `DB_POOL_MAX_IDLE` | `300` | Max idle time in seconds |
| `DB_POOL_MAX_LIFETIME` | `3600` | Max connection lifetime |
| `DB_POOL_TIMEOUT` | `30` | Pool acquisition timeout |
| `DB_USE_PSYCOPG3` | Auto-detected | Use psycopg3 backend |

### pgvector Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_PGVECTOR_ENABLED` | `"False"` | Enable pgvector support |

### Cache Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_BACKEND` | `"auto"` | Cache backend (redis, memcached, locmem, file, auto) |
| `CACHE_TIMEOUT` | `300` | Default cache timeout |
| `CACHE_KEY_PREFIX` | `"django_matt"` | Cache key prefix |
| `REDIS_URL` | `"redis://localhost:6379/0"` | Redis connection URL |
| `REDIS_MAX_CONNECTIONS` | `50` | Maximum Redis connections |
| `MEMCACHED_LOCATION` | `"127.0.0.1:11211"` | Memcached server location |
| `CACHE_MIDDLEWARE_SECONDS` | `600` | Cache middleware timeout |

### Security Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CSRF_COOKIE_SECURE` | `"False"` | Secure CSRF cookie |
| `CSRF_TRUSTED_ORIGINS` | `""` | Comma-separated trusted origins |
| `SESSION_COOKIE_SECURE` | `"False"` | Secure session cookie |
| `SESSION_COOKIE_AGE` | `1209600` | Session cookie age (2 weeks) |
| `SESSION_ENGINE` | `"django.contrib.sessions.backends.db"` | Session backend |
| `SECURE_SSL_REDIRECT` | `"False"` | Redirect HTTP to HTTPS |
| `SECURE_HSTS_SECONDS` | `0` | HSTS header duration |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `"False"` | Include subdomains in HSTS |
| `SECURE_HSTS_PRELOAD` | `"False"` | Enable HSTS preload |
| `SECURE_PROXY_SSL_HEADER` | `"False"` | Trust X-Forwarded-Proto header |
| `PASSWORD_MIN_LENGTH` | `8` | Minimum password length |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATELIMIT_ENABLE` | `"True"` | Enable rate limiting |
| `RATELIMIT_USE_CACHE` | `"default"` | Cache backend for rate limits |
| `RATELIMIT_VIEW` | `"django_matt.views.ratelimited"` | Rate limit view |
| `RATELIMIT_FAIL_OPEN` | `"False"` | Allow requests if rate limiting fails |

### Performance Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_MATT_BENCHMARK_ENABLED` | `"False"` | Enable benchmarking |
| `DJANGO_MATT_BENCHMARK_HEADER` | `"X-Django-Matt-Timing"` | Timing header name |
| `DJANGO_MATT_CACHE_ENABLED` | `"True"` | Enable Django Matt caching |
| `DJANGO_MATT_QUERY_ANALYSIS_ENABLED` | `"False"` | Enable query analysis |
| `DJANGO_MATT_SUGGESTIONS_ENABLED` | `"False"` | Enable performance suggestions |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | `2621440` | Max upload memory size (2.5MB) |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | `2621440` | Max file upload memory size |
| `DATA_UPLOAD_MAX_NUMBER_FIELDS` | `1000` | Max form fields |

### Email Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_BACKEND` | Varies by env | Email backend class |
| `EMAIL_HOST` | `""` | SMTP host |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_HOST_USER` | `""` | SMTP username |
| `EMAIL_HOST_PASSWORD` | `""` | SMTP password |
| `EMAIL_USE_TLS` | `"True"` | Use TLS |
| `EMAIL_USE_SSL` | `"False"` | Use SSL |
| `DEFAULT_FROM_EMAIL` | `"noreply@example.com"` | Default from address |
| `SERVER_EMAIL` | Same as DEFAULT_FROM_EMAIL | Server email address |

### Static/Media Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `STATIC_URL` | `"/static/"` | Static files URL |
| `STATIC_ROOT` | `"/var/www/static"` | Static files directory |
| `MEDIA_URL` | `"/media/"` | Media files URL |
| `MEDIA_ROOT` | `"/var/www/media"` | Media files directory |
| `STATICFILES_STORAGE` | `"ManifestStaticFilesStorage"` | Static files storage backend |

### Logging Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SQL_LOG_LEVEL` | `"WARNING"` | SQL query log level (dev only) |

### Admin Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMINS` | `""` | Admin emails (format: `name:email,name2:email2`) |
| `MANAGERS` | `""` | Manager emails (same format) |

## Default Values by Environment

### Development

```python
DJANGO_MATT = {
    "BENCHMARK_ENABLED": True,
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 60,
    "N1_DETECTION_ENABLED": True,
    "QUERY_OPTIMIZATION_ENABLED": True,
}
```

### Staging

```python
DJANGO_MATT = {
    "BENCHMARK_ENABLED": True,
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 600,
    "N1_DETECTION_ENABLED": True,
    "QUERY_OPTIMIZATION_ENABLED": True,
}
```

### Production

```python
DJANGO_MATT = {
    "BENCHMARK_ENABLED": False,
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 3600,
    "N1_DETECTION_ENABLED": False,
    "QUERY_OPTIMIZATION_ENABLED": True,
}
```

## Accessing Settings at Runtime

```python
from django.conf import settings

# Access DJANGO_MATT settings
cache_enabled = settings.DJANGO_MATT.get("CACHE_ENABLED", False)
cache_timeout = settings.DJANGO_MATT.get("CACHE_TIMEOUT", 300)

# Or use getattr for safety
django_matt = getattr(settings, "DJANGO_MATT", {})
benchmark_enabled = django_matt.get("BENCHMARK_ENABLED", False)
```

## Overriding Settings

Settings can be overridden at multiple levels (in order of precedence):

1. **Environment variables** (highest priority)
2. **Extra settings passed to `configure()`**
3. **Environment-specific settings** (dev.py, staging.py, prod.py)
4. **Common settings** (common.py)
5. **Base settings** (lowest priority)

```python
from django_matt.config import configure

configure(
    environment="production",
    extra_settings={
        # These override everything else
        "DJANGO_MATT": {
            "CACHE_TIMEOUT": 7200,  # 2 hours
        },
    },
)
```
