"""
Deployment & DevOps utilities.

Provides easy deployment to popular cloud platforms with minimal configuration,
along with production utilities like health checks and environment management.

Usage:
    # Deploy to Fly.io
    python manage.py deploy --platform fly

    # Generate Docker configuration
    python manage.py deploy docker --output ./docker

    # Configure environments
    python manage.py deploy env init --environments dev,staging,prod
"""

from django_matt.deploy.base import (
    DeploymentProvider,
    DeploymentConfig,
    DeploymentResult,
    DeploymentStatus,
    SecretManager,
    register_provider,
    get_provider,
    list_providers,
)
from django_matt.deploy.providers.flyio import FlyioProvider
from django_matt.deploy.providers.railway import RailwayProvider
from django_matt.deploy.providers.render import RenderProvider
from django_matt.deploy.providers.digitalocean import DigitalOceanProvider
from django_matt.deploy.providers.aws import AWSProvider
from django_matt.deploy.providers.hetzner import HetznerProvider
from django_matt.deploy.docker import (
    DockerfileGenerator,
    ComposeGenerator,
)
from django_matt.deploy.environments import (
    Environment,
    EnvironmentConfig,
    EnvironmentManager,
)
from django_matt.deploy.health import (
    HealthCheck,
    HealthStatus,
    CheckResult,
    health_check_view,
    readiness_check_view,
    liveness_check_view,
    get_health_urls,
    configure_health_check,
)

__all__ = [
    # Base
    "DeploymentProvider",
    "DeploymentConfig",
    "DeploymentResult",
    "DeploymentStatus",
    "SecretManager",
    "register_provider",
    "get_provider",
    "list_providers",
    # Providers
    "FlyioProvider",
    "RailwayProvider",
    "RenderProvider",
    "DigitalOceanProvider",
    "AWSProvider",
    "HetznerProvider",
    # Docker
    "DockerfileGenerator",
    "ComposeGenerator",
    # Environments
    "Environment",
    "EnvironmentConfig",
    "EnvironmentManager",
    # Health
    "HealthCheck",
    "HealthStatus",
    "CheckResult",
    "health_check_view",
    "readiness_check_view",
    "liveness_check_view",
    "get_health_urls",
    "configure_health_check",
]
