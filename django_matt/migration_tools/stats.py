"""Migration statistics and diagnostics — understand why migrations are slow.

Provides tools to:
- Measure migration timing
- Profile individual migrations
- Identify slow patterns (data migrations, large tables, etc.)
- Track migration history and trends
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger("django_matt.migration_tools.stats")


@dataclass
class MigrationProfile:
    """Detailed profile of a single migration."""

    app_label: str
    migration_name: str
    operations: list[dict[str, Any]]
    estimated_complexity: str  # "trivial", "simple", "moderate", "complex", "extreme"
    has_data_migration: bool
    has_index_creation: bool
    tables_affected: list[str]
    row_estimates: dict[str, int]
    estimated_seconds: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class MigrationRunStats:
    """Statistics from running a migration."""

    app_label: str
    migration_name: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    success: bool
    rows_affected: int = 0
    error: str = ""


@dataclass
class ProjectMigrationStats:
    """Overall migration statistics for a project."""

    total_migrations: int
    applied_migrations: int
    pending_migrations: int
    total_operations: int
    data_migrations_count: int
    index_operations_count: int
    estimated_pending_time: float
    apps: dict[str, int]
    complexity_breakdown: dict[str, int]


class MigrationProfiler:
    """Profile migrations to estimate timing and identify potential issues.

    Usage::

        profiler = MigrationProfiler()

        # Profile a specific migration
        profile = profiler.profile_migration("myapp", "0042_add_indexes")
        print(f"Estimated complexity: {profile.estimated_complexity}")
        print(f"Estimated time: {profile.estimated_seconds}s")

        # Profile all pending migrations
        profiles = profiler.profile_pending()
        total_time = sum(p.estimated_seconds for p in profiles)
        print(f"Total estimated time: {total_time}s")

        # Get project-wide stats
        stats = profiler.get_project_stats()
        print(f"Pending migrations: {stats.pending_migrations}")
    """

    # Rough time estimates per operation type (in seconds)
    OPERATION_ESTIMATES = {
        "CreateModel": 0.1,
        "DeleteModel": 0.05,
        "AddField": 0.5,  # Can be slow on large tables
        "RemoveField": 0.2,
        "AlterField": 1.0,  # Often requires table rewrite
        "RenameField": 0.3,
        "AddIndex": 2.0,  # Index builds are slow
        "RemoveIndex": 0.1,
        "AddConstraint": 0.5,
        "RemoveConstraint": 0.1,
        "AlterModelTable": 0.1,
        "AlterModelOptions": 0.05,
        "AlterUniqueTogether": 0.5,
        "AlterIndexTogether": 0.5,
        "RunSQL": 1.0,  # Highly variable
        "RunPython": 5.0,  # Highly variable, assume worst case
        "SeparateDatabaseAndState": 0.01,
    }

    # Row count thresholds for complexity scaling
    ROW_THRESHOLDS = [
        (1_000_000, 10.0),  # >1M rows: 10x slowdown
        (100_000, 3.0),  # >100K rows: 3x slowdown
        (10_000, 1.5),  # >10K rows: 1.5x slowdown
        (0, 1.0),  # baseline
    ]

    def profile_migration(self, app_label: str, migration_name: str) -> MigrationProfile:
        """Profile a specific migration for complexity and timing."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)
        key = (app_label, migration_name)

        if key not in loader.disk_migrations:
            raise ValueError(f"Migration {app_label}.{migration_name} not found")

        migration = loader.disk_migrations[key]
        return self._analyze_migration(app_label, migration_name, migration)

    def profile_pending(self) -> list[MigrationProfile]:
        """Profile all pending migrations."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        profiles = []
        for (app_label, migration_name), migration in loader.disk_migrations.items():
            if (app_label, migration_name) not in applied:
                profile = self._analyze_migration(app_label, migration_name, migration)
                profiles.append(profile)

        # Sort by estimated time descending (slowest first)
        return sorted(profiles, key=lambda p: p.estimated_seconds, reverse=True)

    def profile_all(self) -> list[MigrationProfile]:
        """Profile all migrations (applied and pending)."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        loader = MigrationLoader(connection)

        profiles = []
        for (app_label, migration_name), migration in loader.disk_migrations.items():
            profile = self._analyze_migration(app_label, migration_name, migration)
            profiles.append(profile)

        return sorted(profiles, key=lambda p: (p.app_label, p.migration_name))

    def get_project_stats(self) -> ProjectMigrationStats:
        """Get overall migration statistics for the project."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        total_migrations = len(loader.disk_migrations)
        applied_count = len(
            [k for k in loader.disk_migrations if k in applied]
        )
        pending_count = total_migrations - applied_count

        # Count operations
        total_ops = 0
        data_migrations = 0
        index_ops = 0
        apps: dict[str, int] = {}
        complexity_breakdown: dict[str, int] = {"trivial": 0, "simple": 0, "moderate": 0, "complex": 0, "extreme": 0}
        estimated_pending = 0.0

        for (app_label, migration_name), migration in loader.disk_migrations.items():
            apps[app_label] = apps.get(app_label, 0) + 1
            operations = getattr(migration, "operations", [])
            total_ops += len(operations)

            for op in operations:
                op_type = type(op).__name__
                if op_type in ("RunPython", "RunSQL"):
                    data_migrations += 1
                if "Index" in op_type:
                    index_ops += 1

            if (app_label, migration_name) not in applied:
                profile = self._analyze_migration(app_label, migration_name, migration)
                estimated_pending += profile.estimated_seconds
                complexity_breakdown[profile.estimated_complexity] += 1

        return ProjectMigrationStats(
            total_migrations=total_migrations,
            applied_migrations=applied_count,
            pending_migrations=pending_count,
            total_operations=total_ops,
            data_migrations_count=data_migrations,
            index_operations_count=index_ops,
            estimated_pending_time=estimated_pending,
            apps=apps,
            complexity_breakdown=complexity_breakdown,
        )

    def _analyze_migration(
        self,
        app_label: str,
        migration_name: str,
        migration: Any,
    ) -> MigrationProfile:
        """Analyze a migration for complexity and timing."""
        operations = getattr(migration, "operations", [])

        ops_info = []
        has_data_migration = False
        has_index = False
        tables_affected = set()
        warnings = []
        total_estimate = 0.0

        for op in operations:
            op_type = type(op).__name__
            op_info = {"type": op_type}

            # Extract model/table info
            model_name = getattr(op, "model_name", None)
            if model_name:
                tables_affected.add(model_name)
                op_info["model"] = model_name

            # Check for potentially slow operations
            if op_type in ("RunPython", "RunSQL"):
                has_data_migration = True
                warnings.append(f"{op_type} operation may be slow and blocks parallel execution")

            if "Index" in op_type:
                has_index = True

            if op_type == "AddField":
                field_obj = getattr(op, "field", None)
                if field_obj:
                    if not getattr(field_obj, "null", True):
                        warnings.append(f"Adding non-nullable field to {model_name} may lock table")

            if op_type == "AlterField":
                warnings.append(f"AlterField on {model_name} may require table rewrite")

            # Estimate time
            base_time = self.OPERATION_ESTIMATES.get(op_type, 0.5)
            total_estimate += base_time
            op_info["estimated_seconds"] = base_time

            ops_info.append(op_info)

        # Determine complexity
        if len(operations) == 0 or (len(operations) <= 2 and not has_data_migration):
            complexity = "trivial"
        elif len(operations) <= 5 and not has_data_migration:
            complexity = "simple"
        elif has_data_migration or has_index:
            if total_estimate > 10:
                complexity = "extreme"
            else:
                complexity = "complex"
        elif len(operations) <= 10:
            complexity = "moderate"
        else:
            complexity = "complex"

        return MigrationProfile(
            app_label=app_label,
            migration_name=migration_name,
            operations=ops_info,
            estimated_complexity=complexity,
            has_data_migration=has_data_migration,
            has_index_creation=has_index,
            tables_affected=list(tables_affected),
            row_estimates={},  # Would need DB introspection
            estimated_seconds=total_estimate,
            warnings=warnings,
        )


class MigrationTimer:
    """Time migrations as they run and store historical data.

    Usage::

        timer = MigrationTimer()

        # Time a migration run
        with timer.time_migration("myapp", "0042_add_indexes"):
            call_command("migrate", "myapp", "0042_add_indexes")

        # View history
        history = timer.get_history("myapp")
        for entry in history:
            print(f"{entry.migration_name}: {entry.elapsed_seconds}s")
    """

    HISTORY_FILE = ".migration_timing_history.json"

    def __init__(self, base_path: Path | None = None) -> None:
        from django.conf import settings

        if base_path is None:
            base_path = Path(settings.BASE_DIR)
        self.history_path = base_path / self.HISTORY_FILE

    def time_migration(
        self,
        app_label: str,
        migration_name: str,
    ) -> MigrationTimingContext:
        """Context manager to time a migration run."""
        return MigrationTimingContext(self, app_label, migration_name)

    def record(self, stats: MigrationRunStats) -> None:
        """Record migration timing to history."""
        history = self._load_history()

        key = f"{stats.app_label}.{stats.migration_name}"
        if key not in history:
            history[key] = []

        history[key].append({
            "started_at": stats.started_at,
            "finished_at": stats.finished_at,
            "elapsed_seconds": stats.elapsed_seconds,
            "success": stats.success,
            "rows_affected": stats.rows_affected,
            "error": stats.error,
        })

        self._save_history(history)

    def get_history(
        self,
        app_label: str | None = None,
    ) -> list[MigrationRunStats]:
        """Get migration timing history."""
        history = self._load_history()
        results = []

        for key, runs in history.items():
            parts = key.split(".", 1)
            if len(parts) != 2:
                continue
            mig_app, mig_name = parts

            if app_label and mig_app != app_label:
                continue

            for run in runs:
                results.append(
                    MigrationRunStats(
                        app_label=mig_app,
                        migration_name=mig_name,
                        started_at=run["started_at"],
                        finished_at=run["finished_at"],
                        elapsed_seconds=run["elapsed_seconds"],
                        success=run["success"],
                        rows_affected=run.get("rows_affected", 0),
                        error=run.get("error", ""),
                    )
                )

        return sorted(results, key=lambda r: r.started_at, reverse=True)

    def get_average_times(self) -> dict[str, float]:
        """Get average migration times from history."""
        history = self._load_history()
        averages = {}

        for key, runs in history.items():
            successful_runs = [r for r in runs if r["success"]]
            if successful_runs:
                avg = sum(r["elapsed_seconds"] for r in successful_runs) / len(successful_runs)
                averages[key] = avg

        return averages

    def get_slowest(self, limit: int = 10) -> list[tuple[str, float]]:
        """Get the slowest migrations from history."""
        averages = self.get_average_times()
        return sorted(averages.items(), key=lambda x: x[1], reverse=True)[:limit]

    def _load_history(self) -> dict[str, Any]:
        if self.history_path.exists():
            return json.loads(self.history_path.read_text())
        return {}

    def _save_history(self, history: dict[str, Any]) -> None:
        self.history_path.write_text(json.dumps(history, indent=2))


class MigrationTimingContext:
    """Context manager for timing a migration."""

    def __init__(
        self,
        timer: MigrationTimer,
        app_label: str,
        migration_name: str,
    ) -> None:
        self.timer = timer
        self.app_label = app_label
        self.migration_name = migration_name
        self.start_time: float = 0
        self.started_at: str = ""
        self.success = True
        self.error = ""

    def __enter__(self) -> MigrationTimingContext:
        self.start_time = time.perf_counter()
        self.started_at = datetime.now(UTC).isoformat()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = time.perf_counter() - self.start_time
        finished_at = datetime.now(UTC).isoformat()

        if exc_val:
            self.success = False
            self.error = str(exc_val)

        stats = MigrationRunStats(
            app_label=self.app_label,
            migration_name=self.migration_name,
            started_at=self.started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed,
            success=self.success,
            error=self.error,
        )
        self.timer.record(stats)


def format_project_stats(stats: ProjectMigrationStats) -> str:
    """Format project migration stats for display."""
    lines = [
        "Migration Statistics",
        "=" * 40,
        f"Total migrations: {stats.total_migrations}",
        f"Applied: {stats.applied_migrations}",
        f"Pending: {stats.pending_migrations}",
        "",
        f"Total operations: {stats.total_operations}",
        f"Data migrations: {stats.data_migrations_count}",
        f"Index operations: {stats.index_operations_count}",
        "",
        f"Estimated pending time: {stats.estimated_pending_time:.1f}s",
        "",
        "Pending complexity breakdown:",
    ]

    for complexity, count in sorted(stats.complexity_breakdown.items()):
        if count > 0:
            lines.append(f"  {complexity}: {count}")

    lines.append("")
    lines.append("Migrations per app:")
    for app, count in sorted(stats.apps.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {app}: {count}")

    return "\n".join(lines)


def format_profiles(profiles: list[MigrationProfile], limit: int = 10) -> str:
    """Format migration profiles for display."""
    lines = [
        f"Top {min(limit, len(profiles))} slowest pending migrations:",
        "=" * 50,
    ]

    for profile in profiles[:limit]:
        lines.append(
            f"\n{profile.app_label}.{profile.migration_name} "
            f"[{profile.estimated_complexity}] ~{profile.estimated_seconds:.1f}s"
        )
        lines.append(f"  Operations: {len(profile.operations)}")
        if profile.has_data_migration:
            lines.append("  ⚠ Contains data migration")
        if profile.has_index_creation:
            lines.append("  ⚠ Creates indexes")
        for warning in profile.warnings:
            lines.append(f"  ⚠ {warning}")

    return "\n".join(lines)
