"""WASM middleware loader — compile and instantiate WASM modules.

ABI contract — WASM modules must export these functions:

    on_request(headers_ptr, headers_len, body_ptr, body_len)
        -> (action, headers_ptr, headers_len, body_ptr, body_len)
        action: 0 = continue, 1 = short-circuit (return immediately)

    on_response(headers_ptr, headers_len, body_ptr, body_len)
        -> (headers_ptr, headers_len, body_ptr, body_len)

    alloc(size) -> ptr       # allocate memory in WASM linear memory
    dealloc(ptr, size)       # free memory in WASM linear memory

Headers are encoded as ``key: value\\n`` pairs (HTTP/1.1 style).
Body is raw bytes.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("django_matt.wasm")

# Actions returned by on_request
ACTION_CONTINUE = 0
ACTION_SHORT_CIRCUIT = 1


class WasmNotAvailableError(ImportError):
    """Raised when wasmtime is not installed."""

    def __init__(self):
        super().__init__(
            "wasmtime is required for WASM middleware. Install with: uv add wasmtime"
        )


def _require_wasmtime():
    """Import wasmtime or raise a clear error."""
    try:
        import wasmtime
        return wasmtime
    except ImportError:
        raise WasmNotAvailableError()


class WasmMiddleware:
    """A loaded and instantiated WASM middleware module."""

    def __init__(
        self,
        name: str,
        module: Any,
        instance: Any,
        store: Any,
        path: Path,
    ) -> None:
        self.name = name
        self._module = module
        self._instance = instance
        self._store = store
        self._path = path
        self._lock = threading.Lock()

        # Cache exported functions
        exports = self._instance.exports(self._store)
        self._on_request = getattr(exports, "on_request", None)
        self._on_response = getattr(exports, "on_response", None)
        self._alloc = getattr(exports, "alloc", None)
        self._dealloc = getattr(exports, "dealloc", None)
        self._memory = getattr(exports, "memory", None)

    @property
    def has_on_request(self) -> bool:
        return self._on_request is not None

    @property
    def has_on_response(self) -> bool:
        return self._on_response is not None

    def process_request(
        self, headers: bytes, body: bytes
    ) -> tuple[int, bytes, bytes]:
        """Call the WASM module's on_request function.

        Returns (action, modified_headers, modified_body).
        action: 0 = continue, 1 = short-circuit.
        """
        if self._on_request is None:
            return (ACTION_CONTINUE, headers, body)

        with self._lock:
            return self._call_transform(
                self._on_request, headers, body, has_action=True
            )

    def process_response(
        self, headers: bytes, body: bytes
    ) -> tuple[bytes, bytes]:
        """Call the WASM module's on_response function.

        Returns (modified_headers, modified_body).
        """
        if self._on_response is None:
            return (headers, body)

        with self._lock:
            result = self._call_transform(
                self._on_response, headers, body, has_action=False
            )
            return result  # type: ignore[return-value]

    def _call_transform(
        self, func: Any, headers: bytes, body: bytes, has_action: bool
    ) -> tuple:
        """Write data into WASM memory, call function, read results back."""
        store = self._store
        memory = self._memory
        alloc = self._alloc

        if memory is None or alloc is None:
            raise RuntimeError(
                f"WASM module '{self.name}' does not export 'memory' or 'alloc'"
            )

        # Allocate and write headers
        h_ptr = alloc(store, len(headers))
        mem_data = memory.data_ptr(store)
        mem_len = memory.data_len(store)

        import ctypes
        ctypes.memmove(mem_data + h_ptr, headers, len(headers))

        # Allocate and write body
        b_ptr = alloc(store, len(body))
        mem_data = memory.data_ptr(store)  # refresh after alloc
        ctypes.memmove(mem_data + b_ptr, body, len(body))

        # Call the WASM function
        result = func(store, h_ptr, len(headers), b_ptr, len(body))

        # Read results back
        mem_data = memory.data_ptr(store)

        if has_action:
            action, rh_ptr, rh_len, rb_ptr, rb_len = result
            out_headers = bytes(
                (ctypes.c_ubyte * rh_len).from_address(mem_data + rh_ptr)
            )
            out_body = bytes(
                (ctypes.c_ubyte * rb_len).from_address(mem_data + rb_ptr)
            )

            # Free WASM memory
            if self._dealloc:
                self._dealloc(store, rh_ptr, rh_len)
                self._dealloc(store, rb_ptr, rb_len)

            return (action, out_headers, out_body)
        else:
            rh_ptr, rh_len, rb_ptr, rb_len = result
            out_headers = bytes(
                (ctypes.c_ubyte * rh_len).from_address(mem_data + rh_ptr)
            )
            out_body = bytes(
                (ctypes.c_ubyte * rb_len).from_address(mem_data + rb_ptr)
            )

            if self._dealloc:
                self._dealloc(store, rh_ptr, rh_len)
                self._dealloc(store, rb_ptr, rb_len)

            return (out_headers, out_body)


class WasmMiddlewareLoader:
    """Load and manage WASM middleware modules.

    Usage::

        loader = WasmMiddlewareLoader()
        loader.load(Path("middleware_wasm/rate_limiter.wasm"))
        loader.load(Path("middleware_wasm/auth_validator.wasm"))

        # Get Django middleware class
        MiddlewareClass = loader.as_django_middleware("rate_limiter")

        # Hot-reload a module
        loader.reload("rate_limiter")
    """

    def __init__(self, wasm_dir: Path | None = None) -> None:
        self._wasmtime = _require_wasmtime()
        self._engine = self._wasmtime.Engine()
        self._modules: dict[str, WasmMiddleware] = {}
        self._wasm_dir = wasm_dir

    def load(self, path: Path, name: str | None = None) -> WasmMiddleware:
        """Compile and instantiate a WASM middleware module."""
        if name is None:
            name = path.stem

        wasm_bytes = path.read_bytes()
        module = self._wasmtime.Module(self._engine, wasm_bytes)
        linker = self._wasmtime.Linker(self._engine)
        store = self._wasmtime.Store(self._engine)

        # Link WASI if the module imports it
        try:
            wasi_config = self._wasmtime.WasiConfig()
            store.set_wasi(wasi_config)
            linker.define_wasi()
        except Exception:
            pass

        instance = linker.instantiate(store, module)

        middleware = WasmMiddleware(
            name=name,
            module=module,
            instance=instance,
            store=store,
            path=path,
        )

        self._modules[name] = middleware
        logger.info("Loaded WASM middleware: %s from %s", name, path)
        return middleware

    def reload(self, name: str) -> WasmMiddleware:
        """Hot-reload a WASM module without server restart."""
        if name not in self._modules:
            raise KeyError(f"No WASM middleware named '{name}'")

        old = self._modules[name]
        return self.load(old._path, name=name)

    def get(self, name: str) -> WasmMiddleware | None:
        """Get a loaded WASM middleware by name."""
        return self._modules.get(name)

    @property
    def loaded_modules(self) -> list[str]:
        """Return names of all loaded WASM modules."""
        return list(self._modules.keys())

    def as_django_middleware(self, name: str) -> type:
        """Create a Django middleware class that delegates to a WASM module.

        Usage::

            MIDDLEWARE = [
                loader.as_django_middleware("rate_limiter"),
            ]
        """
        wasm = self._modules.get(name)
        if wasm is None:
            raise KeyError(f"No WASM middleware named '{name}'")

        class WasmDjangoMiddleware:
            """Django middleware backed by WASM module: {name}."""

            def __init__(mw_self, get_response):
                mw_self.get_response = get_response
                mw_self._wasm = wasm

            async def __call__(mw_self, request):
                # Encode request headers
                header_lines = []
                for key, value in request.META.items():
                    if key.startswith("HTTP_"):
                        header_name = key[5:].replace("_", "-").title()
                        header_lines.append(f"{header_name}: {value}")
                headers_bytes = "\n".join(header_lines).encode("utf-8")
                body_bytes = request.body if hasattr(request, "body") else b""

                # Process request through WASM
                if mw_self._wasm.has_on_request:
                    action, new_headers, new_body = mw_self._wasm.process_request(
                        headers_bytes, body_bytes
                    )
                    if action == ACTION_SHORT_CIRCUIT:
                        from django.http import HttpResponse
                        return HttpResponse(new_body, status=403)

                # Call next middleware/view
                response = await mw_self.get_response(request)

                # Process response through WASM
                if mw_self._wasm.has_on_response:
                    resp_headers = "\n".join(
                        f"{k}: {v}" for k, v in response.items()
                    ).encode("utf-8")
                    resp_body = response.content if hasattr(response, "content") else b""

                    _, new_body = mw_self._wasm.process_response(
                        resp_headers, resp_body
                    )
                    response.content = new_body

                return response

            def __repr__(mw_self):
                return f"WasmDjangoMiddleware({name!r})"

        WasmDjangoMiddleware.__name__ = f"WasmMiddleware_{name}"
        WasmDjangoMiddleware.__qualname__ = f"WasmMiddleware_{name}"
        return WasmDjangoMiddleware
