# Installation

## Requirements

- **Python**: 3.11+ (3.13 recommended)
- **Django**: 5.2+ (6.0+ for Python 3.12+)

## Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast, modern Python package manager.

```bash
# Install the package
uv add django-matt

# With authentication extras
uv add "django-matt[auth]"

# With all extras
uv add "django-matt[all]"
```

## Using pip

```bash
# Basic installation
pip install django-matt

# With extras
pip install "django-matt[auth,performance]"
```

## Optional Dependencies

django-matt uses optional dependencies to keep the base install lightweight:

| Extra | Description | Includes |
|-------|-------------|----------|
| `auth` | JWT, password hashing | PyJWT, passlib, argon2-cffi |
| `oauth` | OAuth providers | authlib |
| `passkeys` | WebAuthn/Passkeys | webauthn |
| `performance` | Fast JSON, caching | orjson, ujson, redis |
| `files` | File uploads, S3 | boto3, python-multipart |
| `tasks` | Background tasks | celery, dramatiq, django-q2 |
| `billing` | Payment providers | stripe |
| `testing` | Test utilities | factory-boy, faker, pytest |
| `docs` | Documentation | mkdocs, mkdocs-material |
| `full` | Common features | auth, performance, files |
| `all` | Everything | All extras |

## Django Configuration

Add `django_matt` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    'django_matt',
]
```

## Version Compatibility Matrix

| django-matt | Python | Django |
|-------------|--------|--------|
| 0.1.x | 3.11, 3.12, 3.13 | 5.2 |
| 0.2.x | 3.12, 3.13, 3.14 | 6.0 |

!!! warning "Django 6.0 requires Python 3.12+"
    Django 6.0 dropped support for Python 3.10 and 3.11. If you need Python 3.11 support, stay on Django 5.2.
