"""
Multi-environment configuration management.

Provides tools for managing different deployment environments
(development, staging, production) with environment-specific settings.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import orjson


class Environment(str, Enum):
    """Standard deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    LOCAL = "local"


@dataclass
class EnvironmentConfig:
    """
    Configuration for a specific environment.

    Contains all settings that vary between environments.
    """

    name: str
    display_name: str = ""

    # Django settings
    debug: bool = False
    allowed_hosts: list[str] = field(default_factory=list)
    secret_key: str | None = None

    # Database
    database_url: str | None = None
    database_options: dict[str, Any] = field(default_factory=dict)

    # Cache/Redis
    redis_url: str | None = None
    cache_backend: str = "django.core.cache.backends.locmem.LocMemCache"

    # Email
    email_backend: str = "django.core.mail.backends.console.EmailBackend"
    email_host: str | None = None
    email_port: int = 587
    email_use_tls: bool = True
    email_host_user: str | None = None

    # Storage
    static_url: str = "/static/"
    media_url: str = "/media/"
    use_s3: bool = False
    aws_storage_bucket_name: str | None = None

    # Security
    secure_ssl_redirect: bool = False
    session_cookie_secure: bool = False
    csrf_cookie_secure: bool = False
    secure_hsts_seconds: int = 0

    # Logging
    log_level: str = "INFO"
    log_format: str = "verbose"

    # Performance
    conn_max_age: int = 0
    cache_timeout: int = 300

    # Custom settings
    extra_settings: dict[str, Any] = field(default_factory=dict)

    # Environment variables
    env_vars: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.name.title()

    def to_django_settings(self) -> dict[str, Any]:
        """Convert to Django settings dictionary."""
        settings = {
            "DEBUG": self.debug,
            "ALLOWED_HOSTS": self.allowed_hosts,
            "CACHES": {
                "default": {
                    "BACKEND": self.cache_backend,
                }
            },
            "EMAIL_BACKEND": self.email_backend,
            "STATIC_URL": self.static_url,
            "MEDIA_URL": self.media_url,
            "LOGGING": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": self.log_level,
                    },
                },
                "root": {
                    "handlers": ["console"],
                    "level": self.log_level,
                },
            },
        }

        if self.secret_key:
            settings["SECRET_KEY"] = self.secret_key

        if self.database_url:
            import dj_database_url

            settings["DATABASES"] = {
                "default": dj_database_url.parse(
                    self.database_url,
                    conn_max_age=self.conn_max_age,
                )
            }
            settings["DATABASES"]["default"].update(self.database_options)

        if self.redis_url:
            settings["CACHES"]["default"] = {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": self.redis_url,
            }

        if self.email_host:
            settings["EMAIL_HOST"] = self.email_host
            settings["EMAIL_PORT"] = self.email_port
            settings["EMAIL_USE_TLS"] = self.email_use_tls
            if self.email_host_user:
                settings["EMAIL_HOST_USER"] = self.email_host_user

        if self.use_s3 and self.aws_storage_bucket_name:
            settings["STORAGES"] = {
                "default": {
                    "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
                },
                "staticfiles": {
                    "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
                },
            }
            settings["AWS_STORAGE_BUCKET_NAME"] = self.aws_storage_bucket_name

        # Security settings
        if self.secure_ssl_redirect:
            settings["SECURE_SSL_REDIRECT"] = True
        if self.session_cookie_secure:
            settings["SESSION_COOKIE_SECURE"] = True
        if self.csrf_cookie_secure:
            settings["CSRF_COOKIE_SECURE"] = True
        if self.secure_hsts_seconds > 0:
            settings["SECURE_HSTS_SECONDS"] = self.secure_hsts_seconds
            settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"] = True
            settings["SECURE_HSTS_PRELOAD"] = True

        settings.update(self.extra_settings)

        return settings

    def to_env_file(self) -> str:
        """Generate .env file content."""
        lines = [
            f"# Environment: {self.display_name}",
            f"DJANGO_ENV={self.name}",
            f"DEBUG={'true' if self.debug else 'false'}",
        ]

        if self.secret_key:
            lines.append(f"SECRET_KEY={self.secret_key}")

        if self.allowed_hosts:
            lines.append(f"ALLOWED_HOSTS={','.join(self.allowed_hosts)}")

        if self.database_url:
            lines.append(f"DATABASE_URL={self.database_url}")

        if self.redis_url:
            lines.append(f"REDIS_URL={self.redis_url}")

        if self.email_host:
            lines.append(f"EMAIL_HOST={self.email_host}")
            lines.append(f"EMAIL_PORT={self.email_port}")
            if self.email_host_user:
                lines.append(f"EMAIL_HOST_USER={self.email_host_user}")

        if self.use_s3 and self.aws_storage_bucket_name:
            lines.append(f"AWS_STORAGE_BUCKET_NAME={self.aws_storage_bucket_name}")

        lines.append(f"LOG_LEVEL={self.log_level}")

        for key, value in self.env_vars.items():
            lines.append(f"{key}={value}")

        return "\n".join(lines)

    @classmethod
    def development(cls, **kwargs) -> "EnvironmentConfig":
        """Create a development environment configuration."""
        defaults = {
            "name": "development",
            "debug": True,
            "allowed_hosts": ["localhost", "127.0.0.1", "[::1]"],
            "database_url": "postgres://django:django@localhost:5432/django",
            "cache_backend": "django.core.cache.backends.locmem.LocMemCache",
            "email_backend": "django.core.mail.backends.console.EmailBackend",
            "log_level": "DEBUG",
        }
        defaults.update(kwargs)
        return cls(**defaults)

    @classmethod
    def staging(cls, domain: str, **kwargs) -> "EnvironmentConfig":
        """Create a staging environment configuration."""
        defaults = {
            "name": "staging",
            "debug": False,
            "allowed_hosts": [domain, f"*.{domain}"],
            "cache_backend": "django.core.cache.backends.redis.RedisCache",
            "email_backend": "django.core.mail.backends.smtp.EmailBackend",
            "secure_ssl_redirect": True,
            "session_cookie_secure": True,
            "csrf_cookie_secure": True,
            "log_level": "INFO",
        }
        defaults.update(kwargs)
        return cls(**defaults)

    @classmethod
    def production(cls, domain: str, **kwargs) -> "EnvironmentConfig":
        """Create a production environment configuration."""
        defaults = {
            "name": "production",
            "debug": False,
            "allowed_hosts": [domain, f"www.{domain}"],
            "cache_backend": "django.core.cache.backends.redis.RedisCache",
            "email_backend": "django.core.mail.backends.smtp.EmailBackend",
            "secure_ssl_redirect": True,
            "session_cookie_secure": True,
            "csrf_cookie_secure": True,
            "secure_hsts_seconds": 31536000,  # 1 year
            "log_level": "WARNING",
            "conn_max_age": 600,
        }
        defaults.update(kwargs)
        return cls(**defaults)


class EnvironmentManager:
    """
    Manages multiple environment configurations.

    Provides tools for:
    - Loading environment configurations
    - Switching between environments
    - Generating environment-specific files
    - Validating configurations
    """

    def __init__(self, project_dir: Path | None = None):
        self.project_dir = project_dir or Path.cwd()
        self.environments: dict[str, EnvironmentConfig] = {}
        self._current: str | None = None

    def add(self, config: EnvironmentConfig):
        """Add an environment configuration."""
        self.environments[config.name] = config

    def remove(self, name: str):
        """Remove an environment configuration."""
        if name in self.environments:
            del self.environments[name]

    def get(self, name: str) -> EnvironmentConfig | None:
        """Get an environment configuration by name."""
        return self.environments.get(name)

    def current(self) -> EnvironmentConfig | None:
        """Get the current environment configuration."""
        if self._current:
            return self.environments.get(self._current)

        # Try to detect from environment variable
        env_name = os.environ.get("DJANGO_ENV", "development")
        return self.environments.get(env_name)

    def set_current(self, name: str):
        """Set the current environment."""
        if name not in self.environments:
            raise ValueError(f"Unknown environment: {name}")
        self._current = name

    def list_environments(self) -> list[str]:
        """List all configured environments."""
        return list(self.environments.keys())

    def init_standard_environments(
        self,
        domain: str,
        db_url_template: str = "postgres://user:pass@host:5432/{env}",
        redis_url_template: str = "redis://host:6379/{db}",
    ):
        """Initialize standard development, staging, and production environments."""
        # Development
        self.add(
            EnvironmentConfig.development(
                database_url=db_url_template.format(env="dev"),
                redis_url=redis_url_template.format(db=0),
            )
        )

        # Staging
        self.add(
            EnvironmentConfig.staging(
                domain=f"staging.{domain}",
                database_url=db_url_template.format(env="staging"),
                redis_url=redis_url_template.format(db=1),
            )
        )

        # Production
        self.add(
            EnvironmentConfig.production(
                domain=domain,
                database_url=db_url_template.format(env="prod"),
                redis_url=redis_url_template.format(db=2),
            )
        )

    def generate_env_files(self, output_dir: Path | None = None):
        """Generate .env files for all environments."""
        output_dir = output_dir or self.project_dir / "envs"
        output_dir.mkdir(exist_ok=True)

        for name, config in self.environments.items():
            env_file = output_dir / f".env.{name}"
            with open(env_file, "w") as f:
                f.write(config.to_env_file())

    def generate_settings_module(self, output_path: Path | None = None) -> str:
        """Generate a Django settings module that loads environment-specific settings."""
        settings_code = '''"""
Environment-based Django settings.

Loads settings based on DJANGO_ENV environment variable.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Determine environment
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development")

# Common settings
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Add your apps here
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Environment-specific settings
'''

        for name, config in self.environments.items():
            settings_code += f'''
if DJANGO_ENV == "{name}":
    DEBUG = {config.debug}
    ALLOWED_HOSTS = {config.allowed_hosts}
'''
            if config.secret_key:
                settings_code += (
                    f'    SECRET_KEY = os.environ.get("SECRET_KEY", "{config.secret_key}")\n'
                )
            else:
                settings_code += '    SECRET_KEY = os.environ.get("SECRET_KEY")\n'

            settings_code += f'''    STATIC_URL = "{config.static_url}"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_URL = "{config.media_url}"
    MEDIA_ROOT = BASE_DIR / "media"
'''

        settings_code += """
# Fallback for unknown environments
if DJANGO_ENV not in ["development", "staging", "production"]:
    DEBUG = True
    ALLOWED_HOSTS = ["*"]
    SECRET_KEY = "insecure-development-key"
"""

        if output_path:
            with open(output_path, "w") as f:
                f.write(settings_code)

        return settings_code

    def validate(self, name: str) -> list[str]:
        """Validate an environment configuration."""
        errors = []
        config = self.environments.get(name)

        if not config:
            return [f"Environment '{name}' not found"]

        # Check required settings
        if not config.secret_key and name != "development":
            errors.append(f"{name}: SECRET_KEY is required for non-development environments")

        if not config.allowed_hosts:
            errors.append(f"{name}: ALLOWED_HOSTS cannot be empty")

        if not config.database_url:
            errors.append(f"{name}: DATABASE_URL is recommended")

        # Security checks for production
        if name == "production" or name == Environment.PRODUCTION.value:
            if config.debug:
                errors.append("production: DEBUG should be False")

            if not config.secure_ssl_redirect:
                errors.append("production: SECURE_SSL_REDIRECT should be True")

            if not config.session_cookie_secure:
                errors.append("production: SESSION_COOKIE_SECURE should be True")

            if not config.csrf_cookie_secure:
                errors.append("production: CSRF_COOKIE_SECURE should be True")

            if config.secure_hsts_seconds < 31536000:
                errors.append(
                    "production: SECURE_HSTS_SECONDS should be at least 31536000 (1 year)"
                )

        return errors

    def validate_all(self) -> dict[str, list[str]]:
        """Validate all environment configurations."""
        return {name: self.validate(name) for name in self.environments}

    def diff(self, env1: str, env2: str) -> dict[str, tuple]:
        """
        Compare two environment configurations.

        Returns a dict of differing settings with (env1_value, env2_value) tuples.
        """
        config1 = self.environments.get(env1)
        config2 = self.environments.get(env2)

        if not config1 or not config2:
            raise ValueError("Both environments must exist")

        diffs = {}
        fields = [
            "debug",
            "allowed_hosts",
            "database_url",
            "redis_url",
            "cache_backend",
            "email_backend",
            "use_s3",
            "log_level",
            "secure_ssl_redirect",
            "session_cookie_secure",
            "csrf_cookie_secure",
            "secure_hsts_seconds",
        ]

        for field in fields:
            val1 = getattr(config1, field)
            val2 = getattr(config2, field)
            if val1 != val2:
                diffs[field] = (val1, val2)

        return diffs

    def to_json(self) -> str:
        """Export all environments to JSON."""
        data = {}
        for name, config in self.environments.items():
            data[name] = {
                "name": config.name,
                "display_name": config.display_name,
                "debug": config.debug,
                "allowed_hosts": config.allowed_hosts,
                "database_url": config.database_url,
                "redis_url": config.redis_url,
                "cache_backend": config.cache_backend,
                "email_backend": config.email_backend,
                "use_s3": config.use_s3,
                "log_level": config.log_level,
                "secure_ssl_redirect": config.secure_ssl_redirect,
                "session_cookie_secure": config.session_cookie_secure,
                "csrf_cookie_secure": config.csrf_cookie_secure,
                "secure_hsts_seconds": config.secure_hsts_seconds,
                "extra_settings": config.extra_settings,
                "env_vars": config.env_vars,
            }
        return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()

    @classmethod
    def from_json(cls, json_str: str, project_dir: Path | None = None) -> "EnvironmentManager":
        """Load environments from JSON."""
        manager = cls(project_dir)
        data = orjson.loads(json_str)

        for name, config_data in data.items():
            config = EnvironmentConfig(**config_data)
            manager.add(config)

        return manager


__all__ = [
    "Environment",
    "EnvironmentConfig",
    "EnvironmentManager",
]
