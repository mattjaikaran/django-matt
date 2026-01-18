"""
CLI Testing Utilities.

Provides comprehensive testing tools for django-matt CLI commands.

Usage:
    from django_matt.cli.testing import (
        CLIRunner,
        MockPromptSession,
        FileTracker,
        ErrorCatcher,
    )

    def test_my_command():
        runner = CLIRunner()
        result = runner.invoke("mycommand", "--option", "value")
        result.assert_success()
        result.assert_output_contains("Expected output")

Fixtures (for pytest):
    - cli_runner: Basic CLI runner
    - isolated_runner: Runner with temp directory
    - mock_console: Mock console output
    - mock_prompts: Mock interactive prompts
    - file_tracker: Track file changes
    - error_catcher: Catch and inspect errors
"""

from .console import (
    CapturedOutput,
    ConsoleCapture,
    MockConsole,
    assert_output_contains,
    assert_output_matches,
    strip_ansi,
)
from .errors import (
    ErrorCapture,
    ErrorCatcher,
    MockErrorHandler,
    assert_raises_cli_error,
    create_cli_error,
)
from .files import (
    FileChange,
    FileSnapshot,
    FileTracker,
    create_test_directory,
    create_test_file,
    isolated_filesystem,
    temp_directory,
    working_directory,
)
from .prompts import (
    MockPromptSession,
    PromptResponse,
    mock_prompts,
)
from .runner import (
    CLIRunner,
    CommandResult,
    IsolatedCLIRunner,
    run_command,
    run_command_with_inputs,
)

__all__ = [
    # Runner
    "CLIRunner",
    "IsolatedCLIRunner",
    "CommandResult",
    "run_command",
    "run_command_with_inputs",
    # Console
    "MockConsole",
    "ConsoleCapture",
    "CapturedOutput",
    "assert_output_contains",
    "assert_output_matches",
    "strip_ansi",
    # Prompts
    "MockPromptSession",
    "PromptResponse",
    "mock_prompts",
    # Files
    "FileTracker",
    "FileSnapshot",
    "FileChange",
    "temp_directory",
    "working_directory",
    "isolated_filesystem",
    "create_test_file",
    "create_test_directory",
    # Errors
    "ErrorCatcher",
    "ErrorCapture",
    "MockErrorHandler",
    "assert_raises_cli_error",
    "create_cli_error",
]
