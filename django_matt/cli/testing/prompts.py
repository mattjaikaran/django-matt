"""
Prompt mocking utilities for CLI testing.

Provides tools to mock interactive prompts in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from unittest.mock import patch


@dataclass
class PromptResponse:
    """A recorded prompt and its response."""

    prompt_type: str
    message: str
    response: Any
    choices: list[str] | None = None
    default: Any = None


@dataclass
class MockPromptSession:
    """
    Mock prompt session for testing interactive commands.

    Usage:
        session = MockPromptSession()
        session.add_response("text", "Enter name:", "John")
        session.add_response("confirm", "Continue?", True)
        session.add_response("select", "Choose:", "option1")

        with session.patch():
            # Run interactive command
            result = runner.invoke("startapi", "myproject")

        # Verify prompts were shown
        session.assert_prompted("Enter name:")
    """

    responses: list[PromptResponse] = field(default_factory=list)
    _recorded_prompts: list[dict[str, Any]] = field(default_factory=list)
    _response_index: int = 0

    def add_response(
        self,
        prompt_type: str,
        message: str | None = None,
        response: Any = None,
    ) -> MockPromptSession:
        """
        Add a response for a prompt.

        Args:
            prompt_type: Type of prompt (text, confirm, select, multiselect, password)
            message: Optional message to match (partial match)
            response: Value to return for this prompt

        Returns:
            self for chaining
        """
        self.responses.append(
            PromptResponse(
                prompt_type=prompt_type,
                message=message or "",
                response=response,
            )
        )
        return self

    def text(self, message: str | None = None, response: str = "") -> MockPromptSession:
        """Add text prompt response."""
        return self.add_response("text", message, response)

    def password(self, message: str | None = None, response: str = "") -> MockPromptSession:
        """Add password prompt response."""
        return self.add_response("password", message, response)

    def confirm(self, message: str | None = None, response: bool = True) -> MockPromptSession:
        """Add confirm prompt response."""
        return self.add_response("confirm", message, response)

    def select(self, message: str | None = None, response: str = "") -> MockPromptSession:
        """Add select prompt response."""
        return self.add_response("select", message, response)

    def multiselect(
        self,
        message: str | None = None,
        response: list[str] | None = None,
    ) -> MockPromptSession:
        """Add multiselect prompt response."""
        return self.add_response("multiselect", message, response or [])

    def path(self, message: str | None = None, response: str = "") -> MockPromptSession:
        """Add path prompt response."""
        return self.add_response("path", message, response)

    def _get_next_response(self, prompt_type: str, message: str) -> Any:
        """Get next response for a prompt."""
        self._recorded_prompts.append(
            {
                "type": prompt_type,
                "message": message,
            }
        )

        # Find matching response
        for i, resp in enumerate(self.responses[self._response_index :], self._response_index):
            if resp.prompt_type == prompt_type:
                if not resp.message or resp.message in message:
                    self._response_index = i + 1
                    return resp.response

        # No matching response found
        raise ValueError(
            f"No mock response for {prompt_type} prompt: '{message}'\n"
            f"Available responses: {self.responses[self._response_index :]}"
        )

    def _mock_text(self, message: str, **kwargs) -> str:
        """Mock text prompt."""
        return self._get_next_response("text", message)

    def _mock_password(self, message: str, **kwargs) -> str:
        """Mock password prompt."""
        return self._get_next_response("password", message)

    def _mock_confirm(self, message: str, **kwargs) -> bool:
        """Mock confirm prompt."""
        return self._get_next_response("confirm", message)

    def _mock_select(self, message: str, choices: list, **kwargs) -> str:
        """Mock select prompt."""
        return self._get_next_response("select", message)

    def _mock_multiselect(self, message: str, choices: list, **kwargs) -> list:
        """Mock multiselect prompt."""
        return self._get_next_response("multiselect", message)

    def _mock_path(self, message: str, **kwargs) -> str:
        """Mock path prompt."""
        return self._get_next_response("path", message)

    def _mock_autocomplete(self, message: str, **kwargs) -> str:
        """Mock autocomplete prompt."""
        return self._get_next_response("text", message)

    def patch(self):
        """
        Return context manager that patches all prompt functions.

        Usage:
            with session.patch():
                # Run code with prompts
        """
        return _PromptPatcher(self)

    def reset(self) -> None:
        """Reset session state."""
        self._recorded_prompts = []
        self._response_index = 0

    @property
    def prompts_shown(self) -> list[dict[str, Any]]:
        """Get list of prompts that were shown."""
        return self._recorded_prompts

    def assert_prompted(self, message: str) -> MockPromptSession:
        """Assert a prompt with given message was shown."""
        for prompt in self._recorded_prompts:
            if message in prompt["message"]:
                return self
        raise AssertionError(
            f"Expected prompt containing '{message}'\n"
            f"Actual prompts: {[p['message'] for p in self._recorded_prompts]}"
        )

    def assert_not_prompted(self, message: str) -> MockPromptSession:
        """Assert a prompt with given message was NOT shown."""
        for prompt in self._recorded_prompts:
            if message in prompt["message"]:
                raise AssertionError(f"Expected NO prompt containing '{message}' but found one")
        return self

    def assert_prompt_count(self, count: int) -> MockPromptSession:
        """Assert number of prompts shown."""
        actual = len(self._recorded_prompts)
        if actual != count:
            raise AssertionError(
                f"Expected {count} prompts, got {actual}\n"
                f"Prompts: {[p['message'] for p in self._recorded_prompts]}"
            )
        return self


class _PromptPatcher:
    """Context manager for patching prompt functions."""

    def __init__(self, session: MockPromptSession):
        self.session = session
        self._patches = []

    def __enter__(self):
        """Start patching."""
        self._patches = [
            patch("django_matt.cli.prompts.text", self.session._mock_text),
            patch("django_matt.cli.prompts.password", self.session._mock_password),
            patch("django_matt.cli.prompts.confirm", self.session._mock_confirm),
            patch("django_matt.cli.prompts.select", self.session._mock_select),
            patch("django_matt.cli.prompts.multiselect", self.session._mock_multiselect),
            patch("django_matt.cli.prompts.path", self.session._mock_path),
            patch("django_matt.cli.prompts.autocomplete", self.session._mock_autocomplete),
        ]
        for p in self._patches:
            p.start()
        return self.session

    def __exit__(self, *args):
        """Stop patching."""
        for p in self._patches:
            p.stop()


def mock_prompts(**responses: Any):
    """
    Decorator to mock prompts in a test.

    Usage:
        @mock_prompts(
            text="John",
            confirm=True,
            select="option1",
        )
        def test_interactive_command():
            result = runner.invoke("mycommand")
            assert result.success
    """

    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            session = MockPromptSession()

            for prompt_type, response in responses.items():
                if isinstance(response, list):
                    for r in response:
                        session.add_response(prompt_type, None, r)
                else:
                    session.add_response(prompt_type, None, response)

            with session.patch():
                return func(*args, **kwargs)

        return wrapper

    return decorator
