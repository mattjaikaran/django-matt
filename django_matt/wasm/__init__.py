"""WASM middleware plugins — load .wasm files as Django middleware layers.

Write middleware in Rust, Go, C, or any language that compiles to WASM.
Modules are sandboxed, hot-reloadable, and run at near-native speed.

Requires ``wasmtime`` (optional dependency)::

    uv add wasmtime
"""

from django_matt.wasm.loader import WasmMiddleware, WasmMiddlewareLoader

__all__ = [
    "WasmMiddleware",
    "WasmMiddlewareLoader",
]
