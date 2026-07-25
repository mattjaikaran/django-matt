"""Management command for migration analysis, parallel execution, and profiling."""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Analyze, profile, and run migrations in parallel for large codebases."""

    help = "Analyze, profile, and accelerate migrations for large Django codebases."

    def add_arguments(self, parser):
        # Safety analysis
        parser.add_argument(
            "--check",
            action="store_true",
            help="Analyze pending migrations for unsafe DDL patterns.",
        )
        parser.add_argument(
            "--rewrite",
            action="store_true",
            help="Show safe rewrite steps for unsafe migrations.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview only — don't write files or execute.",
        )

        # Graph visualization
        parser.add_argument(
            "--graph",
            action="store_true",
            help="Show migration dependency graph.",
        )
        parser.add_argument(
            "--format",
            choices=["ascii", "dot", "mermaid"],
            default="ascii",
            help="Graph output format (default: ascii).",
        )

        # Filtering
        parser.add_argument(
            "--app",
            type=str,
            default=None,
            help="Filter to a specific app.",
        )

        # Validation
        parser.add_argument(
            "--check-cycles",
            action="store_true",
            help="Detect circular dependencies in migration graph.",
        )
        parser.add_argument(
            "--check-conflicts",
            action="store_true",
            help="Detect branch conflicts (multiple leaf migrations per app).",
        )

        # Profiling and stats
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show migration statistics for the project.",
        )
        parser.add_argument(
            "--profile",
            action="store_true",
            help="Profile pending migrations and estimate time.",
        )
        parser.add_argument(
            "--slowest",
            type=int,
            metavar="N",
            help="Show the N slowest migrations from history.",
        )

        # Parallel execution
        parser.add_argument(
            "--parallel",
            action="store_true",
            help="Run pending migrations in parallel waves.",
        )
        parser.add_argument(
            "--plan-waves",
            action="store_true",
            help="Show the parallel execution plan without running.",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=4,
            help="Number of parallel workers (default: 4).",
        )

    def handle(self, **options):
        # Safety analysis
        if options["check"] or options["rewrite"]:
            self._handle_check(options)
        # Graph visualization
        elif options["graph"]:
            self._handle_graph(options)
        # Validation
        elif options["check_cycles"]:
            self._handle_cycles()
        elif options["check_conflicts"]:
            self._handle_conflicts()
        # Profiling and stats
        elif options["stats"]:
            self._handle_stats()
        elif options["profile"]:
            self._handle_profile(options)
        elif options.get("slowest"):
            self._handle_slowest(options["slowest"])
        # Parallel execution
        elif options["parallel"]:
            self._handle_parallel(options)
        elif options["plan_waves"]:
            self._handle_plan_waves()
        else:
            self._handle_status()
            self.stderr.write(
                "\nOptions: --check, --graph, --stats, --profile, --parallel, --plan-waves\n"
                "Run 'python manage.py matt_migrate --help' for full options."
            )

    def _handle_check(self, options):
        from django_matt.migration_tools.advisor import MigrationAdvisor

        advisor = MigrationAdvisor()

        if options.get("app"):
            issues = advisor.analyze_app(options["app"])
        else:
            issues = advisor.analyze_pending()

        if not issues:
            self.stdout.write(self.style.SUCCESS("No unsafe migration patterns detected."))
            return

        for issue in issues:
            icon = "\u26a0" if issue.severity.value == "warning" else "\u2717"
            self.stdout.write(f"\n{icon} {issue.app_label}/{issue.migration_name}")
            self.stdout.write(f"  {issue.operation_description}")
            self.stdout.write(f"  {issue.message}")

            if options["rewrite"] and issue.rewrite:
                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("  Safe rewrite steps:"))
                for i, step in enumerate(issue.rewrite.steps, 1):
                    self.stdout.write(f"    Step {i}: {step.description}")
                    if step.sql and not options.get("dry_run"):
                        for line in step.sql.strip().split("\n"):
                            self.stdout.write(f"      {line}")

        self.stdout.write(f"\n{len(issues)} issue(s) found.")
        if not options["rewrite"]:
            self.stdout.write("Run with --rewrite to see safe alternatives.")

    def _handle_graph(self, options):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        from django_matt.migration_tools.graph import MigrationGraphRenderer

        loader = MigrationLoader(connection)
        renderer = MigrationGraphRenderer()
        app_label = options.get("app")
        fmt = options["format"]

        if fmt == "dot":
            self.stdout.write(renderer.render_dot(loader.graph, app_label=app_label))
        elif fmt == "mermaid":
            self.stdout.write(renderer.render_mermaid(loader.graph, app_label=app_label))
        else:
            self.stdout.write(renderer.render_ascii(loader.graph, app_label=app_label))

    def _handle_cycles(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        from django_matt.migration_tools.graph import MigrationGraphRenderer

        loader = MigrationLoader(connection)
        renderer = MigrationGraphRenderer()
        cycles = renderer.detect_cycles(loader.graph)

        if not cycles:
            self.stdout.write(self.style.SUCCESS("No circular dependencies detected."))
        else:
            for cycle in cycles:
                path = " \u2192 ".join(f"{al}.{mn}" for al, mn in cycle)
                self.stdout.write(self.style.ERROR(f"Cycle: {path}"))

    def _handle_conflicts(self):
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        from django_matt.migration_tools.graph import MigrationGraphRenderer

        loader = MigrationLoader(connection)
        renderer = MigrationGraphRenderer()
        conflicts = renderer.find_conflicts(loader.graph)

        if not conflicts:
            self.stdout.write(self.style.SUCCESS("No branch conflicts detected."))
        else:
            for conflict in conflicts:
                self.stdout.write(
                    self.style.WARNING(
                        f"{conflict.app_label}: {len(conflict.leaves)} leaf migrations "
                        f"({', '.join(conflict.leaves)})"
                    )
                )

    def _handle_status(self):
        """Show a quick migration status overview."""
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        from django.db.migrations.recorder import MigrationRecorder

        loader = MigrationLoader(connection)
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()

        total = len(loader.disk_migrations)
        applied_count = len([k for k in loader.disk_migrations if k in applied])
        pending = total - applied_count

        self.stdout.write("\nMigration Status")
        self.stdout.write("=" * 40)
        self.stdout.write(f"Total migrations: {total}")
        self.stdout.write(f"Applied: {applied_count}")

        if pending > 0:
            self.stdout.write(self.style.WARNING(f"Pending: {pending}"))
        else:
            self.stdout.write(self.style.SUCCESS("Pending: 0 (all applied)"))

    def _handle_stats(self):
        """Show detailed migration statistics."""
        from django_matt.migration_tools.stats import (
            MigrationProfiler,
            format_project_stats,
        )

        profiler = MigrationProfiler()
        stats = profiler.get_project_stats()

        self.stdout.write("\n" + format_project_stats(stats))

        if stats.pending_migrations > 0:
            self.stdout.write(
                f"\n{self.style.NOTICE('Tip:')} Run --profile to see which pending migrations are slowest."
            )

    def _handle_profile(self, options):
        """Profile pending migrations."""
        from django_matt.migration_tools.stats import MigrationProfiler, format_profiles

        profiler = MigrationProfiler()

        app = options.get("app")
        profiles = profiler.profile_pending()

        if app:
            profiles = [p for p in profiles if p.app_label == app]

        if not profiles:
            self.stdout.write("No pending migrations to profile.")
            return

        self.stdout.write("\n" + format_profiles(profiles))

        total_time = sum(p.estimated_seconds for p in profiles)
        self.stdout.write(
            f"\n{self.style.NOTICE('Total estimated time:')} {total_time:.1f}s ({total_time / 60:.1f} minutes)"
        )

        # Check for parallelization opportunity
        from django_matt.migration_tools.parallel import MigrationWavePlanner

        planner = MigrationWavePlanner()
        waves = planner.plan_waves()

        if len(waves) > 1:
            parallel_time = 0
            for wave in waves:
                wave_times = [
                    next(
                        (
                            p.estimated_seconds
                            for p in profiles
                            if p.app_label == app and p.migration_name == name
                        ),
                        0.5,
                    )
                    for app, name in wave
                ]
                parallel_time += max(wave_times) if wave_times else 0

            speedup = total_time / parallel_time if parallel_time > 0 else 1.0
            self.stdout.write(
                f"\n{self.style.SUCCESS('Parallel potential:')} "
                f"{len(waves)} waves, ~{parallel_time:.1f}s, {speedup:.1f}x speedup"
            )
            self.stdout.write("Run with --parallel to execute in parallel waves.")

    def _handle_slowest(self, limit: int):
        """Show slowest migrations from history."""
        from django_matt.migration_tools.stats import MigrationTimer

        timer = MigrationTimer()
        slowest = timer.get_slowest(limit)

        if not slowest:
            self.stdout.write("No migration timing history found.")
            self.stdout.write("Migration times are recorded automatically when using django-matt.")
            return

        self.stdout.write(f"\nTop {limit} slowest migrations (from history):")
        self.stdout.write("=" * 50)

        for i, (key, avg_time) in enumerate(slowest, 1):
            self.stdout.write(f"  {i}. {key}: {avg_time:.2f}s average")

    def _handle_parallel(self, options):
        """Execute migrations in parallel waves."""
        from django_matt.migration_tools.parallel import (
            ParallelMigrationExecutor,
            format_parallel_result,
        )

        executor = ParallelMigrationExecutor(max_workers=options.get("workers", 4))

        if options.get("dry_run"):
            result = executor.execute(dry_run=True)
            self.stdout.write("\nDry run — would execute:")
            for wave in result.waves:
                self.stdout.write(f"\n  Wave {wave.wave_number}:")
                for timing in wave.migrations:
                    self.stdout.write(f"    - {timing.app_label}.{timing.migration_name}")
            self.stdout.write(
                f"\nTotal: {result.migrations_applied} migrations in {len(result.waves)} waves"
            )
            return

        self.stdout.write("Executing migrations in parallel waves...")
        self.stdout.write(
            self.style.WARNING(
                "Note: Parallel migration is experimental. "
                "Ensure your database supports concurrent DDL."
            )
        )

        result = executor.execute()
        self.stdout.write(format_parallel_result(result))

        if result.success:
            self.stdout.write(self.style.SUCCESS("\nAll migrations applied successfully!"))
        else:
            self.stderr.write(self.style.ERROR("\nSome migrations failed. See errors above."))
            sys.exit(1)

    def _handle_plan_waves(self):
        """Show the parallel execution plan."""
        from django_matt.migration_tools.parallel import MigrationWavePlanner

        planner = MigrationWavePlanner()
        waves = planner.plan_waves()

        if not waves:
            self.stdout.write("No pending migrations.")
            return

        self.stdout.write("\nParallel Execution Plan")
        self.stdout.write("=" * 50)
        self.stdout.write(
            f"Migrations will execute in {len(waves)} waves.\n"
            "Migrations in the same wave run concurrently.\n"
        )

        total = 0
        for i, wave in enumerate(waves, 1):
            self.stdout.write(f"Wave {i} ({len(wave)} migrations):")
            for app, name in wave:
                self.stdout.write(f"  - {app}.{name}")
            total += len(wave)
            self.stdout.write("")

        self.stdout.write(f"Total: {total} migrations across {len(waves)} waves")
        self.stdout.write("\nRun with --parallel to execute this plan.")
