"""
File testing utilities for CLI.

Provides tools for testing file generation commands.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileSnapshot:
    """Snapshot of a file's state."""

    path: str
    exists: bool
    content: str | None = None
    size: int = 0
    is_dir: bool = False

    @classmethod
    def capture(cls, path: str | Path) -> FileSnapshot:
        """Capture current state of a file."""
        path = Path(path)
        if not path.exists():
            return cls(path=str(path), exists=False)

        if path.is_dir():
            return cls(
                path=str(path),
                exists=True,
                is_dir=True,
            )

        content = path.read_text() if path.is_file() else None
        return cls(
            path=str(path),
            exists=True,
            content=content,
            size=path.stat().st_size if path.is_file() else 0,
        )


@dataclass
class FileChange:
    """Record of a file change."""

    path: str
    action: str  # created, modified, deleted, unchanged
    before: FileSnapshot | None = None
    after: FileSnapshot | None = None

    @property
    def was_created(self) -> bool:
        return self.action == "created"

    @property
    def was_modified(self) -> bool:
        return self.action == "modified"

    @property
    def was_deleted(self) -> bool:
        return self.action == "deleted"

    @property
    def content_diff(self) -> str | None:
        """Get diff between before and after content."""
        if not self.before or not self.after:
            return None
        if self.before.content == self.after.content:
            return None

        import difflib
        before_lines = (self.before.content or "").splitlines(keepends=True)
        after_lines = (self.after.content or "").splitlines(keepends=True)

        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{self.path}",
            tofile=f"b/{self.path}",
        )
        return "".join(diff)


@dataclass
class FileTracker:
    """
    Track file changes during command execution.

    Usage:
        tracker = FileTracker()
        tracker.watch("output/")

        # Run command that creates files
        runner.invoke("generate_crud", "myapp.Model")

        # Check what was created
        assert tracker.was_created("output/controller.py")
        tracker.assert_file_contains("output/controller.py", "class ModelController")
    """

    watched_paths: list[str] = field(default_factory=list)
    _snapshots: dict[str, FileSnapshot] = field(default_factory=dict)
    _changes: list[FileChange] = field(default_factory=list)

    def watch(self, *paths: str | Path) -> FileTracker:
        """Add paths to watch for changes."""
        for path in paths:
            path_str = str(path)
            self.watched_paths.append(path_str)
            self._capture_recursive(Path(path_str))
        return self

    def _capture_recursive(self, path: Path) -> None:
        """Capture snapshots of path and all children."""
        if path.exists():
            self._snapshots[str(path)] = FileSnapshot.capture(path)
            if path.is_dir():
                for child in path.rglob("*"):
                    self._snapshots[str(child)] = FileSnapshot.capture(child)
        else:
            self._snapshots[str(path)] = FileSnapshot(path=str(path), exists=False)

    def capture_changes(self) -> list[FileChange]:
        """Capture all changes since watching started."""
        self._changes = []
        current_files: set[str] = set()

        for watched in self.watched_paths:
            path = Path(watched)
            if path.exists():
                if path.is_file():
                    current_files.add(str(path))
                else:
                    for child in path.rglob("*"):
                        if child.is_file():
                            current_files.add(str(child))

        # Check for new and modified files
        for file_path in current_files:
            before = self._snapshots.get(file_path)
            after = FileSnapshot.capture(file_path)

            if before is None or not before.exists:
                self._changes.append(FileChange(
                    path=file_path,
                    action="created",
                    after=after,
                ))
            elif before.content != after.content:
                self._changes.append(FileChange(
                    path=file_path,
                    action="modified",
                    before=before,
                    after=after,
                ))

        # Check for deleted files
        for file_path, before in self._snapshots.items():
            if before.exists and not before.is_dir and file_path not in current_files:
                self._changes.append(FileChange(
                    path=file_path,
                    action="deleted",
                    before=before,
                ))

        return self._changes

    @property
    def changes(self) -> list[FileChange]:
        """Get captured changes."""
        if not self._changes:
            self.capture_changes()
        return self._changes

    @property
    def created_files(self) -> list[str]:
        """Get list of created files."""
        return [c.path for c in self.changes if c.was_created]

    @property
    def modified_files(self) -> list[str]:
        """Get list of modified files."""
        return [c.path for c in self.changes if c.was_modified]

    @property
    def deleted_files(self) -> list[str]:
        """Get list of deleted files."""
        return [c.path for c in self.changes if c.was_deleted]

    def was_created(self, path: str) -> bool:
        """Check if file was created."""
        return any(
            c.path.endswith(path) or path in c.path
            for c in self.changes
            if c.was_created
        )

    def was_modified(self, path: str) -> bool:
        """Check if file was modified."""
        return any(
            c.path.endswith(path) or path in c.path
            for c in self.changes
            if c.was_modified
        )

    def was_deleted(self, path: str) -> bool:
        """Check if file was deleted."""
        return any(
            c.path.endswith(path) or path in c.path
            for c in self.changes
            if c.was_deleted
        )

    def get_file_content(self, path: str) -> str | None:
        """Get content of a file."""
        full_path = Path(path)
        if full_path.exists():
            return full_path.read_text()
        return None

    # Assertion methods

    def assert_created(self, path: str) -> FileTracker:
        """Assert file was created."""
        if not self.was_created(path):
            raise AssertionError(
                f"Expected '{path}' to be created\n"
                f"Created files: {self.created_files}"
            )
        return self

    def assert_not_created(self, path: str) -> FileTracker:
        """Assert file was NOT created."""
        if self.was_created(path):
            raise AssertionError(f"Expected '{path}' to NOT be created")
        return self

    def assert_modified(self, path: str) -> FileTracker:
        """Assert file was modified."""
        if not self.was_modified(path):
            raise AssertionError(
                f"Expected '{path}' to be modified\n"
                f"Modified files: {self.modified_files}"
            )
        return self

    def assert_deleted(self, path: str) -> FileTracker:
        """Assert file was deleted."""
        if not self.was_deleted(path):
            raise AssertionError(
                f"Expected '{path}' to be deleted\n"
                f"Deleted files: {self.deleted_files}"
            )
        return self

    def assert_file_exists(self, path: str) -> FileTracker:
        """Assert file exists."""
        if not Path(path).exists():
            raise AssertionError(f"Expected '{path}' to exist")
        return self

    def assert_file_not_exists(self, path: str) -> FileTracker:
        """Assert file does not exist."""
        if Path(path).exists():
            raise AssertionError(f"Expected '{path}' to NOT exist")
        return self

    def assert_file_contains(self, path: str, text: str) -> FileTracker:
        """Assert file contains text."""
        content = self.get_file_content(path)
        if content is None:
            raise AssertionError(f"File '{path}' does not exist")
        if text not in content:
            raise AssertionError(
                f"Expected '{path}' to contain '{text}'\n"
                f"Content: {content[:500]}..."
            )
        return self

    def assert_file_not_contains(self, path: str, text: str) -> FileTracker:
        """Assert file does not contain text."""
        content = self.get_file_content(path)
        if content and text in content:
            raise AssertionError(f"Expected '{path}' to NOT contain '{text}'")
        return self

    def assert_file_count(self, count: int) -> FileTracker:
        """Assert number of files changed."""
        actual = len(self.changes)
        if actual != count:
            raise AssertionError(
                f"Expected {count} file changes, got {actual}\n"
                f"Changes: {[c.path for c in self.changes]}"
            )
        return self


@contextmanager
def temp_directory():
    """
    Context manager that creates a temporary directory.

    Usage:
        with temp_directory() as tmpdir:
            # tmpdir is a Path to the temp directory
            # Files created here are cleaned up after
    """
    tmpdir = tempfile.mkdtemp()
    try:
        yield Path(tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@contextmanager
def working_directory(path: str | Path):
    """
    Context manager to temporarily change working directory.

    Usage:
        with working_directory("/tmp/test"):
            # Current directory is now /tmp/test
    """
    original = os.getcwd()
    try:
        os.chdir(path)
        yield Path(path)
    finally:
        os.chdir(original)


@contextmanager
def isolated_filesystem():
    """
    Context manager for isolated filesystem testing.

    Creates a temp directory and changes to it.

    Usage:
        with isolated_filesystem() as tmpdir:
            # Run commands in isolated directory
            Path("test.txt").write_text("hello")
    """
    with temp_directory() as tmpdir:
        with working_directory(tmpdir):
            yield tmpdir


def create_test_file(path: str | Path, content: str = "") -> Path:
    """Create a test file with content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_test_directory(path: str | Path) -> Path:
    """Create a test directory."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
