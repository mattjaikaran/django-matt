"""Flaky test detection and classification.

A test is classified as *flaky* if it fails on the first run but passes on retry.
Flaky tests can be quarantined (run separately, don't block CI).

Usage via pytest::

    # Stress-test a single test
    pytest --matt-stress tests/test_auth.py::test_jwt_refresh --matt-stress-count=50

    # Detect flaky tests across the suite with retries
    pytest --matt-detect-flaky --matt-retries=3

    # Quarantine known flaky tests (run separately)
    pytest --matt-quarantine
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FlakyRecord:
    """A flaky test record."""

    test_id: str
    failure_count: int
    success_count: int
    total_runs: int
    failure_rate: float
    last_failure: str
    last_traceback: str

    @property
    def is_flaky(self) -> bool:
        return 0 < self.failure_rate < 1.0


FLAKY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS flaky_tests (
    test_id TEXT PRIMARY KEY,
    failure_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    total_runs INTEGER NOT NULL DEFAULT 0,
    last_failure TEXT,
    last_traceback TEXT NOT NULL DEFAULT '',
    first_seen TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stress_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id TEXT NOT NULL,
    run_index INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    traceback TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class FlakyDetector:
    """Detect and classify flaky tests.

    Tracks test outcomes across runs and classifies tests as flaky when
    they show intermittent failures (fail sometimes, pass sometimes).
    """

    def __init__(self, db_path: Path = Path(".matttest.db")) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(FLAKY_SCHEMA_SQL)

    def record_outcome(
        self,
        test_id: str,
        passed: bool,
        traceback: str = "",
    ) -> None:
        """Record a single test run outcome."""
        row = self._conn.execute(
            "SELECT * FROM flaky_tests WHERE test_id = ?", (test_id,)
        ).fetchone()

        if row is None:
            self._conn.execute(
                "INSERT INTO flaky_tests (test_id, failure_count, success_count, total_runs, last_failure, last_traceback) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (
                    test_id,
                    0 if passed else 1,
                    1 if passed else 0,
                    None if passed else time.strftime("%Y-%m-%d %H:%M:%S"),
                    "" if passed else traceback,
                ),
            )
        else:
            if passed:
                self._conn.execute(
                    "UPDATE flaky_tests SET success_count = success_count + 1, "
                    "total_runs = total_runs + 1, last_seen = datetime('now') "
                    "WHERE test_id = ?",
                    (test_id,),
                )
            else:
                self._conn.execute(
                    "UPDATE flaky_tests SET failure_count = failure_count + 1, "
                    "total_runs = total_runs + 1, last_failure = datetime('now'), "
                    "last_traceback = ?, last_seen = datetime('now') "
                    "WHERE test_id = ?",
                    (traceback, test_id),
                )
        self._conn.commit()

    def record_stress_result(
        self,
        test_id: str,
        run_index: int,
        passed: bool,
        duration_ms: float,
        traceback: str = "",
    ) -> None:
        """Record a single stress-test iteration result."""
        self._conn.execute(
            "INSERT INTO stress_results (test_id, run_index, passed, duration_ms, traceback) "
            "VALUES (?, ?, ?, ?, ?)",
            (test_id, run_index, 1 if passed else 0, duration_ms, traceback or None),
        )
        self._conn.commit()

    def get_flaky_tests(self) -> list[FlakyRecord]:
        """Return all tests classified as flaky (mixed pass/fail history)."""
        rows = self._conn.execute(
            "SELECT * FROM flaky_tests WHERE failure_count > 0 AND success_count > 0 "
            "ORDER BY CAST(failure_count AS REAL) / total_runs DESC"
        ).fetchall()

        return [
            FlakyRecord(
                test_id=r["test_id"],
                failure_count=r["failure_count"],
                success_count=r["success_count"],
                total_runs=r["total_runs"],
                failure_rate=r["failure_count"] / r["total_runs"],
                last_failure=r["last_failure"] or "",
                last_traceback=r["last_traceback"] or "",
            )
            for r in rows
        ]

    def get_quarantined_ids(self) -> set[str]:
        """Return test IDs that should be quarantined (flaky)."""
        return {r.test_id for r in self.get_flaky_tests()}

    def get_stress_summary(self, test_id: str) -> dict:
        """Return summary of stress test results for a specific test."""
        rows = self._conn.execute(
            "SELECT * FROM stress_results WHERE test_id = ? ORDER BY run_index",
            (test_id,),
        ).fetchall()

        if not rows:
            return {"test_id": test_id, "total_runs": 0}

        passed = sum(1 for r in rows if r["passed"])
        failed = len(rows) - passed
        durations = [r["duration_ms"] for r in rows]

        return {
            "test_id": test_id,
            "total_runs": len(rows),
            "passed": passed,
            "failed": failed,
            "failure_rate": failed / len(rows),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "is_flaky": 0 < failed < len(rows),
        }

    def clear(self) -> None:
        """Clear all flaky test data."""
        self._conn.execute("DELETE FROM flaky_tests")
        self._conn.execute("DELETE FROM stress_results")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
