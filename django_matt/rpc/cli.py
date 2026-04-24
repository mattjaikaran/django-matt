"""CLI helper for generating RPC client code in Python or TypeScript."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_rpc_client(
    api: Any,
    lang: str = "python",
    output: str | None = None,
    class_name: str | None = None,
) -> str:
    """Generate an RPC client in the specified language and optionally write to a file."""
    from django_matt.rpc.generator import generate_python_client, generate_typescript_client

    if lang == "python":
        code = generate_python_client(api, class_name=class_name or "GeneratedClient")
    elif lang in ("typescript", "ts"):
        code = generate_typescript_client(api, class_name=class_name or "APIClient")
    else:
        raise ValueError(f"Unsupported language: {lang}. Use 'python' or 'typescript'.")

    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    return code
