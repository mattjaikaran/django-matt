# Security Best Practices

Comprehensive security guidance for django-matt applications. Covers authentication, secrets, rate limiting, input validation, and OWASP top 10 mitigations.

---

## JWT Best Practices

### Short-Lived Access Tokens

Access tokens should expire quickly. The default is 15 minutes -- do not increase this beyond 60 minutes for web apps.

```python
from datetime import timedelta

DJANGO_MATT_JWT = {
    "SECRET_KEY": "use-a-strong-random-key",  # or omit to use Django SECRET_KEY
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

### Refresh Token Rotation

Always enable `ROTATE_REFRESH_TOKENS`. When a refresh token is used, the old one is blacklisted and a new pair is issued. This limits the damage from a stolen refresh token.

### Audience and Issuer Claims

Set `AUDIENCE` and `ISSUER` to prevent tokens from one service being accepted by another:

```python
DJANGO_MATT_JWT = {
    "ISSUER": "https://api.example.com",
    "AUDIENCE": "https://app.example.com",
}
```

### Asymmetric Algorithms for Microservices

Use RS256 or ES256 when multiple services need to verify tokens but only one should issue them:

```python
DJANGO_MATT_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": open("/secrets/jwt_private.pem").read(),   # issuing service only
    "VERIFYING_KEY": open("/secrets/jwt_public.pem").read(),  # all services
}
```

### Token Decode Safety

django-matt's JWT implementation validates expiry, algorithm, and signature. The Rust-accelerated path (`jwt_decode_rust`, `jwt_verify_rust`) provides the same guarantees with lower latency.

```python
from django_matt._accel import HAS_RUST

# When HAS_RUST is True, JWT operations use the Rust implementation automatically.
# No code changes needed -- the auth middleware dispatches transparently.
```

---

## API Key Management

### Scoped Keys

Never issue global API keys. Each key should have explicit permission scopes:

```python
# When creating API keys, specify allowed scopes
key = await APIKey.objects.acreate(
    name="CI/CD Pipeline",
    scopes=["read:deployments", "write:deployments"],
    expires_at=timezone.now() + timedelta(days=90),
)
```

### Key Rotation

Set expiration dates on all API keys. Use the secrets rotation system for automatic rotation:

```python
from django_matt.secrets.rotation import RotationPolicy

policy = RotationPolicy(
    max_age_days=90,
    notify_before_days=14,
    auto_rotate=True,
)
```

### Key Storage

Store API keys hashed (like passwords). django-matt hashes keys on creation and compares hashes on authentication -- the raw key is only shown once at creation time.

---

## Secrets Management

### Backend Selection

| Environment | Recommended Backend |
|---|---|
| Local development | `DotenvBackend` or `EnvBackend` |
| CI/CD | `EnvBackend` with injected secrets |
| Staging | `EncryptedFileBackend` or `VaultBackend` |
| Production | `VaultBackend`, `AWSSecretsManagerBackend`, or `GCPSecretManagerBackend` |

### EncryptedFileBackend

Good for small teams or single-server deployments. Uses Fernet symmetric encryption:

```python
from django_matt.secrets.backends import EncryptedFileBackend

# Generate an encryption key (do this once, store securely)
key = EncryptedFileBackend.generate_key()
# e.g., "gAAAAABhQ..."

# Use the backend
secrets = EncryptedFileBackend(path="/etc/myapp/secrets.enc", key=key)
await secrets.set("DATABASE_PASSWORD", "s3cret")
password = await secrets.get("DATABASE_PASSWORD")
```

### HashiCorp Vault

For production deployments with multiple services:

```python
from django_matt.secrets.backends import VaultBackend

secrets = VaultBackend(
    url="https://vault.internal:8200",
    token=os.environ["VAULT_TOKEN"],  # only this one env var needed
    mount_point="secret",
    path_prefix="myapp/production/",
)

db_password = await secrets.get("DATABASE_PASSWORD")
api_key = await secrets.get("STRIPE_SECRET_KEY")
```

### AWS Secrets Manager

```python
from django_matt.secrets.backends import AWSSecretsManagerBackend

secrets = AWSSecretsManagerBackend(
    region_name="us-east-1",
    prefix="myapp/prod/",
)
```

### Never Do This

```python
# WRONG: secrets in source code
DATABASE_PASSWORD = "hunter2"

# WRONG: secrets in settings.py
STRIPE_KEY = "sk_live_..."

# WRONG: secrets in docker-compose.yml committed to git
environment:
  - DB_PASSWORD=hunter2
```

---

## Rate Limiting

### Global Rate Limiting

Apply a default rate limit to all endpoints:

```python
from django_matt.config import configure

configure(throttle="100/hour")
```

### Per-Endpoint Rate Limiting

Use the `@throttle` decorator for fine-grained control:

```python
from django_matt.throttling import throttle, AnonRateThrottle, UserRateThrottle

# Strict limit on anonymous access
@api.get("/search")
@throttle(AnonRateThrottle, rate="30/minute")
async def search(request, q: str):
    ...

# Higher limit for authenticated users
@api.get("/users/me")
@throttle(UserRateThrottle, rate="1000/day")
async def me(request):
    ...
```

### Scoped Rate Limiting

Different limits for different scopes:

```python
from django_matt.throttling import ScopedRateThrottle

@api.post("/auth/login")
@throttle(ScopedRateThrottle, rate="5/minute")
async def login(request, data: LoginSchema):
    ...

@api.post("/auth/forgot-password")
@throttle(ScopedRateThrottle, rate="3/hour")
async def forgot_password(request, data: ForgotPasswordSchema):
    ...
```

### Rate Limiting Backends

| Backend | Use Case |
|---|---|
| `InMemoryBackend` | Single-server, development |
| `RedisBackend` | Multi-server, production |

```python
DJANGO_MATT = {
    "THROTTLE": {
        "DEFAULT_RATE": "100/hour",
        "BACKEND": "django_matt.throttling.backends.RedisBackend",
    },
}
```

### Route-Level Rate Limiting with Interceptors

```python
from django_matt.interceptors.builtins import RateLimitInterceptor
from django_matt.interceptors.decorators import intercept

@api.post("/webhooks/stripe")
@intercept(RateLimitInterceptor(max_requests=50, window=60.0))
async def stripe_webhook(request):
    ...
```

---

## CORS Configuration

### Production CORS

Always specify exact origins in production:

```python
configure(
    cors=["https://app.example.com", "https://admin.example.com"],
)
```

### Per-Environment CORS

```python
# settings/development.py
configure(cors=True)  # allows all origins -- dev only

# settings/production.py
configure(
    cors=["https://app.example.com"],
    middleware="production",
)
```

---

## Input Validation with Pydantic

django-matt uses Pydantic v2 for all request/response validation. This prevents most injection attacks at the schema level.

### Strict Schemas

```python
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID

class UserCreateSchema(BaseModel):
    email: EmailStr                          # validates email format
    name: str = Field(max_length=100)        # prevents oversized input
    age: int = Field(ge=0, le=150)           # range validation
    role: Literal["user", "admin"] = "user"  # enum validation

class UserUpdateSchema(BaseModel):
    name: str | None = Field(None, max_length=100)
    age: int | None = Field(None, ge=0, le=150)
```

### Path Parameter Validation

Use typed path parameters to prevent injection:

```python
@api.get("/users/{user_id}")
async def get_user(request, user_id: UUID):
    # user_id is guaranteed to be a valid UUID
    user = await User.objects.aget(id=user_id)
    ...
```

### File Upload Validation

```python
from django_matt.files import validate_upload

@api.post("/upload")
async def upload(request):
    file = request.FILES["file"]
    validate_upload(
        file,
        max_size_mb=10,
        allowed_types=["image/jpeg", "image/png", "application/pdf"],
    )
```

---

## SQL Injection Prevention

django-matt uses Django's ORM exclusively. The ORM parameterizes all queries, preventing SQL injection.

### Safe Patterns

```python
# Parameterized queries via ORM
users = await User.objects.filter(email=user_input).afirst()

# Even raw queries are parameterized
from django_matt.db import execute_raw_sql
results = execute_raw_sql(
    "SELECT * FROM users WHERE email = %s",
    params=[user_input],
)
```

### Dangerous Patterns to Avoid

```python
# NEVER do string interpolation in raw SQL
cursor.execute(f"SELECT * FROM users WHERE email = '{user_input}'")  # SQL INJECTION

# NEVER use .extra() with unsanitized input
User.objects.extra(where=[f"email = '{user_input}'"])  # SQL INJECTION
```

---

## OWASP Top 10 Coverage

| # | Vulnerability | django-matt Mitigation |
|---|---|---|
| A01 | Broken Access Control | `IsAuthenticated`, `IsAdmin`, `IsOwner`, `HasRole`, `@requires_role`, `@requires_permission` permission classes and decorators |
| A02 | Cryptographic Failures | Secrets backends (Vault, AWS SM, GCP SM), encrypted file backend with Fernet |
| A03 | Injection | Pydantic input validation, Django ORM parameterized queries, no raw SQL by default |
| A04 | Insecure Design | Type-safe schemas, permission-first controller pattern, audit logging |
| A05 | Security Misconfiguration | `configure(middleware="production")` enables security headers, CORS, request ID; `matt doctor` CLI checks config |
| A06 | Vulnerable Components | `uv` lockfile for reproducible deps, no unnecessary dependencies in slim mode |
| A07 | Auth Failures | Short-lived JWT, refresh rotation, blacklisting, rate-limited login, API key scoping |
| A08 | Data Integrity Failures | Pydantic validation on all inputs, signed JWTs, HMAC verification on webhooks |
| A09 | Logging & Monitoring | Structured logging, OpenTelemetry tracing, Prometheus metrics, request correlation IDs |
| A10 | SSRF | No built-in URL fetching; external HTTP calls should use allowlists |

---

## Security Checklist Summary

```
[ ] JWT access tokens expire in <= 15 minutes
[ ] Refresh token rotation enabled
[ ] Secrets loaded from a secure backend (not env vars in production)
[ ] Rate limiting on all public and auth endpoints
[ ] CORS restricted to exact origins
[ ] All input validated via Pydantic schemas
[ ] No raw SQL with string interpolation
[ ] Security headers enabled (middleware="production")
[ ] Audit logging enabled for sensitive operations
[ ] API keys scoped and rotated
[ ] HTTPS enforced (SECURE_SSL_REDIRECT)
[ ] Admin panel access restricted
```
