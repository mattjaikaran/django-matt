# file-length-max: 600
"""SQL baseline management — replace hundreds of migrations with a single dump.

Instead of running 500+ migrations sequentially, developers can:
1. Load a SQL dump of the schema at migration N
2. Fake-apply all migrations up to N
3. Only run the few remaining migrations

This reduces 2-hour migration runs to seconds.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper

logger = logging.getLogger("django_matt.migration_tools.baseline")


@dataclass
class BaselineInfo:
    """Metadata about a migration baseline."""

    version: str
    created_at: str
    schema_hash: str
    applied_migrations: dict[str, list[str]]
    db_vendor: str
    django_version: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "schema_hash": self.schema_hash,
            "applied_migrations": self.applied_migrations,
            "db_vendor": self.db_vendor,
            "django_version": self.django_version,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineInfo:
        return cls(
            version=data["version"],
            created_at=data["created_at"],
            schema_hash=data["schema_hash"],
            applied_migrations=data["applied_migrations"],
            db_vendor=data["db_vendor"],
            django_version=data["django_version"],
            notes=data.get("notes", ""),
        )


@dataclass
class LoadResult:
    """Result of loading a baseline."""

    success: bool
    baseline_version: str
    migrations_faked: int
    migrations_remaining: int
    elapsed_seconds: float
    error: str = ""


@dataclass
class CreateResult:
    """Result of creating a baseline."""

    success: bool
    version: str
    dump_path: Path | None = None
    manifest_path: Path | None = None
    schema_hash: str = ""
    migrations_captured: int = 0
    error: str = ""


class MigrationBaseline:
    """Manage SQL baselines for fast migration setup.

    Usage::

        baseline = MigrationBaseline()

        # Create a baseline at the current migration state
        result = baseline.create("v1.0.0", notes="Release 1.0 schema")

        # On a new dev environment, load the baseline
        result = baseline.load("v1.0.0")
        # Then run `manage.py migrate` to apply any remaining migrations

        # List available baselines
        for info in baseline.list():
            print(f"{info.version}: {info.migrations_captured} migrations")
    """

    BASELINES_DIR = "migration_baselines"

    def __init__(self, base_path: Path | None = None) -> None:
        from django.conf import settings

        if base_path is None:
            base_path = Path(settings.BASE_DIR)
        self.base_path = base_path
        self.baselines_dir = base_path / self.BASELINES_DIR

    def create(
        self,
        version: str,
        notes: str = "",
        compress: bool = True,
    ) -> CreateResult:
        """Create a baseline from the current database state.

        Args:
            version: Version identifier (e.g., "v1.0.0", "2024-01")
            notes: Optional description
            compress: Whether to gzip the dump

        Returns:
            CreateResult with paths to generated files
        """
        import time

        import django
        from django.db import connection
        from django.db.migrations.recorder import MigrationRecorder

        start = time.perf_counter()

        # Ensure baselines directory exists
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        version_dir = self.baselines_dir / version
        version_dir.mkdir(exist_ok=True)

        # Get all applied migrations
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()
        migrations_by_app: dict[str, list[str]] = {}
        for app_label, migration_name in sorted(applied):
            migrations_by_app.setdefault(app_label, []).append(migration_name)

        # Dump the schema (not data)
        dump_filename = f"schema.sql{'.gz' if compress else ''}"
        dump_path = version_dir / dump_filename

        try:
            sql = self._dump_schema(connection)
            schema_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]

            if compress:
                with gzip.open(dump_path, "wt", encoding="utf-8") as f:
                    f.write(sql)
            else:
                dump_path.write_text(sql)
        except Exception as e:
            return CreateResult(
                success=False,
                version=version,
                error=f"Failed to dump schema: {e}",
            )

        # Write manifest
        info = BaselineInfo(
            version=version,
            created_at=datetime.now(UTC).isoformat(),
            schema_hash=schema_hash,
            applied_migrations=migrations_by_app,
            db_vendor=connection.vendor,
            django_version=django.get_version(),
            notes=notes,
        )

        manifest_path = version_dir / "manifest.json"
        manifest_path.write_text(json.dumps(info.to_dict(), indent=2))

        elapsed = time.perf_counter() - start
        total_migrations = sum(len(v) for v in migrations_by_app.values())

        logger.info(
            "Created baseline %s with %d migrations in %.2fs",
            version,
            total_migrations,
            elapsed,
        )

        return CreateResult(
            success=True,
            version=version,
            dump_path=dump_path,
            manifest_path=manifest_path,
            schema_hash=schema_hash,
            migrations_captured=total_migrations,
        )

    def load(self, version: str) -> LoadResult:
        """Load a baseline into an empty database.

        This:
        1. Loads the SQL dump to create all tables
        2. Populates django_migrations with all baseline migrations
        3. Returns stats on remaining migrations to apply

        Args:
            version: The baseline version to load

        Returns:
            LoadResult with details on what was loaded
        """
        import time

        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        start = time.perf_counter()

        version_dir = self.baselines_dir / version
        if not version_dir.exists():
            return LoadResult(
                success=False,
                baseline_version=version,
                migrations_faked=0,
                migrations_remaining=0,
                elapsed_seconds=0,
                error=f"Baseline '{version}' not found",
            )

        # Read manifest
        manifest_path = version_dir / "manifest.json"
        if not manifest_path.exists():
            return LoadResult(
                success=False,
                baseline_version=version,
                migrations_faked=0,
                migrations_remaining=0,
                elapsed_seconds=0,
                error=f"Manifest not found for baseline '{version}'",
            )

        info = BaselineInfo.from_dict(json.loads(manifest_path.read_text()))

        # Check vendor compatibility
        if info.db_vendor != connection.vendor:
            return LoadResult(
                success=False,
                baseline_version=version,
                migrations_faked=0,
                migrations_remaining=0,
                elapsed_seconds=0,
                error=f"Baseline is for {info.db_vendor}, current DB is {connection.vendor}",
            )

        # Load the SQL dump
        dump_path = version_dir / "schema.sql.gz"
        if not dump_path.exists():
            dump_path = version_dir / "schema.sql"
        if not dump_path.exists():
            return LoadResult(
                success=False,
                baseline_version=version,
                migrations_faked=0,
                migrations_remaining=0,
                elapsed_seconds=0,
                error="Schema dump not found",
            )

        try:
            self._load_schema(connection, dump_path)
        except Exception as e:
            return LoadResult(
                success=False,
                baseline_version=version,
                migrations_faked=0,
                migrations_remaining=0,
                elapsed_seconds=0,
                error=f"Failed to load schema: {e}",
            )

        # Fake-apply all baseline migrations
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        migrations_faked = 0

        for app_label, migration_names in info.applied_migrations.items():
            for migration_name in migration_names:
                recorder.record_applied(app_label, migration_name)
                migrations_faked += 1

        # Calculate remaining migrations
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        applied = recorder.applied_migrations()
        remaining = 0

        for app_label, migration_name in loader.disk_migrations:
            if (app_label, migration_name) not in applied:
                remaining += 1

        elapsed = time.perf_counter() - start

        logger.info(
            "Loaded baseline %s: %d migrations faked, %d remaining in %.2fs",
            version,
            migrations_faked,
            remaining,
            elapsed,
        )

        return LoadResult(
            success=True,
            baseline_version=version,
            migrations_faked=migrations_faked,
            migrations_remaining=remaining,
            elapsed_seconds=elapsed,
        )

    def list(self) -> list[BaselineInfo]:
        """List all available baselines."""
        if not self.baselines_dir.exists():
            return []

        baselines = []
        for version_dir in sorted(self.baselines_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            manifest_path = version_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    info = BaselineInfo.from_dict(json.loads(manifest_path.read_text()))
                    baselines.append(info)
                except Exception as e:
                    logger.warning("Failed to read baseline %s: %s", version_dir.name, e)

        return baselines

    def verify(self, version: str) -> tuple[bool, str]:
        """Verify a baseline's schema matches its recorded hash.

        Returns:
            Tuple of (is_valid, message)
        """
        version_dir = self.baselines_dir / version
        manifest_path = version_dir / "manifest.json"

        if not manifest_path.exists():
            return False, f"Baseline '{version}' not found"

        info = BaselineInfo.from_dict(json.loads(manifest_path.read_text()))

        dump_path = version_dir / "schema.sql.gz"
        if not dump_path.exists():
            dump_path = version_dir / "schema.sql"
        if not dump_path.exists():
            return False, "Schema dump not found"

        if dump_path.suffix == ".gz":
            with gzip.open(dump_path, "rt", encoding="utf-8") as f:
                sql = f.read()
        else:
            sql = dump_path.read_text()

        actual_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]

        if actual_hash != info.schema_hash:
            return False, f"Hash mismatch: expected {info.schema_hash}, got {actual_hash}"

        return True, f"Baseline '{version}' is valid"

    def delete(self, version: str) -> bool:
        """Delete a baseline."""
        import shutil

        version_dir = self.baselines_dir / version
        if version_dir.exists():
            shutil.rmtree(version_dir)
            logger.info("Deleted baseline %s", version)
            return True
        return False

    def _dump_schema(self, connection: BaseDatabaseWrapper) -> str:
        """Dump the database schema using vendor-specific tools."""
        vendor = connection.vendor
        settings = connection.settings_dict

        if vendor == "postgresql":
            return self._dump_postgres(settings)
        if vendor == "mysql":
            return self._dump_mysql(settings)
        if vendor == "sqlite":
            return self._dump_sqlite(settings)
        raise ValueError(f"Unsupported database vendor: {vendor}")

    def _dump_postgres(self, settings: dict[str, Any]) -> str:
        """Dump PostgreSQL schema using pg_dump."""
        env = {}
        if settings.get("PASSWORD"):
            env["PGPASSWORD"] = settings["PASSWORD"]

        cmd = [
            "pg_dump",
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "--no-comments",
        ]

        if settings.get("HOST"):
            cmd.extend(["-h", settings["HOST"]])
        if settings.get("PORT"):
            cmd.extend(["-p", str(settings["PORT"])])
        if settings.get("USER"):
            cmd.extend(["-U", settings["USER"]])

        cmd.append(settings["NAME"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
            check=True,
        )
        return result.stdout

    def _dump_mysql(self, settings: dict[str, Any]) -> str:
        """Dump MySQL schema using mysqldump."""
        cmd = ["mysqldump", "--no-data", "--skip-comments", "--compact"]

        if settings.get("HOST"):
            cmd.extend(["-h", settings["HOST"]])
        if settings.get("PORT"):
            cmd.extend(["-P", str(settings["PORT"])])
        if settings.get("USER"):
            cmd.extend(["-u", settings["USER"]])
        if settings.get("PASSWORD"):
            cmd.append(f"-p{settings['PASSWORD']}")

        cmd.append(settings["NAME"])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    def _dump_sqlite(self, settings: dict[str, Any]) -> str:
        """Dump SQLite schema."""
        cmd = ["sqlite3", settings["NAME"], ".schema"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout

    def _load_schema(self, connection: BaseDatabaseWrapper, dump_path: Path) -> None:
        """Load a schema dump into the database."""
        if dump_path.suffix == ".gz":
            with gzip.open(dump_path, "rt", encoding="utf-8") as f:
                sql = f.read()
        else:
            sql = dump_path.read_text()

        vendor = connection.vendor
        settings = connection.settings_dict

        if vendor == "postgresql":
            self._load_postgres(settings, sql)
        elif vendor == "mysql":
            self._load_mysql(settings, sql)
        elif vendor == "sqlite":
            self._load_sqlite(settings, sql)
        else:
            raise ValueError(f"Unsupported database vendor: {vendor}")

    def _load_postgres(self, settings: dict[str, Any], sql: str) -> None:
        """Load SQL into PostgreSQL."""
        env = {}
        if settings.get("PASSWORD"):
            env["PGPASSWORD"] = settings["PASSWORD"]

        cmd = ["psql", "--quiet", "--no-psqlrc"]
        if settings.get("HOST"):
            cmd.extend(["-h", settings["HOST"]])
        if settings.get("PORT"):
            cmd.extend(["-p", str(settings["PORT"])])
        if settings.get("USER"):
            cmd.extend(["-U", settings["USER"]])
        cmd.extend(["-d", settings["NAME"]])

        subprocess.run(
            cmd,
            input=sql,
            text=True,
            env={**subprocess.os.environ, **env},
            check=True,
        )

    def _load_mysql(self, settings: dict[str, Any], sql: str) -> None:
        """Load SQL into MySQL."""
        cmd = ["mysql"]
        if settings.get("HOST"):
            cmd.extend(["-h", settings["HOST"]])
        if settings.get("PORT"):
            cmd.extend(["-P", str(settings["PORT"])])
        if settings.get("USER"):
            cmd.extend(["-u", settings["USER"]])
        if settings.get("PASSWORD"):
            cmd.append(f"-p{settings['PASSWORD']}")
        cmd.append(settings["NAME"])

        subprocess.run(cmd, input=sql, text=True, check=True)

    def _load_sqlite(self, settings: dict[str, Any], sql: str) -> None:
        """Load SQL into SQLite."""
        cmd = ["sqlite3", settings["NAME"]]
        subprocess.run(cmd, input=sql, text=True, check=True)


def suggest_baseline_version() -> str:
    """Suggest a version string based on current date and git tag if available."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return datetime.now().strftime("%Y-%m")
