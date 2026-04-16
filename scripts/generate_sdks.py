#!/usr/bin/env python
"""Generate TypeScript / Python / Swift SDK packages from an OpenAPI schema.

Meant to be wired into a release pipeline — users point it at an OpenAPI spec
(either a local JSON file or an HTTP URL) and receive three publish-ready
packages under ``dist/sdks/{typescript,python,swift}/``.

Usage:
    uv run python scripts/generate_sdks.py \
        --schema https://api.example.com/openapi.json \
        --package my-api \
        --version 1.2.3 \
        --base-url https://api.example.com \
        --output dist/sdks

    # From a local file (CI-friendly — no live server needed)
    uv run python scripts/generate_sdks.py \
        --schema openapi.json --package my-api --version 1.2.3 \
        --output dist/sdks --targets typescript,python
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen

from django_matt.sdkgen import (
    PythonSDKGenerator,
    SDKConfig,
    SwiftSDKGenerator,
    TypeScriptSDKGenerator,
)

_GENERATORS = {
    "typescript": TypeScriptSDKGenerator,
    "python": PythonSDKGenerator,
    "swift": SwiftSDKGenerator,
}


def _load_schema(schema: str) -> dict:
    if schema.startswith(("http://", "https://")):
        with urlopen(schema) as response:
            return json.loads(response.read().decode())
    path = Path(schema)
    if not path.exists():
        raise SystemExit(f"Schema not found: {path}")
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema",
        required=True,
        help="Path to a local openapi.json OR an http(s) URL to fetch",
    )
    parser.add_argument("--package", required=True, help="SDK package name (kebab-case)")
    parser.add_argument("--version", required=True, help="SDK version (e.g. 1.2.3)")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Default API base URL baked into the SDKs",
    )
    parser.add_argument("--author", default="", help="Author name for package metadata")
    parser.add_argument("--description", default="", help="Package description")
    parser.add_argument(
        "--license",
        default="MIT",
        help="SPDX license identifier (default: MIT)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/sdks"),
        help="Output directory root; per-target subdirs are created (default: dist/sdks)",
    )
    parser.add_argument(
        "--targets",
        default="typescript,python,swift",
        help="Comma-separated targets (default: all three)",
    )
    args = parser.parse_args(argv)

    schema = _load_schema(args.schema)
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]

    for target in targets:
        generator_cls = _GENERATORS.get(target)
        if generator_cls is None:
            raise SystemExit(f"Unknown target: {target} (expected one of {list(_GENERATORS)})")
        config = SDKConfig(
            package_name=args.package,
            version=args.version,
            base_url=args.base_url,
            author=args.author,
            description=args.description,
            license=args.license,
        )
        out_dir = args.output / target
        out_dir.mkdir(parents=True, exist_ok=True)
        sdk = generator_cls().generate(schema, config)
        written = sdk.write_to_disk(out_dir)
        print(f"{target}: wrote {len(written)} files to {out_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
