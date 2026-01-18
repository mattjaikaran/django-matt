"""
File watching utilities for code generation.

Provides efficient file watching with debouncing and optional watchdog support.

Usage:
    from django_matt.codegen.watcher import CodegenWatcher

    watcher = CodegenWatcher(
        paths=["myapp/models.py", "myapp/schemas.py"],
        on_change=lambda files: regenerate_code(),
    )
    watcher.start()
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("django_matt.codegen.watcher")

# Try to import watchdog for efficient file watching
try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    FileModifiedEvent = None  # type: ignore[assignment,misc]


@dataclass
class WatchConfig:
    """Configuration for the file watcher."""

    # Paths to watch (files or directories)
    paths: list[str] = field(default_factory=list)

    # File patterns to include (glob patterns)
    include_patterns: list[str] = field(default_factory=lambda: ["*.py"])

    # File patterns to exclude
    exclude_patterns: list[str] = field(
        default_factory=lambda: ["__pycache__", "*.pyc", ".git", ".venv", "venv"]
    )

    # Debounce delay in seconds
    debounce_delay: float = 0.5

    # Polling interval (used when watchdog is not available)
    poll_interval: float = 1.0

    # Whether to clear terminal before regeneration
    clear_screen: bool = False

    # Whether to use polling even if watchdog is available
    force_polling: bool = False


class DebouncedCallback:
    """Debounces multiple rapid calls into a single call."""

    def __init__(self, callback: Callable[[], None], delay: float = 0.5):
        self.callback = callback
        self.delay = delay
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._pending_files: set[str] = set()

    def __call__(self, filepath: str | None = None):
        with self._lock:
            if filepath:
                self._pending_files.add(filepath)

            if self._timer is not None:
                self._timer.cancel()

            self._timer = threading.Timer(self.delay, self._execute)
            self._timer.start()

    def _execute(self):
        with self._lock:
            files = list(self._pending_files)
            self._pending_files.clear()
            self._timer = None

        self.callback(files)

    def cancel(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class WatchdogHandler(FileSystemEventHandler):
    """Watchdog event handler for file changes."""

    def __init__(
        self,
        callback: Callable[[str], None],
        include_patterns: list[str],
        exclude_patterns: list[str],
    ):
        self.callback = callback
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns

    def _should_handle(self, path: str) -> bool:
        """Check if the file should trigger regeneration."""
        from fnmatch import fnmatch

        name = Path(path).name

        # Check excludes first
        for pattern in self.exclude_patterns:
            if fnmatch(name, pattern) or fnmatch(path, f"*/{pattern}/*"):
                return False

        # Check includes
        for pattern in self.include_patterns:
            if fnmatch(name, pattern):
                return True

        return False

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_handle(event.src_path):
            self.callback(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_handle(event.src_path):
            self.callback(event.src_path)


class PollingWatcher:
    """Fallback polling-based file watcher."""

    def __init__(
        self,
        paths: list[str],
        callback: Callable[[str], None],
        interval: float = 1.0,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.paths = paths
        self.callback = callback
        self.interval = interval
        self.include_patterns = include_patterns or ["*.py"]
        self.exclude_patterns = exclude_patterns or []
        self._running = False
        self._thread: threading.Thread | None = None
        self._mtimes: dict[str, float] = {}
        self._hashes: dict[str, str] = {}

    def _get_files_to_watch(self) -> set[str]:
        """Get all files that should be watched."""
        from fnmatch import fnmatch

        files = set()

        for path in self.paths:
            path_obj = Path(path)

            if path_obj.is_file():
                files.add(str(path_obj.resolve()))
            elif path_obj.is_dir():
                for pattern in self.include_patterns:
                    for f in path_obj.rglob(pattern):
                        # Check excludes
                        excluded = False
                        for exclude in self.exclude_patterns:
                            if fnmatch(f.name, exclude) or any(
                                fnmatch(p, exclude) for p in f.parts
                            ):
                                excluded = True
                                break
                        if not excluded:
                            files.add(str(f.resolve()))

        return files

    def _get_file_hash(self, filepath: str) -> str:
        """Get hash of file contents."""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except OSError:
            return ""

    def _check_changes(self) -> list[str]:
        """Check for file changes."""
        changed = []
        current_files = self._get_files_to_watch()

        for filepath in current_files:
            try:
                # Check mtime first (faster)
                mtime = os.path.getmtime(filepath)
                old_mtime = self._mtimes.get(filepath)

                if old_mtime is None or mtime > old_mtime:
                    # Verify with hash to avoid false positives
                    new_hash = self._get_file_hash(filepath)
                    old_hash = self._hashes.get(filepath)

                    if old_hash is None or new_hash != old_hash:
                        changed.append(filepath)
                        self._hashes[filepath] = new_hash

                    self._mtimes[filepath] = mtime

            except OSError:
                # File may have been deleted
                pass

        return changed

    def _watch_loop(self):
        """Main watching loop."""
        # Initialize mtimes and hashes
        for filepath in self._get_files_to_watch():
            try:
                self._mtimes[filepath] = os.path.getmtime(filepath)
                self._hashes[filepath] = self._get_file_hash(filepath)
            except OSError:
                pass

        while self._running:
            time.sleep(self.interval)

            changed = self._check_changes()
            for filepath in changed:
                self.callback(filepath)

    def start(self):
        """Start watching."""
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)


class CodegenWatcher:
    """
    File watcher for code generation with automatic regeneration.

    Uses watchdog if available, falls back to polling otherwise.

    Usage:
        watcher = CodegenWatcher(
            config=WatchConfig(
                paths=["myapp/models.py", "myapp/schemas.py"],
                debounce_delay=0.5,
            ),
            on_change=lambda files: print(f"Changed: {files}"),
        )

        try:
            watcher.start()
            watcher.wait()  # Block until interrupted
        finally:
            watcher.stop()
    """

    def __init__(
        self,
        config: WatchConfig,
        on_change: Callable[[list[str]], None],
        on_start: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ):
        self.config = config
        self.on_change = on_change
        self.on_start = on_start
        self.on_error = on_error

        self._debounced = DebouncedCallback(
            self._handle_changes,
            delay=config.debounce_delay,
        )

        self._use_watchdog = HAS_WATCHDOG and not config.force_polling
        self._observer = None
        self._poller = None
        self._running = False

    def _handle_changes(self, files: list[str]):
        """Handle file changes with optional screen clear."""
        if self.config.clear_screen:
            import subprocess

            cmd = "cls" if os.name == "nt" else "clear"
            subprocess.run([cmd], shell=True, check=False)  # noqa: S602

        try:
            self.on_change(files)
        except Exception as e:
            if self.on_error:
                self.on_error(e)
            else:
                logger.exception("Error during code generation")

    def _on_file_change(self, filepath: str):
        """Called when a file changes."""
        logger.debug(f"File changed: {filepath}")
        self._debounced(filepath)

    def start(self):
        """Start the file watcher."""
        if self._running:
            return

        self._running = True

        if self.on_start:
            self.on_start()

        if self._use_watchdog:
            self._start_watchdog()
        else:
            self._start_polling()

    def _start_watchdog(self):
        """Start watching with watchdog."""
        handler = WatchdogHandler(
            callback=self._on_file_change,
            include_patterns=self.config.include_patterns,
            exclude_patterns=self.config.exclude_patterns,
        )

        self._observer = Observer()

        for path in self.config.paths:
            path_obj = Path(path)
            if path_obj.is_file():
                # Watch parent directory for file
                self._observer.schedule(
                    handler,
                    str(path_obj.parent),
                    recursive=False,
                )
            elif path_obj.is_dir():
                self._observer.schedule(
                    handler,
                    str(path_obj),
                    recursive=True,
                )
            else:
                logger.warning(f"Path does not exist: {path}")

        self._observer.start()
        logger.info("Started watchdog file watcher")

    def _start_polling(self):
        """Start watching with polling."""
        self._poller = PollingWatcher(
            paths=self.config.paths,
            callback=self._on_file_change,
            interval=self.config.poll_interval,
            include_patterns=self.config.include_patterns,
            exclude_patterns=self.config.exclude_patterns,
        )
        self._poller.start()
        logger.info("Started polling file watcher")

    def stop(self):
        """Stop the file watcher."""
        self._running = False
        self._debounced.cancel()

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

        if self._poller:
            self._poller.stop()
            self._poller = None

    def wait(self):
        """Wait until interrupted."""
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    @property
    def is_using_watchdog(self) -> bool:
        """Whether the watcher is using watchdog."""
        return self._use_watchdog


def reload_module(module_name: str) -> Any:
    """Reload a module and return it."""
    if module_name in sys.modules:
        module = sys.modules[module_name]
        return importlib.reload(module)
    return importlib.import_module(module_name)


def get_module_file(module_name: str) -> str | None:
    """Get the file path for a module."""
    try:
        module = importlib.import_module(module_name)
        if hasattr(module, "__file__") and module.__file__:
            return module.__file__
    except ImportError:
        pass
    return None


__all__ = [
    "CodegenWatcher",
    "WatchConfig",
    "DebouncedCallback",
    "PollingWatcher",
    "HAS_WATCHDOG",
    "reload_module",
    "get_module_file",
]
