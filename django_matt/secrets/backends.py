"""Secrets backend implementations (env, dotenv, encrypted file, AWS, Vault, GCP)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import orjson

logger = logging.getLogger("django_matt.secrets")


@runtime_checkable
class SecretsBackend(Protocol):
    """Protocol defining the interface all secrets backends must implement."""

    async def get(self, key: str) -> str | None: ...
    async def get_many(self, keys: list[str]) -> dict[str, str | None]: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def list_keys(self) -> list[str]: ...


class EnvBackend:
    """Resolve secrets from environment variables."""

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix

    def _resolve_key(self, key: str) -> str:
        return f"{self._prefix}{key}" if self._prefix else key

    async def get(self, key: str) -> str | None:
        return os.environ.get(self._resolve_key(key))

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        return {k: os.environ.get(self._resolve_key(k)) for k in keys}

    async def set(self, key: str, value: str) -> None:
        os.environ[self._resolve_key(key)] = value

    async def delete(self, key: str) -> None:
        os.environ.pop(self._resolve_key(key), None)

    async def list_keys(self) -> list[str]:
        if not self._prefix:
            return list(os.environ.keys())
        return [k[len(self._prefix) :] for k in os.environ if k.startswith(self._prefix)]


class DotenvBackend:
    """Resolve secrets from .env files."""

    def __init__(self, path: str | Path = ".env") -> None:
        self._path = Path(path)
        self._data: dict[str, str] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._data = {}
        if self._path.exists():
            for line in self._path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                self._data[key] = value
        self._loaded = True

    def _save(self) -> None:
        lines = [f"{k}={v}" for k, v in sorted(self._data.items())]
        self._path.write_text("\n".join(lines) + "\n")

    async def get(self, key: str) -> str | None:
        self._load()
        return self._data.get(key)

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        self._load()
        return {k: self._data.get(k) for k in keys}

    async def set(self, key: str, value: str) -> None:
        self._load()
        self._data[key] = value
        self._save()

    async def delete(self, key: str) -> None:
        self._load()
        self._data.pop(key, None)
        self._save()

    async def list_keys(self) -> list[str]:
        self._load()
        return list(self._data.keys())


class EncryptedFileBackend:
    """Encrypted JSON file backend using Fernet symmetric encryption."""

    def __init__(self, path: str | Path, key: str | bytes) -> None:
        from cryptography.fernet import Fernet

        self._path = Path(path)
        if isinstance(key, str):
            key = key.encode()
        self._fernet = Fernet(key)
        self._data: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._data is not None:
            return self._data
        if not self._path.exists():
            self._data = {}
            return self._data
        encrypted = self._path.read_bytes()
        decrypted = self._fernet.decrypt(encrypted)
        self._data = orjson.loads(decrypted)
        return self._data

    def _save(self) -> None:
        data = self._data or {}
        raw = orjson.dumps(data)
        encrypted = self._fernet.encrypt(raw)
        self._path.write_bytes(encrypted)

    async def get(self, key: str) -> str | None:
        return self._load().get(key)

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        data = self._load()
        return {k: data.get(k) for k in keys}

    async def set(self, key: str, value: str) -> None:
        self._load()[key] = value
        self._save()

    async def delete(self, key: str) -> None:
        self._load().pop(key, None)
        self._save()

    async def list_keys(self) -> list[str]:
        return list(self._load().keys())

    @staticmethod
    def generate_key() -> str:
        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()


class AWSSecretsManagerBackend:
    """AWS Secrets Manager backend. Requires boto3."""

    def __init__(
        self,
        region_name: str = "us-east-1",
        prefix: str = "",
        **client_kwargs: Any,
    ) -> None:
        import boto3

        self._client = boto3.client("secretsmanager", region_name=region_name, **client_kwargs)
        self._prefix = prefix

    def _resolve_key(self, key: str) -> str:
        return f"{self._prefix}{key}" if self._prefix else key

    async def get(self, key: str) -> str | None:
        import asyncio

        try:
            resp = await asyncio.to_thread(
                self._client.get_secret_value, SecretId=self._resolve_key(key)
            )
            return resp.get("SecretString")
        except self._client.exceptions.ResourceNotFoundException:
            return None

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for key in keys:
            result[key] = await self.get(key)
        return result

    async def set(self, key: str, value: str) -> None:
        import asyncio

        resolved = self._resolve_key(key)
        try:
            await asyncio.to_thread(
                self._client.put_secret_value,
                SecretId=resolved,
                SecretString=value,
            )
        except self._client.exceptions.ResourceNotFoundException:
            await asyncio.to_thread(
                self._client.create_secret,
                Name=resolved,
                SecretString=value,
            )

    async def delete(self, key: str) -> None:
        import asyncio

        try:
            await asyncio.to_thread(
                self._client.delete_secret,
                SecretId=self._resolve_key(key),
                ForceDeleteWithoutRecovery=True,
            )
        except self._client.exceptions.ResourceNotFoundException:
            pass

    async def list_keys(self) -> list[str]:
        import asyncio

        resp = await asyncio.to_thread(self._client.list_secrets)
        names = [s["Name"] for s in resp.get("SecretList", [])]
        if self._prefix:
            return [n[len(self._prefix) :] for n in names if n.startswith(self._prefix)]
        return names


class VaultBackend:
    """HashiCorp Vault backend. Requires hvac."""

    def __init__(
        self,
        url: str = "http://127.0.0.1:8200",
        token: str | None = None,
        mount_point: str = "secret",
        path_prefix: str = "",
    ) -> None:
        import hvac

        self._client = hvac.Client(url=url, token=token)
        self._mount_point = mount_point
        self._path_prefix = path_prefix

    def _resolve_path(self, key: str) -> str:
        return f"{self._path_prefix}/{key}" if self._path_prefix else key

    async def get(self, key: str) -> str | None:
        import asyncio

        try:
            resp = await asyncio.to_thread(
                self._client.secrets.kv.v2.read_secret_version,
                path=self._resolve_path(key),
                mount_point=self._mount_point,
            )
            data = resp.get("data", {}).get("data", {})
            return data.get("value")
        except Exception:
            logger.debug("vault key not found: %s", key)
            return None

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for key in keys:
            result[key] = await self.get(key)
        return result

    async def set(self, key: str, value: str) -> None:
        import asyncio

        await asyncio.to_thread(
            self._client.secrets.kv.v2.create_or_update_secret,
            path=self._resolve_path(key),
            secret={"value": value},
            mount_point=self._mount_point,
        )

    async def delete(self, key: str) -> None:
        import asyncio

        try:
            await asyncio.to_thread(
                self._client.secrets.kv.v2.delete_metadata_and_all_versions,
                path=self._resolve_path(key),
                mount_point=self._mount_point,
            )
        except Exception:
            pass

    async def list_keys(self) -> list[str]:
        import asyncio

        try:
            resp = await asyncio.to_thread(
                self._client.secrets.kv.v2.list_secrets,
                path=self._path_prefix or "",
                mount_point=self._mount_point,
            )
            return resp.get("data", {}).get("keys", [])
        except Exception:
            return []


class GCPSecretManagerBackend:
    """GCP Secret Manager backend. Requires google-cloud-secret-manager."""

    def __init__(self, project_id: str, prefix: str = "") -> None:
        from google.cloud import secretmanager

        self._client = secretmanager.SecretManagerServiceClient()
        self._project_id = project_id
        self._prefix = prefix

    def _resolve_name(self, key: str) -> str:
        name = f"{self._prefix}{key}" if self._prefix else key
        return f"projects/{self._project_id}/secrets/{name}/versions/latest"

    def _secret_parent(self, key: str) -> str:
        name = f"{self._prefix}{key}" if self._prefix else key
        return f"projects/{self._project_id}/secrets/{name}"

    async def get(self, key: str) -> str | None:
        import asyncio

        try:
            resp = await asyncio.to_thread(
                self._client.access_secret_version,
                request={"name": self._resolve_name(key)},
            )
            return resp.payload.data.decode("utf-8")
        except Exception:
            logger.debug("gcp secret not found: %s", key)
            return None

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for key in keys:
            result[key] = await self.get(key)
        return result

    async def set(self, key: str, value: str) -> None:
        import asyncio

        parent = f"projects/{self._project_id}"
        secret_id = f"{self._prefix}{key}" if self._prefix else key
        try:
            await asyncio.to_thread(
                self._client.create_secret,
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                },
            )
        except Exception:
            pass
        await asyncio.to_thread(
            self._client.add_secret_version,
            request={
                "parent": self._secret_parent(key),
                "payload": {"data": value.encode("utf-8")},
            },
        )

    async def delete(self, key: str) -> None:
        import asyncio

        try:
            await asyncio.to_thread(
                self._client.delete_secret,
                request={"name": self._secret_parent(key)},
            )
        except Exception:
            pass

    async def list_keys(self) -> list[str]:
        import asyncio

        parent = f"projects/{self._project_id}"
        resp = await asyncio.to_thread(
            self._client.list_secrets,
            request={"parent": parent},
        )
        keys = []
        for s in resp:
            name = s.name.split("/")[-1]
            if self._prefix:
                if name.startswith(self._prefix):
                    keys.append(name[len(self._prefix) :])
            else:
                keys.append(name)
        return keys
