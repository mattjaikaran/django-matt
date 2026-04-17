"""
pytest plugin for smart test selection.

Registers CLI flags:
  --matt-affected       Run only tests affected by source changes
  --matt-failed         Re-run only tests that failed last time
  --matt-rebuild-deps   Rebuild the dependency database from scratch
  --matt-clear-failures Clear all recorded failures
  --matt-changed=PATH   Specify changed files explicitly (comma-separated)
  --matt-db=PATH        Path to .matttest.db (default: .matttest.db)

Plugin entry point is registered via pyproject.toml:
  [project.entry-points.pytest11]
  matt = "django_matt.testing.smart.plugin"
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from _pytest.reports import TestReport
    from _pytest.terminal import TerminalReporter

logger = logging.getLogger("django_matt.testing.smart")


def pytest_addoption(parser: Parser) -> None:
    """Register CLI flags."""
    group = parser.getgroup("matt", "Django Matt smart testing")
    group.addoption(
        "--matt-affected",
        action="store_true",
        default=False,
        help="Run only tests affected by source changes since last commit",
    )
    group.addoption(
        "--matt-failed",
        action="store_true",
        default=False,
        help="Re-run only tests that failed in the last run",
    )
    group.addoption(
        "--matt-rebuild-deps",
        action="store_true",
        default=False,
        help="Rebuild the dependency database from scratch (full instrumented run)",
    )
    group.addoption(
        "--matt-clear-failures",
        action="store_true",
        default=False,
        help="Clear all recorded test failures",
    )
    group.addoption(
        "--matt-changed",
        default=None,
        help="Comma-separated list of changed files (overrides git detection)",
    )
    group.addoption(
        "--matt-db",
        default=".matttest.db",
        help="Path to smart testing database (default: .matttest.db)",
    )
    # Flaky detection
    group.addoption(
        "--matt-stress",
        action="store_true",
        default=False,
        help="Stress-test selected tests to detect flakiness",
    )
    group.addoption(
        "--matt-stress-count",
        type=int,
        default=50,
        help="Number of iterations for --matt-stress (default: 50)",
    )
    group.addoption(
        "--matt-detect-flaky",
        action="store_true",
        default=False,
        help="Run with automatic flaky classification (retry failures)",
    )
    group.addoption(
        "--matt-retries",
        type=int,
        default=3,
        help="Number of retries for --matt-detect-flaky (default: 3)",
    )
    group.addoption(
        "--matt-quarantine",
        action="store_true",
        default=False,
        help="Run only quarantined (known flaky) tests",
    )
    # Replay archives
    group.addoption(
        "--matt-record",
        default=None,
        help="Record test run to a ZIP archive",
    )
    group.addoption(
        "--matt-replay",
        default=None,
        help="Replay a recorded test run (re-run only failed tests from archive)",
    )


def pytest_configure(config: Config) -> None:
    """Register the plugin if any matt flags are active."""
    matt_active = any([
        config.getoption("--matt-affected", False),
        config.getoption("--matt-failed", False),
        config.getoption("--matt-rebuild-deps", False),
        config.getoption("--matt-clear-failures", False),
        config.getoption("--matt-stress", False),
        config.getoption("--matt-detect-flaky", False),
        config.getoption("--matt-quarantine", False),
        config.getoption("--matt-record", None) is not None,
        config.getoption("--matt-replay", None) is not None,
    ])

    if matt_active:
        config.pluginmanager.register(MattSmartPlugin(config), "matt-smart")


class MattSmartPlugin:
    """Core plugin that handles test selection and coverage recording."""

    def __init__(self, config: Config):
        self.config = config
        self.db_path = Path(config.getoption("--matt-db"))
        self._tracker = None
        self._recording = config.getoption("--matt-rebuild-deps", False)
        self._coverage_collector = None
        self._run_id = str(uuid.uuid4())[:8]
        self._stats = {"total": 0, "passed": 0, "failed": 0}

        # Flaky detection
        self._flaky_detector = None
        self._stress_mode = config.getoption("--matt-stress", False)
        self._detect_flaky = config.getoption("--matt-detect-flaky", False)
        self._quarantine = config.getoption("--matt-quarantine", False)

        # Replay archives
        self._recorder = None
        record_path = config.getoption("--matt-record", None)
        if record_path:
            from django_matt.testing.smart.recorder import TestRecorder
            self._recorder = TestRecorder(record_path)

    @property
    def tracker(self):
        """Lazy-init tracker to avoid DB creation when not needed."""
        if self._tracker is None:
            self._tracker = TrackerWrapper(self.db_path)
        return self._tracker

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        """Handle --matt-clear-failures at session start."""
        if self.config.getoption("--matt-clear-failures", False):
            self.tracker.clear_failures()
            logger.info("Cleared all failure records")

        if self._recording:
            self.tracker.rebuild()
            logger.info("Rebuilding dependency database")

    @property
    def flaky_detector(self):
        """Lazy-init flaky detector."""
        if self._flaky_detector is None:
            from django_matt.testing.smart.flaky import FlakyDetector
            self._flaky_detector = FlakyDetector(self.db_path)
        return self._flaky_detector

    def pytest_collection_modifyitems(
        self, session: pytest.Session, config: Config, items: list[Item]
    ) -> None:
        """Filter tests based on --matt-affected, --matt-failed, --matt-quarantine, or --matt-replay."""
        if self.config.getoption("--matt-affected", False):
            self._filter_affected(items)
        elif self.config.getoption("--matt-failed", False):
            self._filter_failed(items)
        elif self._quarantine:
            self._filter_quarantine(items)
        elif self.config.getoption("--matt-replay", None):
            self._filter_replay(items)

    def _filter_affected(self, items: list[Item]) -> None:
        """Keep only tests affected by source changes."""
        changed_opt = self.config.getoption("--matt-changed")
        if changed_opt:
            changed_files = [Path(f.strip()) for f in changed_opt.split(",")]
        else:
            changed_files = None

        if not self.tracker.has_data():
            logger.warning(
                "No dependency data. Run pytest --matt-rebuild-deps first. "
                "Running all tests."
            )
            return

        affected_ids = set(
            self.tracker.get_affected_tests(changed_files=changed_files)
        )

        if not affected_ids:
            logger.info("No affected tests detected — nothing to run")

        selected = []
        deselected = []
        for item in items:
            if item.nodeid in affected_ids:
                selected.append(item)
            else:
                deselected.append(item)

        if deselected:
            self.config.hook.pytest_deselected(items=deselected)
        items[:] = selected

        logger.info(
            f"Smart selection: {len(selected)} affected, {len(deselected)} skipped"
        )

    def _filter_failed(self, items: list[Item]) -> None:
        """Keep only tests that failed in the last run."""
        failed_ids = set(self.tracker.get_failed_tests())

        if not failed_ids:
            logger.info("No failed tests recorded — nothing to re-run")

        selected = []
        deselected = []
        for item in items:
            if item.nodeid in failed_ids:
                selected.append(item)
            else:
                deselected.append(item)

        if deselected:
            self.config.hook.pytest_deselected(items=deselected)
        items[:] = selected

        logger.info(
            f"Failed-only: {len(selected)} to re-run, {len(deselected)} skipped"
        )

    def _filter_quarantine(self, items: list[Item]) -> None:
        """Keep only known flaky (quarantined) tests."""
        quarantined_ids = self.flaky_detector.get_quarantined_ids()

        selected = []
        deselected = []
        for item in items:
            if item.nodeid in quarantined_ids:
                selected.append(item)
            else:
                deselected.append(item)

        if deselected:
            self.config.hook.pytest_deselected(items=deselected)
        items[:] = selected
        logger.info(f"Quarantine: {len(selected)} flaky tests, {len(deselected)} skipped")

    def _filter_replay(self, items: list[Item]) -> None:
        """Keep only tests that failed in the replay archive."""
        replay_path = self.config.getoption("--matt-replay")
        from django_matt.testing.smart.recorder import TestReplayer

        replayer = TestReplayer(replay_path)
        failed_ids = set(replayer.get_failed_test_ids())

        selected = []
        deselected = []
        for item in items:
            if item.nodeid in failed_ids:
                selected.append(item)
            else:
                deselected.append(item)

        if deselected:
            self.config.hook.pytest_deselected(items=deselected)
        items[:] = selected
        logger.info(
            f"Replay: {len(selected)} failed tests from archive, {len(deselected)} skipped"
        )

    # ------------------------------------------------------------------
    # Coverage recording (--matt-rebuild-deps)
    # ------------------------------------------------------------------

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item: Item, nextitem: Item | None):
        """Wrap each test in coverage recording when rebuilding deps."""
        if self._recording:
            coverage_data = self._run_with_coverage(item)
            yield
            if coverage_data is not None:
                self.tracker.record_test_coverage(item.nodeid, coverage_data)
        else:
            yield

    def _run_with_coverage(self, item: Item) -> dict[str, set[int]] | None:
        """Start coverage for a single test. Returns coverage data after test runs."""
        try:
            import coverage
        except ImportError:
            logger.warning("coverage package not installed — skipping dependency recording")
            return None

        cov = coverage.Coverage(
            data_file=None,  # in-memory only
            source=["django_matt"],
            branch=False,
        )
        cov.start()

        # Store on item so we can retrieve after test
        item._matt_cov = cov  # type: ignore[attr-defined]
        return None  # We'll collect in pytest_runtest_makereport

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: Item, call):
        """Collect coverage data and record pass/fail."""
        outcome = yield
        report: TestReport = outcome.get_result()

        # Only process the "call" phase (not setup/teardown)
        if report.when != "call":
            return

        self._stats["total"] += 1

        # Record pass/fail
        duration_ms = report.duration * 1000 if hasattr(report, "duration") else 0.0
        longrepr = str(report.longrepr) if report.longrepr else ""

        if report.passed:
            self._stats["passed"] += 1
            self.tracker.record_pass(item.nodeid)
            if self._detect_flaky:
                self.flaky_detector.record_outcome(item.nodeid, passed=True)
            if self._recorder:
                self._recorder.record_pass(item.nodeid, duration_ms)
        elif report.failed:
            self._stats["failed"] += 1
            self.tracker.record_failure(item.nodeid, longrepr)
            if self._detect_flaky:
                self.flaky_detector.record_outcome(item.nodeid, passed=False, traceback=longrepr)
            if self._recorder:
                self._recorder.record_fail(item.nodeid, duration_ms, traceback=longrepr)
        elif report.skipped:
            if self._recorder:
                self._recorder.record_skip(item.nodeid)

        # Collect coverage if recording
        if self._recording and hasattr(item, "_matt_cov"):
            cov = item._matt_cov  # type: ignore[attr-defined]
            try:
                cov.stop()
                data = cov.get_data()
                coverage_map: dict[str, set[int]] = {}
                for measured_file in data.measured_files():
                    lines = data.lines(measured_file)
                    if lines:
                        coverage_map[measured_file] = set(lines)
                self.tracker.record_test_coverage(item.nodeid, coverage_map)
            except Exception:
                logger.debug(f"Failed to collect coverage for {item.nodeid}", exc_info=True)
            finally:
                del item._matt_cov  # type: ignore[attr-defined]

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Record run metadata and close tracker."""
        if self._tracker is not None:
            try:
                import subprocess

                sha = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except Exception:
                sha = None

            self.tracker.record_run(
                self._run_id,
                sha,
                self._stats["total"],
                self._stats["passed"],
                self._stats["failed"],
            )
            self.tracker.close()

        if self._recorder:
            archive_path = self._recorder.save()
            logger.info(f"Test run recorded to {archive_path}")

        if self._flaky_detector is not None:
            self._flaky_detector.close()

    def pytest_terminal_summary(
        self, terminalreporter: TerminalReporter, exitstatus: int, config: Config
    ) -> None:
        """Print smart testing summary."""
        if self._recording:
            terminalreporter.write_sep("=", "matt: dependency database rebuilt")
        elif self.config.getoption("--matt-affected", False):
            n = self._stats["total"]
            terminalreporter.write_sep(
                "=", f"matt: {n} affected test(s) selected"
            )
        elif self.config.getoption("--matt-failed", False):
            n = self._stats["total"]
            terminalreporter.write_sep(
                "=", f"matt: {n} previously-failed test(s) re-run"
            )
        elif self._detect_flaky:
            flaky = self.flaky_detector.get_flaky_tests()
            if flaky:
                terminalreporter.write_sep("=", f"matt: {len(flaky)} flaky test(s) detected")
                for f in flaky[:10]:
                    terminalreporter.write_line(
                        f"  {f.test_id} — {f.failure_rate:.0%} failure rate "
                        f"({f.failure_count}/{f.total_runs})"
                    )
            else:
                terminalreporter.write_sep("=", "matt: no flaky tests detected")
        if self._recorder:
            terminalreporter.write_sep(
                "=", f"matt: run recorded to {self._recorder.output_path}"
            )


class TrackerWrapper:
    """Thin wrapper that lazy-loads TestDependencyTracker."""

    def __init__(self, db_path: Path):
        from django_matt.testing.smart.tracker import TestDependencyTracker

        self._tracker = TestDependencyTracker(db_path)

    def __getattr__(self, name: str):
        return getattr(self._tracker, name)
