"""
Tests for the Django Matt CLI module.

Covers: base commands, prompts/validators, error types, error handler,
suggestion engine, and console output.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from django_matt.cli.console import Console
from django_matt.cli.errors.handler import CLIErrorHandler
from django_matt.cli.errors.suggestions import DOCS_URLS, SuggestionEngine
from django_matt.cli.errors.types import CLIError, CLIErrorCode
from django_matt.cli.prompts import (
    validate_is_directory,
    validate_is_file,
    validate_model_path,
    validate_not_empty,
    validate_path_exists,
    validate_path_not_exists,
    validate_python_identifier,
)

# ---------------------------------------------------------------------------
# CLIError and CLIErrorCode
# ---------------------------------------------------------------------------


class TestCLIErrorCode:
    """Tests for CLIErrorCode enum."""

    def test_file_error_codes_exist(self):
        assert CLIErrorCode.FILE_NOT_FOUND.value == "file_not_found"
        assert CLIErrorCode.FILE_EXISTS.value == "file_exists"
        assert CLIErrorCode.FILE_PERMISSION.value == "file_permission"

    def test_model_error_codes_exist(self):
        assert CLIErrorCode.MODEL_NOT_FOUND.value == "model_not_found"
        assert CLIErrorCode.APP_NOT_FOUND.value == "app_not_found"

    def test_config_error_codes_exist(self):
        assert CLIErrorCode.CONFIG_NOT_FOUND.value == "config_not_found"
        assert CLIErrorCode.CONFIG_INVALID.value == "config_invalid"

    def test_general_error_codes_exist(self):
        assert CLIErrorCode.UNKNOWN_ERROR.value == "unknown_error"
        assert CLIErrorCode.VALIDATION_ERROR.value == "validation_error"
        assert CLIErrorCode.INVALID_ARGUMENT.value == "invalid_argument"
        assert CLIErrorCode.MISSING_ARGUMENT.value == "missing_argument"


class TestCLIError:
    """Tests for CLIError exception class."""

    def test_basic_creation(self):
        err = CLIError(message="boom")
        assert err.message == "boom"
        assert err.code == CLIErrorCode.UNKNOWN_ERROR
        assert err.context == {}
        assert err.suggestion is None
        assert err.doc_url is None
        assert str(err) == "boom"

    def test_creation_with_all_fields(self):
        err = CLIError(
            message="not found",
            code=CLIErrorCode.FILE_NOT_FOUND,
            context={"path": "/tmp/x"},
            suggestion="check path",
            doc_url="https://example.com",
        )
        assert err.code == CLIErrorCode.FILE_NOT_FOUND
        assert err.context == {"path": "/tmp/x"}
        assert err.suggestion == "check path"
        assert err.doc_url == "https://example.com"

    def test_with_suggestion_chaining(self):
        err = CLIError(message="err").with_suggestion("try this")
        assert err.suggestion == "try this"
        # returns self for chaining
        assert isinstance(err, CLIError)

    def test_with_context_chaining(self):
        err = CLIError(message="err").with_context(key="val", other=42)
        assert err.context == {"key": "val", "other": 42}

    def test_with_doc_url_chaining(self):
        err = CLIError(message="err").with_doc_url("https://docs.example.com")
        assert err.doc_url == "https://docs.example.com"

    def test_full_chaining(self):
        err = (
            CLIError(message="chain", code=CLIErrorCode.MODEL_NOT_FOUND)
            .with_suggestion("do X")
            .with_context(model="auth.User")
            .with_doc_url("https://docs.dev")
        )
        assert err.message == "chain"
        assert err.suggestion == "do X"
        assert err.context == {"model": "auth.User"}
        assert err.doc_url == "https://docs.dev"

    def test_is_exception(self):
        err = CLIError(message="exception test")
        assert isinstance(err, Exception)
        with pytest.raises(CLIError):
            raise err


# ---------------------------------------------------------------------------
# Validators (prompts.py)
# ---------------------------------------------------------------------------


class TestValidateNotEmpty:
    def test_empty_string(self):
        assert validate_not_empty("") == "This field is required"

    def test_whitespace_only(self):
        assert validate_not_empty("   ") == "This field is required"

    def test_valid_string(self):
        assert validate_not_empty("hello") is True

    def test_none_value(self):
        # None is falsy
        assert validate_not_empty(None) == "This field is required"


class TestValidatePythonIdentifier:
    def test_valid_identifier(self):
        assert validate_python_identifier("my_var") is True

    def test_valid_class_name(self):
        assert validate_python_identifier("MyClass") is True

    def test_starts_with_number(self):
        result = validate_python_identifier("1bad")
        assert isinstance(result, str)
        assert "valid Python identifier" in result

    def test_has_spaces(self):
        result = validate_python_identifier("has space")
        assert isinstance(result, str)

    def test_has_hyphens(self):
        result = validate_python_identifier("my-var")
        assert isinstance(result, str)

    def test_underscore_only(self):
        assert validate_python_identifier("_") is True

    def test_empty_string(self):
        result = validate_python_identifier("")
        assert isinstance(result, str)


class TestValidateModelPath:
    def test_valid_model_path(self):
        assert validate_model_path("auth.User") is True

    def test_valid_model_path_underscore(self):
        assert validate_model_path("my_app.MyModel") is True

    def test_no_dot(self):
        result = validate_model_path("User")
        assert "app_name.ModelName" in result

    def test_too_many_parts(self):
        result = validate_model_path("a.b.c")
        assert "app_name.ModelName" in result

    def test_empty_app_name(self):
        result = validate_model_path(".Model")
        assert "Both app name and model name are required" in result

    def test_empty_model_name(self):
        result = validate_model_path("app.")
        assert "Both app name and model name are required" in result

    def test_just_a_dot(self):
        result = validate_model_path(".")
        assert isinstance(result, str)
        assert result is not True


class TestValidatePathExists:
    def test_existing_path(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("data")
        assert validate_path_exists(str(f)) is True

    def test_nonexistent_path(self):
        result = validate_path_exists("/nonexistent/path/xyz")
        assert "does not exist" in result


class TestValidatePathNotExists:
    def test_existing_path(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("data")
        result = validate_path_not_exists(str(f))
        assert "already exists" in result

    def test_nonexistent_path(self):
        assert validate_path_not_exists("/nonexistent/path/xyz") is True


class TestValidateIsDirectory:
    def test_valid_directory(self, tmp_path):
        assert validate_is_directory(str(tmp_path)) is True

    def test_file_not_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        result = validate_is_directory(str(f))
        assert "Not a directory" in result

    def test_nonexistent(self):
        result = validate_is_directory("/nonexistent/path")
        assert "does not exist" in result


class TestValidateIsFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        assert validate_is_file(str(f)) is True

    def test_directory_not_file(self, tmp_path):
        result = validate_is_file(str(tmp_path))
        assert "Not a file" in result

    def test_nonexistent(self):
        result = validate_is_file("/nonexistent/path")
        assert "does not exist" in result


# ---------------------------------------------------------------------------
# SuggestionEngine
# ---------------------------------------------------------------------------


class TestSuggestionEngine:
    def setup_method(self):
        self.engine = SuggestionEngine()

    def test_static_suggestion_file_not_found(self):
        suggestion = self.engine.get_suggestion(CLIErrorCode.FILE_NOT_FOUND)
        assert "file path is correct" in suggestion

    def test_static_suggestion_file_exists(self):
        suggestion = self.engine.get_suggestion(CLIErrorCode.FILE_EXISTS)
        assert "--force" in suggestion

    def test_static_suggestion_unknown_error(self):
        suggestion = self.engine.get_suggestion(CLIErrorCode.UNKNOWN_ERROR)
        assert "--debug" in suggestion

    def test_dynamic_suggestion_model_with_similar(self):
        context = {
            "attempted_model": "auth.Usar",
            "available_models": ["auth.User", "auth.Group"],
        }
        suggestion = self.engine.get_suggestion(CLIErrorCode.MODEL_NOT_FOUND, context)
        assert "auth.User" in suggestion
        assert "Did you mean" in suggestion

    def test_dynamic_suggestion_model_no_similar(self):
        context = {
            "attempted_model": "zzz.Qqq",
            "available_models": ["auth.User"],
        }
        # No close match, falls back to static
        suggestion = self.engine.get_suggestion(CLIErrorCode.MODEL_NOT_FOUND, context)
        assert isinstance(suggestion, str)

    def test_dynamic_suggestion_app_with_similar(self):
        context = {
            "attempted_app": "aut",
            "available_apps": ["auth", "admin"],
        }
        suggestion = self.engine.get_suggestion(CLIErrorCode.APP_NOT_FOUND, context)
        assert "auth" in suggestion

    def test_dynamic_suggestion_missing_dependency(self):
        context = {"package": "celery"}
        suggestion = self.engine.get_suggestion(CLIErrorCode.MISSING_DEPENDENCY, context)
        assert "celery" in suggestion
        assert "uv add" in suggestion

    def test_dynamic_suggestion_command_not_found(self):
        context = {
            "attempted_command": "modles",
            "available_commands": ["models", "routes", "info"],
        }
        suggestion = self.engine.get_suggestion(CLIErrorCode.COMMAND_NOT_FOUND, context)
        assert "models" in suggestion

    def test_get_doc_url_known_code(self):
        url = self.engine.get_doc_url(CLIErrorCode.MODEL_NOT_FOUND)
        assert url is not None
        assert "models" in url

    def test_get_doc_url_unknown_code(self):
        url = self.engine.get_doc_url(CLIErrorCode.UNKNOWN_ERROR)
        assert url is None

    def test_doc_urls_match_suggestions_module(self):
        for code in DOCS_URLS:
            assert self.engine.get_doc_url(code) == DOCS_URLS[code]

    def test_similarity_identical(self):
        assert self.engine._similarity("abc", "abc") == 1.0

    def test_similarity_empty(self):
        assert self.engine._similarity("", "abc") == 0.0
        assert self.engine._similarity("abc", "") == 0.0

    def test_find_similar_no_match(self):
        result = self.engine._find_similar("zzzzz", ["abc", "def"])
        assert result is None

    def test_find_similar_empty_candidates(self):
        result = self.engine._find_similar("abc", [])
        assert result is None


# ---------------------------------------------------------------------------
# CLIErrorHandler
# ---------------------------------------------------------------------------


class TestCLIErrorHandler:
    def setup_method(self):
        self.mock_console = MagicMock()
        self.handler = CLIErrorHandler(console=self.mock_console, debug=False)

    def test_handle_cli_error_with_exit(self):
        err = CLIError(message="test", code=CLIErrorCode.FILE_NOT_FOUND)
        with pytest.raises(SystemExit) as exc_info:
            self.handler.handle(err, exit_code=1)
        assert exc_info.value.code == 1

    def test_handle_cli_error_no_exit(self):
        err = CLIError(message="test", code=CLIErrorCode.FILE_NOT_FOUND)
        # Should not raise
        self.handler.handle(err, exit_code=None)

    def test_handle_generic_exception_maps_to_cli_error(self):
        exc = FileNotFoundError("missing.txt")
        with pytest.raises(SystemExit):
            self.handler.handle(exc, exit_code=1)

    def test_map_exception_file_not_found(self):
        exc = FileNotFoundError("missing.txt")
        exc.filename = "missing.txt"
        mapped = self.handler._map_exception(exc)
        assert mapped.code == CLIErrorCode.FILE_NOT_FOUND
        assert mapped.context["filename"] == "missing.txt"

    def test_map_exception_permission_error(self):
        exc = PermissionError("denied")
        mapped = self.handler._map_exception(exc)
        assert mapped.code == CLIErrorCode.FILE_PERMISSION

    def test_map_exception_import_error(self):
        exc = ImportError("no module")
        exc.name = "some_module"
        mapped = self.handler._map_exception(exc)
        assert mapped.code == CLIErrorCode.IMPORT_ERROR
        assert mapped.context["module"] == "some_module"

    def test_map_exception_module_not_found(self):
        # ModuleNotFoundError is a subclass of ImportError.
        # The handler checks ImportError first, so it maps to IMPORT_ERROR.
        exc = ModuleNotFoundError("No module named 'celery'")
        exc.name = "celery"
        mapped = self.handler._map_exception(exc)
        assert mapped.code == CLIErrorCode.IMPORT_ERROR
        assert mapped.context["module"] == "celery"

    def test_map_exception_value_error(self):
        mapped = self.handler._map_exception(ValueError("bad value"))
        assert mapped.code == CLIErrorCode.VALIDATION_ERROR

    def test_map_exception_key_error(self):
        mapped = self.handler._map_exception(KeyError("missing_key"))
        assert mapped.code == CLIErrorCode.CONFIG_INVALID
        assert "missing_key" in mapped.message

    def test_map_exception_unknown(self):
        mapped = self.handler._map_exception(RuntimeError("unexpected"))
        assert mapped.code == CLIErrorCode.UNKNOWN_ERROR

    def test_file_not_found_helper(self):
        with pytest.raises(SystemExit):
            self.handler.file_not_found("/tmp/missing.txt")

    def test_file_exists_helper(self):
        with pytest.raises(SystemExit):
            self.handler.file_exists("/tmp/existing.txt")

    def test_model_not_found_helper(self):
        with pytest.raises(SystemExit):
            self.handler.model_not_found("auth.Bogus")

    def test_app_not_found_helper(self):
        with pytest.raises(SystemExit):
            self.handler.app_not_found("bogus_app")

    def test_invalid_argument_helper(self):
        with pytest.raises(SystemExit):
            self.handler.invalid_argument("--format", "not valid", ["json", "xml"])

    def test_missing_argument_helper(self):
        with pytest.raises(SystemExit):
            self.handler.missing_argument("--name")

    def test_config_error_helper(self):
        with pytest.raises(SystemExit):
            self.handler.config_error("bad config", config_file="matt.toml")

    def test_quick_error_no_exit(self):
        # quick_error should not raise SystemExit
        self.handler.quick_error("quick msg", suggestion="try again")

    def test_wrap_decorator_catches_cli_error(self):
        def failing():
            raise CLIError(message="wrapped", code=CLIErrorCode.UNKNOWN_ERROR)

        wrapped = self.handler.wrap(failing, exit_on_error=False)
        # Should not raise
        wrapped()

    def test_wrap_decorator_catches_generic_error(self):
        def failing():
            raise ValueError("bad")

        wrapped = self.handler.wrap(failing, exit_on_error=False)
        wrapped()

    def test_wrap_decorator_with_exit(self):
        def failing():
            raise CLIError(message="fatal", code=CLIErrorCode.UNKNOWN_ERROR)

        wrapped = self.handler.wrap(failing, exit_on_error=True)
        with pytest.raises(SystemExit):
            wrapped()

    def test_catch_context_manager_suppresses(self):
        with self.handler.catch(exit_on_error=False):
            raise ValueError("caught")
        # If we reach here, exception was suppressed

    def test_catch_context_manager_with_exit(self):
        with pytest.raises(SystemExit):
            with self.handler.catch(exit_on_error=True):
                raise ValueError("fatal in context")

    def test_catch_context_manager_no_error(self):
        with self.handler.catch(exit_on_error=False):
            pass  # No error, should work fine

    def test_debug_mode_from_env(self):
        with patch.dict("os.environ", {"DJANGO_MATT_DEBUG": "true"}):
            handler = CLIErrorHandler(console=self.mock_console)
            assert handler.debug is True

    def test_debug_mode_default_off(self):
        with patch.dict("os.environ", {"DJANGO_MATT_DEBUG": ""}, clear=False):
            handler = CLIErrorHandler(console=self.mock_console)
            assert handler.debug is False


# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------


class TestConsole:
    def setup_method(self):
        self.console = Console()
        self.console._console = MagicMock()

    def test_quiet_property_default(self):
        assert self.console.quiet is False

    def test_quiet_setter(self):
        self.console.quiet = True
        assert self.console.quiet is True

    def test_print_normal(self):
        self.console.print("hello")
        self.console._console.print.assert_called_once()

    def test_print_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.print("hello")
        self.console._console.print.assert_not_called()

    def test_success_output(self):
        self.console.success("done")
        self.console._console.print.assert_called_once()
        call_arg = self.console._console.print.call_args[0][0]
        assert "done" in call_arg

    def test_success_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.success("done")
        self.console._console.print.assert_not_called()

    def test_error_always_prints(self):
        """error() should print even in quiet mode (no quiet guard)."""
        self.console.quiet = True
        self.console.error("bad")
        self.console._console.print.assert_called_once()

    def test_warning_output(self):
        self.console.warning("careful")
        self.console._console.print.assert_called_once()

    def test_warning_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.warning("careful")
        self.console._console.print.assert_not_called()

    def test_info_output(self):
        self.console.info("fyi")
        self.console._console.print.assert_called_once()

    def test_debug_output(self):
        self.console.debug("trace")
        self.console._console.print.assert_called_once()

    def test_header_output(self):
        self.console.header("Title", "subtitle")
        # header prints: newline, title, subtitle, newline = multiple calls
        assert self.console._console.print.call_count >= 3

    def test_section_output(self):
        self.console.section("Section")
        # section prints: newline, title, divider
        assert self.console._console.print.call_count == 3

    def test_table_with_dict_data(self):
        data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        self.console.table(data)
        self.console._console.print.assert_called_once()

    def test_table_with_list_data(self):
        data = [["Alice", "30"], ["Bob", "25"]]
        self.console.table(data, columns=["Name", "Age"])
        self.console._console.print.assert_called_once()

    def test_table_empty_data(self):
        self.console.table([])
        self.console._console.print.assert_not_called()

    def test_table_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.table([{"a": "b"}])
        self.console._console.print.assert_not_called()

    def test_tree_output(self):
        self.console.tree({"src": {"models.py": None}}, title="Project")
        self.console._console.print.assert_called_once()

    def test_tree_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.tree({"src": None})
        self.console._console.print.assert_not_called()

    def test_code_output(self):
        self.console.code("x = 1", language="python")
        self.console._console.print.assert_called_once()

    def test_code_with_title(self):
        self.console.code("x = 1", title="Example")
        assert self.console._console.print.call_count == 2

    def test_panel_output(self):
        self.console.panel("content", title="Title")
        self.console._console.print.assert_called_once()

    def test_panel_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.panel("content")
        self.console._console.print.assert_not_called()

    def test_file_created(self):
        self.console.file_created("/tmp/new.py")
        call_arg = self.console._console.print.call_args[0][0]
        assert "Created" in call_arg

    def test_file_modified(self):
        self.console.file_modified("/tmp/mod.py")
        call_arg = self.console._console.print.call_args[0][0]
        assert "Modified" in call_arg

    def test_file_deleted(self):
        self.console.file_deleted("/tmp/del.py")
        call_arg = self.console._console.print.call_args[0][0]
        assert "Deleted" in call_arg

    def test_file_skipped(self):
        self.console.file_skipped("/tmp/skip.py", "already exists")
        call_arg = self.console._console.print.call_args[0][0]
        assert "Skipped" in call_arg
        assert "already exists" in call_arg

    def test_files_summary_no_changes(self):
        self.console.files_summary(created=[], modified=[], deleted=[])
        # Should print "No files changed" via muted
        self.console._console.print.assert_called()

    def test_files_summary_with_changes(self):
        self.console.files_summary(
            created=["a.py"],
            modified=["b.py"],
        )
        # Multiple prints: newline, section header, divider, created, modified, newline, total
        assert self.console._console.print.call_count >= 5

    def test_next_steps_output(self):
        self.console.next_steps(["step 1", "step 2"])
        assert self.console._console.print.call_count >= 3

    def test_next_steps_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.next_steps(["step 1"])
        self.console._console.print.assert_not_called()

    def test_banner_output(self):
        self.console.banner()
        self.console._console.print.assert_called_once()

    def test_banner_suppressed_in_quiet(self):
        self.console.quiet = True
        self.console.banner()
        self.console._console.print.assert_not_called()


# ---------------------------------------------------------------------------
# MattCommand (base.py)
# ---------------------------------------------------------------------------


class TestMattCommand:
    def setup_method(self):
        from django_matt.cli.base import MattCommand

        self.cmd = MattCommand()
        self.cmd.console = MagicMock()
        self.cmd.error_handler = MagicMock()

    def test_has_console(self):
        assert self.cmd.console is not None

    def test_has_error_handler(self):
        assert self.cmd.error_handler is not None

    def test_success_delegates(self):
        self.cmd.success("ok")
        self.cmd.console.success.assert_called_once_with("ok")

    def test_error_delegates(self):
        self.cmd.error("bad")
        self.cmd.console.error.assert_called_once_with("bad")

    def test_error_raises_command_error(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            self.cmd.error("bad", raise_error=True)

    def test_warning_delegates(self):
        self.cmd.warning("careful")
        self.cmd.console.warning.assert_called_once_with("careful")

    def test_info_delegates(self):
        self.cmd.info("note")
        self.cmd.console.info.assert_called_once_with("note")

    def test_debug_delegates(self):
        self.cmd.debug("trace")
        self.cmd.console.debug.assert_called_once_with("trace")

    def test_header_delegates(self):
        self.cmd.header("Title", "sub")
        self.cmd.console.header.assert_called_once_with("Title", "sub")

    def test_section_delegates(self):
        self.cmd.section("Section")
        self.cmd.console.section.assert_called_once_with("Section")

    def test_handle_error_delegates(self):
        err = CLIError(message="x")
        self.cmd.handle_error(err, exit_code=2)
        self.cmd.error_handler.handle.assert_called_once_with(err, exit_code=2)

    def test_fail_creates_error_and_handles(self):
        self.cmd.fail("failed", CLIErrorCode.FILE_NOT_FOUND, suggestion="try again")
        self.cmd.error_handler.handle.assert_called_once()
        call_args = self.cmd.error_handler.handle.call_args
        err = call_args[0][0]
        assert isinstance(err, CLIError)
        assert err.message == "failed"
        assert err.code == CLIErrorCode.FILE_NOT_FOUND
        assert err.suggestion == "try again"

    def test_fail_model_not_found(self):
        self.cmd.fail_model_not_found("auth.Bogus", ["auth.User"])
        self.cmd.error_handler.model_not_found.assert_called_once_with(
            "auth.Bogus", ["auth.User"]
        )

    def test_fail_file_not_found(self):
        self.cmd.fail_file_not_found("/tmp/missing")
        self.cmd.error_handler.file_not_found.assert_called_once_with("/tmp/missing")

    def test_fail_file_exists(self):
        self.cmd.fail_file_exists("/tmp/exists")
        self.cmd.error_handler.file_exists.assert_called_once_with("/tmp/exists")

    def test_fail_invalid_argument(self):
        self.cmd.fail_invalid_argument("--fmt", "bad format", ["json", "xml"])
        self.cmd.error_handler.invalid_argument.assert_called_once_with(
            "--fmt", "bad format", ["json", "xml"]
        )

    def test_table_delegates(self):
        data = [{"a": 1}]
        self.cmd.table(data, columns=["a"])
        self.cmd.console.table.assert_called_once_with(data, ["a"])

    def test_tree_delegates(self):
        data = {"src": None}
        self.cmd.tree(data, title="root")
        self.cmd.console.tree.assert_called_once_with(data, "root")

    def test_code_delegates(self):
        self.cmd.code("x = 1", language="python")
        self.cmd.console.code.assert_called_once_with("x = 1", "python")

    def test_panel_delegates(self):
        self.cmd.panel("content", title="T")
        self.cmd.console.panel.assert_called_once_with("content", title="T")

    def test_next_steps_delegates(self):
        self.cmd.next_steps(["a", "b"])
        self.cmd.console.next_steps.assert_called_once_with(["a", "b"])

    def test_add_arguments(self):
        """MattCommand adds --quiet and --debug."""
        import argparse

        parser = argparse.ArgumentParser()
        self.cmd.add_arguments(parser)
        args = parser.parse_args(["--quiet", "--debug"])
        assert args.quiet is True
        assert args.debug is True


# ---------------------------------------------------------------------------
# InteractiveCommand (base.py)
# ---------------------------------------------------------------------------


class TestInteractiveCommand:
    def setup_method(self):
        from django_matt.cli.base import InteractiveCommand

        self.cmd = InteractiveCommand()
        self.cmd.console = MagicMock()
        self.cmd.error_handler = MagicMock()

    def test_add_arguments_has_yes_and_wizard(self):
        import argparse

        parser = argparse.ArgumentParser()
        self.cmd.add_arguments(parser)
        args = parser.parse_args(["--yes", "--wizard"])
        assert args.yes is True
        assert args.wizard is True

    @patch("django_matt.cli.base.text", return_value="hello")
    def test_prompt_text(self, mock_text):
        result = self.cmd.prompt_text("Name?")
        assert result == "hello"
        mock_text.assert_called_once()

    @patch("django_matt.cli.base.text", return_value="hello")
    def test_prompt_text_required_uses_validator(self, mock_text):
        self.cmd.prompt_text("Name?", required=True)
        # When required=True and no validate, validate_not_empty is passed
        call_kwargs = mock_text.call_args[1]
        assert call_kwargs["validate"] is not None

    @patch("django_matt.cli.base.select", return_value="opt1")
    def test_prompt_select(self, mock_select):
        result = self.cmd.prompt_select("Pick:", choices=["opt1", "opt2"])
        assert result == "opt1"

    @patch("django_matt.cli.base.multiselect", return_value=["a", "b"])
    def test_prompt_multiselect(self, mock_multi):
        result = self.cmd.prompt_multiselect("Pick many:", choices=["a", "b", "c"])
        assert result == ["a", "b"]

    @patch("django_matt.cli.base.confirm", return_value=True)
    def test_prompt_confirm(self, mock_confirm):
        result = self.cmd.prompt_confirm("Sure?")
        assert result is True

    @patch("django_matt.cli.base.path", return_value="/tmp")
    def test_prompt_path(self, mock_path):
        result = self.cmd.prompt_path("Dir?", only_directories=True)
        assert result == "/tmp"

    @patch("django_matt.cli.base.text", return_value="auth.User")
    def test_prompt_model(self, mock_text):
        result = self.cmd.prompt_model()
        assert result == "auth.User"
        call_kwargs = mock_text.call_args[1]
        assert call_kwargs["validate"] is not None

    @patch("django_matt.cli.base.text", return_value="my_var")
    def test_prompt_identifier(self, mock_text):
        result = self.cmd.prompt_identifier("Var name?")
        assert result == "my_var"

    @patch("django_matt.cli.base.autocomplete", return_value="models")
    def test_prompt_autocomplete(self, mock_auto):
        result = self.cmd.prompt_autocomplete("Cmd?", choices=["models", "routes"])
        assert result == "models"


# ---------------------------------------------------------------------------
# GeneratorCommand (base.py)
# ---------------------------------------------------------------------------


class TestGeneratorCommand:
    def setup_method(self):
        from django_matt.cli.base import GeneratorCommand

        self.cmd = GeneratorCommand()
        self.cmd.console = MagicMock()
        self.cmd.error_handler = MagicMock()

    def test_initial_state(self):
        assert self.cmd.files_created == []
        assert self.cmd.files_modified == []
        assert self.cmd.total_changes == 0

    def test_add_arguments_has_dry_run_and_force(self):
        import argparse

        parser = argparse.ArgumentParser()
        self.cmd.add_arguments(parser)
        args = parser.parse_args(["--dry-run", "--force"])
        assert args.dry_run is True
        assert args.force is True

    def test_write_file_creates_new_file(self, tmp_path):
        target = tmp_path / "new_file.py"
        self.cmd._dry_run = False
        self.cmd._force = False
        result = self.cmd.write_file(target, "# new file")
        assert result is True
        assert target.read_text() == "# new file"
        assert len(self.cmd.files_created) == 1
        assert self.cmd.total_changes == 1

    def test_write_file_skips_existing_without_force(self, tmp_path):
        target = tmp_path / "existing.py"
        target.write_text("# original")
        self.cmd._dry_run = True
        self.cmd._force = False
        result = self.cmd.write_file(target, "# overwrite")
        # File exists, not force, dry_run -> skipped
        assert result is False

    def test_write_file_force_overwrites(self, tmp_path):
        target = tmp_path / "existing.py"
        target.write_text("# original")
        self.cmd._dry_run = False
        self.cmd._force = True
        result = self.cmd.write_file(target, "# overwritten")
        assert result is True
        assert target.read_text() == "# overwritten"
        assert len(self.cmd.files_modified) == 1

    def test_write_file_dry_run_new_file(self, tmp_path):
        target = tmp_path / "dry_new.py"
        self.cmd._dry_run = True
        self.cmd._force = False
        result = self.cmd.write_file(target, "# content", preview=True)
        assert result is True
        assert not target.exists()  # Not actually written
        assert len(self.cmd.files_created) == 1

    def test_write_file_dry_run_no_preview(self, tmp_path):
        target = tmp_path / "dry_no_preview.py"
        self.cmd._dry_run = True
        result = self.cmd.write_file(target, "# content", preview=False)
        assert result is True
        assert not target.exists()

    def test_write_file_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "file.py"
        self.cmd._dry_run = False
        self.cmd._force = False
        result = self.cmd.write_file(target, "# nested")
        assert result is True
        assert target.exists()

    def test_append_to_file_existing(self, tmp_path):
        target = tmp_path / "append.py"
        target.write_text("# line 1")
        self.cmd._dry_run = False
        result = self.cmd.append_to_file(target, "# line 2")
        assert result is True
        content = target.read_text()
        assert "# line 1" in content
        assert "# line 2" in content
        assert len(self.cmd.files_modified) == 1

    def test_append_to_file_nonexistent_creates(self, tmp_path):
        target = tmp_path / "new_append.py"
        self.cmd._dry_run = False
        result = self.cmd.append_to_file(target, "# new content")
        assert result is True
        assert target.exists()
        assert len(self.cmd.files_created) == 1

    def test_append_to_file_dry_run(self, tmp_path):
        target = tmp_path / "dry_append.py"
        target.write_text("# original")
        self.cmd._dry_run = True
        result = self.cmd.append_to_file(target, "# appended")
        assert result is True
        # Content should not actually change
        assert target.read_text() == "# original"
        assert len(self.cmd.files_modified) == 1

    def test_delete_file_existing(self, tmp_path):
        target = tmp_path / "to_delete.py"
        target.write_text("bye")
        self.cmd._dry_run = False
        result = self.cmd.delete_file(target)
        assert result is True
        assert not target.exists()

    def test_delete_file_nonexistent(self, tmp_path):
        target = tmp_path / "nonexistent.py"
        result = self.cmd.delete_file(target)
        assert result is False

    def test_delete_file_dry_run(self, tmp_path):
        target = tmp_path / "keep.py"
        target.write_text("keep me")
        self.cmd._dry_run = True
        result = self.cmd.delete_file(target)
        assert result is True
        assert target.exists()  # Not actually deleted

    def test_ensure_directory_creates(self, tmp_path):
        target = tmp_path / "new_dir" / "sub"
        self.cmd._dry_run = False
        result = self.cmd.ensure_directory(target)
        assert result == target
        assert target.is_dir()

    def test_ensure_directory_dry_run(self, tmp_path):
        target = tmp_path / "dry_dir"
        self.cmd._dry_run = True
        result = self.cmd.ensure_directory(target)
        assert result == target
        assert not target.exists()

    def test_show_summary(self):
        self.cmd._files_created = [Path("/a.py")]
        self.cmd._files_modified = [Path("/b.py")]
        self.cmd._files_skipped = []
        self.cmd.show_summary()
        self.cmd.console.files_summary.assert_called_once()

    def test_show_summary_with_skipped(self):
        self.cmd._files_skipped = [(Path("/c.py"), "already exists")]
        self.cmd.show_summary()
        self.cmd.console.section.assert_called()

    def test_show_summary_dry_run_warning(self):
        self.cmd._dry_run = True
        self.cmd.show_summary()
        self.cmd.console.box_warning.assert_called_once()

    def test_reset_tracking(self):
        self.cmd._files_created = [Path("/a.py")]
        self.cmd._files_modified = [Path("/b.py")]
        self.cmd._files_skipped = [(Path("/c.py"), "skip")]
        self.cmd.reset_tracking()
        assert self.cmd.files_created == []
        assert self.cmd.files_modified == []
        assert self.cmd.total_changes == 0

    def test_total_changes(self, tmp_path):
        self.cmd._dry_run = False
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f2.write_text("existing")
        self.cmd._force = True
        self.cmd.write_file(f1, "new")
        self.cmd.write_file(f2, "modified")
        assert self.cmd.total_changes == 2


# ---------------------------------------------------------------------------
# Prompt functions (with questionary mocked)
# ---------------------------------------------------------------------------


class TestPromptFunctions:
    """Test the prompt wrapper functions by mocking questionary."""

    questionary = pytest.importorskip("questionary")

    @patch("django_matt.cli.prompts.questionary")
    def test_text_prompt(self, mock_q):
        from django_matt.cli.prompts import text

        mock_q.text.return_value.ask.return_value = "answer"
        result = text("Question?")
        assert result == "answer"
        mock_q.text.assert_called_once()

    @patch("django_matt.cli.prompts.questionary")
    def test_password_prompt(self, mock_q):
        from django_matt.cli.prompts import password

        mock_q.password.return_value.ask.return_value = "secret"
        result = password("Password?")
        assert result == "secret"

    @patch("django_matt.cli.prompts.questionary")
    def test_select_prompt(self, mock_q):
        from django_matt.cli.prompts import select

        mock_q.select.return_value.ask.return_value = "B"
        result = select("Pick:", choices=["A", "B", "C"])
        assert result == "B"

    @patch("django_matt.cli.prompts.questionary")
    def test_confirm_prompt(self, mock_q):
        from django_matt.cli.prompts import confirm

        mock_q.confirm.return_value.ask.return_value = False
        result = confirm("Sure?", default=True)
        assert result is False
