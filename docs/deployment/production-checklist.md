# Production Checklist

A comprehensive checklist for deploying django-matt applications to production. Complete all items before going live.

## Security

### Django Settings

- [ ] **DEBUG = False**
  ```python
  DEBUG = False
  ```

- [ ] **SECRET_KEY is unique and secure**
  ```bash
  # Generate a secure key
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```

- [ ] **ALLOWED_HOSTS is configured**
  ```python
  ALLOWED_HOSTS = ["myapp.example.com", "www.myapp.example.com"]
  ```

- [ ] **CSRF protection is enabled**
  ```python
  CSRF_COOKIE_SECURE = True
  CSRF_COOKIE_HTTPONLY = True
  CSRF_TRUSTED_ORIGINS = ["https://myapp.example.com"]
  ```

- [ ] **Session security is configured**
  ```python
  SESSION_COOKIE_SECURE = True
  SESSION_COOKIE_HTTPONLY = True
  SESSION_COOKIE_AGE = 1209600  # 2 weeks
  ```

### HTTPS/SSL

- [ ] **SSL redirect is enabled**
  ```python
  SECURE_SSL_REDIRECT = True
  ```

- [ ] **HSTS is configured**
  ```python
  SECURE_HSTS_SECONDS = 31536000  # 1 year
  SECURE_HSTS_INCLUDE_SUBDOMAINS = True
  SECURE_HSTS_PRELOAD = True
  ```

- [ ] **Security headers are set**
  ```python
  SECURE_CONTENT_TYPE_NOSNIFF = True
  SECURE_BROWSER_XSS_FILTER = True
  X_FRAME_OPTIONS = "DENY"
  SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
  ```

### Authentication

- [ ] **Password validation is strong**
  ```python
  AUTH_PASSWORD_VALIDATORS = [
      {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
      {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
      {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
      {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
  ]
  ```

- [ ] **JWT tokens have appropriate expiry**
  ```python
  # django-matt JWT settings
  DJANGO_MATT_JWT = {
      "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
      "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
      "ROTATE_REFRESH_TOKENS": True,
  }
  ```

- [ ] **Rate limiting is configured**
  ```python
  from django_matt.permissions import ThrottleMiddleware

  MIDDLEWARE = [
      ...
      "django_matt.permissions.ThrottleMiddleware",
  ]

  MATT_THROTTLE = {
      "DEFAULT_RATE": "100/minute",
      "LOGIN_RATE": "5/minute",
  }
  ```

### CORS

- [ ] **CORS is properly configured**
  ```python
  CORS_ALLOWED_ORIGINS = [
      "https://myapp.example.com",
      "https://www.myapp.example.com",
  ]
  CORS_ALLOW_CREDENTIALS = True
  ```

### Secrets Management

- [ ] **No secrets in code or version control**
- [ ] **Environment variables are used for secrets**
- [ ] **Platform-specific secret management is used** (Fly secrets, AWS Secrets Manager, etc.)

## Database

### Configuration

- [ ] **PostgreSQL is used in production**
  ```python
  DATABASES = {
      "default": {
          "ENGINE": "django.db.backends.postgresql",
          "NAME": os.environ["DB_NAME"],
          "USER": os.environ["DB_USER"],
          "PASSWORD": os.environ["DB_PASSWORD"],
          "HOST": os.environ["DB_HOST"],
          "PORT": os.environ.get("DB_PORT", "5432"),
      }
  }
  ```

- [ ] **Connection pooling is enabled**
  ```python
  DATABASES["default"]["CONN_MAX_AGE"] = 600  # 10 minutes
  DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
  ```

- [ ] **Database SSL is enabled** (for managed databases)
  ```python
  DATABASES["default"]["OPTIONS"] = {
      "sslmode": "require",
  }
  ```

### Migrations

- [ ] **All migrations are applied**
  ```bash
  python manage.py migrate --check
  ```

- [ ] **No pending migrations**
  ```bash
  python manage.py makemigrations --check --dry-run
  ```

### Backups

- [ ] **Automated backups are configured**
- [ ] **Backup restoration has been tested**
- [ ] **Point-in-time recovery is available** (for critical data)

## Caching

### Redis Configuration

- [ ] **Redis is configured for caching**
  ```python
  CACHES = {
      "default": {
          "BACKEND": "django.core.cache.backends.redis.RedisCache",
          "LOCATION": os.environ["REDIS_URL"],
          "OPTIONS": {
              "CLIENT_CLASS": "django_redis.client.DefaultClient",
          }
      }
  }
  ```

- [ ] **Session backend uses cache**
  ```python
  SESSION_ENGINE = "django.contrib.sessions.backends.cache"
  SESSION_CACHE_ALIAS = "default"
  ```

### Cache Strategy

- [ ] **Appropriate cache timeouts are set**
- [ ] **Cache invalidation strategy is in place**
- [ ] **Cache warming is configured** (if needed)

## Static Files

### Configuration

- [ ] **WhiteNoise is configured**
  ```python
  MIDDLEWARE = [
      "django.middleware.security.SecurityMiddleware",
      "whitenoise.middleware.WhiteNoiseMiddleware",
      ...
  ]

  STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
  ```

- [ ] **Static files are collected**
  ```bash
  python manage.py collectstatic --noinput
  ```

- [ ] **CDN is configured** (optional but recommended)
  ```python
  STATIC_URL = "https://cdn.example.com/static/"
  ```

### Media Files

- [ ] **S3 or object storage is configured for media**
  ```python
  STORAGES = {
      "default": {
          "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
      },
  }
  AWS_STORAGE_BUCKET_NAME = "myapp-media"
  AWS_S3_REGION_NAME = "us-east-1"
  ```

- [ ] **File upload limits are set**
  ```python
  DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
  FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
  ```

## Performance

### Application

- [ ] **Gunicorn/Uvicorn is properly configured**
  ```bash
  gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers 4 \
      --threads 2 \
      --worker-class uvicorn.workers.UvicornWorker \
      --timeout 120 \
      --keep-alive 5
  ```

- [ ] **Database queries are optimized**
  ```python
  from django_matt.utils import optimize_queryset

  # Auto-add select_related/prefetch_related
  users = optimize_queryset(User.objects.all())
  ```

- [ ] **N+1 queries are eliminated**
  ```python
  # Enable query logging in development to detect N+1
  LOGGING["loggers"]["django.db.backends"] = {
      "level": "DEBUG",
      "handlers": ["console"],
  }
  ```

- [ ] **Async views are used where appropriate**
  ```python
  @api.get("/async")
  async def async_endpoint(request):
      data = await some_async_operation()
      return data
  ```

### Response Optimization

- [ ] **Compression is enabled**
  ```python
  MIDDLEWARE = [
      "django.middleware.gzip.GZipMiddleware",
      ...
  ]
  ```

- [ ] **Response caching is configured**
  ```python
  from django_matt.utils import cache_response

  @cache_response(timeout=300)
  @api.get("/cached")
  def cached_view(request):
      return expensive_computation()
  ```

## Logging & Monitoring

### Logging

- [ ] **Structured logging is configured**
  ```python
  LOGGING = {
      "version": 1,
      "disable_existing_loggers": False,
      "formatters": {
          "json": {
              "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
              "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
          },
      },
      "handlers": {
          "console": {
              "class": "logging.StreamHandler",
              "formatter": "json",
          },
      },
      "root": {
          "handlers": ["console"],
          "level": "INFO",
      },
      "loggers": {
          "django": {
              "handlers": ["console"],
              "level": "WARNING",
              "propagate": False,
          },
      },
  }
  ```

- [ ] **Log level is appropriate for production**
  ```python
  # INFO or WARNING for production
  "level": "INFO",
  ```

### Error Tracking

- [ ] **Sentry is configured**
  ```python
  import sentry_sdk
  from sentry_sdk.integrations.django import DjangoIntegration

  sentry_sdk.init(
      dsn=os.environ["SENTRY_DSN"],
      integrations=[DjangoIntegration()],
      traces_sample_rate=0.1,
      send_default_pii=False,
  )
  ```

### Health Checks

- [ ] **Health check endpoints are configured**
  ```python
  from django_matt.deploy import get_health_urls

  urlpatterns = [
      ...
      *get_health_urls(),  # /health/, /ready/, /live/
  ]
  ```

- [ ] **Custom health checks are added**
  ```python
  from django_matt.deploy import health_check, CheckResult, HealthStatus

  @health_check("external_api")
  def check_external_api():
      # Check external service
      return CheckResult(
          name="external_api",
          status=HealthStatus.HEALTHY,
          message="API is reachable",
      )
  ```

### Metrics

- [ ] **Application metrics are collected**
- [ ] **Dashboard is set up** (Grafana, Datadog, etc.)
- [ ] **Alerts are configured** (PagerDuty, OpsGenie, etc.)

## Infrastructure

### Container

- [ ] **Non-root user is used**
  ```dockerfile
  RUN useradd -m appuser && chown -R appuser:appuser /app
  USER appuser
  ```

- [ ] **Health checks are in Dockerfile**
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
      CMD curl -f http://localhost:8000/health/ || exit 1
  ```

- [ ] **Image is optimized** (multi-stage build)

### Scaling

- [ ] **Horizontal scaling is configured**
- [ ] **Auto-scaling policies are in place**
- [ ] **Load balancing is configured**

### Disaster Recovery

- [ ] **Disaster recovery plan exists**
- [ ] **RTO and RPO are defined**
- [ ] **Failover has been tested**

## Email

- [ ] **Production email backend is configured**
  ```python
  EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
  EMAIL_HOST = os.environ["EMAIL_HOST"]
  EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
  EMAIL_USE_TLS = True
  EMAIL_HOST_USER = os.environ["EMAIL_HOST_USER"]
  EMAIL_HOST_PASSWORD = os.environ["EMAIL_HOST_PASSWORD"]
  ```

- [ ] **Email delivery is tested**
- [ ] **SPF, DKIM, and DMARC are configured** (for custom domains)

## Compliance

### Data Protection

- [ ] **Personal data is encrypted at rest**
- [ ] **Personal data is encrypted in transit**
- [ ] **Data retention policies are implemented**
- [ ] **User data export is available** (GDPR)
- [ ] **User data deletion is available** (GDPR)

### Documentation

- [ ] **Privacy policy is published**
- [ ] **Terms of service are published**
- [ ] **Cookie policy is published** (if using cookies)

## Pre-Launch Testing

### Functional Testing

- [ ] **All critical user flows are tested**
- [ ] **API endpoints are tested**
- [ ] **Error handling is tested**

### Performance Testing

- [ ] **Load testing has been performed**
  ```bash
  # Using k6, locust, or similar
  k6 run loadtest.js
  ```

- [ ] **Response times are acceptable**
- [ ] **No memory leaks**

### Security Testing

- [ ] **Security scan has been performed**
- [ ] **Dependency vulnerabilities are checked**
  ```bash
  pip audit
  # or
  safety check
  ```

- [ ] **OWASP Top 10 is addressed**

## Deployment

### Process

- [ ] **CI/CD pipeline is configured**
- [ ] **Deployment process is documented**
- [ ] **Rollback procedure is documented and tested**

### DNS

- [ ] **DNS is configured correctly**
- [ ] **TTL is set appropriately**
- [ ] **CAA records are configured** (optional)

### SSL

- [ ] **SSL certificate is valid**
- [ ] **Certificate auto-renewal is configured**
- [ ] **SSL Labs grade is A or higher**
  ```
  https://www.ssllabs.com/ssltest/
  ```

## Post-Launch

- [ ] **Monitoring alerts are active**
- [ ] **Uptime monitoring is configured**
- [ ] **First deployment metrics are baseline**
- [ ] **On-call rotation is established**
- [ ] **Incident response plan is in place**

## Quick Validation Script

Run this script to validate critical settings:

```python
# validate_production.py
import os
import sys

def check_production():
    errors = []

    # Check DEBUG
    from django.conf import settings

    if settings.DEBUG:
        errors.append("DEBUG is True - must be False in production")

    if not settings.SECRET_KEY or settings.SECRET_KEY == "insecure":
        errors.append("SECRET_KEY is not set or insecure")

    if not settings.ALLOWED_HOSTS:
        errors.append("ALLOWED_HOSTS is empty")

    if not settings.SECURE_SSL_REDIRECT:
        errors.append("SECURE_SSL_REDIRECT is not enabled")

    if settings.SECURE_HSTS_SECONDS < 31536000:
        errors.append("SECURE_HSTS_SECONDS should be at least 1 year")

    if not settings.CSRF_COOKIE_SECURE:
        errors.append("CSRF_COOKIE_SECURE is not enabled")

    if not settings.SESSION_COOKIE_SECURE:
        errors.append("SESSION_COOKIE_SECURE is not enabled")

    # Check database
    db_config = settings.DATABASES.get("default", {})
    if db_config.get("ENGINE") == "django.db.backends.sqlite3":
        errors.append("SQLite should not be used in production")

    if errors:
        print("Production validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("Production validation PASSED")
        sys.exit(0)

if __name__ == "__main__":
    import django
    django.setup()
    check_production()
```

Run with:

```bash
DJANGO_SETTINGS_MODULE=config.settings python validate_production.py
```

## Related Documentation

- [Environment Variables](./environment-variables.md)
- [Docker Deployment](./docker.md)
- [Fly.io Deployment](./fly-io.md)
- [AWS Deployment](./aws.md)
