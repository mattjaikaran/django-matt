"""
Kubernetes and Helm deployment support.

Provides comprehensive Kubernetes deployment capabilities including:
- Helm chart generation with templates for all common resources
- K3s lightweight cluster support with Traefik ingress
- Kubernetes manifest generators for deployments, services, ingress, etc.
- Kustomize support with environment overlays
"""

import base64
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentProvider,
    DeploymentResult,
    DeploymentStatus,
)


# =============================================================================
# Configuration Classes
# =============================================================================


class ServiceType(str, Enum):
    """Kubernetes service types."""

    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"


class IngressClass(str, Enum):
    """Common ingress controller classes."""

    NGINX = "nginx"
    TRAEFIK = "traefik"
    CONTOUR = "contour"
    ISTIO = "istio"
    HAProxy = "haproxy"


@dataclass
class KubernetesConfig:
    """
    Configuration for Kubernetes deployments.

    Contains all settings needed to generate Kubernetes manifests.
    """

    # Application settings
    app_name: str
    namespace: str = "default"
    image: str = ""
    image_tag: str = "latest"
    replicas: int = 2

    # Container settings
    port: int = 8000
    health_check_path: str = "/health/"
    liveness_path: str = "/live/"
    readiness_path: str = "/ready/"
    startup_probe_enabled: bool = True

    # Resource limits
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"

    # Autoscaling
    hpa_enabled: bool = True
    hpa_min_replicas: int = 2
    hpa_max_replicas: int = 10
    hpa_cpu_target: int = 80
    hpa_memory_target: int = 80

    # Service
    service_type: ServiceType = ServiceType.CLUSTER_IP
    service_port: int = 80
    service_annotations: dict[str, str] = field(default_factory=dict)

    # Ingress
    ingress_enabled: bool = True
    ingress_class: IngressClass = IngressClass.NGINX
    ingress_host: str = ""
    ingress_tls_enabled: bool = True
    ingress_tls_secret: str = ""
    ingress_annotations: dict[str, str] = field(default_factory=dict)

    # Environment
    env_vars: dict[str, str] = field(default_factory=dict)
    secret_refs: list[str] = field(default_factory=list)
    configmap_refs: list[str] = field(default_factory=list)

    # Pod settings
    service_account: str = ""
    node_selector: dict[str, str] = field(default_factory=dict)
    tolerations: list[dict[str, Any]] = field(default_factory=list)
    affinity: dict[str, Any] = field(default_factory=dict)

    # Pod Disruption Budget
    pdb_enabled: bool = True
    pdb_min_available: int | str = 1
    pdb_max_unavailable: int | str | None = None

    # Security
    security_context_enabled: bool = True
    run_as_non_root: bool = True
    run_as_user: int = 1000
    run_as_group: int = 1000
    fs_group: int = 1000
    read_only_root_filesystem: bool = False

    # Labels and annotations
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def get_labels(self) -> dict[str, str]:
        """Get all labels including defaults."""
        default_labels = {
            "app.kubernetes.io/name": self.app_name,
            "app.kubernetes.io/instance": self.app_name,
            "app.kubernetes.io/version": self.image_tag,
            "app.kubernetes.io/managed-by": "django-matt",
        }
        default_labels.update(self.labels)
        return default_labels

    def get_selector_labels(self) -> dict[str, str]:
        """Get labels for pod selection."""
        return {
            "app.kubernetes.io/name": self.app_name,
            "app.kubernetes.io/instance": self.app_name,
        }


@dataclass
class HelmValues:
    """
    Default values for Helm chart.

    These become the values.yaml file.
    """

    # Image
    image_repository: str = ""
    image_tag: str = "latest"
    image_pull_policy: str = "IfNotPresent"
    image_pull_secrets: list[str] = field(default_factory=list)

    # Replicas
    replicas: int = 2

    # Service
    service_type: str = "ClusterIP"
    service_port: int = 80
    service_target_port: int = 8000
    service_annotations: dict[str, str] = field(default_factory=dict)

    # Ingress
    ingress_enabled: bool = True
    ingress_class_name: str = "nginx"
    ingress_annotations: dict[str, str] = field(default_factory=dict)
    ingress_hosts: list[dict[str, Any]] = field(default_factory=list)
    ingress_tls: list[dict[str, Any]] = field(default_factory=list)

    # Resources
    resources_limits_cpu: str = "500m"
    resources_limits_memory: str = "512Mi"
    resources_requests_cpu: str = "100m"
    resources_requests_memory: str = "128Mi"

    # Autoscaling
    autoscaling_enabled: bool = True
    autoscaling_min_replicas: int = 2
    autoscaling_max_replicas: int = 10
    autoscaling_target_cpu: int = 80
    autoscaling_target_memory: int = 80

    # Pod Disruption Budget
    pdb_enabled: bool = True
    pdb_min_available: int = 1

    # Probes
    liveness_probe_path: str = "/live/"
    liveness_probe_initial_delay: int = 10
    liveness_probe_period: int = 10
    readiness_probe_path: str = "/ready/"
    readiness_probe_initial_delay: int = 5
    readiness_probe_period: int = 5

    # Security
    pod_security_context_enabled: bool = True
    pod_security_context_fs_group: int = 1000
    container_security_context_enabled: bool = True
    container_security_context_run_as_non_root: bool = True
    container_security_context_run_as_user: int = 1000

    # Service Account
    service_account_create: bool = True
    service_account_name: str = ""
    service_account_annotations: dict[str, str] = field(default_factory=dict)

    # Extra environment variables
    env: list[dict[str, Any]] = field(default_factory=list)
    env_from: list[dict[str, Any]] = field(default_factory=list)

    # ConfigMap and Secret
    config_map_data: dict[str, str] = field(default_factory=dict)
    secret_data: dict[str, str] = field(default_factory=dict)

    # Node selection
    node_selector: dict[str, str] = field(default_factory=dict)
    tolerations: list[dict[str, Any]] = field(default_factory=list)
    affinity: dict[str, Any] = field(default_factory=dict)

    # Extra labels and annotations
    pod_labels: dict[str, str] = field(default_factory=dict)
    pod_annotations: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to nested dictionary structure for values.yaml."""
        return {
            "replicaCount": self.replicas,
            "image": {
                "repository": self.image_repository,
                "tag": self.image_tag,
                "pullPolicy": self.image_pull_policy,
            },
            "imagePullSecrets": [{"name": s} for s in self.image_pull_secrets],
            "service": {
                "type": self.service_type,
                "port": self.service_port,
                "targetPort": self.service_target_port,
                "annotations": self.service_annotations,
            },
            "ingress": {
                "enabled": self.ingress_enabled,
                "className": self.ingress_class_name,
                "annotations": self.ingress_annotations,
                "hosts": self.ingress_hosts
                or [{"host": "chart-example.local", "paths": [{"path": "/", "pathType": "Prefix"}]}],
                "tls": self.ingress_tls,
            },
            "resources": {
                "limits": {
                    "cpu": self.resources_limits_cpu,
                    "memory": self.resources_limits_memory,
                },
                "requests": {
                    "cpu": self.resources_requests_cpu,
                    "memory": self.resources_requests_memory,
                },
            },
            "autoscaling": {
                "enabled": self.autoscaling_enabled,
                "minReplicas": self.autoscaling_min_replicas,
                "maxReplicas": self.autoscaling_max_replicas,
                "targetCPUUtilizationPercentage": self.autoscaling_target_cpu,
                "targetMemoryUtilizationPercentage": self.autoscaling_target_memory,
            },
            "podDisruptionBudget": {
                "enabled": self.pdb_enabled,
                "minAvailable": self.pdb_min_available,
            },
            "livenessProbe": {
                "httpGet": {"path": self.liveness_probe_path, "port": "http"},
                "initialDelaySeconds": self.liveness_probe_initial_delay,
                "periodSeconds": self.liveness_probe_period,
            },
            "readinessProbe": {
                "httpGet": {"path": self.readiness_probe_path, "port": "http"},
                "initialDelaySeconds": self.readiness_probe_initial_delay,
                "periodSeconds": self.readiness_probe_period,
            },
            "podSecurityContext": {
                "enabled": self.pod_security_context_enabled,
                "fsGroup": self.pod_security_context_fs_group,
            },
            "securityContext": {
                "enabled": self.container_security_context_enabled,
                "runAsNonRoot": self.container_security_context_run_as_non_root,
                "runAsUser": self.container_security_context_run_as_user,
            },
            "serviceAccount": {
                "create": self.service_account_create,
                "name": self.service_account_name,
                "annotations": self.service_account_annotations,
            },
            "env": self.env,
            "envFrom": self.env_from,
            "configMap": {"data": self.config_map_data},
            "secret": {"data": self.secret_data},
            "nodeSelector": self.node_selector,
            "tolerations": self.tolerations,
            "affinity": self.affinity,
            "podLabels": self.pod_labels,
            "podAnnotations": self.pod_annotations,
        }


# =============================================================================
# Kubernetes Manifest Generator
# =============================================================================


class KubernetesManifestGenerator:
    """
    Generates Kubernetes manifests for Django applications.

    Supports:
    - Deployments with rolling updates
    - Services (ClusterIP, NodePort, LoadBalancer)
    - Ingress with TLS
    - ConfigMaps and Secrets
    - Horizontal Pod Autoscaler
    - Pod Disruption Budget
    """

    def __init__(self, config: KubernetesConfig):
        self.config = config

    def generate_all(self) -> dict[str, str]:
        """Generate all Kubernetes manifests."""
        manifests = {
            "deployment.yaml": self.generate_deployment(),
            "service.yaml": self.generate_service(),
        }

        if self.config.ingress_enabled:
            manifests["ingress.yaml"] = self.generate_ingress()

        if self.config.env_vars:
            manifests["configmap.yaml"] = self.generate_configmap()

        if self.config.hpa_enabled:
            manifests["hpa.yaml"] = self.generate_hpa()

        if self.config.pdb_enabled:
            manifests["pdb.yaml"] = self.generate_pdb()

        return manifests

    def generate_deployment(self) -> str:
        """Generate Deployment YAML."""
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": self.config.app_name,
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
                "annotations": self.config.annotations,
            },
            "spec": {
                "replicas": self.config.replicas,
                "selector": {"matchLabels": self.config.get_selector_labels()},
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxSurge": "25%", "maxUnavailable": "25%"},
                },
                "template": {
                    "metadata": {
                        "labels": self.config.get_labels(),
                        "annotations": self.config.annotations,
                    },
                    "spec": self._build_pod_spec(),
                },
            },
        }

        return yaml.dump(deployment, default_flow_style=False, sort_keys=False)

    def _build_pod_spec(self) -> dict[str, Any]:
        """Build pod specification."""
        container = {
            "name": self.config.app_name,
            "image": f"{self.config.image}:{self.config.image_tag}",
            "imagePullPolicy": "IfNotPresent",
            "ports": [{"name": "http", "containerPort": self.config.port, "protocol": "TCP"}],
            "resources": {
                "requests": {
                    "cpu": self.config.cpu_request,
                    "memory": self.config.memory_request,
                },
                "limits": {"cpu": self.config.cpu_limit, "memory": self.config.memory_limit},
            },
            "livenessProbe": {
                "httpGet": {"path": self.config.liveness_path, "port": "http"},
                "initialDelaySeconds": 10,
                "periodSeconds": 10,
                "timeoutSeconds": 5,
                "failureThreshold": 3,
            },
            "readinessProbe": {
                "httpGet": {"path": self.config.readiness_path, "port": "http"},
                "initialDelaySeconds": 5,
                "periodSeconds": 5,
                "timeoutSeconds": 3,
                "failureThreshold": 3,
            },
        }

        # Add startup probe if enabled
        if self.config.startup_probe_enabled:
            container["startupProbe"] = {
                "httpGet": {"path": self.config.health_check_path, "port": "http"},
                "initialDelaySeconds": 5,
                "periodSeconds": 5,
                "timeoutSeconds": 3,
                "failureThreshold": 30,
            }

        # Add environment variables
        env = []
        for key, value in self.config.env_vars.items():
            env.append({"name": key, "value": value})

        if env:
            container["env"] = env

        # Add envFrom for configmaps and secrets
        env_from = []
        for configmap in self.config.configmap_refs:
            env_from.append({"configMapRef": {"name": configmap}})
        for secret in self.config.secret_refs:
            env_from.append({"secretRef": {"name": secret}})

        if env_from:
            container["envFrom"] = env_from

        # Add security context
        if self.config.security_context_enabled:
            container["securityContext"] = {
                "runAsNonRoot": self.config.run_as_non_root,
                "runAsUser": self.config.run_as_user,
                "runAsGroup": self.config.run_as_group,
                "readOnlyRootFilesystem": self.config.read_only_root_filesystem,
                "allowPrivilegeEscalation": False,
                "capabilities": {"drop": ["ALL"]},
            }

        # Build pod spec
        pod_spec: dict[str, Any] = {
            "containers": [container],
            "terminationGracePeriodSeconds": 30,
        }

        # Add service account
        if self.config.service_account:
            pod_spec["serviceAccountName"] = self.config.service_account

        # Add pod security context
        if self.config.security_context_enabled:
            pod_spec["securityContext"] = {
                "fsGroup": self.config.fs_group,
                "runAsNonRoot": self.config.run_as_non_root,
            }

        # Add node selector
        if self.config.node_selector:
            pod_spec["nodeSelector"] = self.config.node_selector

        # Add tolerations
        if self.config.tolerations:
            pod_spec["tolerations"] = self.config.tolerations

        # Add affinity
        if self.config.affinity:
            pod_spec["affinity"] = self.config.affinity

        return pod_spec

    def generate_service(self) -> str:
        """Generate Service YAML."""
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.config.app_name,
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
            },
            "spec": {
                "type": self.config.service_type.value,
                "ports": [
                    {
                        "name": "http",
                        "port": self.config.service_port,
                        "targetPort": "http",
                        "protocol": "TCP",
                    }
                ],
                "selector": self.config.get_selector_labels(),
            },
        }

        if self.config.service_annotations:
            service["metadata"]["annotations"] = self.config.service_annotations

        return yaml.dump(service, default_flow_style=False, sort_keys=False)

    def generate_ingress(self) -> str:
        """Generate Ingress YAML with TLS support."""
        ingress: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": self.config.app_name,
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
                "annotations": {
                    "kubernetes.io/ingress.class": self.config.ingress_class.value,
                },
            },
            "spec": {
                "ingressClassName": self.config.ingress_class.value,
                "rules": [
                    {
                        "host": self.config.ingress_host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": self.config.app_name,
                                            "port": {"number": self.config.service_port},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ],
            },
        }

        # Add custom annotations
        if self.config.ingress_annotations:
            ingress["metadata"]["annotations"].update(self.config.ingress_annotations)

        # Add TLS configuration
        if self.config.ingress_tls_enabled and self.config.ingress_host:
            tls_secret = self.config.ingress_tls_secret or f"{self.config.app_name}-tls"
            ingress["spec"]["tls"] = [
                {"hosts": [self.config.ingress_host], "secretName": tls_secret}
            ]

            # Add cert-manager annotation for automatic certificate
            if "cert-manager.io/cluster-issuer" not in ingress["metadata"]["annotations"]:
                ingress["metadata"]["annotations"]["cert-manager.io/cluster-issuer"] = (
                    "letsencrypt-prod"
                )

        return yaml.dump(ingress, default_flow_style=False, sort_keys=False)

    def generate_configmap(self, data: dict[str, str] | None = None) -> str:
        """Generate ConfigMap YAML from settings."""
        config_data = data or self.config.env_vars

        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"{self.config.app_name}-config",
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
            },
            "data": config_data,
        }

        return yaml.dump(configmap, default_flow_style=False, sort_keys=False)

    def generate_secret(self, data: dict[str, str] | None = None) -> str:
        """Generate Secret YAML from env vars (base64 encoded)."""
        secret_data = data or {}

        # Base64 encode the values
        encoded_data = {
            key: base64.b64encode(value.encode()).decode() for key, value in secret_data.items()
        }

        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": f"{self.config.app_name}-secret",
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
            },
            "type": "Opaque",
            "data": encoded_data,
        }

        return yaml.dump(secret, default_flow_style=False, sort_keys=False)

    def generate_hpa(self) -> str:
        """Generate Horizontal Pod Autoscaler YAML."""
        hpa = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": self.config.app_name,
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": self.config.app_name,
                },
                "minReplicas": self.config.hpa_min_replicas,
                "maxReplicas": self.config.hpa_max_replicas,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": self.config.hpa_cpu_target,
                            },
                        },
                    },
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "memory",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": self.config.hpa_memory_target,
                            },
                        },
                    },
                ],
                "behavior": {
                    "scaleDown": {
                        "stabilizationWindowSeconds": 300,
                        "policies": [
                            {"type": "Percent", "value": 10, "periodSeconds": 60},
                            {"type": "Pods", "value": 1, "periodSeconds": 60},
                        ],
                        "selectPolicy": "Min",
                    },
                    "scaleUp": {
                        "stabilizationWindowSeconds": 0,
                        "policies": [
                            {"type": "Percent", "value": 100, "periodSeconds": 15},
                            {"type": "Pods", "value": 4, "periodSeconds": 15},
                        ],
                        "selectPolicy": "Max",
                    },
                },
            },
        }

        return yaml.dump(hpa, default_flow_style=False, sort_keys=False)

    def generate_pdb(self) -> str:
        """Generate Pod Disruption Budget YAML."""
        pdb: dict[str, Any] = {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {
                "name": self.config.app_name,
                "namespace": self.config.namespace,
                "labels": self.config.get_labels(),
            },
            "spec": {"selector": {"matchLabels": self.config.get_selector_labels()}},
        }

        if self.config.pdb_max_unavailable is not None:
            pdb["spec"]["maxUnavailable"] = self.config.pdb_max_unavailable
        else:
            pdb["spec"]["minAvailable"] = self.config.pdb_min_available

        return yaml.dump(pdb, default_flow_style=False, sort_keys=False)


# =============================================================================
# Standalone Generator Functions
# =============================================================================


def generate_deployment(
    app_name: str,
    image: str,
    replicas: int = 2,
    port: int = 8000,
    namespace: str = "default",
    **kwargs: Any,
) -> str:
    """
    Generate a Kubernetes Deployment manifest.

    Args:
        app_name: Application name
        image: Container image (e.g., "myapp:latest")
        replicas: Number of replicas
        port: Container port
        namespace: Kubernetes namespace
        **kwargs: Additional KubernetesConfig parameters

    Returns:
        YAML string of the Deployment manifest
    """
    image_parts = image.rsplit(":", 1)
    image_name = image_parts[0]
    image_tag = image_parts[1] if len(image_parts) > 1 else "latest"

    config = KubernetesConfig(
        app_name=app_name,
        image=image_name,
        image_tag=image_tag,
        replicas=replicas,
        port=port,
        namespace=namespace,
        **kwargs,
    )
    generator = KubernetesManifestGenerator(config)
    return generator.generate_deployment()


def generate_service(
    app_name: str,
    port: int = 80,
    target_port: int = 8000,
    service_type: ServiceType = ServiceType.CLUSTER_IP,
    namespace: str = "default",
    **kwargs: Any,
) -> str:
    """
    Generate a Kubernetes Service manifest.

    Args:
        app_name: Application name
        port: Service port
        target_port: Target container port
        service_type: Service type (ClusterIP, NodePort, LoadBalancer)
        namespace: Kubernetes namespace

    Returns:
        YAML string of the Service manifest
    """
    config = KubernetesConfig(
        app_name=app_name,
        service_port=port,
        port=target_port,
        service_type=service_type,
        namespace=namespace,
        **kwargs,
    )
    generator = KubernetesManifestGenerator(config)
    return generator.generate_service()


def generate_ingress(
    app_name: str,
    host: str,
    service_port: int = 80,
    tls_enabled: bool = True,
    ingress_class: IngressClass = IngressClass.NGINX,
    namespace: str = "default",
    annotations: dict[str, str] | None = None,
    **kwargs: Any,
) -> str:
    """
    Generate a Kubernetes Ingress manifest.

    Args:
        app_name: Application name
        host: Hostname for the ingress
        service_port: Backend service port
        tls_enabled: Enable TLS
        ingress_class: Ingress controller class
        namespace: Kubernetes namespace
        annotations: Additional annotations

    Returns:
        YAML string of the Ingress manifest
    """
    config = KubernetesConfig(
        app_name=app_name,
        ingress_host=host,
        service_port=service_port,
        ingress_tls_enabled=tls_enabled,
        ingress_class=ingress_class,
        namespace=namespace,
        ingress_annotations=annotations or {},
        **kwargs,
    )
    generator = KubernetesManifestGenerator(config)
    return generator.generate_ingress()


def generate_configmap(
    app_name: str,
    data: dict[str, str],
    namespace: str = "default",
) -> str:
    """
    Generate a Kubernetes ConfigMap manifest.

    Args:
        app_name: Application name
        data: ConfigMap data
        namespace: Kubernetes namespace

    Returns:
        YAML string of the ConfigMap manifest
    """
    config = KubernetesConfig(app_name=app_name, namespace=namespace)
    generator = KubernetesManifestGenerator(config)
    return generator.generate_configmap(data)


def generate_secret(
    app_name: str,
    data: dict[str, str],
    namespace: str = "default",
) -> str:
    """
    Generate a Kubernetes Secret manifest.

    Args:
        app_name: Application name
        data: Secret data (will be base64 encoded)
        namespace: Kubernetes namespace

    Returns:
        YAML string of the Secret manifest
    """
    config = KubernetesConfig(app_name=app_name, namespace=namespace)
    generator = KubernetesManifestGenerator(config)
    return generator.generate_secret(data)


def generate_hpa(
    app_name: str,
    min_replicas: int = 2,
    max_replicas: int = 10,
    cpu_target: int = 80,
    memory_target: int = 80,
    namespace: str = "default",
) -> str:
    """
    Generate a Horizontal Pod Autoscaler manifest.

    Args:
        app_name: Application name
        min_replicas: Minimum number of replicas
        max_replicas: Maximum number of replicas
        cpu_target: Target CPU utilization percentage
        memory_target: Target memory utilization percentage
        namespace: Kubernetes namespace

    Returns:
        YAML string of the HPA manifest
    """
    config = KubernetesConfig(
        app_name=app_name,
        hpa_min_replicas=min_replicas,
        hpa_max_replicas=max_replicas,
        hpa_cpu_target=cpu_target,
        hpa_memory_target=memory_target,
        namespace=namespace,
    )
    generator = KubernetesManifestGenerator(config)
    return generator.generate_hpa()


def generate_pdb(
    app_name: str,
    min_available: int | str = 1,
    max_unavailable: int | str | None = None,
    namespace: str = "default",
) -> str:
    """
    Generate a Pod Disruption Budget manifest.

    Args:
        app_name: Application name
        min_available: Minimum available pods (int or percentage string)
        max_unavailable: Maximum unavailable pods (overrides min_available)
        namespace: Kubernetes namespace

    Returns:
        YAML string of the PDB manifest
    """
    config = KubernetesConfig(
        app_name=app_name,
        pdb_min_available=min_available,
        pdb_max_unavailable=max_unavailable,
        namespace=namespace,
    )
    generator = KubernetesManifestGenerator(config)
    return generator.generate_pdb()


# =============================================================================
# Helm Chart Generator
# =============================================================================


class HelmChartGenerator:
    """
    Generates complete Helm charts for Django applications.

    Creates:
    - Chart.yaml with metadata
    - values.yaml with sensible defaults
    - Templates for Deployment, Service, Ingress, ConfigMap, Secret, HPA, PDB
    - _helpers.tpl for template functions
    - NOTES.txt for post-install instructions
    """

    def __init__(
        self,
        app_name: str,
        version: str = "0.1.0",
        app_version: str = "1.0.0",
        description: str = "",
        values: HelmValues | None = None,
    ):
        self.app_name = app_name
        self.version = version
        self.app_version = app_version
        self.description = description or f"A Helm chart for {app_name}"
        self.values = values or HelmValues(image_repository=app_name)

    def generate(self) -> dict[str, str]:
        """Generate all Helm chart files."""
        files = {
            "Chart.yaml": self._generate_chart_yaml(),
            "values.yaml": self._generate_values_yaml(),
            "templates/_helpers.tpl": self._generate_helpers(),
            "templates/deployment.yaml": self._generate_deployment_template(),
            "templates/service.yaml": self._generate_service_template(),
            "templates/ingress.yaml": self._generate_ingress_template(),
            "templates/configmap.yaml": self._generate_configmap_template(),
            "templates/secret.yaml": self._generate_secret_template(),
            "templates/hpa.yaml": self._generate_hpa_template(),
            "templates/pdb.yaml": self._generate_pdb_template(),
            "templates/serviceaccount.yaml": self._generate_serviceaccount_template(),
            "templates/NOTES.txt": self._generate_notes(),
            ".helmignore": self._generate_helmignore(),
        }
        return files

    def write(self, output_dir: Path):
        """Write Helm chart to directory."""
        chart_dir = output_dir / self.app_name
        chart_dir.mkdir(parents=True, exist_ok=True)

        files = self.generate()
        for filename, content in files.items():
            file_path = chart_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)

        return chart_dir

    def _generate_chart_yaml(self) -> str:
        """Generate Chart.yaml."""
        chart = {
            "apiVersion": "v2",
            "name": self.app_name,
            "description": self.description,
            "type": "application",
            "version": self.version,
            "appVersion": self.app_version,
            "keywords": ["django", "python", "web"],
            "home": f"https://github.com/example/{self.app_name}",
            "sources": [f"https://github.com/example/{self.app_name}"],
            "maintainers": [{"name": "maintainer", "email": "maintainer@example.com"}],
        }
        return yaml.dump(chart, default_flow_style=False, sort_keys=False)

    def _generate_values_yaml(self) -> str:
        """Generate values.yaml with defaults."""
        values = self.values.to_dict()

        # Add header comment
        header = """# Default values for {app_name}.
# This is a YAML-formatted file.
# Declare variables to be passed into your templates.

""".format(app_name=self.app_name)

        return header + yaml.dump(values, default_flow_style=False, sort_keys=False)

    def _generate_helpers(self) -> str:
        """Generate _helpers.tpl template functions."""
        return '''{{/*
Expand the name of the chart.
*/}}
{{{{- define "{app_name}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{/*
Create a default fully qualified app name.
*/}}
{{{{- define "{app_name}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{{{- define "{app_name}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{/*
Common labels
*/}}
{{{{- define "{app_name}.labels" -}}}}
helm.sh/chart: {{{{ include "{app_name}.chart" . }}}}
{{{{ include "{app_name}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{/*
Selector labels
*/}}
{{{{- define "{app_name}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{app_name}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}

{{/*
Create the name of the service account to use
*/}}
{{{{- define "{app_name}.serviceAccountName" -}}}}
{{{{- if .Values.serviceAccount.create }}}}
{{{{- default (include "{app_name}.fullname" .) .Values.serviceAccount.name }}}}
{{{{- else }}}}
{{{{- default "default" .Values.serviceAccount.name }}}}
{{{{- end }}}}
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_deployment_template(self) -> str:
        """Generate deployment.yaml template."""
        return '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
spec:
  {{{{- if not .Values.autoscaling.enabled }}}}
  replicas: {{{{ .Values.replicaCount }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{app_name}.selectorLabels" . | nindent 6 }}}}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 25%
  template:
    metadata:
      {{{{- with .Values.podAnnotations }}}}
      annotations:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      labels:
        {{{{- include "{app_name}.selectorLabels" . | nindent 8 }}}}
        {{{{- with .Values.podLabels }}}}
        {{{{- toYaml . | nindent 8 }}}}
        {{{{- end }}}}
    spec:
      {{{{- with .Values.imagePullSecrets }}}}
      imagePullSecrets:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      serviceAccountName: {{{{ include "{app_name}.serviceAccountName" . }}}}
      {{{{- if .Values.podSecurityContext.enabled }}}}
      securityContext:
        fsGroup: {{{{ .Values.podSecurityContext.fsGroup }}}}
      {{{{- end }}}}
      containers:
        - name: {{{{ .Chart.Name }}}}
          {{{{- if .Values.securityContext.enabled }}}}
          securityContext:
            runAsNonRoot: {{{{ .Values.securityContext.runAsNonRoot }}}}
            runAsUser: {{{{ .Values.securityContext.runAsUser }}}}
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          {{{{- end }}}}
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          ports:
            - name: http
              containerPort: {{{{ .Values.service.targetPort }}}}
              protocol: TCP
          {{{{- with .Values.env }}}}
          env:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
          {{{{- with .Values.envFrom }}}}
          envFrom:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
          livenessProbe:
            {{{{- toYaml .Values.livenessProbe | nindent 12 }}}}
          readinessProbe:
            {{{{- toYaml .Values.readinessProbe | nindent 12 }}}}
          resources:
            {{{{- toYaml .Values.resources | nindent 12 }}}}
      {{{{- with .Values.nodeSelector }}}}
      nodeSelector:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.affinity }}}}
      affinity:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.tolerations }}}}
      tolerations:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_service_template(self) -> str:
        """Generate service.yaml template."""
        return '''apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.service.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
    - port: {{{{ .Values.service.port }}}}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{{{- include "{app_name}.selectorLabels" . | nindent 4 }}}}
'''.format(app_name=self.app_name)

    def _generate_ingress_template(self) -> str:
        """Generate ingress.yaml template."""
        return '''{{{{- if .Values.ingress.enabled -}}}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.ingress.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
spec:
  {{{{- if .Values.ingress.className }}}}
  ingressClassName: {{{{ .Values.ingress.className }}}}
  {{{{- end }}}}
  {{{{- if .Values.ingress.tls }}}}
  tls:
    {{{{- range .Values.ingress.tls }}}}
    - hosts:
        {{{{- range .hosts }}}}
        - {{{{ . | quote }}}}
        {{{{- end }}}}
      secretName: {{{{ .secretName }}}}
    {{{{- end }}}}
  {{{{- end }}}}
  rules:
    {{{{- range .Values.ingress.hosts }}}}
    - host: {{{{ .host | quote }}}}
      http:
        paths:
          {{{{- range .paths }}}}
          - path: {{{{ .path }}}}
            pathType: {{{{ .pathType }}}}
            backend:
              service:
                name: {{{{ include "{app_name}.fullname" $ }}}}
                port:
                  number: {{{{ $.Values.service.port }}}}
          {{{{- end }}}}
    {{{{- end }}}}
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_configmap_template(self) -> str:
        """Generate configmap.yaml template."""
        return '''{{{{- if .Values.configMap.data }}}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}-config
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
data:
  {{{{- toYaml .Values.configMap.data | nindent 2 }}}}
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_secret_template(self) -> str:
        """Generate secret.yaml template."""
        return '''{{{{- if .Values.secret.data }}}}
apiVersion: v1
kind: Secret
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}-secret
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
type: Opaque
data:
  {{{{- range $key, $val := .Values.secret.data }}}}
  {{{{ $key }}}}: {{{{ $val | b64enc | quote }}}}
  {{{{- end }}}}
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_hpa_template(self) -> str:
        """Generate hpa.yaml template."""
        return '''{{{{- if .Values.autoscaling.enabled }}}}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{{{ include "{app_name}.fullname" . }}}}
  minReplicas: {{{{ .Values.autoscaling.minReplicas }}}}
  maxReplicas: {{{{ .Values.autoscaling.maxReplicas }}}}
  metrics:
    {{{{- if .Values.autoscaling.targetCPUUtilizationPercentage }}}}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.autoscaling.targetCPUUtilizationPercentage }}}}
    {{{{- end }}}}
    {{{{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}}}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.autoscaling.targetMemoryUtilizationPercentage }}}}
    {{{{- end }}}}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
        - type: Pods
          value: 4
          periodSeconds: 15
      selectPolicy: Max
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_pdb_template(self) -> str:
        """Generate pdb.yaml template."""
        return '''{{{{- if .Values.podDisruptionBudget.enabled }}}}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{{{ include "{app_name}.fullname" . }}}}
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
spec:
  {{{{- if .Values.podDisruptionBudget.minAvailable }}}}
  minAvailable: {{{{ .Values.podDisruptionBudget.minAvailable }}}}
  {{{{- end }}}}
  {{{{- if .Values.podDisruptionBudget.maxUnavailable }}}}
  maxUnavailable: {{{{ .Values.podDisruptionBudget.maxUnavailable }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{app_name}.selectorLabels" . | nindent 6 }}}}
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_serviceaccount_template(self) -> str:
        """Generate serviceaccount.yaml template."""
        return '''{{{{- if .Values.serviceAccount.create -}}}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{{{ include "{app_name}.serviceAccountName" . }}}}
  labels:
    {{{{- include "{app_name}.labels" . | nindent 4 }}}}
  {{{{- with .Values.serviceAccount.annotations }}}}
  annotations:
    {{{{- toYaml . | nindent 4 }}}}
  {{{{- end }}}}
{{{{- end }}}}
'''.format(app_name=self.app_name)

    def _generate_notes(self) -> str:
        """Generate NOTES.txt for post-install instructions."""
        return '''1. Get the application URL by running these commands:
{{{{- if .Values.ingress.enabled }}}}
{{{{- range $host := .Values.ingress.hosts }}}}
  {{{{- range .paths }}}}
  http{{{{ if $.Values.ingress.tls }}}}s{{{{ end }}}}://{{{{ $host.host }}}}{{{{ .path }}}}
  {{{{- end }}}}
{{{{- end }}}}
{{{{- else if contains "NodePort" .Values.service.type }}}}
  export NODE_PORT=$(kubectl get --namespace {{{{ .Release.Namespace }}}} -o jsonpath="{{{{.spec.ports[0].nodePort}}}}" services {{{{ include "{app_name}.fullname" . }}}})
  export NODE_IP=$(kubectl get nodes --namespace {{{{ .Release.Namespace }}}} -o jsonpath="{{{{.items[0].status.addresses[0].address}}}}")
  echo http://$NODE_IP:$NODE_PORT
{{{{- else if contains "LoadBalancer" .Values.service.type }}}}
     NOTE: It may take a few minutes for the LoadBalancer IP to be available.
           You can watch the status of by running 'kubectl get --namespace {{{{ .Release.Namespace }}}} svc -w {{{{ include "{app_name}.fullname" . }}}}'
  export SERVICE_IP=$(kubectl get svc --namespace {{{{ .Release.Namespace }}}} {{{{ include "{app_name}.fullname" . }}}} --template "{{{{ range (index .status.loadBalancer.ingress 0) }}}}{{{{.}}}}{{{{ end }}}}")
  echo http://$SERVICE_IP:{{{{ .Values.service.port }}}}
{{{{- else if contains "ClusterIP" .Values.service.type }}}}
  export POD_NAME=$(kubectl get pods --namespace {{{{ .Release.Namespace }}}} -l "app.kubernetes.io/name={{{{ include "{app_name}.name" . }}}},app.kubernetes.io/instance={{{{ .Release.Name }}}}" -o jsonpath="{{{{.items[0].metadata.name}}}}")
  export CONTAINER_PORT=$(kubectl get pod --namespace {{{{ .Release.Namespace }}}} $POD_NAME -o jsonpath="{{{{.spec.containers[0].ports[0].containerPort}}}}")
  echo "Visit http://127.0.0.1:8080 to use your application"
  kubectl --namespace {{{{ .Release.Namespace }}}} port-forward $POD_NAME 8080:$CONTAINER_PORT
{{{{- end }}}}

2. Check the application status:
  kubectl get pods -l app.kubernetes.io/name={{{{ include "{app_name}.name" . }}}} -n {{{{ .Release.Namespace }}}}

3. View application logs:
  kubectl logs -f -l app.kubernetes.io/name={{{{ include "{app_name}.name" . }}}} -n {{{{ .Release.Namespace }}}}
'''.format(app_name=self.app_name)

    def _generate_helmignore(self) -> str:
        """Generate .helmignore file."""
        return """# Patterns to ignore when building packages.
# This supports shell glob matching, relative path matching, and
# negation (prefixed with !). Only one pattern per line.
.DS_Store
# Common VCS dirs
.git/
.gitignore
.bzr/
.bzrignore
.hg/
.hgignore
.svn/
# Common backup files
*.swp
*.bak
*.tmp
*.orig
*~
# Various IDEs
.project
.idea/
*.tmproj
.vscode/
"""


def generate_helm_chart(
    app_name: str,
    output_dir: str | Path = ".",
    version: str = "0.1.0",
    app_version: str = "1.0.0",
    description: str = "",
    values: HelmValues | None = None,
) -> Path:
    """
    Generate a complete Helm chart for a Django application.

    Args:
        app_name: Application name (becomes chart name)
        output_dir: Output directory for the chart
        version: Chart version
        app_version: Application version
        description: Chart description
        values: Custom HelmValues configuration

    Returns:
        Path to the generated chart directory
    """
    generator = HelmChartGenerator(
        app_name=app_name,
        version=version,
        app_version=app_version,
        description=description,
        values=values,
    )
    return generator.write(Path(output_dir))


# =============================================================================
# K3s Provider
# =============================================================================


class K3sProvider(DeploymentProvider):
    """
    K3s lightweight Kubernetes deployment provider.

    Supports:
    - Automatic manifest generation
    - Traefik ingress configuration
    - Local storage class setup
    - Single-node and multi-node clusters
    """

    name = "k3s"
    display_name = "K3s (Lightweight Kubernetes)"

    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self.k8s_config = self._build_k8s_config()

    def _build_k8s_config(self) -> KubernetesConfig:
        """Build KubernetesConfig from DeploymentConfig."""
        return KubernetesConfig(
            app_name=self.config.app_name,
            namespace="default",
            image=f"{self.config.app_name}",
            image_tag="latest",
            replicas=self.config.min_instances,
            port=self.config.port,
            health_check_path=self.config.health_check_path,
            ingress_enabled=bool(self.config.allowed_hosts),
            ingress_class=IngressClass.TRAEFIK,
            ingress_host=self.config.allowed_hosts[0] if self.config.allowed_hosts else "",
            ingress_tls_enabled=True,
            env_vars=self.config.get_env_vars(),
            hpa_enabled=self.config.auto_scale,
            hpa_min_replicas=self.config.min_instances,
            hpa_max_replicas=self.config.max_instances,
        )

    def validate(self) -> list[str]:
        """Validate configuration for K3s deployment."""
        errors = []

        # Check kubectl is installed
        if not self.check_cli_installed("kubectl"):
            errors.append("kubectl CLI is not installed")

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")

        # Check k3s cluster is accessible
        result = self.run_command(["kubectl", "cluster-info"])
        if result.returncode != 0:
            errors.append("Cannot connect to Kubernetes cluster. Is K3s running?")

        return errors

    def generate_config(self) -> dict[str, str]:
        """Generate K3s-specific configuration files."""
        generator = KubernetesManifestGenerator(self.k8s_config)
        files = generator.generate_all()

        # Add K3s-specific Traefik IngressRoute if using Traefik
        if self.k8s_config.ingress_enabled:
            files["ingressroute.yaml"] = self._generate_traefik_ingressroute()

        # Add local storage class
        files["storageclass.yaml"] = self._generate_local_storage_class()

        # Add combined manifest
        files["all-in-one.yaml"] = self._generate_combined_manifest(files)

        return files

    def _generate_traefik_ingressroute(self) -> str:
        """Generate Traefik IngressRoute for K3s."""
        ingressroute = {
            "apiVersion": "traefik.containo.us/v1alpha1",
            "kind": "IngressRoute",
            "metadata": {
                "name": self.k8s_config.app_name,
                "namespace": self.k8s_config.namespace,
            },
            "spec": {
                "entryPoints": ["websecure"],
                "routes": [
                    {
                        "match": f"Host(`{self.k8s_config.ingress_host}`)",
                        "kind": "Rule",
                        "services": [
                            {
                                "name": self.k8s_config.app_name,
                                "port": self.k8s_config.service_port,
                            }
                        ],
                    }
                ],
                "tls": {"certResolver": "letsencrypt"},
            },
        }
        return yaml.dump(ingressroute, default_flow_style=False, sort_keys=False)

    def _generate_local_storage_class(self) -> str:
        """Generate local-path storage class for K3s."""
        storage_class = {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "StorageClass",
            "metadata": {"name": "local-path"},
            "provisioner": "rancher.io/local-path",
            "reclaimPolicy": "Delete",
            "volumeBindingMode": "WaitForFirstConsumer",
        }
        return yaml.dump(storage_class, default_flow_style=False, sort_keys=False)

    def _generate_combined_manifest(self, files: dict[str, str]) -> str:
        """Generate combined manifest for easy deployment."""
        manifests = []
        for name, content in files.items():
            if name != "all-in-one.yaml":
                manifests.append(f"# Source: {name}\n{content}")
        return "---\n".join(manifests)

    async def deploy(self) -> DeploymentResult:
        """Deploy to K3s cluster."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        # Validate first
        errors = self.validate()
        if errors:
            result.status = DeploymentStatus.FAILED
            result.errors = errors
            return result

        try:
            result.status = DeploymentStatus.BUILDING

            # Generate manifests
            configs = self.generate_config()
            manifest_dir = self.config.project_dir / "k8s"
            manifest_dir.mkdir(exist_ok=True)

            for filename, content in configs.items():
                file_path = manifest_dir / filename
                with open(file_path, "w") as f:
                    f.write(content)
                result.add_log(f"Generated {filename}")

            # Apply manifests
            result.status = DeploymentStatus.DEPLOYING
            result.add_log("Applying Kubernetes manifests...")

            apply_result = self.run_command(
                ["kubectl", "apply", "-f", str(manifest_dir / "all-in-one.yaml")]
            )

            if apply_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error(f"Failed to apply manifests: {apply_result.stderr}")
                return result

            result.add_log(apply_result.stdout)

            # Wait for rollout
            result.add_log("Waiting for deployment rollout...")
            rollout_result = self.run_command(
                [
                    "kubectl",
                    "rollout",
                    "status",
                    f"deployment/{self.config.app_name}",
                    "--timeout=300s",
                ]
            )

            if rollout_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error(f"Rollout failed: {rollout_result.stderr}")
                return result

            result.status = DeploymentStatus.SUCCESS
            if self.k8s_config.ingress_host:
                result.url = f"https://{self.k8s_config.ingress_host}"
            result.add_log("Deployment successful!")

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            status_result = self.run_command(
                [
                    "kubectl",
                    "get",
                    "deployment",
                    self.config.app_name,
                    "-o",
                    "json",
                ]
            )

            if status_result.returncode == 0:
                deployment = json.loads(status_result.stdout)
                status = deployment.get("status", {})

                replicas = status.get("replicas", 0)
                ready = status.get("readyReplicas", 0)

                if ready == replicas and replicas > 0:
                    result.status = DeploymentStatus.SUCCESS
                elif ready > 0:
                    result.status = DeploymentStatus.DEPLOYING
                else:
                    result.status = DeploymentStatus.PENDING

                result.metadata = status
                if self.k8s_config.ingress_host:
                    result.url = f"https://{self.k8s_config.ingress_host}"
            else:
                result.status = DeploymentStatus.FAILED
                result.add_error(status_result.stderr)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def scale(self, instances: int) -> DeploymentResult:
        """Scale the deployment."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            scale_result = self.run_command(
                [
                    "kubectl",
                    "scale",
                    f"deployment/{self.config.app_name}",
                    f"--replicas={instances}",
                ]
            )

            if scale_result.returncode == 0:
                result.status = DeploymentStatus.SUCCESS
                result.add_log(f"Scaled to {instances} instances")
            else:
                result.status = DeploymentStatus.FAILED
                result.add_error(scale_result.stderr)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_logs(self, lines: int = 100) -> list[str]:
        """Get application logs."""
        result = self.run_command(
            [
                "kubectl",
                "logs",
                f"deployment/{self.config.app_name}",
                f"--tail={lines}",
            ]
        )

        if result.returncode == 0:
            return result.stdout.split("\n")
        return []


# =============================================================================
# Kustomize Generator
# =============================================================================


class KustomizeGenerator:
    """
    Generates Kustomize configurations for Kubernetes deployments.

    Creates:
    - Base kustomization with common resources
    - Overlays for dev, staging, and production environments
    """

    def __init__(self, app_name: str, namespace: str = "default"):
        self.app_name = app_name
        self.namespace = namespace

    def generate(self) -> dict[str, str]:
        """Generate all Kustomize files."""
        files = {
            # Base
            "base/kustomization.yaml": self._generate_base_kustomization(),
            "base/deployment.yaml": self._generate_base_deployment(),
            "base/service.yaml": self._generate_base_service(),
            "base/configmap.yaml": self._generate_base_configmap(),
            # Dev overlay
            "overlays/dev/kustomization.yaml": self._generate_dev_overlay(),
            "overlays/dev/replica-patch.yaml": self._generate_replica_patch(1),
            "overlays/dev/resources-patch.yaml": self._generate_resources_patch("dev"),
            # Staging overlay
            "overlays/staging/kustomization.yaml": self._generate_staging_overlay(),
            "overlays/staging/replica-patch.yaml": self._generate_replica_patch(2),
            "overlays/staging/resources-patch.yaml": self._generate_resources_patch("staging"),
            "overlays/staging/ingress.yaml": self._generate_ingress("staging"),
            # Production overlay
            "overlays/prod/kustomization.yaml": self._generate_prod_overlay(),
            "overlays/prod/replica-patch.yaml": self._generate_replica_patch(3),
            "overlays/prod/resources-patch.yaml": self._generate_resources_patch("prod"),
            "overlays/prod/ingress.yaml": self._generate_ingress("prod"),
            "overlays/prod/hpa.yaml": self._generate_hpa(),
            "overlays/prod/pdb.yaml": self._generate_pdb(),
        }
        return files

    def write(self, output_dir: Path):
        """Write Kustomize files to directory."""
        output_dir = Path(output_dir)

        files = self.generate()
        for filename, content in files.items():
            file_path = output_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)

        return output_dir

    def _generate_base_kustomization(self) -> str:
        """Generate base kustomization.yaml."""
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "metadata": {"name": self.app_name},
            "namespace": self.namespace,
            "commonLabels": {
                "app.kubernetes.io/name": self.app_name,
                "app.kubernetes.io/managed-by": "kustomize",
            },
            "resources": ["deployment.yaml", "service.yaml", "configmap.yaml"],
        }
        return yaml.dump(kustomization, default_flow_style=False, sort_keys=False)

    def _generate_base_deployment(self) -> str:
        """Generate base deployment.yaml."""
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": self.app_name},
            "spec": {
                "selector": {"matchLabels": {"app": self.app_name}},
                "template": {
                    "metadata": {"labels": {"app": self.app_name}},
                    "spec": {
                        "containers": [
                            {
                                "name": self.app_name,
                                "image": f"{self.app_name}:latest",
                                "ports": [{"containerPort": 8000, "name": "http"}],
                                "envFrom": [{"configMapRef": {"name": f"{self.app_name}-config"}}],
                                "livenessProbe": {
                                    "httpGet": {"path": "/live/", "port": "http"},
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/ready/", "port": "http"},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            }
                        ]
                    },
                },
            },
        }
        return yaml.dump(deployment, default_flow_style=False, sort_keys=False)

    def _generate_base_service(self) -> str:
        """Generate base service.yaml."""
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": self.app_name},
            "spec": {
                "type": "ClusterIP",
                "ports": [{"port": 80, "targetPort": "http", "name": "http"}],
                "selector": {"app": self.app_name},
            },
        }
        return yaml.dump(service, default_flow_style=False, sort_keys=False)

    def _generate_base_configmap(self) -> str:
        """Generate base configmap.yaml."""
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": f"{self.app_name}-config"},
            "data": {
                "DEBUG": "false",
                "DJANGO_ENV": "production",
            },
        }
        return yaml.dump(configmap, default_flow_style=False, sort_keys=False)

    def _generate_dev_overlay(self) -> str:
        """Generate dev overlay kustomization."""
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "namespace": f"{self.namespace}-dev",
            "namePrefix": "dev-",
            "commonLabels": {"environment": "development"},
            "resources": ["../../base"],
            "patchesStrategicMerge": ["replica-patch.yaml", "resources-patch.yaml"],
            "configMapGenerator": [
                {
                    "name": f"{self.app_name}-config",
                    "behavior": "merge",
                    "literals": ["DEBUG=true", "DJANGO_ENV=development"],
                }
            ],
        }
        return yaml.dump(kustomization, default_flow_style=False, sort_keys=False)

    def _generate_staging_overlay(self) -> str:
        """Generate staging overlay kustomization."""
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "namespace": f"{self.namespace}-staging",
            "namePrefix": "staging-",
            "commonLabels": {"environment": "staging"},
            "resources": ["../../base", "ingress.yaml"],
            "patchesStrategicMerge": ["replica-patch.yaml", "resources-patch.yaml"],
            "configMapGenerator": [
                {
                    "name": f"{self.app_name}-config",
                    "behavior": "merge",
                    "literals": ["DEBUG=false", "DJANGO_ENV=staging"],
                }
            ],
        }
        return yaml.dump(kustomization, default_flow_style=False, sort_keys=False)

    def _generate_prod_overlay(self) -> str:
        """Generate production overlay kustomization."""
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "namespace": f"{self.namespace}-prod",
            "namePrefix": "prod-",
            "commonLabels": {"environment": "production"},
            "resources": ["../../base", "ingress.yaml", "hpa.yaml", "pdb.yaml"],
            "patchesStrategicMerge": ["replica-patch.yaml", "resources-patch.yaml"],
            "configMapGenerator": [
                {
                    "name": f"{self.app_name}-config",
                    "behavior": "merge",
                    "literals": ["DEBUG=false", "DJANGO_ENV=production"],
                }
            ],
        }
        return yaml.dump(kustomization, default_flow_style=False, sort_keys=False)

    def _generate_replica_patch(self, replicas: int) -> str:
        """Generate replica count patch."""
        patch = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": self.app_name},
            "spec": {"replicas": replicas},
        }
        return yaml.dump(patch, default_flow_style=False, sort_keys=False)

    def _generate_resources_patch(self, env: str) -> str:
        """Generate resource limits patch."""
        resources = {
            "dev": {"cpu": "100m", "memory": "128Mi"},
            "staging": {"cpu": "250m", "memory": "256Mi"},
            "prod": {"cpu": "500m", "memory": "512Mi"},
        }

        limits = resources.get(env, resources["prod"])

        patch = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": self.app_name},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": self.app_name,
                                "resources": {
                                    "requests": limits,
                                    "limits": {
                                        "cpu": "1000m" if env == "prod" else limits["cpu"],
                                        "memory": "1Gi" if env == "prod" else limits["memory"],
                                    },
                                },
                            }
                        ]
                    }
                }
            },
        }
        return yaml.dump(patch, default_flow_style=False, sort_keys=False)

    def _generate_ingress(self, env: str) -> str:
        """Generate ingress for environment."""
        host = f"{self.app_name}.example.com" if env == "prod" else f"{env}.{self.app_name}.example.com"

        ingress = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": self.app_name,
                "annotations": {
                    "kubernetes.io/ingress.class": "nginx",
                    "cert-manager.io/cluster-issuer": "letsencrypt-prod",
                },
            },
            "spec": {
                "ingressClassName": "nginx",
                "tls": [{"hosts": [host], "secretName": f"{self.app_name}-tls"}],
                "rules": [
                    {
                        "host": host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {"name": self.app_name, "port": {"number": 80}}
                                    },
                                }
                            ]
                        },
                    }
                ],
            },
        }
        return yaml.dump(ingress, default_flow_style=False, sort_keys=False)

    def _generate_hpa(self) -> str:
        """Generate HPA for production."""
        hpa = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": self.app_name},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": self.app_name,
                },
                "minReplicas": 3,
                "maxReplicas": 10,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {"type": "Utilization", "averageUtilization": 80},
                        },
                    }
                ],
            },
        }
        return yaml.dump(hpa, default_flow_style=False, sort_keys=False)

    def _generate_pdb(self) -> str:
        """Generate PDB for production."""
        pdb = {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {"name": self.app_name},
            "spec": {
                "minAvailable": 2,
                "selector": {"matchLabels": {"app": self.app_name}},
            },
        }
        return yaml.dump(pdb, default_flow_style=False, sort_keys=False)


def generate_kustomization(
    app_name: str,
    output_dir: str | Path = ".",
    namespace: str = "default",
) -> Path:
    """
    Generate Kustomize configuration with base and environment overlays.

    Args:
        app_name: Application name
        output_dir: Output directory for Kustomize files
        namespace: Base Kubernetes namespace

    Returns:
        Path to the generated Kustomize directory
    """
    generator = KustomizeGenerator(app_name=app_name, namespace=namespace)
    return generator.write(Path(output_dir) / "k8s")


# =============================================================================
# Provider Registration
# =============================================================================


def register_k3s_provider():
    """
    Register the K3sProvider with the deployment system.

    This function is called lazily to avoid circular imports.
    Call this function before using `get_provider("k3s", config)`.
    """
    from django_matt.deploy.base import register_provider

    # Use the decorator function to register the provider
    register_provider("k3s")(K3sProvider)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Config classes
    "KubernetesConfig",
    "HelmValues",
    "ServiceType",
    "IngressClass",
    # Manifest generator
    "KubernetesManifestGenerator",
    # Standalone functions
    "generate_deployment",
    "generate_service",
    "generate_ingress",
    "generate_configmap",
    "generate_secret",
    "generate_hpa",
    "generate_pdb",
    # Helm
    "HelmChartGenerator",
    "generate_helm_chart",
    # K3s
    "K3sProvider",
    "register_k3s_provider",
    # Kustomize
    "KustomizeGenerator",
    "generate_kustomization",
]
