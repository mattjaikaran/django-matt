"""
Base classes for deployment providers.

Provides the abstract interface that all deployment providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type
from pathlib import Path
import os
import subprocess


class DeploymentStatus(str, Enum):
    """Status of a deployment."""
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DeploymentConfig:
    """
    Configuration for a deployment.

    Contains all settings needed to deploy an application
    to a specific platform.
    """
    # App settings
    app_name: str
    project_dir: Path = field(default_factory=Path.cwd)
    python_version: str = "3.13"
    django_settings_module: str = ""

    # Server settings
    port: int = 8000
    workers: int = 4
    worker_class: str = "uvicorn.workers.UvicornWorker"

    # Database
    database_url: Optional[str] = None
    create_database: bool = True
    database_type: str = "postgresql"

    # Redis/Cache
    redis_url: Optional[str] = None
    create_redis: bool = False

    # Static files
    static_url: str = "/static/"
    static_root: str = "staticfiles"
    use_whitenoise: bool = True

    # Media files
    media_url: str = "/media/"
    media_root: str = "media"
    use_s3: bool = False
    s3_bucket: Optional[str] = None

    # Environment
    environment: str = "production"
    debug: bool = False
    allowed_hosts: List[str] = field(default_factory=list)

    # Secrets
    secrets: Dict[str, str] = field(default_factory=dict)
    secret_key: Optional[str] = None

    # Scaling
    min_instances: int = 1
    max_instances: int = 1
    auto_scale: bool = False

    # Health checks
    health_check_path: str = "/health/"
    health_check_interval: int = 30

    # Custom
    extra_env: Dict[str, str] = field(default_factory=dict)
    extra_packages: List[str] = field(default_factory=list)

    def get_env_vars(self) -> Dict[str, str]:
        """Get all environment variables for deployment."""
        env = {
            "DJANGO_SETTINGS_MODULE": self.django_settings_module,
            "DJANGO_ENV": self.environment,
            "DEBUG": str(self.debug).lower(),
            "PORT": str(self.port),
            "STATIC_URL": self.static_url,
            "STATIC_ROOT": self.static_root,
        }

        if self.database_url:
            env["DATABASE_URL"] = self.database_url

        if self.redis_url:
            env["REDIS_URL"] = self.redis_url

        if self.secret_key:
            env["SECRET_KEY"] = self.secret_key

        if self.allowed_hosts:
            env["ALLOWED_HOSTS"] = ",".join(self.allowed_hosts)

        if self.use_s3 and self.s3_bucket:
            env["AWS_STORAGE_BUCKET_NAME"] = self.s3_bucket

        env.update(self.extra_env)
        env.update(self.secrets)

        return env


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    status: DeploymentStatus
    url: Optional[str] = None
    deployment_id: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == DeploymentStatus.SUCCESS

    def add_log(self, message: str):
        self.logs.append(message)

    def add_error(self, message: str):
        self.errors.append(message)


class DeploymentProvider(ABC):
    """
    Abstract base class for deployment providers.

    Each provider implements deployment to a specific platform
    (Fly.io, Railway, Render, etc.).
    """

    name: str = "base"
    display_name: str = "Base Provider"

    def __init__(self, config: DeploymentConfig):
        self.config = config

    @abstractmethod
    def validate(self) -> List[str]:
        """
        Validate the deployment configuration.

        Returns a list of error messages (empty if valid).
        """
        pass

    @abstractmethod
    def generate_config(self) -> Dict[str, str]:
        """
        Generate platform-specific configuration files.

        Returns a dict mapping filename to content.
        """
        pass

    @abstractmethod
    async def deploy(self) -> DeploymentResult:
        """
        Deploy the application.

        Returns the deployment result.
        """
        pass

    @abstractmethod
    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get the status of a deployment."""
        pass

    async def rollback(self, deployment_id: str) -> DeploymentResult:
        """Rollback to a previous deployment."""
        raise NotImplementedError(f"{self.name} does not support rollback")

    async def scale(self, instances: int) -> DeploymentResult:
        """Scale the application."""
        raise NotImplementedError(f"{self.name} does not support scaling")

    async def get_logs(self, lines: int = 100) -> List[str]:
        """Get application logs."""
        raise NotImplementedError(f"{self.name} does not support logs")

    def run_command(self, command: List[str], capture: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command."""
        return subprocess.run(
            command,
            cwd=self.config.project_dir,
            capture_output=capture,
            text=True,
        )

    def check_cli_installed(self, command: str) -> bool:
        """Check if a CLI tool is installed."""
        try:
            result = subprocess.run(
                ["which", command],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False


class SecretManager:
    """
    Manages secrets for deployments.

    Handles loading secrets from various sources:
    - Environment variables
    - .env files
    - Platform secret stores
    - Vault/AWS Secrets Manager
    """

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = project_dir or Path.cwd()
        self._secrets: Dict[str, str] = {}

    def load_from_env(self, prefix: str = "") -> Dict[str, str]:
        """Load secrets from environment variables."""
        secrets = {}
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            secrets[key] = value
        self._secrets.update(secrets)
        return secrets

    def load_from_dotenv(self, filename: str = ".env") -> Dict[str, str]:
        """Load secrets from a .env file."""
        env_path = self.project_dir / filename
        secrets = {}

        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Remove quotes
                        value = value.strip().strip("'\"")
                        secrets[key.strip()] = value

        self._secrets.update(secrets)
        return secrets

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        return self._secrets.get(key, os.environ.get(key, default))

    def set(self, key: str, value: str):
        """Set a secret value."""
        self._secrets[key] = value

    def get_all(self) -> Dict[str, str]:
        """Get all loaded secrets."""
        return self._secrets.copy()

    def generate_secret_key(self, length: int = 50) -> str:
        """Generate a Django secret key."""
        import secrets
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
        return "".join(secrets.choice(chars) for _ in range(length))

    def export_to_file(self, filename: str, keys: Optional[List[str]] = None):
        """Export secrets to an env file."""
        env_path = self.project_dir / filename
        secrets_to_export = self._secrets if keys is None else {k: self._secrets[k] for k in keys if k in self._secrets}

        with open(env_path, "w") as f:
            for key, value in sorted(secrets_to_export.items()):
                # Quote values with spaces
                if " " in value or "'" in value or '"' in value:
                    value = f'"{value}"'
                f.write(f"{key}={value}\n")


# Provider registry
_providers: Dict[str, Type[DeploymentProvider]] = {}


def register_provider(name: str):
    """Decorator to register a deployment provider."""
    def decorator(cls: Type[DeploymentProvider]):
        _providers[name] = cls
        return cls
    return decorator


def get_provider(name: str, config: DeploymentConfig) -> DeploymentProvider:
    """Get a deployment provider instance by name."""
    if name not in _providers:
        raise ValueError(f"Unknown provider: {name}. Available: {list(_providers.keys())}")
    return _providers[name](config)


def list_providers() -> List[str]:
    """List all registered providers."""
    return list(_providers.keys())


__all__ = [
    "DeploymentStatus",
    "DeploymentConfig",
    "DeploymentResult",
    "DeploymentProvider",
    "SecretManager",
    "register_provider",
    "get_provider",
    "list_providers",
]
