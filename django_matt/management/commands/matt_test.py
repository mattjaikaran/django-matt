"""
Django Matt smart test runner command.

Wraps pytest with smart test selection flags.

Usage:
    python manage.py matt_test --affected         # run only affected tests
    python manage.py matt_test --failed            # re-run failed tests
    python manage.py matt_test --smart             # auto-detect best mode
    python manage.py matt_test --rebuild-deps      # rebuild dependency DB
    python manage.py matt_test --clear-failures    # clear failure records
    python manage.py matt_test --dashboard         # show test health summary
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from django_matt.cli import MattCommand


class Command(MattCommand):
    """Smart test runner with affected detection and failure tracking."""

    help = "Run tests smartly: affected-only, failed-only, or auto-detect"

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "--affected",
            action="store_true",
            help="Run only tests affected by source changes",
        )
        parser.add_argument(
            "--failed",
            action="store_true",
            help="Re-run only tests that failed in the last run",
        )
        parser.add_argument(
            "--smart",
            action="store_true",
            help="Auto-detect: --affected if changes, --failed if failures, else full suite",
        )
        parser.add_argument(
            "--rebuild-deps",
            action="store_true",
            help="Rebuild dependency database from scratch",
        )
        parser.add_argument(
            "--clear-failures",
            action="store_true",
            help="Clear all recorded failures",
        )
        parser.add_argument(
            "--changed",
            default=None,
            help="Comma-separated changed files (overrides git detection)",
        )
        parser.add_argument(
            "--dashboard",
            action="store_true",
            help="Show test health dashboard",
        )
        parser.add_argument(
            "--db",
            default=".matttest.db",
            help="Path to .matttest.db (default: .matttest.db)",
        )
        parser.add_argument(
            "pytest_args",
            nargs="*",
            help="Additional args passed to pytest",
        )

    def handle(self, *args, **options) -> None:
        if options.get("dashboard"):
            self._show_dashboard(options)
            return

        cmd = self._build_pytest_command(options)
        self.console.header("Smart Test Runner")
        self.console.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    def _build_pytest_command(self, options: dict) -> list[str]:
        cmd = ["python", "-m", "pytest"]

        db_path = options.get("db", ".matttest.db")
        cmd.append(f"--matt-db={db_path}")

        if options.get("rebuild_deps"):
            cmd.append("--matt-rebuild-deps")
        elif options.get("smart"):
            cmd.extend(self._smart_flags(db_path))
        elif options.get("affected"):
            cmd.append("--matt-affected")
            if options.get("changed"):
                cmd.append(f"--matt-changed={options['changed']}")
        elif options.get("failed"):
            cmd.append("--matt-failed")

        if options.get("clear_failures"):
            cmd.append("--matt-clear-failures")

        # Pass through extra pytest args
        extra = options.get("pytest_args", [])
        if extra:
            cmd.extend(extra)

        return cmd

    def _smart_flags(self, db_path: str) -> list[str]:
        """Auto-detect the best test selection mode."""
        from django_matt.testing.smart.tracker import TestDependencyTracker

        tracker = TestDependencyTracker(Path(db_path))

        try:
            # Check for source changes first
            changed = tracker._git_changed_files("HEAD")
            if changed and tracker.has_data():
                self.console.info(
                    f"Detected {len(changed)} changed file(s) — running affected tests"
                )
                return ["--matt-affected"]

            # Check for failures
            failed = tracker.get_failed_tests()
            if failed:
                self.console.info(f"Found {len(failed)} failed test(s) — re-running")
                return ["--matt-failed"]

            # No changes, no failures — full suite
            self.console.info("No changes or failures detected — running full suite")
            return []
        finally:
            tracker.close()

    def _show_dashboard(self, options: dict) -> None:
        """Show a dashboard of test health."""
        from rich.table import Table
        from rich.text import Text

        from django_matt.cli.console import console
        from django_matt.testing.smart.tracker import TestDependencyTracker

        rc = console._console
        db_path = Path(options.get("db", ".matttest.db"))

        if not db_path.exists():
            self.console.warning(f"No database at {db_path}. Run with --rebuild-deps first.")
            return

        tracker = TestDependencyTracker(db_path)

        try:
            self.console.header("Test Health Dashboard")

            # Run stats
            runs = tracker.conn.execute(
                "SELECT * FROM run_meta ORDER BY timestamp DESC LIMIT 5"
            ).fetchall()

            if runs:
                table = Table(title="Recent Runs", show_edge=False)
                table.add_column("Run ID", style="cyan")
                table.add_column("Commit", style="dim")
                table.add_column("Total", justify="right")
                table.add_column("Passed", justify="right", style="green")
                table.add_column("Failed", justify="right", style="red")
                table.add_column("Date", style="dim")

                for run in runs:
                    sha = (run["commit_sha"] or "")[:8]
                    table.add_row(
                        run["run_id"],
                        sha,
                        str(run["total_tests"]),
                        str(run["passed"]),
                        str(run["failed"]),
                        run["timestamp"],
                    )
                rc.print(table)
                rc.print()

            # Current failures
            failures = tracker.get_failure_details()
            if failures:
                rc.print(Text(f"\n{len(failures)} Failing Test(s):", style="bold red"))
                for f in failures[:20]:
                    rc.print(Text(f"  {f['test_id']}", style="red"))
                    if f.get("exc_repr"):
                        # Show first line of traceback
                        first_line = f["exc_repr"].split("\n")[0][:100]
                        rc.print(Text(f"    {first_line}", style="dim"))
            else:
                rc.print(Text("\nNo failing tests", style="bold green"))

            # Dependency stats
            dep_count = tracker.conn.execute(
                "SELECT COUNT(DISTINCT test_id) as cnt FROM test_deps"
            ).fetchone()
            file_count = tracker.conn.execute(
                "SELECT COUNT(DISTINCT file) as cnt FROM test_deps"
            ).fetchone()
            rc.print(
                Text(
                    f"\nDependency DB: {dep_count['cnt']} tests tracked across "
                    f"{file_count['cnt']} source files",
                    style="dim",
                )
            )
        finally:
            tracker.close()
