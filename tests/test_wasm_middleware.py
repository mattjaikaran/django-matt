"""Tests for WASM middleware loader.

Since wasmtime is an optional dependency and we can't easily compile .wasm
files in tests, these tests focus on the loader API, error handling, and
the WasmMiddleware interface using mocks where needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from django_matt.wasm.loader import (
    ACTION_CONTINUE,
    ACTION_SHORT_CIRCUIT,
    WasmMiddleware,
    WasmMiddlewareLoader,
    WasmNotAvailableError,
)


class TestWasmNotAvailable:
    def test_import_error_message(self):
        err = WasmNotAvailableError()
        assert "wasmtime" in str(err)
        assert "uv add" in str(err)

    def test_loader_requires_wasmtime(self):
        with patch.dict("sys.modules", {"wasmtime": None}):
            with pytest.raises((WasmNotAvailableError, ImportError)):
                WasmMiddlewareLoader()


class TestWasmMiddlewareInterface:
    def _make_middleware(self, has_request=True, has_response=True):
        """Create a WasmMiddleware with mocked internals."""
        mw = WasmMiddleware.__new__(WasmMiddleware)
        mw.name = "test_module"
        mw._module = MagicMock()
        mw._instance = MagicMock()
        mw._store = MagicMock()
        mw._path = Path("test.wasm")
        mw._lock = __import__("threading").Lock()
        mw._memory = None
        mw._alloc = None
        mw._dealloc = None
        mw._on_request = MagicMock() if has_request else None
        mw._on_response = MagicMock() if has_response else None
        return mw

    def test_has_on_request(self):
        mw = self._make_middleware(has_request=True)
        assert mw.has_on_request is True

        mw2 = self._make_middleware(has_request=False)
        assert mw2.has_on_request is False

    def test_has_on_response(self):
        mw = self._make_middleware(has_response=True)
        assert mw.has_on_response is True

        mw2 = self._make_middleware(has_response=False)
        assert mw2.has_on_response is False

    def test_process_request_passthrough_when_no_handler(self):
        mw = self._make_middleware(has_request=False)
        action, headers, body = mw.process_request(b"Host: x\n", b"body")
        assert action == ACTION_CONTINUE
        assert headers == b"Host: x\n"
        assert body == b"body"

    def test_process_response_passthrough_when_no_handler(self):
        mw = self._make_middleware(has_response=False)
        headers, body = mw.process_response(b"Content-Type: json\n", b"response")
        assert headers == b"Content-Type: json\n"
        assert body == b"response"

    def test_process_request_requires_memory(self):
        mw = self._make_middleware(has_request=True)
        with pytest.raises(RuntimeError, match="memory"):
            mw.process_request(b"headers", b"body")


class TestWasmMiddlewareLoaderAPI:
    @pytest.fixture
    def mock_wasmtime(self):
        """Create a mock wasmtime module."""
        wasmtime = MagicMock()
        wasmtime.Engine.return_value = MagicMock()
        return wasmtime

    def test_loader_init(self, mock_wasmtime):
        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            assert loader.loaded_modules == []

    def test_load_sets_name_from_stem(self, mock_wasmtime, tmp_path):
        wasm_file = tmp_path / "my_middleware.wasm"
        wasm_file.write_bytes(b"\x00asm\x01\x00\x00\x00")  # minimal WASM header

        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            # Mock the instantiation chain
            mock_instance = MagicMock()
            mock_exports = MagicMock()
            mock_exports.on_request = None
            mock_exports.on_response = None
            mock_exports.alloc = None
            mock_exports.dealloc = None
            mock_exports.memory = None
            mock_instance.exports.return_value = mock_exports
            mock_wasmtime.Linker.return_value.instantiate.return_value = mock_instance

            mw = loader.load(wasm_file)
            assert mw.name == "my_middleware"
            assert "my_middleware" in loader.loaded_modules

    def test_load_custom_name(self, mock_wasmtime, tmp_path):
        wasm_file = tmp_path / "module.wasm"
        wasm_file.write_bytes(b"\x00asm\x01\x00\x00\x00")

        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            mock_instance = MagicMock()
            mock_exports = MagicMock(spec=[])
            mock_instance.exports.return_value = mock_exports
            mock_wasmtime.Linker.return_value.instantiate.return_value = mock_instance

            mw = loader.load(wasm_file, name="custom_name")
            assert mw.name == "custom_name"

    def test_get_module(self, mock_wasmtime, tmp_path):
        wasm_file = tmp_path / "test.wasm"
        wasm_file.write_bytes(b"\x00asm\x01\x00\x00\x00")

        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            mock_instance = MagicMock()
            mock_exports = MagicMock(spec=[])
            mock_instance.exports.return_value = mock_exports
            mock_wasmtime.Linker.return_value.instantiate.return_value = mock_instance

            loader.load(wasm_file)
            assert loader.get("test") is not None
            assert loader.get("nonexistent") is None

    def test_reload_unknown_raises(self, mock_wasmtime):
        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            with pytest.raises(KeyError, match="No WASM middleware"):
                loader.reload("nonexistent")

    def test_as_django_middleware_unknown_raises(self, mock_wasmtime):
        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            with pytest.raises(KeyError, match="No WASM middleware"):
                loader.as_django_middleware("nonexistent")

    def test_as_django_middleware_returns_class(self, mock_wasmtime, tmp_path):
        wasm_file = tmp_path / "test_mw.wasm"
        wasm_file.write_bytes(b"\x00asm\x01\x00\x00\x00")

        with patch("django_matt.wasm.loader._require_wasmtime", return_value=mock_wasmtime):
            loader = WasmMiddlewareLoader()
            mock_instance = MagicMock()
            mock_exports = MagicMock(spec=[])
            mock_instance.exports.return_value = mock_exports
            mock_wasmtime.Linker.return_value.instantiate.return_value = mock_instance

            loader.load(wasm_file, name="test_mw")
            mw_class = loader.as_django_middleware("test_mw")
            assert callable(mw_class)
            assert "test_mw" in mw_class.__name__
