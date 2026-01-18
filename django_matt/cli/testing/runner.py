"""
CLI command runner for testing.

Provides utilities to run management commands and capture output.
"""

from __future__ import annotations

import io
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError


@dataclass
class CommandResult:
    """Result of running a CLI command."""

    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    exception: Exception | None = None

    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0 and self.exception is None

    @property
    def failed(self) -> bool:
        """Check if command failed."""
        return not self.success

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        return self.stdout + self.stderr

    def __contains__(self, text: str) -> bool:
        """Check if text is in output."""
        return text in self.output

    def assert_success(self) -> CommandResult:
        """Assert command succeeded, raise if not."""
        if self.failed:
            raise AssertionError(
                f"Command failed with exit code {self.exit_code}\n"
                f"stdout: {self.stdout}\n"
                f"stderr: {self.stderr}\n"
                f"exception: {self.exception}"
            )
        return self

    def assert_failed(self) -> CommandResult:
        """Assert command failed, raise if not."""
        if self.success:
            raise AssertionError(
                f"Expected command to fail but it succeeded\n"
                f"stdout: {self.stdout}"
            )
        return self

    def assert_exit_code(self, code: int) -> CommandResult:
        """Assert specific exit code."""
        if self.exit_code != code:
            raise AssertionError(
                f"Expected exit code {code}, got {self.exit_code}\n"
                f"stdout: {self.stdout}\n"
                f"stderr: {self.stderr}"
            )
        return self

    def assert_output_contains(self, text: str) -> CommandResult:
        """Assert output contains text."""
        if text not in self.output:
            raise AssertionError(
                f"Expected output to contain '{text}'\n"
                f"Actual output: {self.output}"
            )
        return self

    def assert_output_not_contains(self, text: str) -> CommandResult:
        """Assert output does not contain text."""
        if text in self.output:
            raise AssertionError(
                f"Expected output to NOT contain '{text}'\n"
                f"Actual output: {self.output}"
            )
        return self

    def assert_stdout_contains(self, text: str) -> CommandResult:
        """Assert stdout contains text."""
        if text not in self.stdout:
            raise AssertionError(
                f"Expected stdout to contain '{text}'\n"
                f"Actual stdout: {self.stdout}"
            )
        return self

    def assert_stderr_contains(self, text: str) -> CommandResult:
        """Assert stderr contains text."""
        if text not in self.stderr:
            raise AssertionError(
                f"Expected stderr to contain '{text}'\n"
                f"Actual stderr: {self.stderr}"
            )
        return self


@dataclass
class CLIRunner:
    """
    CLI command runner for testing.

    Usage:
        runner = CLIRunner()
        result = runner.invoke("matt", "info")
        result.assert_success()
        assert "django-matt" in result.stdout
    """

    env: dict[str, str] = field(default_factory=dict)
    mix_stderr: bool = True

    def invoke(
        self,
        command: str,
        *args: str,
        stdin: str | None = None,
        **options: Any,
    ) -> CommandResult:
        """
        Run a management command and capture output.

        Args:
            command: Command name (e.g., "matt", "generate_crud")
            *args: Positional arguments
            stdin: Optional stdin input
            **options: Keyword options (converted to --option=value)

        Returns:
            CommandResult with captured output
        """
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        result = CommandResult()

        # Prepare stdin mock
        stdin_mock = io.StringIO(stdin) if stdin else io.StringIO()

        try:
            with patch.dict("os.environ", self.env):
                with patch("sys.stdin", stdin_mock):
                    call_command(
                        command,
                        *args,
                        stdout=stdout_buffer,
                        stderr=stderr_buffer if not self.mix_stderr else stdout_buffer,
                        **options,
                    )
        except SystemExit as e:
            result.exit_code = e.code if isinstance(e.code, int) else 1
        except CommandError as e:
            result.exit_code = 1
            result.exception = e
            stderr_buffer.write(str(e))
        except Exception as e:
            result.exit_code = 1
            result.exception = e

        result.stdout = stdout_buffer.getvalue()
        result.stderr = stderr_buffer.getvalue() if not self.mix_stderr else ""

        return result

    def invoke_with_inputs(
        self,
        command: str,
        *args: str,
        inputs: list[str] | None = None,
        **options: Any,
    ) -> CommandResult:
        """
        Run command with simulated user inputs.

        Args:
            command: Command name
            *args: Positional arguments
            inputs: List of inputs to provide (one per prompt)
            **options: Keyword options

        Returns:
            CommandResult with captured output
        """
        stdin_text = "\n".join(inputs or []) + "\n"
        return self.invoke(command, *args, stdin=stdin_text, **options)


class IsolatedCLIRunner(CLIRunner):
    """
    CLI runner with isolated filesystem.

    Creates a temporary directory for file operations.
    """

    def __init__(self, temp_dir: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.temp_dir = temp_dir
        self._original_cwd: str | None = None

    @contextmanager
    def isolated_filesystem(self):
        """Context manager for isolated filesystem."""
        import os
        import tempfile

        self._original_cwd = os.getcwd()

        if self.temp_dir:
            work_dir = self.temp_dir
        else:
            work_dir = tempfile.mkdtemp()

        try:
            os.chdir(work_dir)
            yield work_dir
        finally:
            os.chdir(self._original_cwd)

    def invoke_isolated(
        self,
        command: str,
        *args: str,
        **options: Any,
    ) -> CommandResult:
        """Run command in isolated filesystem."""
        with self.isolated_filesystem():
            return self.invoke(command, *args, **options)


def run_command(
    command: str,
    *args: str,
    **options: Any,
) -> CommandResult:
    """
    Convenience function to run a command.

    Usage:
        result = run_command("matt", "info")
        result.assert_success()
    """
    runner = CLIRunner()
    return runner.invoke(command, *args, **options)


def run_command_with_inputs(
    command: str,
    *args: str,
    inputs: list[str] | None = None,
    **options: Any,
) -> CommandResult:
    """
    Convenience function to run command with inputs.

    Usage:
        result = run_command_with_inputs(
            "startapi", "myproject",
            inputs=["y", "postgres", "jwt"]
        )
    """
    runner = CLIRunner()
    return runner.invoke_with_inputs(command, *args, inputs=inputs, **options)
