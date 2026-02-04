"""
Pytest fixtures for CLI testing.

Provides reusable fixtures for testing CLI commands.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest

from .console import ConsoleCapture, MockConsole
from .errors import ErrorCatcher, MockErrorHandler
from .files import FileTracker
from .prompts import MockPromptSession
from .runner import CLIRunner, CommandResult, IsolatedCLIRunner

if TYPE_CHECKING:
    pass


# ============================================================================
# Runner Fixtures
# ============================================================================


@pytest.fixture
def cli_runner() -> CLIRunner:
    """
    Fixture providing a CLI runner.

    Usage:
        def test_command(cli_runner):
            result = cli_runner.invoke("matt", "info")
            result.assert_success()
    """
    return CLIRunner()


@pytest.fixture
def isolated_runner(tmp_path: Path) -> IsolatedCLIRunner:
    """
    Fixture providing an isolated CLI runner with temp directory.

    Usage:
        def test_file_generation(isolated_runner):
            result = isolated_runner.invoke_isolated("generate_crud", "myapp.Model")
            result.assert_success()
    """
    return IsolatedCLIRunner(temp_dir=str(tmp_path))


# ============================================================================
# Console Fixtures
# ============================================================================


@pytest.fixture
def mock_console() -> Generator[MockConsole, None, None]:
    """
    Fixture providing a mock console.

    Usage:
        def test_output(mock_console):
            with mock_console:
                # run code
                pass
            mock_console.output.assert_contains("Success")
    """
    console = MockConsole()
    yield console


@pytest.fixture
def console_capture() -> Generator[ConsoleCapture, None, None]:
    """
    Fixture providing console capture.

    Usage:
        def test_output(console_capture):
            with console_capture:
                print("Hello")
            assert "Hello" in console_capture.output
    """
    capture = ConsoleCapture()
    yield capture


# ============================================================================
# Prompt Fixtures
# ============================================================================


@pytest.fixture
def mock_prompts() -> MockPromptSession:
    """
    Fixture providing mock prompt session.

    Usage:
        def test_interactive(mock_prompts):
            mock_prompts.text("name", "John").confirm("continue", True)
            with mock_prompts.patch():
                result = runner.invoke("interactive_command")
    """
    return MockPromptSession()


@pytest.fixture
def prompt_session() -> Generator[MockPromptSession, None, None]:
    """
    Fixture providing mock prompt session with auto-patch.

    Usage:
        def test_interactive(prompt_session):
            prompt_session.text("name", "John")
            # prompts are auto-patched for the test
    """
    session = MockPromptSession()
    with session.patch():
        yield session


# ============================================================================
# File Fixtures
# ============================================================================


@pytest.fixture
def file_tracker(tmp_path: Path) -> FileTracker:
    """
    Fixture providing file change tracker.

    Usage:
        def test_generation(file_tracker, tmp_path):
            file_tracker.watch(tmp_path)
            # run generation command
            file_tracker.assert_created("output.py")
    """
    return FileTracker()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Fixture providing a temporary directory.

    Usage:
        def test_files(temp_dir):
            (temp_dir / "test.txt").write_text("hello")
    """
    tmpdir = Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def working_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """
    Fixture that changes to a temp directory.

    Usage:
        def test_in_temp(working_dir):
            # Current directory is working_dir
            Path("test.txt").write_text("hello")
    """
    original = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(original)


# ============================================================================
# Error Fixtures
# ============================================================================


@pytest.fixture
def error_catcher() -> ErrorCatcher:
    """
    Fixture providing error catcher.

    Usage:
        def test_error(error_catcher):
            with error_catcher:
                raise CLIError("test")
            error_catcher.captured.assert_cli_error()
    """
    return ErrorCatcher()


@pytest.fixture
def mock_error_handler() -> MockErrorHandler:
    """
    Fixture providing mock error handler.

    Usage:
        def test_errors(mock_error_handler):
            with mock_error_handler.patch():
                # run code that may error
                pass
            mock_error_handler.assert_no_errors()
    """
    return MockErrorHandler()


# ============================================================================
# Combined Fixtures
# ============================================================================


@pytest.fixture
def cli_test_env(
    cli_runner: CLIRunner,
    mock_prompts: MockPromptSession,
    file_tracker: FileTracker,
    tmp_path: Path,
) -> dict:
    """
    Fixture providing complete CLI test environment.

    Usage:
        def test_full(cli_test_env):
            runner = cli_test_env["runner"]
            prompts = cli_test_env["prompts"]
            tracker = cli_test_env["tracker"]
            tmp_path = cli_test_env["tmp_path"]
    """
    return {
        "runner": cli_runner,
        "prompts": mock_prompts,
        "tracker": file_tracker,
        "tmp_path": tmp_path,
    }


# ============================================================================
# Django Fixtures
# ============================================================================


@pytest.fixture
def django_settings():
    """
    Fixture for overriding Django settings.

    Usage:
        def test_with_settings(django_settings):
            with django_settings(DEBUG=True):
                # test with DEBUG=True
    """
    from django.test import override_settings

    def override(**kwargs):
        return override_settings(**kwargs)

    return override


# ============================================================================
# Helper Functions (can be imported directly)
# ============================================================================


def run_command(command: str, *args, **kwargs) -> CommandResult:
    """
    Quick helper to run a command.

    Usage:
        from django_matt.cli.testing.fixtures import run_command

        result = run_command("matt", "info")
        result.assert_success()
    """
    return CLIRunner().invoke(command, *args, **kwargs)


def assert_command_success(command: str, *args, **kwargs) -> CommandResult:
    """
    Run command and assert it succeeds.

    Usage:
        assert_command_success("matt", "info")
    """
    result = run_command(command, *args, **kwargs)
    result.assert_success()
    return result


def assert_command_fails(command: str, *args, **kwargs) -> CommandResult:
    """
    Run command and assert it fails.

    Usage:
        assert_command_fails("matt", "nonexistent")
    """
    result = run_command(command, *args, **kwargs)
    result.assert_failed()
    return result
