"""Multi-backend secrets management (env, Vault, AWS SM, GCP SM, dotenv, encrypted files)."""

from __future__ import annotations

from django_matt.secrets.backends import (
    AWSSecretsManagerBackend,
    DotenvBackend,
    EncryptedFileBackend,
    EnvBackend,
    GCPSecretManagerBackend,
    SecretsBackend,
    VaultBackend,
)
from django_matt.secrets.fields import SecretField, secret
from django_matt.secrets.manager import SecretReference, SecretsManager, get_secrets_manager
from django_matt.secrets.rotation import RotationPolicy, on_rotation

__all__ = [
    "AWSSecretsManagerBackend",
    "DotenvBackend",
    "EncryptedFileBackend",
    "EnvBackend",
    "GCPSecretManagerBackend",
    "RotationPolicy",
    "SecretField",
    "SecretReference",
    "SecretsBackend",
    "SecretsManager",
    "VaultBackend",
    "get_secrets_manager",
    "on_rotation",
    "secret",
]
