"""SDK generator base classes and configuration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SDKConfig:
    """Configuration for SDK generation."""

    package_name: str
    version: str = "0.1.0"
    base_url: str = "http://localhost:8000"
    auth_type: str = "jwt"  # jwt, api_key, oauth
    output_dir: Path = field(default_factory=lambda: Path("./sdk"))
    include_models: bool = True
    include_client: bool = True
    include_tests: bool = True
    description: str = ""
    author: str = ""
    license: str = "MIT"
    schema_hash_file: Path = field(default_factory=lambda: Path(".sdk-schema-hash"))
    auto_bump: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if isinstance(self.schema_hash_file, str):
            self.schema_hash_file = Path(self.schema_hash_file)


@dataclass
class SDKOutput:
    """Generated SDK output — files ready to write to disk."""

    files: dict[str, str]  # relative path -> content
    package_config: str  # package.json / pyproject.toml / Package.swift
    target: str  # typescript, python, swift
    schema_hash: str = ""

    def write_to_disk(self, output_dir: Path | None = None) -> list[Path]:
        """Write all generated files to the output directory."""
        base = output_dir or Path()
        written: list[Path] = []
        for rel_path, content in self.files.items():
            full_path = base / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            written.append(full_path)
        return written


class SchemaVersioning:
    """Track API schema changes and auto-bump SDK version."""

    HASH_FILE = ".sdk-schema-hash"

    @staticmethod
    def compute_hash(api_schema: dict[str, Any]) -> str:
        """Compute a stable hash of the OpenAPI schema."""
        import hashlib

        import orjson

        normalized = orjson.dumps(api_schema, option=orjson.OPT_SORT_KEYS)
        return hashlib.sha256(normalized).hexdigest()[:16]

    @staticmethod
    def detect_breaking_changes(
        old_schema: dict[str, Any], new_schema: dict[str, Any]
    ) -> list[str]:
        """Detect breaking changes between two OpenAPI schemas."""
        changes = []
        old_paths = set((old_schema.get("paths") or {}).keys())
        new_paths = set((new_schema.get("paths") or {}).keys())

        # Removed endpoints
        for path in old_paths - new_paths:
            changes.append(f"removed endpoint: {path}")

        # Removed methods on existing endpoints
        for path in old_paths & new_paths:
            old_methods = set((old_schema["paths"][path]).keys())
            new_methods = set((new_schema["paths"][path]).keys())
            for method in old_methods - new_methods:
                changes.append(f"removed method: {method.upper()} {path}")

        # Removed schemas
        old_schemas = set((old_schema.get("components", {}).get("schemas", {})).keys())
        new_schemas = set((new_schema.get("components", {}).get("schemas", {})).keys())
        for schema in old_schemas - new_schemas:
            changes.append(f"removed schema: {schema}")

        # New required fields on existing schemas
        for name in old_schemas & new_schemas:
            old_required = set(old_schema["components"]["schemas"][name].get("required", []))
            new_required = set(new_schema["components"]["schemas"][name].get("required", []))
            for field_name in new_required - old_required:
                changes.append(f"new required field: {name}.{field_name}")

        return changes

    @classmethod
    def load_previous(cls, output_dir: Path) -> tuple[str, str, dict[str, Any] | None]:
        """Load previous hash, version, and schema from output directory."""
        import orjson

        hash_file = output_dir / cls.HASH_FILE
        if not hash_file.exists():
            return "", "0.0.0", None

        try:
            data = orjson.loads(hash_file.read_bytes())
            return data.get("hash", ""), data.get("version", "0.0.0"), data.get("schema")
        except Exception:
            return "", "0.0.0", None

    @classmethod
    def save(
        cls,
        output_dir: Path,
        schema_hash: str,
        version: str,
        api_schema: dict[str, Any],
    ) -> None:
        """Save current hash, version, and schema."""
        import orjson

        hash_file = output_dir / cls.HASH_FILE
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        hash_file.write_bytes(
            orjson.dumps({"hash": schema_hash, "version": version, "schema": api_schema})
        )

    @classmethod
    def auto_bump_version(cls, current_version: str, breaking: bool) -> str:
        """Bump version based on change type."""
        parts = current_version.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0

        if breaking:
            if major >= 1:
                return f"{major + 1}.0.0"
            return f"0.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"

    @staticmethod
    def load_state(hash_file: Path) -> dict[str, Any]:
        """Load previous schema hash and version from hash file."""
        if not hash_file.exists():
            return {}
        try:
            import orjson

            return orjson.loads(hash_file.read_bytes())
        except Exception:
            return {}

    @staticmethod
    def save_state(
        hash_file: Path, schema_hash: str, version: str, api_schema: dict[str, Any] | None = None
    ) -> None:
        """Save current schema hash and version."""
        import orjson

        state: dict[str, Any] = {"hash": schema_hash, "version": version}
        if api_schema is not None:
            state["schema"] = api_schema
        hash_file.write_bytes(orjson.dumps(state, option=orjson.OPT_INDENT_2))

    @classmethod
    def resolve_version(cls, api_schema: dict[str, Any], config: SDKConfig) -> str:
        """Resolve the SDK version, auto-bumping if schema changed."""
        if not config.auto_bump:
            return config.version

        current_hash = cls.compute_hash(api_schema)
        state = cls.load_state(config.schema_hash_file)

        if not state:
            # First generation — use config version
            return config.version

        prev_hash = state.get("hash", "")
        prev_version = state.get("version", config.version)

        if current_hash == prev_hash:
            return prev_version

        # Schema changed — bump version
        prev_schema = state.get("schema")
        if prev_schema:
            breaking = cls.detect_breaking_changes(prev_schema, api_schema)
        else:
            breaking = []

        return cls._bump_version(prev_version, major=bool(breaking))

    @staticmethod
    def _bump_version(version: str, major: bool = False) -> str:
        """Bump a semver version string."""
        parts = version.split(".")
        if len(parts) < 3:
            parts.extend(["0"] * (3 - len(parts)))

        try:
            maj, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return version

        if major:
            if maj == 0:
                return f"0.{minor + 1}.0"
            return f"{maj + 1}.0.0"
        return f"{maj}.{minor}.{patch + 1}"


class SDKGenerator(ABC):
    """Abstract base for SDK generators."""

    target: str  # "typescript", "python", "swift"

    @abstractmethod
    def generate(self, api_schema: dict[str, Any], config: SDKConfig) -> SDKOutput:
        """Generate a complete SDK package from an OpenAPI schema.

        Implementations should call SchemaVersioning.resolve_version() to
        determine the SDK version and SchemaVersioning.save_state() after
        successful generation to persist the schema hash.
        """
        ...

    def generate_versioned(
        self,
        api_schema: dict[str, Any],
        config: SDKConfig,
    ) -> SDKOutput:
        """Generate SDK with automatic version bumping based on schema changes."""
        current_hash = SchemaVersioning.compute_hash(api_schema)
        prev_hash, prev_version, prev_schema = SchemaVersioning.load_previous(config.output_dir)

        if current_hash == prev_hash:
            config.version = prev_version
        elif prev_schema is not None:
            breaking = SchemaVersioning.detect_breaking_changes(prev_schema, api_schema)
            config.version = SchemaVersioning.auto_bump_version(prev_version, bool(breaking))

        output = self.generate(api_schema, config)
        output.schema_hash = current_hash

        SchemaVersioning.save(config.output_dir, current_hash, config.version, api_schema)

        return output
