"""Test replay archives — record and replay test runs as portable ZIP files.

Archive format::

    run-2026-04-16.zip/
        meta.json           # Python/Django version, git SHA, installed packages
        events.ndjson       # Newline-delimited JSON event stream
        tests/
            test_id_hash/
                stdout.txt  # Captured stdout
                stderr.txt  # Captured stderr

Usage via pytest::

    pytest --matt-record=run-2026-04-16.zip   # Record
    pytest --matt-replay=run-2026-04-16.zip   # Replay
"""

from __future__ import annotations

import io
import json
import platform
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass
class TestEvent:
    """A single event in the test run timeline."""

    event: str  # "test_start", "test_pass", "test_fail", "test_skip", "test_error"
    test_id: str
    timestamp: float
    duration_ms: float = 0.0
    traceback: str = ""
    stdout: str = ""
    stderr: str = ""


@dataclass
class RunMetadata:
    """Environment snapshot for the test run."""

    python_version: str = ""
    django_version: str = ""
    platform_info: str = ""
    git_sha: str = ""
    git_dirty: bool = False
    packages: dict[str, str] = field(default_factory=dict)
    recorded_at: str = ""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class TestRecorder:
    """Record a test run into a portable ZIP archive."""

    def __init__(self, output_path: str | Path) -> None:
        self.output_path = Path(output_path)
        self.events: list[TestEvent] = []
        self.metadata = self._capture_metadata()

    def record_start(self, test_id: str) -> None:
        self.events.append(TestEvent(event="test_start", test_id=test_id, timestamp=time.time()))

    def record_pass(
        self, test_id: str, duration_ms: float, stdout: str = "", stderr: str = ""
    ) -> None:
        self.metadata.passed += 1
        self.metadata.total_tests += 1
        self.events.append(
            TestEvent(
                event="test_pass",
                test_id=test_id,
                timestamp=time.time(),
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
            )
        )

    def record_fail(
        self,
        test_id: str,
        duration_ms: float,
        traceback: str = "",
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.metadata.failed += 1
        self.metadata.total_tests += 1
        self.events.append(
            TestEvent(
                event="test_fail",
                test_id=test_id,
                timestamp=time.time(),
                duration_ms=duration_ms,
                traceback=traceback,
                stdout=stdout,
                stderr=stderr,
            )
        )

    def record_skip(self, test_id: str, reason: str = "") -> None:
        self.metadata.skipped += 1
        self.metadata.total_tests += 1
        self.events.append(
            TestEvent(
                event="test_skip",
                test_id=test_id,
                timestamp=time.time(),
                traceback=reason,
            )
        )

    def save(self) -> Path:
        """Write the archive to disk."""
        with zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Metadata
            zf.writestr("meta.json", json.dumps(asdict(self.metadata), indent=2))

            # Event stream (NDJSON)
            events_buf = io.StringIO()
            for ev in self.events:
                events_buf.write(json.dumps(asdict(ev)) + "\n")
            zf.writestr("events.ndjson", events_buf.getvalue())

            # Per-test output files
            for ev in self.events:
                if ev.event in ("test_pass", "test_fail", "test_error"):
                    test_hash = sha256(ev.test_id.encode()).hexdigest()[:12]
                    if ev.stdout:
                        zf.writestr(f"tests/{test_hash}/stdout.txt", ev.stdout)
                    if ev.stderr:
                        zf.writestr(f"tests/{test_hash}/stderr.txt", ev.stderr)
                    if ev.traceback:
                        zf.writestr(f"tests/{test_hash}/traceback.txt", ev.traceback)

        return self.output_path

    @staticmethod
    def _capture_metadata() -> RunMetadata:
        meta = RunMetadata(
            python_version=sys.version,
            platform_info=platform.platform(),
            recorded_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        try:
            import django

            meta.django_version = django.__version__
        except ImportError:
            pass

        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            meta.git_sha = result.stdout.strip()
            dirty = subprocess.run(
                ["git", "diff", "--quiet"],
                capture_output=True,
                check=False,
            )
            meta.git_dirty = dirty.returncode != 0
        except Exception:
            pass

        try:
            from importlib.metadata import distributions

            meta.packages = {
                d.metadata["Name"]: d.metadata["Version"]
                for d in distributions()
                if d.metadata["Name"]
            }
        except Exception:
            pass

        return meta


class TestReplayer:
    """Replay a recorded test run from a ZIP archive."""

    def __init__(self, archive_path: str | Path) -> None:
        self.archive_path = Path(archive_path)
        self._metadata: RunMetadata | None = None
        self._events: list[TestEvent] | None = None

    @property
    def metadata(self) -> RunMetadata:
        if self._metadata is None:
            self._load()
        return self._metadata  # type: ignore[return-value]

    @property
    def events(self) -> list[TestEvent]:
        if self._events is None:
            self._load()
        return self._events  # type: ignore[return-value]

    def _load(self) -> None:
        with zipfile.ZipFile(self.archive_path, "r") as zf:
            meta_json = json.loads(zf.read("meta.json"))
            self._metadata = RunMetadata(**meta_json)

            events_data = zf.read("events.ndjson").decode("utf-8")
            self._events = []
            for line in events_data.strip().split("\n"):
                if line:
                    self._events.append(TestEvent(**json.loads(line)))

    def get_failed_test_ids(self) -> list[str]:
        """Return test IDs that failed in the recorded run."""
        return [e.test_id for e in self.events if e.event == "test_fail"]

    def get_test_output(self, test_id: str) -> dict[str, str]:
        """Return stdout/stderr/traceback for a specific test."""
        test_hash = sha256(test_id.encode()).hexdigest()[:12]
        output: dict[str, str] = {}

        with zipfile.ZipFile(self.archive_path, "r") as zf:
            for key in ("stdout", "stderr", "traceback"):
                path = f"tests/{test_hash}/{key}.txt"
                try:
                    output[key] = zf.read(path).decode("utf-8")
                except KeyError:
                    pass

        return output

    def summary(self) -> dict[str, Any]:
        """Return a summary of the recorded run."""
        m = self.metadata
        return {
            "recorded_at": m.recorded_at,
            "python_version": m.python_version,
            "django_version": m.django_version,
            "git_sha": m.git_sha,
            "git_dirty": m.git_dirty,
            "total_tests": m.total_tests,
            "passed": m.passed,
            "failed": m.failed,
            "skipped": m.skipped,
        }
