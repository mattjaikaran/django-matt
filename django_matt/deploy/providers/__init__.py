"""
Deployment providers for various platforms.
"""

from django_matt.deploy.providers.aws import AWSProvider
from django_matt.deploy.providers.digitalocean import DigitalOceanProvider
from django_matt.deploy.providers.flyio import FlyioProvider
from django_matt.deploy.providers.hetzner import HetznerProvider
from django_matt.deploy.providers.railway import RailwayProvider
from django_matt.deploy.providers.render import RenderProvider

__all__ = [
    "AWSProvider",
    "DigitalOceanProvider",
    "FlyioProvider",
    "HetznerProvider",
    "RailwayProvider",
    "RenderProvider",
    "get_k3s_provider",
]


def get_k3s_provider():
    """
    Lazy import for K3sProvider to avoid circular import.

    K3sProvider is in django_matt.deployment.kubernetes which depends
    on django_matt.deploy.base.
    """
    from django_matt.deployment.kubernetes import K3sProvider

    return K3sProvider
