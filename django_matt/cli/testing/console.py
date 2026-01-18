"""
Console output testing utilities.

Provides assertions for CLI console output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

from rich.console import Console as RichConsole


@dataclass
class CapturedOutput:
    """Captured console output with assertion methods."""

    raw: str = ""
    calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Get plain text without ANSI codes."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", self.raw)

    @property
    def lines(self) -> list[str]:
        """Get output as lines."""
        return self.text.strip().split("\n")

    def __contains__(self, text: str) -> bool:
        """Check if text is in output."""
        return text in self.text

    def contains(self, text: str) -> bool:
        """Check if output contains text."""
        return text in self.text

    def contains_any(self, *texts: str) -> bool:
        """Check if output contains any of the texts."""
        return any(t in self.text for t in texts)

    def contains_all(self, *texts: str) -> bool:
        """Check if output contains all of the texts."""
        return all(t in self.text for t in texts)

    def matches(self, pattern: str) -> bool:
        """Check if output matches regex pattern."""
        return bool(re.search(pattern, self.text))

    # Assertion methods

    def assert_contains(self, text: str, msg: str | None = None) -> CapturedOutput:
        """Assert output contains text."""
        if text not in self.text:
            raise AssertionError(
                msg or f"Expected output to contain '{text}'\nActual: {self.text}"
            )
        return self

    def assert_not_contains(self, text: str, msg: str | None = None) -> CapturedOutput:
        """Assert output does not contain text."""
        if text in self.text:
            raise AssertionError(
                msg or f"Expected output to NOT contain '{text}'\nActual: {self.text}"
            )
        return self

    def assert_matches(self, pattern: str, msg: str | None = None) -> CapturedOutput:
        """Assert output matches regex pattern."""
        if not re.search(pattern, self.text):
            raise AssertionError(
                msg or f"Expected output to match '{pattern}'\nActual: {self.text}"
            )
        return self

    def assert_line_count(self, count: int, msg: str | None = None) -> CapturedOutput:
        """Assert number of lines in output."""
        actual = len(self.lines)
        if actual != count:
            raise AssertionError(
                msg or f"Expected {count} lines, got {actual}\nActual: {self.text}"
            )
        return self

    def assert_empty(self, msg: str | None = None) -> CapturedOutput:
        """Assert output is empty."""
        if self.text.strip():
            raise AssertionError(
                msg or f"Expected empty output\nActual: {self.text}"
            )
        return self

    def assert_not_empty(self, msg: str | None = None) -> CapturedOutput:
        """Assert output is not empty."""
        if not self.text.strip():
            raise AssertionError(msg or "Expected non-empty output")
        return self

    # Message type assertions

    def assert_success_message(self, text: str | None = None) -> CapturedOutput:
        """Assert a success message was printed."""
        if text:
            return self.assert_contains(text)
        # Check for common success indicators
        if not self.contains_any("✓", "Success", "success", "Done", "done", "✔"):
            raise AssertionError(
                f"Expected success message in output\nActual: {self.text}"
            )
        return self

    def assert_error_message(self, text: str | None = None) -> CapturedOutput:
        """Assert an error message was printed."""
        if text:
            return self.assert_contains(text)
        if not self.contains_any("✗", "Error", "error", "Failed", "failed", "✘"):
            raise AssertionError(
                f"Expected error message in output\nActual: {self.text}"
            )
        return self

    def assert_warning_message(self, text: str | None = None) -> CapturedOutput:
        """Assert a warning message was printed."""
        if text:
            return self.assert_contains(text)
        if not self.contains_any("⚠", "Warning", "warning", "Warn"):
            raise AssertionError(
                f"Expected warning message in output\nActual: {self.text}"
            )
        return self

    def assert_info_message(self, text: str | None = None) -> CapturedOutput:
        """Assert an info message was printed."""
        if text:
            return self.assert_contains(text)
        if not self.contains_any("ℹ", "Info", "info", "Note"):
            raise AssertionError(
                f"Expected info message in output\nActual: {self.text}"
            )
        return self


class MockConsole:
    """
    Mock console for capturing output in tests.

    Usage:
        with MockConsole() as console:
            # Run code that uses console
            my_command.handle()

        console.output.assert_contains("Success")
    """

    def __init__(self):
        self._buffer = StringIO()
        self._rich_console = RichConsole(file=self._buffer, force_terminal=True)
        self._calls: list[dict[str, Any]] = []
        self._patches: list[Any] = []

    @property
    def output(self) -> CapturedOutput:
        """Get captured output."""
        return CapturedOutput(
            raw=self._buffer.getvalue(),
            calls=self._calls,
        )

    def __enter__(self) -> MockConsole:
        """Enter context and start capturing."""
        # Patch the Console class in the cli.console module
        self._patches = [
            patch("django_matt.cli.console.Console._console", self._rich_console),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *args) -> None:
        """Exit context and stop capturing."""
        for p in self._patches:
            p.stop()

    def reset(self) -> None:
        """Reset captured output."""
        self._buffer = StringIO()
        self._rich_console = RichConsole(file=self._buffer, force_terminal=True)
        self._calls = []


class ConsoleCapture:
    """
    Context manager for capturing console output.

    Usage:
        with ConsoleCapture() as capture:
            console.success("Done!")

        assert "Done" in capture.output
    """

    def __init__(self):
        self._buffer = StringIO()
        self._original_stdout = None
        self._original_stderr = None

    @property
    def output(self) -> CapturedOutput:
        """Get captured output."""
        return CapturedOutput(raw=self._buffer.getvalue())

    def __enter__(self) -> ConsoleCapture:
        """Start capturing."""
        import sys
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = self._buffer
        sys.stderr = self._buffer
        return self

    def __exit__(self, *args) -> None:
        """Stop capturing."""
        import sys
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr


def assert_output_contains(output: str, text: str, msg: str | None = None) -> None:
    """Assert that output contains text."""
    if text not in output:
        raise AssertionError(
            msg or f"Expected output to contain '{text}'\nActual: {output}"
        )


def assert_output_matches(output: str, pattern: str, msg: str | None = None) -> None:
    """Assert that output matches regex pattern."""
    if not re.search(pattern, output):
        raise AssertionError(
            msg or f"Expected output to match '{pattern}'\nActual: {output}"
        )


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)
