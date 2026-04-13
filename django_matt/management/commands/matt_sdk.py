"""
Management command for SDK generation.

Usage:
    python manage.py matt_sdk generate --target typescript --output ./sdk/ts/
    python manage.py matt_sdk generate --target python --output ./sdk/py/
    python manage.py matt_sdk generate --target swift --output ./sdk/swift/
    python manage.py matt_sdk generate --target all --output ./sdk/
    python manage.py matt_sdk preview --target typescript
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from django_matt.sdkgen.base import SDKConfig, SDKOutput

_TARGETS = ("typescript", "python", "swift", "all")


class Command(BaseCommand):
    help = "Generate typed client SDKs from your API definition"

    def add_arguments(self, parser: Any) -> None:
        subparsers = parser.add_subparsers(dest="subcommand", help="SDK commands")

        # generate
        gen = subparsers.add_parser("generate", help="Generate SDK package")
        gen.add_argument(
            "--target", "-t",
            choices=_TARGETS,
            default="typescript",
            help="Target language (default: typescript)",
        )
        gen.add_argument("--output", "-o", default="./sdk", help="Output directory")
        gen.add_argument("--package-name", default=None, help="Package name")
        gen.add_argument("--version", default="0.1.0", help="Package version")
        gen.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
        gen.add_argument(
            "--auth-type",
            choices=("jwt", "api_key", "oauth"),
            default="jwt",
            help="Auth type for generated client",
        )

        # preview
        preview = subparsers.add_parser("preview", help="Preview generated SDK without writing")
        preview.add_argument(
            "--target", "-t",
            choices=_TARGETS,
            default="typescript",
            help="Target language",
        )
        preview.add_argument("--package-name", default=None, help="Package name")
        preview.add_argument("--version", default="0.1.0", help="Package version")
        preview.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
        preview.add_argument(
            "--auth-type",
            choices=("jwt", "api_key", "oauth"),
            default="jwt",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subcommand = options.get("subcommand")
        if not subcommand:
            self.stderr.write(self.style.ERROR("Usage: matt_sdk {generate|preview} [options]"))
            sys.exit(1)

        if subcommand == "generate":
            self._handle_generate(options)
        elif subcommand == "preview":
            self._handle_preview(options)
        else:
            raise CommandError(f"Unknown subcommand: {subcommand}")

    def _get_schema(self) -> dict[str, Any]:
        """Extract OpenAPI schema from the running Django app."""
        try:
            from django_matt.openapi.schema import OpenAPISchema
        except ImportError as e:
            raise CommandError(f"OpenAPI module not available: {e}") from e

        schema_builder = OpenAPISchema()

        # Try to discover the API instance
        api = self._discover_api()
        if api is None:
            self.stderr.write(self.style.WARNING(
                "No API instance found. Generating SDK from empty schema."
            ))
            return schema_builder.build()

        # Register routes from the API
        routes = getattr(api, "routes", [])
        if routes:
            schema_builder.add_routes(routes)

        controllers = getattr(api, "controllers", [])
        for controller_cls in controllers:
            schema_builder.add_controller(controller_cls)

        return schema_builder.build()

    def _discover_api(self) -> Any:
        """Try to find the MattAPI instance from the project."""
        from django.conf import settings

        # Check DJANGO_MATT settings
        matt_config = getattr(settings, "DJANGO_MATT", {})
        api_path = matt_config.get("API_INSTANCE")
        if api_path:
            return self._import_api(api_path)

        # Try common patterns
        for candidate in ("api.api", "core.api", "config.api", "app.api"):
            try:
                return self._import_api(candidate)
            except (ImportError, AttributeError):
                continue

        return None

    def _import_api(self, dotted_path: str) -> Any:
        """Import an API instance from a dotted path."""
        module_path, _, attr_name = dotted_path.rpartition(".")
        if not module_path:
            raise ImportError(f"Invalid API path: {dotted_path}")
        from importlib import import_module
        module = import_module(module_path)
        return getattr(module, attr_name)

    def _build_config(self, options: dict[str, Any]) -> SDKConfig:
        pkg_name = options.get("package_name") or "my-api-client"
        return SDKConfig(
            package_name=pkg_name,
            version=options.get("version", "0.1.0"),
            base_url=options.get("base_url", "http://localhost:8000"),
            auth_type=options.get("auth_type", "jwt"),
            output_dir=Path(options.get("output", "./sdk")),
        )

    def _get_generators(self, target: str) -> list[tuple[str, Any]]:
        from django_matt.sdkgen.python_sdk import PythonSDKGenerator
        from django_matt.sdkgen.swift import SwiftSDKGenerator
        from django_matt.sdkgen.typescript import TypeScriptSDKGenerator

        generators = {
            "typescript": TypeScriptSDKGenerator,
            "python": PythonSDKGenerator,
            "swift": SwiftSDKGenerator,
        }

        if target == "all":
            return [(name, cls()) for name, cls in generators.items()]
        if target not in generators:
            raise CommandError(f"Unknown target: {target}")
        return [(target, generators[target]())]

    def _handle_generate(self, options: dict[str, Any]) -> None:
        schema = self._get_schema()
        config = self._build_config(options)
        target = options.get("target", "typescript")
        output_dir = Path(options.get("output", "./sdk"))

        for name, generator in self._get_generators(target):
            if target == "all":
                gen_output_dir = output_dir / name
            else:
                gen_output_dir = output_dir

            output: SDKOutput = generator.generate(schema, config)
            written = output.write_to_disk(gen_output_dir)

            self.stdout.write(self.style.SUCCESS(
                f"\n[{name}] Generated {len(written)} files in {gen_output_dir}"
            ))
            for path in written:
                self.stdout.write(f"  {path}")

    def _handle_preview(self, options: dict[str, Any]) -> None:
        schema = self._get_schema()
        config = self._build_config(options)
        target = options.get("target", "typescript")

        for name, generator in self._get_generators(target):
            output: SDKOutput = generator.generate(schema, config)

            self.stdout.write(self.style.SUCCESS(f"\n=== {name} SDK Preview ==="))
            for path, content in sorted(output.files.items()):
                self.stdout.write(self.style.NOTICE(f"\n--- {path} ---"))
                # Show first 50 lines
                preview_lines = content.split("\n")[:50]
                self.stdout.write("\n".join(preview_lines))
                if len(content.split("\n")) > 50:
                    self.stdout.write(f"\n  ... ({len(content.split(chr(10)))} lines total)")
