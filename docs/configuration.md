# Django Matt Configuration System

Django Matt provides a more organized and flexible approach to Django settings by separating concerns into different modules and supporting multiple environments.

## Overview

The traditional Django approach of having a single `settings.py` file can become unwieldy as projects grow. The Django Matt configuration system addresses this by:

1. **Separating settings by concern**: Database settings, cache settings, security settings, etc.
2. **Supporting multiple environments**: Development, staging, production, etc.
3. **Providing a clean API**: Easy to use and extend.

## Directory Structure

The configuration system is organized as follows:

```
django_matt/
└── config/
    ├── __init__.py         # Main configuration API
    ├── utils.py            # Utility functions
    ├── base/               # Base settings for all environments
    │   └── __init__.py
    ├── environments/       # Environment-specific settings
    │   ├── __init__.py
    │   ├── development.py
    │   ├── staging.py
    │   └── production.py
    └── components/         # Component-specific settings
        ├── __init__.py
        ├── database.py
        ├── cache.py
        ├── security.py
        └── performance.py
```

## Usage

### Basic Usage

In your project's `settings.py` file, you can use the configuration system as follows:

```python
from django_matt.config import configure

# Configure the application
settings = configure(
    environment='development',
    components=['database', 'cache', 'security'],
)
```

### Complete Example

Here's a more complete example:

```python
import os
from pathlib import Path

# Import the Django Matt configuration system
from django_matt.config import configure

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Determine the environment
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development')

# Configure the application
settings = configure(
    # Specify the environment (development, staging, production)
    environment=ENVIRONMENT,
    
    # Specify the components to load
    components=[
        'database',
        'cache',
        'security',
        'performance',
    ],
    
    # Specify additional settings
    extra_settings={
        # Project-specific settings
        'ROOT_URLCONF': 'myproject.urls',
        'WSGI_APPLICATION': 'myproject.wsgi.application',
        
        # Add your project's apps
        'INSTALLED_APPS': [
            'myproject.apps.core',
            'myproject.apps.users',
            'myproject.apps.api',
        ],
    },
    
    # Apply the settings to Django's settings module
    apply_to_django=True,
)

# You can access the settings directly if needed
DEBUG = settings['DEBUG']
SECRET_KEY = settings['SECRET_KEY']
```

## Configuration API

### `configure(environment, components, extra_settings, apply_to_django)`

Configures the application with the specified settings.

- `environment`: The name of the environment to load (default: 'development').
- `components`: A list of component names to load (default: None).
- `extra_settings`: Additional settings to apply (default: None).
- `apply_to_django`: Whether to apply the settings to Django's settings module (default: True).

Returns the final settings dictionary.

### `get_settings()`

Gets the current settings dictionary.

Returns the settings dictionary.

## Environments

The configuration system includes the following environments:

### Development

Settings suitable for local development:

- `DEBUG = True`
- Console email backend
- Django Debug Toolbar
- No password validation
- Random secret key

### Staging

Settings suitable for staging/testing environments:

- `DEBUG = False`
- Less strict security settings than production
- Console email backend
- Detailed logging

### Production

Settings suitable for production deployment:

- `DEBUG = False`
- Strict security settings
- SMTP email backend
- Comprehensive logging
- Strong password validation

## Components

The configuration system includes the following components:

### Database

Settings for configuring the database connection:

- Database connection settings
- Connection pooling options

### Cache

Settings for configuring the cache backend:

- Cache backend settings
- Redis settings (if using Redis)
- Cache middleware settings

### Security

Settings for enhancing security:

- CSRF settings
- Session settings
- Security middleware settings
- Content Security Policy
- Password validation
- Rate limiting

### Performance

Settings for optimizing performance:

- Django Matt performance settings
- Django optimization settings
- Template caching
- Static files settings
- Performance middleware

## Environment Variables

The configuration system uses environment variables to customize settings. Here are some of the key environment variables:

### Core Settings

- `DJANGO_ENV`: The environment to use (development, staging, production).
- `DJANGO_SECRET_KEY`: The secret key for production/staging.
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts.

### Database Settings

- `DB_ENGINE`: The database engine to use.
- `DB_NAME`: The name of the database.
- `DB_USER`: The database user.
- `DB_PASSWORD`: The database password.
- `DB_HOST`: The database host.
- `DB_PORT`: The database port.

### Cache Settings

- `CACHE_BACKEND`: The cache backend to use.
- `CACHE_LOCATION`: The cache location.
- `CACHE_TIMEOUT`: The cache timeout in seconds.
- `REDIS_URL`: The Redis URL (if using Redis).

### Security Settings

- `CSRF_COOKIE_SECURE`: Whether to use secure CSRF cookies.
- `SESSION_COOKIE_SECURE`: Whether to use secure session cookies.
- `SECURE_SSL_REDIRECT`: Whether to redirect to HTTPS.
- `SECURE_HSTS_SECONDS`: The HSTS timeout in seconds.

### Performance Settings

- `DJANGO_MATT_BENCHMARK_ENABLED`: Whether to enable benchmarking.
- `DJANGO_MATT_CACHE_ENABLED`: Whether to enable caching.
- `DJANGO_MATT_CACHE_TIMEOUT`: The cache timeout in seconds.

## Extending the Configuration System

You can extend the configuration system by adding your own components or environments.

### Adding a New Component

1. Create a new file in the `django_matt/config/components/` directory.
2. Define a `settings` dictionary with your component's settings.
3. Use the component in your `settings.py` file.

Example:

```python
# django_matt/config/components/my_component.py
settings = {
    'MY_SETTING': 'my value',
}

# settings.py
settings = configure(
    components=['database', 'my_component'],
)
```

### Adding a New Environment

1. Create a new file in the `django_matt/config/environments/` directory.
2. Define a `settings` dictionary with your environment's settings.
3. Use the environment in your `settings.py` file.

Example:

```python
# django_matt/config/environments/my_environment.py
settings = {
    'DEBUG': True,
    'MY_SETTING': 'my value',
}

# settings.py
settings = configure(
    environment='my_environment',
)
```

## Best Practices

- Use environment variables for sensitive information (passwords, API keys, etc.).
- Use the `extra_settings` parameter for project-specific settings.
- Keep the `settings.py` file as clean as possible.
- Use the `apply_to_django=False` parameter if you want to manipulate the settings before applying them to Django.
- Use the `get_settings()` function to access the settings dictionary directly. 