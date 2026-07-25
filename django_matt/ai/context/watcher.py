# file-length-max: 500
"""
File watcher for automatic AI context regeneration.

Provides:
- Debounced file watching for auto-updates
- Pre-commit hook integration
- Watch mode for development
"""

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class FileChangeEvent:
    """Represents a file change event."""

    path: Path
    event_type: str  # created, modified, deleted
    timestamp: float = field(default_factory=time.time)


class DebouncedCallback:
    """
    Debounced callback that waits for a quiet period before executing.

    Useful for batching multiple rapid file changes into a single regeneration.

    Usage:
        def regenerate():
            print("Regenerating context files...")

        debounced = DebouncedCallback(regenerate, delay=1.0)
        debounced.call()  # First call
        debounced.call()  # This resets the timer
        debounced.call()  # This also resets
        # After 1.0 seconds of no calls, regenerate() is called once
    """

    def __init__(self, callback: Callable[[], None], delay: float = 1.0):
        """
        Initialize debounced callback.

        Args:
            callback: Function to call after quiet period
            delay: Seconds to wait after last call before executing
        """
        self.callback = callback
        self.delay = delay
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def call(self):
        """Trigger the callback (debounced)."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()

            self._timer = threading.Timer(self.delay, self._execute)
            self._timer.start()

    def _execute(self):
        """Execute the callback."""
        with self._lock:
            self._timer = None
        self.callback()

    def cancel(self):
        """Cancel any pending callback."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class FileChangeHandler:
    """
    Handles file change events for context regeneration.

    Filters relevant file changes and triggers regeneration.

    Usage:
        handler = FileChangeHandler(on_change=regenerate_callback)
        handler.on_file_modified(Path("app/models.py"))
    """

    # File patterns that trigger regeneration
    WATCH_PATTERNS = [
        "*.py",
        "*.pyi",
    ]

    # Directories to ignore
    IGNORE_DIRS = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "htmlcov",
        "dist",
        "build",
        ".eggs",
        ".tox",
    }

    # Files to ignore
    IGNORE_FILES = {
        "CLAUDE.md",
        ".cursorrules",
        ".copilot-instructions",
        "introspection.json",
    }

    def __init__(
        self,
        on_change: Callable[[], None],
        debounce_delay: float = 1.0,
    ):
        """
        Initialize handler.

        Args:
            on_change: Callback to execute on relevant file changes
            debounce_delay: Seconds to wait before regenerating
        """
        self.debounced = DebouncedCallback(on_change, delay=debounce_delay)
        self._pending_events: list[FileChangeEvent] = []
        self._lock = threading.Lock()

    def should_watch(self, path: Path) -> bool:
        """Check if a file should trigger regeneration."""
        # Check if in ignored directory
        for part in path.parts:
            if part in self.IGNORE_DIRS:
                return False

        # Check if ignored file
        if path.name in self.IGNORE_FILES:
            return False

        # Check if matches watch patterns
        for pattern in self.WATCH_PATTERNS:
            if path.match(pattern):
                return True

        return False

    def on_file_created(self, path: Path):
        """Handle file creation."""
        if self.should_watch(path):
            self._handle_event(FileChangeEvent(path, "created"))

    def on_file_modified(self, path: Path):
        """Handle file modification."""
        if self.should_watch(path):
            self._handle_event(FileChangeEvent(path, "modified"))

    def on_file_deleted(self, path: Path):
        """Handle file deletion."""
        if self.should_watch(path):
            self._handle_event(FileChangeEvent(path, "deleted"))

    def _handle_event(self, event: FileChangeEvent):
        """Handle a file change event."""
        with self._lock:
            self._pending_events.append(event)
        self.debounced.call()

    def get_pending_events(self) -> list[FileChangeEvent]:
        """Get and clear pending events."""
        with self._lock:
            events = self._pending_events.copy()
            self._pending_events.clear()
            return events


class ContextWatcher:
    """
    Watches for file changes and regenerates AI context files.

    Integrates with the filesystem to detect changes in Python files
    and automatically regenerate context files.

    Usage:
        watcher = ContextWatcher(
            project_root="/path/to/project",
            formats=["claude", "cursor", "copilot"],
        )
        watcher.start()

        # ... do work ...

        watcher.stop()

    Or use as context manager:
        with ContextWatcher() as watcher:
            # ... do work ...
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        formats: list[str] | None = None,
        debounce_delay: float = 1.0,
        on_regenerate: Callable[[], None] | None = None,
        quiet: bool = False,
    ):
        """
        Initialize watcher.

        Args:
            project_root: Root directory to watch (default: cwd)
            formats: List of formats to generate (claude, cursor, copilot, json)
            debounce_delay: Seconds to wait after last change before regenerating
            on_regenerate: Optional callback after regeneration
            quiet: Suppress output
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.formats = formats or ["claude", "cursor", "copilot"]
        self.debounce_delay = debounce_delay
        self.on_regenerate = on_regenerate
        self.quiet = quiet

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._handler = FileChangeHandler(
            on_change=self._regenerate,
            debounce_delay=debounce_delay,
        )

        # Track file modification times
        self._file_mtimes: dict[Path, float] = {}

    def _log(self, message: str):
        """Log a message if not quiet."""
        if not self.quiet:
            print(f"[AI Context Watcher] {message}")

    def _regenerate(self):
        """Regenerate context files."""
        from django_matt.ai.context.generators import ContextGenerator

        events = self._handler.get_pending_events()
        if not events:
            return

        self._log(f"Detected {len(events)} file change(s), regenerating...")

        try:
            generator = ContextGenerator(
                output_dir=self.project_root,
                include_examples=True,
            )
            files = generator.generate_all(formats=self.formats)

            for name, path in files.items():
                self._log(f"  Generated: {path.name}")

            if self.on_regenerate:
                self.on_regenerate()

        except Exception as e:
            self._log(f"Error regenerating context: {e}")

    def _scan_files(self) -> dict[Path, float]:
        """Scan project files and return their modification times."""
        mtimes = {}

        for py_file in self.project_root.rglob("*.py"):
            if self._handler.should_watch(py_file):
                try:
                    mtimes[py_file] = py_file.stat().st_mtime
                except (OSError, FileNotFoundError):
                    pass

        return mtimes

    def _check_for_changes(self):
        """Check for file changes since last scan."""
        current_mtimes = self._scan_files()

        # Find new and modified files
        for path, mtime in current_mtimes.items():
            if path not in self._file_mtimes:
                self._handler.on_file_created(path)
            elif self._file_mtimes[path] < mtime:
                self._handler.on_file_modified(path)

        # Find deleted files
        for path in self._file_mtimes:
            if path not in current_mtimes:
                self._handler.on_file_deleted(path)

        self._file_mtimes = current_mtimes

    def _watch_loop(self):
        """Main watch loop."""
        self._log(f"Watching {self.project_root} for changes...")
        self._log(f"Formats: {', '.join(self.formats)}")
        self._log("Press Ctrl+C to stop")

        # Initial scan
        self._file_mtimes = self._scan_files()

        while not self._stop_event.is_set():
            self._check_for_changes()
            self._stop_event.wait(0.5)  # Check every 500ms

    def start(self):
        """Start watching for file changes."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching for file changes."""
        if not self._running:
            return

        self._stop_event.set()
        self._handler.debounced.cancel()

        if self._thread:
            self._thread.join(timeout=2.0)

        self._running = False
        self._log("Stopped watching")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


def generate_precommit_hook() -> str:
    """
    Generate a pre-commit hook script for AI context regeneration.

    Returns:
        Shell script content for pre-commit hook
    """
    return """#!/bin/bash
# Pre-commit hook for django-matt AI context generation
# Auto-generated by django-matt

# Check if any Python files changed
PYTHON_CHANGED=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.py$' | wc -l)

if [ "$PYTHON_CHANGED" -gt 0 ]; then
    echo "Python files changed, regenerating AI context..."

    # Regenerate context files
    python manage.py generate_ai_context --quiet

    # Check if context files were modified
    if [ -n "$(git status --porcelain CLAUDE.md .cursorrules .copilot-instructions 2>/dev/null)" ]; then
        echo "AI context files updated. Adding to commit..."
        git add CLAUDE.md .cursorrules .copilot-instructions 2>/dev/null
    fi
fi

exit 0
"""


def generate_precommit_config() -> str:
    """
    Generate pre-commit configuration for .pre-commit-config.yaml.

    Returns:
        YAML configuration snippet
    """
    return """# Add this to your .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: update-ai-context
        name: Update AI Context Files
        entry: python manage.py generate_ai_context --quiet
        language: python
        pass_filenames: false
        stages: [commit]
        files: '\\.py$'
        additional_dependencies:
          - django
          - django-matt
"""


def install_precommit_hook(project_root: str | Path | None = None) -> Path:
    """
    Install the pre-commit hook in the project.

    Args:
        project_root: Project root directory

    Returns:
        Path to installed hook
    """
    root = Path(project_root) if project_root else Path.cwd()
    hooks_dir = root / ".git" / "hooks"

    if not hooks_dir.exists():
        raise FileNotFoundError(
            f"Git hooks directory not found: {hooks_dir}. Make sure you're in a git repository."
        )

    hook_path = hooks_dir / "pre-commit"

    # Check for existing hook
    if hook_path.exists():
        existing = hook_path.read_text()
        if "django-matt" not in existing:
            # Append to existing hook
            hook_content = existing + "\n\n" + generate_precommit_hook()
        else:
            # Already installed
            return hook_path
    else:
        hook_content = generate_precommit_hook()

    hook_path.write_text(hook_content)
    hook_path.chmod(0o755)

    return hook_path


__all__ = [
    "ContextWatcher",
    "DebouncedCallback",
    "FileChangeEvent",
    "FileChangeHandler",
    "generate_precommit_config",
    "generate_precommit_hook",
    "install_precommit_hook",
]
