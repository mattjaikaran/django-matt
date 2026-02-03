"""
Deployment & DevOps utilities.

Provides easy deployment to popular cloud platforms with minimal configuration,
along with production utilities like health checks and environment management.

Usage:
    # Deploy to Fly.io
    python manage.py deploy --platform fly

    # Deploy to K3s
    python manage.py deploy --platform k3s

    # Generate Docker configuration
    python manage.py deploy docker --output ./docker

    # Generate Kubernetes/Helm configuration
    python manage.py deploy kubernetes helm --output ./charts
    python manage.py deploy kubernetes manifests --output ./k8s
    python manage.py deploy kubernetes kustomize --output ./k8s

    # Configure environments
    python manage.py deploy env init --environments dev,staging,prod
"""

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentProvider,
    DeploymentResult,
    DeploymentStatus,
    SecretManager,
    get_provider,
    list_providers,
    register_provider,
)
from django_matt.deploy.docker import (
    ComposeGenerator,
    DockerfileGenerator,
)
from django_matt.deploy.environments import (
    Environment,
    EnvironmentConfig,
    EnvironmentManager,
)
from django_matt.deploy.health import (
    CheckResult,
    HealthCheck,
    HealthStatus,
    configure_health_check,
    get_health_urls,
    health_check_view,
    liveness_check_view,
    readiness_check_view,
)
from django_matt.deploy.providers.aws import AWSProvider
from django_matt.deploy.providers.digitalocean import DigitalOceanProvider
from django_matt.deploy.providers.flyio import FlyioProvider
from django_matt.deploy.providers.hetzner import HetznerProvider
from django_matt.deploy.providers.railway import RailwayProvider
from django_matt.deploy.providers.render import RenderProvider

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
    # K3s (lazy import)
    "get_k3s_provider",
]


def get_k3s_provider():
    """
    Lazy import for K3sProvider to avoid circular import.

    K3sProvider is in django_matt.deployment.kubernetes which depends
    on this module (django_matt.deploy).

    Usage:
        K3sProvider = get_k3s_provider()
        provider = K3sProvider(config)
    """
    from django_matt.deployment.kubernetes import K3sProvider

    return K3sProvider
