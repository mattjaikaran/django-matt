"""
Kubernetes and Helm deployment utilities.

Provides Kubernetes manifest generation, Helm chart creation, K3s support,
and Kustomize overlays for deploying Django applications.

Usage:
    # Generate Helm chart
    from django_matt.deployment import generate_helm_chart
    generate_helm_chart("myapp", output_dir="./charts")

    # Generate Kubernetes manifests
    from django_matt.deployment import KubernetesManifestGenerator
    generator = KubernetesManifestGenerator(app_name="myapp")
    manifests = generator.generate_all()

    # Use K3s provider
    from django_matt.deployment import K3sProvider
    provider = K3sProvider(config)
    await provider.deploy()

    # Generate Kustomize overlays
    from django_matt.deployment import generate_kustomization
    generate_kustomization("myapp", output_dir="./k8s")
"""

from django_matt.deployment.kubernetes import (
    # Helm chart generation
    HelmChartGenerator,
    HelmValues,
    generate_helm_chart,
    # Kubernetes manifest generators
    IngressClass,
    KubernetesConfig,
    KubernetesManifestGenerator,
    ServiceType,
    generate_configmap,
    generate_deployment,
    generate_hpa,
    generate_ingress,
    generate_pdb,
    generate_secret,
    generate_service,
    # K3s provider
    K3sProvider,
    register_k3s_provider,
    # Kustomize support
    KustomizeGenerator,
    generate_kustomization,
)

__all__ = [
    # Helm
    "HelmChartGenerator",
    "HelmValues",
    "generate_helm_chart",
    # Kubernetes manifests
    "KubernetesConfig",
    "KubernetesManifestGenerator",
    "ServiceType",
    "IngressClass",
    "generate_deployment",
    "generate_service",
    "generate_ingress",
    "generate_configmap",
    "generate_secret",
    "generate_hpa",
    "generate_pdb",
    # K3s
    "K3sProvider",
    "register_k3s_provider",
    # Kustomize
    "KustomizeGenerator",
    "generate_kustomization",
]
