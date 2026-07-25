# file-length-max: 500
"""Parallel migration execution — run independent migrations concurrently.

Django runs migrations sequentially by default, even when they're independent.
This module analyzes the dependency graph and executes migrations in parallel
waves where possible.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.migrations.graph import MigrationGraph

logger = logging.getLogger("django_matt.migration_tools.parallel")


@dataclass
class MigrationTiming:
    """Timing information for a single migration."""

    app_label: str
    migration_name: str
    elapsed_seconds: float
    success: bool
    error: str = ""


@dataclass
class WaveResult:
    """Result of executing a wave of parallel migrations."""

    wave_number: int
    migrations: list[MigrationTiming]
    total_elapsed: float
    sequential_would_take: float


@dataclass
class ParallelMigrateResult:
    """Result of a parallel migration run."""

    success: bool
    waves: list[WaveResult]
    total_elapsed: float
    sequential_would_take: float
    speedup_factor: float
    migrations_applied: int
    migrations_failed: int
    errors: list[str] = field(default_factory=list)


class MigrationWavePlanner:
    """Plan migration execution in parallel waves based on dependency graph.

    Migrations are grouped into "waves" where all migrations in a wave
    have no dependencies on each other and can run in parallel.

    Example::

        planner = MigrationWavePlanner()
        waves = planner.plan_waves()
        for i, wave in enumerate(waves):
            print(f"Wave {i + 1}: {wave}")
            # All migrations in this wave can run concurrently
    """

    def plan_waves(self) -> list[list[tuple[str, str]]]:
        """Plan migration waves based on dependency graph.

        Returns:
            List of waves, where each wave is a list of (app_label, migration_name) tuples
            that can be executed in parallel.
        """
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        # Get pending migrations
        pending = set()
        for app_label, migration_name in loader.disk_migrations:
            if (app_label, migration_name) not in applied:
                pending.add((app_label, migration_name))

        if not pending:
            return []

        return self._topological_waves(loader.graph, pending)

    def _topological_waves(
        self,
        graph: MigrationGraph,
        pending: set[tuple[str, str]],
    ) -> list[list[tuple[str, str]]]:
        """Group migrations into waves using topological sort.

        Migrations with no pending dependencies form wave 1.
        After those complete, migrations whose dependencies are now satisfied form wave 2.
        And so on.
        """
        waves: list[list[tuple[str, str]]] = []
        completed = set()

        # Get dependencies for all pending migrations
        deps_map: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for key in pending:
            try:
                node = graph.node_map[key]
                deps_map[key] = set()
                for parent in node.parents:
                    parent_key = (parent.app_label, parent.name)
                    # Only include dependencies that are in pending set
                    if parent_key in pending:
                        deps_map[key].add(parent_key)
            except KeyError:
                # Migration node not in graph
                deps_map[key] = set()

        remaining = set(pending)

        while remaining:
            # Find all migrations with no remaining dependencies
            wave = []
            for key in remaining:
                pending_deps = deps_map[key] - completed
                if not pending_deps:
                    wave.append(key)

            if not wave:
                # Circular dependency detected
                logger.warning(
                    "Circular dependency detected in migrations, "
                    "falling back to sequential execution for remaining %d migrations",
                    len(remaining),
                )
                # Just add remaining as sequential waves
                for key in sorted(remaining):
                    waves.append([key])
                    completed.add(key)
                break

            # Sort wave for deterministic order
            wave = sorted(wave)
            waves.append(wave)
            completed.update(wave)
            remaining -= set(wave)

        return waves

    def estimate_speedup(self, timings: dict[tuple[str, str], float]) -> dict[str, Any]:
        """Estimate speedup from parallel execution given historical timings.

        Args:
            timings: Dict mapping (app_label, migration_name) to seconds

        Returns:
            Dict with sequential time, parallel time, and speedup factor
        """
        waves = self.plan_waves()

        sequential_time = sum(timings.get(key, 0.5) for wave in waves for key in wave)

        parallel_time = 0.0
        for wave in waves:
            wave_time = max(timings.get(key, 0.5) for key in wave) if wave else 0
            parallel_time += wave_time

        speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0

        return {
            "waves": len(waves),
            "total_migrations": sum(len(w) for w in waves),
            "sequential_seconds": sequential_time,
            "parallel_seconds": parallel_time,
            "speedup_factor": speedup,
        }


class ParallelMigrationExecutor:
    """Execute migrations in parallel waves.

    Usage::

        executor = ParallelMigrationExecutor()

        # Preview what will happen
        plan = executor.plan()
        for i, wave in enumerate(plan):
            print(f"Wave {i + 1}: {len(wave)} migrations")

        # Execute
        result = executor.execute()
        print(f"Speedup: {result.speedup_factor:.1f}x")

    Warning:
        Parallel execution requires database support for concurrent DDL.
        PostgreSQL generally handles this well. MySQL/SQLite may have issues.
    """

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self.planner = MigrationWavePlanner()

    def plan(self) -> list[list[tuple[str, str]]]:
        """Get the execution plan as waves of migrations."""
        return self.planner.plan_waves()

    def execute(self, dry_run: bool = False) -> ParallelMigrateResult:
        """Execute migrations in parallel waves.

        Args:
            dry_run: If True, show what would be done without executing

        Returns:
            ParallelMigrateResult with timing and success information
        """
        waves_plan = self.plan()

        if not waves_plan:
            return ParallelMigrateResult(
                success=True,
                waves=[],
                total_elapsed=0,
                sequential_would_take=0,
                speedup_factor=1.0,
                migrations_applied=0,
                migrations_failed=0,
            )

        if dry_run:
            return self._dry_run(waves_plan)

        return asyncio.run(self._execute_async(waves_plan))

    def _dry_run(self, waves_plan: list[list[tuple[str, str]]]) -> ParallelMigrateResult:
        """Simulate execution without actually running migrations."""
        waves = []
        total_migrations = 0

        for i, wave in enumerate(waves_plan):
            timings = [
                MigrationTiming(
                    app_label=app,
                    migration_name=name,
                    elapsed_seconds=0,
                    success=True,
                )
                for app, name in wave
            ]
            waves.append(
                WaveResult(
                    wave_number=i + 1,
                    migrations=timings,
                    total_elapsed=0,
                    sequential_would_take=0,
                )
            )
            total_migrations += len(wave)

        return ParallelMigrateResult(
            success=True,
            waves=waves,
            total_elapsed=0,
            sequential_would_take=0,
            speedup_factor=1.0,
            migrations_applied=total_migrations,
            migrations_failed=0,
        )

    async def _execute_async(
        self,
        waves_plan: list[list[tuple[str, str]]],
    ) -> ParallelMigrateResult:
        """Execute waves asynchronously."""

        waves: list[WaveResult] = []
        total_start = time.perf_counter()
        total_sequential = 0.0
        total_applied = 0
        total_failed = 0
        errors: list[str] = []

        for wave_num, wave_migrations in enumerate(waves_plan, 1):
            wave_start = time.perf_counter()
            logger.info(
                "Wave %d: executing %d migrations in parallel",
                wave_num,
                len(wave_migrations),
            )

            # Create tasks for each migration
            tasks = []
            for app_label, migration_name in wave_migrations:
                task = self._run_single_migration(app_label, migration_name)
                tasks.append(task)

            # Run all migrations in this wave concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            wave_timings: list[MigrationTiming] = []
            wave_sequential = 0.0

            for i, result in enumerate(results):
                app_label, migration_name = wave_migrations[i]

                if isinstance(result, Exception):
                    timing = MigrationTiming(
                        app_label=app_label,
                        migration_name=migration_name,
                        elapsed_seconds=0,
                        success=False,
                        error=str(result),
                    )
                    total_failed += 1
                    errors.append(f"{app_label}.{migration_name}: {result}")
                else:
                    timing = result
                    if timing.success:
                        total_applied += 1
                    else:
                        total_failed += 1
                        errors.append(f"{app_label}.{migration_name}: {timing.error}")

                wave_timings.append(timing)
                wave_sequential += timing.elapsed_seconds

            wave_elapsed = time.perf_counter() - wave_start
            total_sequential += wave_sequential

            waves.append(
                WaveResult(
                    wave_number=wave_num,
                    migrations=wave_timings,
                    total_elapsed=wave_elapsed,
                    sequential_would_take=wave_sequential,
                )
            )

            # Stop if any migration failed
            if total_failed > 0:
                logger.error("Wave %d had failures, stopping parallel execution", wave_num)
                break

        total_elapsed = time.perf_counter() - total_start
        speedup = total_sequential / total_elapsed if total_elapsed > 0 else 1.0

        return ParallelMigrateResult(
            success=total_failed == 0,
            waves=waves,
            total_elapsed=total_elapsed,
            sequential_would_take=total_sequential,
            speedup_factor=speedup,
            migrations_applied=total_applied,
            migrations_failed=total_failed,
            errors=errors,
        )

    async def _run_single_migration(
        self,
        app_label: str,
        migration_name: str,
    ) -> MigrationTiming:
        """Run a single migration in a thread pool."""
        loop = asyncio.get_event_loop()

        def _run():
            from django.core.management import call_command

            start = time.perf_counter()
            try:
                call_command(
                    "migrate",
                    app_label,
                    migration_name,
                    "--no-input",
                    verbosity=0,
                )
                elapsed = time.perf_counter() - start
                return MigrationTiming(
                    app_label=app_label,
                    migration_name=migration_name,
                    elapsed_seconds=elapsed,
                    success=True,
                )
            except Exception as e:
                elapsed = time.perf_counter() - start
                return MigrationTiming(
                    app_label=app_label,
                    migration_name=migration_name,
                    elapsed_seconds=elapsed,
                    success=False,
                    error=str(e),
                )

        return await loop.run_in_executor(None, _run)


def format_parallel_result(result: ParallelMigrateResult) -> str:
    """Format parallel migration result for display."""
    lines = []

    if result.migrations_applied == 0 and result.migrations_failed == 0:
        return "No migrations to apply."

    for wave in result.waves:
        lines.append(f"\nWave {wave.wave_number}:")
        for timing in wave.migrations:
            status = "OK" if timing.success else "FAILED"
            lines.append(
                f"  [{status}] {timing.app_label}.{timing.migration_name} ({timing.elapsed_seconds:.2f}s)"
            )
            if timing.error:
                lines.append(f"        Error: {timing.error}")
        lines.append(
            f"  Wave time: {wave.total_elapsed:.2f}s "
            f"(sequential would be: {wave.sequential_would_take:.2f}s)"
        )

    lines.append("\nSummary:")
    lines.append(f"  Migrations applied: {result.migrations_applied}")
    lines.append(f"  Migrations failed: {result.migrations_failed}")
    lines.append(f"  Total time: {result.total_elapsed:.2f}s")
    lines.append(f"  Sequential would take: {result.sequential_would_take:.2f}s")
    lines.append(f"  Speedup: {result.speedup_factor:.1f}x")

    return "\n".join(lines)
