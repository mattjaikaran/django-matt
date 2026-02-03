# Security Configuration

Django Matt provides comprehensive security settings following OWASP best practices, including CSRF protection, session security, HTTPS enforcement, and rate limiting.

## Quick Start

=== "Development"

    ```python
    # Relaxed security for local development
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    ```

=== "Production"

    ```python
    # Full security hardening
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    ```

## CSRF Protection

Cross-Site Request Forgery protection settings.

### Configuration

```python
# Cookie settings
CSRF_COOKIE_SECURE = True          # Only send over HTTPS
CSRF_COOKIE_HTTPONLY = True        # Not accessible via JavaScript
CSRF_COOKIE_SAMESITE = "Lax"       # SameSite policy

# Trusted origins for cross-origin requests
CSRF_TRUSTED_ORIGINS = [
    "https://example.com",
    "https://www.example.com",
    "https://api.example.com",
]
```

### Environment Variables

```bash
export CSRF_COOKIE_SECURE=true
export CSRF_TRUSTED_ORIGINS=https://example.com,https://api.example.com
```

### CSRF in APIs

For API endpoints that don't use sessions:

```python
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@api.post("/webhook")
def webhook_handler(request):
    # Verify signature instead of CSRF
    verify_webhook_signature(request)
    return process_webhook(request)
```

## Session Security

### Configuration

```python
# Cookie security
SESSION_COOKIE_SECURE = True       # Only send over HTTPS
SESSION_COOKIE_HTTPONLY = True     # Not accessible via JavaScript
SESSION_COOKIE_SAMESITE = "Lax"    # SameSite policy
SESSION_COOKIE_AGE = 1209600       # 2 weeks in seconds

# Session backend
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
```

### Environment Variables

```bash
export SESSION_COOKIE_SECURE=true
export SESSION_COOKIE_AGE=1209600
export SESSION_ENGINE=django.contrib.sessions.backends.cache
```

### Session Backends

=== "Database (Default)"

    ```python
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
    ```

=== "Cache"

    ```python
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
    ```

=== "Cache + DB Fallback"

    ```python
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"
    ```

=== "Signed Cookies"

    ```python
    SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    ```

## HTTPS / SSL Configuration

### HTTP Strict Transport Security (HSTS)

```python
# Enable HSTS
SECURE_HSTS_SECONDS = 31536000         # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # Apply to all subdomains
SECURE_HSTS_PRELOAD = True             # Submit to browser preload list
```

### SSL Redirect

```python
# Redirect all HTTP to HTTPS
SECURE_SSL_REDIRECT = True

# Trust proxy headers (when behind load balancer)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

### Environment Variables

```bash
export SECURE_SSL_REDIRECT=true
export SECURE_HSTS_SECONDS=31536000
export SECURE_HSTS_INCLUDE_SUBDOMAINS=true
export SECURE_HSTS_PRELOAD=true
export SECURE_PROXY_SSL_HEADER=true
```

## Security Headers

### Browser Security

```python
# XSS Protection
SECURE_BROWSER_XSS_FILTER = True

# Content Type Sniffing Prevention
SECURE_CONTENT_TYPE_NOSNIFF = True

# Clickjacking Protection
X_FRAME_OPTIONS = "DENY"  # or "SAMEORIGIN"
```

### Content Security Policy (CSP)

Django Matt provides default CSP settings that can be customized:

```python
# Default CSP settings
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'")
CSP_IMG_SRC = ("'self'", "data:", "*.googleapis.com", "*.gstatic.com")
CSP_FONT_SRC = ("'self'", "data:", "*.googleapis.com", "*.gstatic.com")
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_SRC = ("'self'",)
```

### Strict CSP Example

```python
# Recommended for production
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'", "https://api.example.com")
CSP_FRAME_SRC = ("'none'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_BASE_URI = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)
```

## Password Validation

### Default Validators

```python
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 10,  # Production: 10, Dev: can be disabled
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
```

### Environment Variable

```bash
export PASSWORD_MIN_LENGTH=10
```

### By Environment

| Environment | Min Length | Validators |
|-------------|------------|------------|
| Development | Disabled | None |
| Staging | 8 | All enabled |
| Production | 10 | All enabled |

## Rate Limiting

Django Matt includes rate limiting configuration.

### Configuration

```python
# Enable rate limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_VIEW = "django_matt.views.ratelimited"
RATELIMIT_FAIL_OPEN = False  # Block requests if rate limiting fails
```

### Environment Variables

```bash
export RATELIMIT_ENABLE=true
export RATELIMIT_USE_CACHE=default
export RATELIMIT_FAIL_OPEN=false
```

### Using Rate Limits

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='100/h', method='POST')
@api.post("/api/resource")
def create_resource(request):
    return create(request)

# Rate limit by IP
@ratelimit(key='ip', rate='10/m', method='GET')
@api.get("/api/search")
def search(request):
    return search_results(request)
```

### Rate Limit Keys

| Key | Description |
|-----|-------------|
| `ip` | Client IP address |
| `user` | Authenticated user ID |
| `user_or_ip` | User ID if authenticated, else IP |
| `get:param` | GET parameter value |
| `post:param` | POST parameter value |
| `header:name` | HTTP header value |

## CORS Configuration

When using APIs with web frontends:

```python
# Install django-cors-headers
INSTALLED_APPS += ["corsheaders"]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    # ... other middleware
]

# Allow specific origins
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
    "https://admin.example.com",
]

# Or allow all origins (development only!)
CORS_ALLOW_ALL_ORIGINS = True  # DON'T use in production

# Allow credentials
CORS_ALLOW_CREDENTIALS = True

# Allowed methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Allowed headers
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "origin",
    "x-csrftoken",
    "x-requested-with",
]
```

## Secret Key Management

### Generation

```python
from django.core.management.utils import get_random_secret_key

# Generate a new secret key
SECRET_KEY = get_random_secret_key()
```

### Environment Variable

```bash
# Generate and set
export DJANGO_SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
```

### Production Requirements

```python
# settings.py
import os

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable is required")
```

## Security Checklist

### Development

```python
# settings/dev.py
DEBUG = True
SECRET_KEY = secrets.token_hex(32)  # Auto-generated

# Relaxed security for localhost
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# Disable password validation
AUTH_PASSWORD_VALIDATORS = []
```

### Staging

```python
# settings/staging.py
DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# Enable security, but shorter HSTS for testing
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600  # 1 hour

# Full password validation
AUTH_PASSWORD_VALIDATORS = [...]
```

### Production

```python
# settings/prod.py
DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

# Full security hardening
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Strict password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
```

## Django Security Check

Run Django's built-in security check:

```bash
python manage.py check --deploy
```

This checks for:

- DEBUG mode
- HTTPS settings
- HSTS configuration
- Cookie security
- Secret key strength
- And more...

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | None | Django secret key (required) |
| `CSRF_COOKIE_SECURE` | `False` | Secure CSRF cookie |
| `CSRF_TRUSTED_ORIGINS` | `""` | Trusted origins |
| `SESSION_COOKIE_SECURE` | `False` | Secure session cookie |
| `SESSION_COOKIE_AGE` | `1209600` | Session cookie age |
| `SESSION_ENGINE` | `backends.db` | Session backend |
| `SECURE_SSL_REDIRECT` | `False` | Redirect to HTTPS |
| `SECURE_HSTS_SECONDS` | `0` | HSTS duration |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False` | HSTS subdomains |
| `SECURE_HSTS_PRELOAD` | `False` | HSTS preload |
| `SECURE_PROXY_SSL_HEADER` | `False` | Trust proxy header |
| `PASSWORD_MIN_LENGTH` | `8` | Minimum password length |
| `RATELIMIT_ENABLE` | `True` | Enable rate limiting |
| `RATELIMIT_USE_CACHE` | `default` | Rate limit cache |
| `RATELIMIT_FAIL_OPEN` | `False` | Fail open on errors |

## Complete Security Settings Example

```python
# Production security settings

# Secret key from environment
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Browser security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# CSRF
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "https://example.com",
    "https://www.example.com",
]

# Sessions
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 1209600
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FRAME_ANCESTORS = ("'none'",)

# Rate limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
RATELIMIT_FAIL_OPEN = False
```
