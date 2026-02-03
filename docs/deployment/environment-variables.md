# Environment Variables Reference

Complete reference for all environment variables used in django-matt deployments.

## Core Django Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DJANGO_SETTINGS_MODULE` | Path to Django settings module | - | Yes |
| `DJANGO_ENV` | Environment name (development, staging, production) | `development` | Yes |
| `DEBUG` | Enable debug mode | `false` | Yes |
| `SECRET_KEY` | Django secret key (min 50 chars) | - | Yes |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | - | Yes |
| `LANGUAGE_CODE` | Default language code | `en-us` | No |
| `TIME_ZONE` | Default timezone | `UTC` | No |

### Example

```bash
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_ENV=production
DEBUG=false
SECRET_KEY=your-very-long-and-secure-secret-key-here-at-least-50-characters
ALLOWED_HOSTS=myapp.example.com,www.myapp.example.com
```

## Database Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Full database connection URL | - | Yes* |
| `DB_NAME` | Database name | - | Alt |
| `DB_USER` | Database username | - | Alt |
| `DB_PASSWORD` | Database password | - | Alt |
| `DB_HOST` | Database host | `localhost` | Alt |
| `DB_PORT` | Database port | `5432` | No |
| `DB_CONN_MAX_AGE` | Connection max age in seconds | `0` | No |
| `DB_SSL_MODE` | SSL mode (require, prefer, disable) | `prefer` | No |

*Either `DATABASE_URL` or individual `DB_*` variables are required.

### Database URL Format

```bash
# PostgreSQL
DATABASE_URL=postgres://user:password@host:5432/dbname

# With SSL
DATABASE_URL=postgres://user:password@host:5432/dbname?sslmode=require

# SQLite (development only)
DATABASE_URL=sqlite:///db.sqlite3
```

### Individual Variables

```bash
DB_NAME=myapp
DB_USER=django
DB_PASSWORD=secure-password
DB_HOST=db.example.com
DB_PORT=5432
DB_CONN_MAX_AGE=600
```

## Cache Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REDIS_URL` | Redis connection URL | - | No |
| `CACHE_BACKEND` | Cache backend class | `locmem` | No |
| `CACHE_TIMEOUT` | Default cache timeout in seconds | `300` | No |

### Example

```bash
REDIS_URL=redis://redis:6379/0

# With authentication
REDIS_URL=redis://:password@redis:6379/0

# With SSL
REDIS_URL=rediss://redis:6379/0
```

## Static & Media Files

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `STATIC_URL` | URL prefix for static files | `/static/` | No |
| `STATIC_ROOT` | Directory for collected static files | `staticfiles` | No |
| `MEDIA_URL` | URL prefix for media files | `/media/` | No |
| `MEDIA_ROOT` | Directory for uploaded files | `media` | No |

### S3 Storage

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `USE_S3` | Enable S3 storage | `false` | No |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | S3 |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | S3 |
| `AWS_STORAGE_BUCKET_NAME` | S3 bucket name | - | S3 |
| `AWS_S3_REGION_NAME` | S3 region | `us-east-1` | No |
| `AWS_S3_CUSTOM_DOMAIN` | Custom domain for S3/CloudFront | - | No |
| `AWS_S3_ENDPOINT_URL` | Custom S3 endpoint (for S3-compatible) | - | No |
| `AWS_DEFAULT_ACL` | Default ACL for uploads | `private` | No |

### Example

```bash
USE_S3=true
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_STORAGE_BUCKET_NAME=myapp-media
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=cdn.myapp.example.com
```

## Email Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `EMAIL_BACKEND` | Email backend class | `console` | No |
| `EMAIL_HOST` | SMTP server hostname | - | SMTP |
| `EMAIL_PORT` | SMTP port | `587` | No |
| `EMAIL_USE_TLS` | Use TLS | `true` | No |
| `EMAIL_USE_SSL` | Use SSL | `false` | No |
| `EMAIL_HOST_USER` | SMTP username | - | SMTP |
| `EMAIL_HOST_PASSWORD` | SMTP password | - | SMTP |
| `DEFAULT_FROM_EMAIL` | Default from email address | - | No |
| `SERVER_EMAIL` | Server error email from address | - | No |

### Example (SendGrid)

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxx
DEFAULT_FROM_EMAIL=noreply@myapp.example.com
```

### Example (AWS SES)

```bash
EMAIL_BACKEND=django_ses.SESBackend
AWS_SES_REGION_NAME=us-east-1
AWS_SES_REGION_ENDPOINT=email.us-east-1.amazonaws.com
DEFAULT_FROM_EMAIL=noreply@myapp.example.com
```

## Authentication (django-matt)

### JWT Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET_KEY` | Secret key for JWT signing | `SECRET_KEY` | No |
| `JWT_ACCESS_TOKEN_LIFETIME` | Access token lifetime in minutes | `15` | No |
| `JWT_REFRESH_TOKEN_LIFETIME` | Refresh token lifetime in days | `7` | No |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` | No |
| `JWT_ROTATE_REFRESH_TOKENS` | Rotate refresh tokens on use | `true` | No |

### Example

```bash
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_LIFETIME=15
JWT_REFRESH_TOKEN_LIFETIME=7
JWT_ALGORITHM=HS256
```

### OAuth Providers

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | OAuth |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | OAuth |
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID | OAuth |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret | OAuth |
| `APPLE_CLIENT_ID` | Apple OAuth client ID | OAuth |
| `APPLE_CLIENT_SECRET` | Apple OAuth client secret | OAuth |
| `MICROSOFT_CLIENT_ID` | Microsoft OAuth client ID | OAuth |
| `MICROSOFT_CLIENT_SECRET` | Microsoft OAuth client secret | OAuth |

### Example

```bash
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GITHUB_CLIENT_ID=xxxxx
GITHUB_CLIENT_SECRET=xxxxx
```

### SSO (Enterprise)

| Variable | Description | Required |
|----------|-------------|----------|
| `SAML_METADATA_URL` | SAML IdP metadata URL | SAML |
| `SAML_ENTITY_ID` | SAML entity ID | SAML |
| `OIDC_RP_CLIENT_ID` | OIDC client ID | OIDC |
| `OIDC_RP_CLIENT_SECRET` | OIDC client secret | OIDC |
| `OIDC_OP_AUTHORIZATION_ENDPOINT` | OIDC authorization endpoint | OIDC |
| `OIDC_OP_TOKEN_ENDPOINT` | OIDC token endpoint | OIDC |
| `OIDC_OP_JWKS_ENDPOINT` | OIDC JWKS endpoint | OIDC |

## Billing (django-matt)

### Stripe

| Variable | Description | Required |
|----------|-------------|----------|
| `STRIPE_SECRET_KEY` | Stripe secret key | Stripe |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key | Stripe |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | Stripe |

### PayPal

| Variable | Description | Required |
|----------|-------------|----------|
| `PAYPAL_CLIENT_ID` | PayPal client ID | PayPal |
| `PAYPAL_CLIENT_SECRET` | PayPal client secret | PayPal |
| `PAYPAL_MODE` | PayPal mode (sandbox, live) | PayPal |
| `PAYPAL_WEBHOOK_ID` | PayPal webhook ID | PayPal |

### Polar

| Variable | Description | Required |
|----------|-------------|----------|
| `POLAR_ACCESS_TOKEN` | Polar access token | Polar |
| `POLAR_ORGANIZATION_ID` | Polar organization ID | Polar |
| `POLAR_WEBHOOK_SECRET` | Polar webhook secret | Polar |

### Example

```bash
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

## Security Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS | `true` | Prod |
| `SECURE_HSTS_SECONDS` | HSTS max age | `31536000` | Prod |
| `CSRF_COOKIE_SECURE` | CSRF cookie HTTPS only | `true` | Prod |
| `SESSION_COOKIE_SECURE` | Session cookie HTTPS only | `true` | Prod |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins | - | No |
| `CORS_ALLOW_CREDENTIALS` | Allow credentials in CORS | `true` | No |

### Example

```bash
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
CSRF_COOKIE_SECURE=true
SESSION_COOKIE_SECURE=true
CORS_ALLOWED_ORIGINS=https://myapp.example.com,https://www.myapp.example.com
```

## Monitoring & Logging

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SENTRY_DSN` | Sentry DSN for error tracking | - | No |
| `SENTRY_ENVIRONMENT` | Sentry environment name | `DJANGO_ENV` | No |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry tracing sample rate | `0.1` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `LOG_FORMAT` | Logging format (json, verbose) | `json` | No |

### Example

```bash
SENTRY_DSN=https://xxxxx@o123456.ingest.sentry.io/123456
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
LOG_LEVEL=INFO
```

## Performance

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PORT` | Server port | `8000` | No |
| `WORKERS` | Gunicorn workers | `4` | No |
| `THREADS` | Gunicorn threads per worker | `2` | No |
| `WORKER_CLASS` | Gunicorn worker class | `sync` | No |
| `TIMEOUT` | Request timeout in seconds | `120` | No |

### Example

```bash
PORT=8000
WORKERS=4
THREADS=2
WORKER_CLASS=uvicorn.workers.UvicornWorker
TIMEOUT=120
```

## Celery

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CELERY_BROKER_URL` | Celery broker URL | `REDIS_URL` | Celery |
| `CELERY_RESULT_BACKEND` | Celery result backend | `REDIS_URL` | No |
| `CELERY_TASK_ALWAYS_EAGER` | Run tasks synchronously | `false` | No |
| `CELERY_WORKER_CONCURRENCY` | Worker concurrency | `4` | No |

### Example

```bash
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_WORKER_CONCURRENCY=4
```

## Feature Flags

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FEATURE_NEW_UI` | Enable new UI | `false` | No |
| `FEATURE_BETA_API` | Enable beta API | `false` | No |
| `MAINTENANCE_MODE` | Enable maintenance mode | `false` | No |

## Platform-Specific Variables

### Fly.io

| Variable | Description |
|----------|-------------|
| `FLY_APP_NAME` | Fly.io app name (auto-set) |
| `FLY_REGION` | Current region (auto-set) |
| `PRIMARY_REGION` | Primary region for writes |

### Railway

| Variable | Description |
|----------|-------------|
| `RAILWAY_ENVIRONMENT` | Railway environment (auto-set) |
| `RAILWAY_PROJECT_ID` | Railway project ID (auto-set) |

### Render

| Variable | Description |
|----------|-------------|
| `RENDER` | `true` when running on Render |
| `RENDER_SERVICE_ID` | Render service ID (auto-set) |
| `RENDER_INSTANCE_ID` | Render instance ID (auto-set) |

### Heroku

| Variable | Description |
|----------|-------------|
| `DYNO` | Dyno identifier (auto-set) |
| `PORT` | Assigned port (auto-set) |

## Environment File Templates

### Development (.env.development)

```bash
# Django
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_ENV=development
DEBUG=true
SECRET_KEY=insecure-development-key-not-for-production

# Database
DATABASE_URL=postgres://django:django@localhost:5432/django

# Cache
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Logging
LOG_LEVEL=DEBUG
```

### Staging (.env.staging)

```bash
# Django
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_ENV=staging
DEBUG=false
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=staging.myapp.example.com

# Database
DATABASE_URL=${DATABASE_URL}

# Cache
REDIS_URL=${REDIS_URL}

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=${SENDGRID_API_KEY}

# Security
SECURE_SSL_REDIRECT=true
CSRF_COOKIE_SECURE=true
SESSION_COOKIE_SECURE=true

# Monitoring
SENTRY_DSN=${SENTRY_DSN}
LOG_LEVEL=INFO
```

### Production (.env.production)

```bash
# Django
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_ENV=production
DEBUG=false
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=myapp.example.com,www.myapp.example.com

# Database
DATABASE_URL=${DATABASE_URL}
DB_CONN_MAX_AGE=600

# Cache
REDIS_URL=${REDIS_URL}

# Storage
USE_S3=true
AWS_STORAGE_BUCKET_NAME=myapp-media
AWS_S3_REGION_NAME=us-east-1

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=${SENDGRID_API_KEY}
DEFAULT_FROM_EMAIL=noreply@myapp.example.com

# Security
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
CSRF_COOKIE_SECURE=true
SESSION_COOKIE_SECURE=true
CORS_ALLOWED_ORIGINS=https://myapp.example.com

# Monitoring
SENTRY_DSN=${SENTRY_DSN}
LOG_LEVEL=WARNING

# Performance
WORKERS=4
THREADS=2
```

## Loading Environment Variables

### Using python-dotenv

```python
# settings.py
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access variables
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ["SECRET_KEY"]
```

### Using django-environ

```python
# settings.py
import environ

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Read .env file
environ.Env.read_env()

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
DATABASES = {"default": env.db()}
```

### Using django-matt Config

```python
from django_matt.config import configure

settings = configure(
    environment=os.environ.get("DJANGO_ENV", "development"),
    extra_settings={
        "CUSTOM_SETTING": "value",
    },
)
```

## Related Documentation

- [Production Checklist](./production-checklist.md)
- [Docker Deployment](./docker.md)
- [Fly.io Deployment](./fly-io.md)
- [Railway Deployment](./railway.md)
- [Render Deployment](./render.md)
- [AWS Deployment](./aws.md)
- [Hetzner Deployment](./hetzner.md)
