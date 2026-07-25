"""Tests for django_matt.servers module."""

from __future__ import annotations

import multiprocessing
from unittest.mock import patch

import pytest

from django_matt.servers.base import ServerBackend
from django_matt.servers.config import DEFAULTS, ServerConfig, get_server_config
from django_matt.servers.granian_backend import GranianBackend
from django_matt.servers.registry import ServerRegistry, get_backend
from django_matt.servers.robyn_backend import RobynBackend
from django_matt.servers.uvicorn_backend import UvicornBackend

# ---------------------------------------------------------------------------
# Base ABC
# ---------------------------------------------------------------------------


class TestServerBackendABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ServerBackend()  # type: ignore[abstract]

    def test_auto_workers(self):
        cpus = multiprocessing.cpu_count()
        assert ServerBackend.auto_workers() == 2 * cpus + 1

    def test_resolve_workers_none(self):
        backend = UvicornBackend()
        result = backend.resolve_workers(None)
        assert result == ServerBackend.auto_workers()

    def test_resolve_workers_auto_string(self):
        backend = UvicornBackend()
        result = backend.resolve_workers("auto")
        assert result == ServerBackend.auto_workers()

    def test_resolve_workers_explicit(self):
        backend = UvicornBackend()
        assert backend.resolve_workers(4) == 4


# ---------------------------------------------------------------------------
# Uvicorn backend
# ---------------------------------------------------------------------------


class TestUvicornBackend:
    def test_name(self):
        b = UvicornBackend()
        assert b.name == "uvicorn"

    def test_supports_websockets(self):
        assert UvicornBackend.supports_websockets is True

    def test_supports_http2(self):
        assert UvicornBackend.supports_http2 is False

    def test_get_command_defaults(self):
        b = UvicornBackend()
        cmd = b.get_command(host="127.0.0.1", port=9000, workers=2)
        assert cmd[0] == "gunicorn"
        assert "--worker-class" in cmd
        assert "uvicorn.workers.UvicornWorker" in cmd
        assert "127.0.0.1:9000" in cmd
        assert "2" in cmd

    def test_get_command_ssl(self):
        b = UvicornBackend()
        cmd = b.get_command(
            workers=1,
            ssl_cert="/tmp/cert.pem",
            ssl_key="/tmp/key.pem",
        )
        assert "--certfile" in cmd
        assert "/tmp/cert.pem" in cmd
        assert "--keyfile" in cmd

    def test_get_command_no_access_log(self):
        b = UvicornBackend()
        cmd = b.get_command(workers=1, access_log=False)
        assert "--no-access-log" in cmd

    def test_get_command_custom_app_path(self):
        b = UvicornBackend()
        cmd = b.get_command(workers=1, app_path="myapp.asgi:app")
        assert "myapp.asgi:app" in cmd

    def test_get_config(self):
        b = UvicornBackend()
        cfg = b.get_config({"host": "0.0.0.0", "port": 8000, "workers": 4, "access_log": True})
        assert cfg["bind"] == "0.0.0.0:8000"
        assert cfg["workers"] == 4
        assert cfg["worker_class"] == "uvicorn.workers.UvicornWorker"
        assert cfg["accesslog"] == "-"

    def test_check_available(self):
        b = UvicornBackend()
        # uvicorn is installed in our test env
        result = b.check_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Robyn backend
# ---------------------------------------------------------------------------


class TestRobynBackend:
    def test_name(self):
        assert RobynBackend().name == "robyn"

    def test_get_command(self):
        b = RobynBackend()
        cmd = b.get_command(host="0.0.0.0", port=5000, workers=3)
        assert cmd[0] == "robyn"
        assert "--host" in cmd
        assert "0.0.0.0" in cmd
        assert "--port" in cmd
        assert "5000" in cmd
        assert "--processes" in cmd
        assert "3" in cmd

    def test_get_config(self):
        b = RobynBackend()
        cfg = b.get_config({"host": "localhost", "port": 3000, "workers": 2, "access_log": False})
        assert cfg["host"] == "localhost"
        assert cfg["port"] == 3000
        assert cfg["processes"] == 2
        assert cfg["log_level"] == "warning"

    def test_check_available_mocked(self):
        b = RobynBackend()
        with patch("importlib.util.find_spec", return_value=None):
            assert b.check_available() is False
        with patch("importlib.util.find_spec", return_value=True):
            assert b.check_available() is True


# ---------------------------------------------------------------------------
# Granian backend
# ---------------------------------------------------------------------------


class TestGranianBackend:
    def test_name(self):
        assert GranianBackend().name == "granian"

    def test_supports_http2(self):
        assert GranianBackend.supports_http2 is True

    def test_get_command_basic(self):
        b = GranianBackend()
        cmd = b.get_command(host="0.0.0.0", port=8080, workers=2)
        assert cmd[0] == "granian"
        assert "--interface" in cmd
        assert "asgi" in cmd
        assert "--host" in cmd
        assert "0.0.0.0" in cmd
        assert "--port" in cmd
        assert "8080" in cmd
        assert "--workers" in cmd
        assert "2" in cmd

    def test_get_command_http2(self):
        b = GranianBackend()
        cmd = b.get_command(workers=1, http2=True)
        assert "--http2" in cmd

    def test_get_command_no_http2_by_default(self):
        b = GranianBackend()
        cmd = b.get_command(workers=1)
        assert "--http2" not in cmd

    def test_get_command_ssl(self):
        b = GranianBackend()
        cmd = b.get_command(workers=1, ssl_cert="/c.pem", ssl_key="/k.pem")
        assert "--ssl-certificate" in cmd
        assert "--ssl-keyfile" in cmd

    def test_get_command_threading_mode(self):
        b = GranianBackend()
        cmd = b.get_command(workers=1, threading_mode="threads")
        assert "--threading-mode" in cmd
        assert "threads" in cmd

    def test_get_config(self):
        b = GranianBackend()
        cfg = b.get_config(
            {
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 4,
                "http2": True,
                "access_log": True,
            }
        )
        assert cfg["interface"] == "asgi"
        assert cfg["workers"] == 4
        assert cfg["http2"] is True
        assert cfg["log_level"] == "info"

    def test_check_available_mocked(self):
        b = GranianBackend()
        with patch("importlib.util.find_spec", return_value=None):
            assert b.check_available() is False
        with patch("importlib.util.find_spec", return_value=True):
            assert b.check_available() is True


# ---------------------------------------------------------------------------
# ServerConfig
# ---------------------------------------------------------------------------


class TestServerConfig:
    def test_defaults(self):
        cfg = ServerConfig()
        assert cfg.backend == "uvicorn"
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.workers == "auto"
        assert cfg.http2 is False

    def test_from_dict(self):
        cfg = ServerConfig.from_dict(
            {
                "backend": "granian",
                "port": 9000,
                "http2": True,
                "custom_option": "value",
            }
        )
        assert cfg.backend == "granian"
        assert cfg.port == 9000
        assert cfg.http2 is True
        assert cfg.extra == {"custom_option": "value"}

    def test_get_server_config_no_django(self):
        # When django settings aren't configured, falls back to defaults
        cfg = get_server_config()
        assert cfg.backend == DEFAULTS["backend"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestServerRegistry:
    def setup_method(self):
        # Clear registry between tests
        ServerRegistry._backends = {}

    def test_builtins_registered_on_access(self):
        backends = ServerRegistry.list_backends()
        names = [name for name, _ in backends]
        assert "uvicorn" in names
        assert "robyn" in names
        assert "granian" in names

    def test_get_known_backend(self):
        backend = ServerRegistry.get("uvicorn")
        assert backend.name == "uvicorn"

    def test_get_unknown_backend_raises(self):
        with pytest.raises(KeyError, match="Unknown server backend"):
            ServerRegistry.get("nonexistent")

    def test_register_custom_backend(self):
        class FakeBackend(ServerBackend):
            name = "fake"
            supports_http2 = False
            supports_websockets = False

            def get_command(self, host="0.0.0.0", port=8000, workers=None, **kw):
                return ["fake-server"]

            def get_config(self, settings):
                return {}

            def check_available(self):
                return True

        ServerRegistry.register(FakeBackend)
        b = ServerRegistry.get("fake")
        assert b.name == "fake"
        assert b.check_available() is True

    def test_get_best_available(self):
        backend = ServerRegistry.get_best_available()
        # Should return something — at minimum uvicorn
        assert hasattr(backend, "name")

    def test_get_backend_factory_none(self):
        backend = get_backend(None)
        assert hasattr(backend, "name")

    def test_get_backend_factory_named(self):
        backend = get_backend("uvicorn")
        assert backend.name == "uvicorn"


# ---------------------------------------------------------------------------
# matt_serve command argument parsing
# ---------------------------------------------------------------------------


class TestMattServeCommand:
    def test_command_imports(self):
        from django_matt.management.commands.matt_serve import Command

        cmd = Command()
        assert cmd.help is not None

    def test_command_has_arguments(self):
        from django_matt.management.commands.matt_serve import Command

        cmd = Command()
        parser = cmd.create_parser("manage.py", "matt_serve")
        # Should parse without error
        args = parser.parse_args(["--backend", "granian", "--workers", "4", "--port", "9000"])
        assert args.backend == "granian"
        assert args.workers == "4"
        assert args.port == 9000

    def test_command_list_flag(self):
        from django_matt.management.commands.matt_serve import Command

        cmd = Command()
        parser = cmd.create_parser("manage.py", "matt_serve")
        args = parser.parse_args(["--list"])
        assert args.list is True

    def test_command_http2_flag(self):
        from django_matt.management.commands.matt_serve import Command

        cmd = Command()
        parser = cmd.create_parser("manage.py", "matt_serve")
        args = parser.parse_args(["--http2"])
        assert args.http2 is True
