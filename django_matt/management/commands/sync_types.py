"""
Management command to synchronize types between Python and TypeScript/Swift.

Usage:
    # Generate TypeScript types
    python manage.py sync_types --target typescript --output frontend/src/types/api.ts

    # Generate Zod schemas
    python manage.py sync_types --target zod --output frontend/src/schemas/api.ts

    # Generate Swift types
    python manage.py sync_types --target swift --output ios/App/API/Models.swift

    # Generate API client
    python manage.py sync_types --target api-client --output frontend/src/api/client.ts

    # Watch mode for development (uses watchdog if available)
    python manage.py sync_types --target typescript --output frontend/src/types/api.ts --watch

    # Watch specific directories
    python manage.py sync_types --target typescript --output frontend/types --watch --watch-dirs myapp,otherapp

    # Scan specific apps
    python manage.py sync_types --target typescript --apps myapp,otherapp

    # Scan specific schema modules
    python manage.py sync_types --target typescript --modules myapp.schemas,otherapp.schemas

    # Use config file (auto-discovers django_matt_codegen.py or pyproject.toml)
    python manage.py sync_types --config

    # Use specific config file
    python manage.py sync_types --config path/to/config.py

    # Use config with watch mode
    python manage.py sync_types --config --watch
"""

from __future__ import annotations

import importlib
import os
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from pydantic import BaseModel


class Command(BaseCommand):
    help = "Generate TypeScript or Swift types from Pydantic schemas and Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            "-c",
            nargs="?",
            const=True,
            default=False,
            help="Use config file (django_matt_codegen.py or pyproject.toml). Optionally specify path.",
        )
        parser.add_argument(
            "--target",
            "-t",
            choices=["typescript", "ts", "zod", "swift", "api-client", "all"],
            default="typescript",
            help="Target output format (default: typescript)",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path",
        )
        parser.add_argument(
            "--apps",
            "-a",
            type=str,
            help="Comma-separated list of Django apps to scan",
        )
        parser.add_argument(
            "--modules",
            "-m",
            type=str,
            help="Comma-separated list of Python modules to scan for schemas",
        )
        parser.add_argument(
            "--models",
            action="store_true",
            help="Include Django models (not just Pydantic schemas)",
        )
        parser.add_argument(
            "--watch",
            "-w",
            action="store_true",
            help="Watch for changes and regenerate",
        )
        parser.add_argument(
            "--watch-interval",
            type=float,
            default=1.0,
            help="Watch interval in seconds (default: 1.0)",
        )
        parser.add_argument(
            "--watch-dirs",
            type=str,
            help="Comma-separated directories to watch (default: auto-detect from apps/modules)",
        )
        parser.add_argument(
            "--debounce",
            type=float,
            default=0.5,
            help="Debounce delay in seconds for watch mode (default: 0.5)",
        )
        parser.add_argument(
            "--force-polling",
            action="store_true",
            help="Force polling mode instead of watchdog (for debugging)",
        )
        parser.add_argument(
            "--clear-screen",
            action="store_true",
            help="Clear screen before each regeneration in watch mode",
        )
        parser.add_argument(
            "--camel-case",
            action="store_true",
            help="Convert field names to camelCase",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default="/api",
            help="Base URL for API client (default: /api)",
        )
        parser.add_argument(
            "--include-react-query",
            action="store_true",
            help="Include React Query hooks in API client",
        )
        parser.add_argument(
            "--include-swr",
            action="store_true",
            help="Include SWR hooks in API client",
        )
        parser.add_argument(
            "--from-openapi",
            action="store_true",
            default=False,
            help="Generate types from the project's OpenAPI schema (calls OpenAPISchema.build())",
        )
        parser.add_argument(
            "--openapi-file",
            type=str,
            default=None,
            help="Path to a pre-generated OpenAPI JSON/YAML spec file (for CI use case)",
        )

    def handle(self, *args, **options):
        config_option = options["config"]

        # Load config if requested
        if config_option:
            config = self._load_config(config_option)
            # Use config values as defaults, CLI options override
            target = options["target"] if options["target"] != "typescript" else config.framework
            output = options["output"] or config.output_dir
            apps = options["apps"]  # CLI only
            modules = options["modules"]  # CLI only
            include_models = options["models"]
            watch = options["watch"]
            watch_interval = (
                options["watch_interval"]
                if options["watch_interval"] != 1.0
                else config.poll_interval
            )
            watch_dirs = options["watch_dirs"] or (
                ",".join(config.watch_dirs) if config.watch_dirs else None
            )
            debounce = options["debounce"] if options["debounce"] != 0.5 else config.debounce_delay
            force_polling = options["force_polling"]
            clear_screen = options["clear_screen"]
            camel_case = options["camel_case"] or config.camel_case
            base_url = options["base_url"] if options["base_url"] != "/api" else config.base_url
            include_react_query = options["include_react_query"]
            include_swr = options["include_swr"]

            # Show config info
            self.stdout.write(f"Using config: {config.framework} / {config.ui_library}")
            self.stdout.write(f"Output: {output}")

            # Derive modules from config models
            if not apps and not modules and config.models:
                model_configs = config.get_model_configs()
                modules = ",".join(m.path.rsplit(".", 1)[0] for m in model_configs)
                self.stdout.write(f"Scanning modules from config: {modules}")
        else:
            target = options["target"]
            output = options["output"]
            apps = options["apps"]
            modules = options["modules"]
            include_models = options["models"]
            watch = options["watch"]
            watch_interval = options["watch_interval"]
            watch_dirs = options["watch_dirs"]
            debounce = options["debounce"]
            force_polling = options["force_polling"]
            clear_screen = options["clear_screen"]
            camel_case = options["camel_case"]
            base_url = options["base_url"]
            include_react_query = options["include_react_query"]
            include_swr = options["include_swr"]

        from_openapi = options.get("from_openapi", False)
        openapi_file = options.get("openapi_file")

        # Normalize target
        if target == "ts":
            target = "typescript"

        # Handle --openapi-file: generate from pre-built OpenAPI spec
        if openapi_file:
            code = self._generate_from_openapi_file(
                openapi_file=openapi_file,
                target=target,
                camel_case=camel_case,
                base_url=base_url,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )
            if output:
                self._write_output(output, code)
                self.stdout.write(
                    self.style.SUCCESS(f"Generated {target} types from OpenAPI file to {output}")
                )
            else:
                self.stdout.write(code)
            return

        # Handle --from-openapi: introspect project's OpenAPI schema
        if from_openapi:
            code = self._generate_from_project_openapi(
                target=target,
                camel_case=camel_case,
                base_url=base_url,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )
            if output:
                self._write_output(output, code)
                self.stdout.write(
                    self.style.SUCCESS(f"Generated {target} types from OpenAPI schema to {output}")
                )
            else:
                self.stdout.write(code)
            return

        # Collect schemas and models
        schemas = self._collect_schemas(apps, modules)
        models = self._collect_models(apps) if include_models else []

        if not schemas and not models:
            self.stderr.write(
                self.style.WARNING(
                    "No schemas or models found. Use --apps or --modules to specify sources."
                )
            )
            return

        self.stdout.write(f"Found {len(schemas)} Pydantic schemas and {len(models)} Django models")

        # Generate code
        if watch:
            self._watch_and_generate(
                target=target,
                output=output,
                schemas=schemas,
                models=models,
                interval=watch_interval,
                watch_dirs=watch_dirs,
                debounce=debounce,
                force_polling=force_polling,
                clear_screen=clear_screen,
                camel_case=camel_case,
                base_url=base_url,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )
        else:
            code = self._generate(
                target=target,
                schemas=schemas,
                models=models,
                camel_case=camel_case,
                base_url=base_url,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )

            if output:
                self._write_output(output, code)
                self.stdout.write(self.style.SUCCESS(f"Generated {target} types to {output}"))
            else:
                self.stdout.write(code)

    def _collect_schemas(
        self,
        apps: str | None,
        modules: str | None,
    ) -> list[type[BaseModel]]:
        """Collect Pydantic schemas from specified apps or modules."""
        schemas = []

        # Collect from modules
        if modules:
            for module_path in modules.split(","):
                module_path = module_path.strip()
                try:
                    from django_matt.typegen.utils import collect_schemas_from_module

                    module_schemas = collect_schemas_from_module(module_path)
                    schemas.extend(module_schemas)
                    self.stdout.write(f"  Found {len(module_schemas)} schemas in {module_path}")
                except ImportError as e:
                    self.stderr.write(
                        self.style.WARNING(f"Could not import module {module_path}: {e}")
                    )

        # Collect from apps
        if apps:
            for app_label in apps.split(","):
                app_label = app_label.strip()
                # Try to find schemas module in app
                for suffix in ["schemas", "schema", "types"]:
                    module_path = f"{app_label}.{suffix}"
                    try:
                        from django_matt.typegen.utils import collect_schemas_from_module

                        module_schemas = collect_schemas_from_module(module_path)
                        schemas.extend(module_schemas)
                        self.stdout.write(f"  Found {len(module_schemas)} schemas in {module_path}")
                    except ImportError:
                        pass

        # Remove duplicates while preserving order
        seen = set()
        unique_schemas = []
        for schema in schemas:
            if schema.__name__ not in seen:
                seen.add(schema.__name__)
                unique_schemas.append(schema)

        return unique_schemas

    def _collect_models(self, apps: str | None) -> list[type]:
        """Collect Django models from specified apps."""
        models = []

        if not apps:
            return models

        from django_matt.typegen.utils import collect_models_from_app

        for app_label in apps.split(","):
            app_label = app_label.strip()
            app_models = collect_models_from_app(app_label)
            models.extend(app_models)
            self.stdout.write(f"  Found {len(app_models)} models in {app_label}")

        return models

    def _generate(
        self,
        target: str,
        schemas: list[type[BaseModel]],
        models: list[type],
        camel_case: bool = False,
        base_url: str = "/api",
        include_react_query: bool = False,
        include_swr: bool = False,
    ) -> str:
        """Generate code for the specified target."""
        if target == "typescript":
            from django_matt.typegen.typescript import TypeScriptGenerator

            generator = TypeScriptGenerator(camel_case=camel_case)

            parts = []
            if schemas:
                parts.append(generator.generate(schemas))
            if models:
                parts.append(generator.generate_from_django_models(models))

            return "\n".join(parts)

        if target == "zod":
            from django_matt.typegen.zod import ZodGenerator

            generator = ZodGenerator(camel_case=camel_case)
            return generator.generate(schemas)

        if target == "swift":
            from django_matt.typegen.swift import SwiftGenerator

            generator = SwiftGenerator()
            # Generate Codable structs
            structs_code = generator.generate(schemas)
            # Generate URLSession-based API client
            api_client_code = generator.generate_api_client(
                base_url=base_url,
                schemas=schemas,
            )
            return f"{structs_code}\n{api_client_code}"

        if target == "api-client":
            from django_matt.typegen.api_client import APIClientGenerator

            # First generate types
            from django_matt.typegen.typescript import TypeScriptGenerator

            ts_generator = TypeScriptGenerator(camel_case=camel_case)
            types_code = ts_generator.generate(schemas)

            # Then generate client stub
            api_generator = APIClientGenerator(
                base_url=base_url,
                camel_case=camel_case,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )

            # Note: Without OpenAPI schema or controllers, we generate a basic client
            client_code = self._generate_basic_client(
                schemas,
                base_url,
                camel_case,
                include_react_query,
                include_swr,
            )

            return f"{types_code}\n{client_code}"

        if target == "all":
            parts = []
            for t in ["typescript", "zod"]:
                parts.append(f"// === {t.upper()} ===")
                parts.append(
                    self._generate(
                        target=t,
                        schemas=schemas,
                        models=models,
                        camel_case=camel_case,
                        base_url=base_url,
                        include_react_query=include_react_query,
                        include_swr=include_swr,
                    )
                )
                parts.append("")
            return "\n".join(parts)

        raise CommandError(f"Unknown target: {target}")

    def _generate_from_openapi_file(
        self,
        openapi_file: str,
        target: str,
        camel_case: bool = False,
        base_url: str = "/api",
        include_react_query: bool = False,
        include_swr: bool = False,
    ) -> str:
        """Generate types from a pre-built OpenAPI spec file (JSON or YAML)."""
        import json
        from pathlib import Path

        spec_path = Path(openapi_file)
        if not spec_path.exists():
            raise CommandError(f"OpenAPI spec file not found: {openapi_file}")

        content = spec_path.read_text()

        # Try JSON first, then YAML
        try:
            schema = json.loads(content)
        except json.JSONDecodeError:
            try:
                import yaml  # type: ignore[import]

                schema = yaml.safe_load(content)
            except ImportError:
                raise CommandError(
                    "YAML spec files require PyYAML. Install it with: uv add pyyaml"
                )

        return self._generate_from_openapi_schema(
            schema=schema,
            target=target,
            camel_case=camel_case,
            base_url=base_url,
            include_react_query=include_react_query,
            include_swr=include_swr,
        )

    def _generate_from_project_openapi(
        self,
        target: str,
        camel_case: bool = False,
        base_url: str = "/api",
        include_react_query: bool = False,
        include_swr: bool = False,
    ) -> str:
        """Generate types from the project's live OpenAPI schema."""
        try:
            from django_matt.openapi.schema import OpenAPISchema

            schema = OpenAPISchema.build()
        except Exception as e:
            self.stderr.write(
                self.style.WARNING(
                    f"Could not build OpenAPI schema: {e}. "
                    "Ensure MattAPI is configured. Falling back to empty schema."
                )
            )
            schema = {"openapi": "3.0.0", "info": {}, "paths": {}, "components": {"schemas": {}}}

        return self._generate_from_openapi_schema(
            schema=schema,
            target=target,
            camel_case=camel_case,
            base_url=base_url,
            include_react_query=include_react_query,
            include_swr=include_swr,
        )

    def _generate_from_openapi_schema(
        self,
        schema: dict,
        target: str,
        camel_case: bool = False,
        base_url: str = "/api",
        include_react_query: bool = False,
        include_swr: bool = False,
    ) -> str:
        """Generate code from an OpenAPI schema dict."""
        components = schema.get("components", {})
        openapi_schemas = components.get("schemas", {})

        self.stdout.write(
            f"Found {len(openapi_schemas)} component schemas in OpenAPI spec"
        )

        if target in ("typescript", "ts"):
            from django_matt.typegen.api_client import APIClientGenerator

            generator = APIClientGenerator(
                base_url=base_url,
                camel_case=camel_case,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )
            return generator.generate_from_openapi(schema)

        if target == "zod":
            # Generate Zod types from OpenAPI schema definitions
            from django_matt.typegen.api_client import APIClientGenerator

            # Use TS generator to get type definitions, then convert comment
            generator = APIClientGenerator(base_url=base_url, camel_case=camel_case)
            ts_code = generator.generate_from_openapi(schema)
            # For now, return TS types with a note — full Zod-from-OpenAPI is complex
            lines = [
                "// Auto-generated from OpenAPI schema",
                '// Note: Use --target typescript for full OpenAPI type generation',
                "",
                ts_code,
            ]
            return "\n".join(lines)

        if target == "api-client":
            from django_matt.typegen.api_client import APIClientGenerator

            generator = APIClientGenerator(
                base_url=base_url,
                camel_case=camel_case,
                include_react_query=include_react_query,
                include_swr=include_swr,
            )
            return generator.generate_from_openapi(schema)

        if target == "swift":
            # For OpenAPI → Swift, generate interfaces from components
            lines = [
                "// Auto-generated Swift types from OpenAPI schema",
                "// Do not edit manually - regenerate with sync_types command",
                "",
                "import Foundation",
                "",
            ]
            for schema_name, schema_def in openapi_schemas.items():
                lines.append(f"public struct {schema_name}: Codable, Equatable {{")
                properties = schema_def.get("properties", {})
                required = set(schema_def.get("required", []))
                for prop_name, prop_def in properties.items():
                    swift_type = self._openapi_type_to_swift(prop_def)
                    is_optional = prop_name not in required
                    if is_optional:
                        swift_type = f"{swift_type}?"
                    lines.append(f"    public let {prop_name}: {swift_type}")
                lines.append("}")
                lines.append("")
            return "\n".join(lines)

        # Default: typescript
        from django_matt.typegen.api_client import APIClientGenerator

        generator = APIClientGenerator(base_url=base_url, camel_case=camel_case)
        return generator.generate_from_openapi(schema)

    def _openapi_type_to_swift(self, schema_def: dict) -> str:
        """Convert an OpenAPI type definition to a Swift type."""
        if "$ref" in schema_def:
            return schema_def["$ref"].split("/")[-1]

        schema_type = schema_def.get("type", "any")
        schema_format = schema_def.get("format", "")

        type_map = {
            "string": "String",
            "integer": "Int",
            "number": "Double",
            "boolean": "Bool",
            "array": "[Any]",
            "object": "[String: Any]",
        }

        if schema_type == "string" and schema_format in ("date-time", "date"):
            return "Date"
        if schema_type == "string" and schema_format == "uuid":
            return "UUID"
        if schema_type == "array":
            items = schema_def.get("items", {})
            inner = self._openapi_type_to_swift(items)
            return f"[{inner}]"

        return type_map.get(schema_type, "Any")

    def _generate_basic_client(
        self,
        schemas: list[type[BaseModel]],
        base_url: str,
        camel_case: bool,
        include_react_query: bool,
        include_swr: bool,
    ) -> str:
        """Generate a basic API client without OpenAPI or controller information."""
        lines = [
            "",
            "// API Client",
            "",
            "export interface ApiClientConfig {",
            "  baseUrl?: string;",
            "  headers?: Record<string, string>;",
            "  onError?: (error: Error) => void;",
            "}",
            "",
            "export class ApiClient {",
            "  private baseUrl: string;",
            "  private headers: Record<string, string>;",
            "  private onError?: (error: Error) => void;",
            "",
            "  constructor(config: ApiClientConfig = {}) {",
            f'    this.baseUrl = config.baseUrl ?? "{base_url}";',
            "    this.headers = config.headers ?? {};",
            "    this.onError = config.onError;",
            "  }",
            "",
            "  setAuthToken(token: string) {",
            '    this.headers["Authorization"] = `Bearer ${token}`;',
            "  }",
            "",
            "  clearAuthToken() {",
            '    delete this.headers["Authorization"];',
            "  }",
            "",
            "  async request<T>(",
            "    method: string,",
            "    path: string,",
            "    options: {",
            "      body?: any;",
            "      params?: Record<string, any>;",
            "      headers?: Record<string, string>;",
            "    } = {}",
            "  ): Promise<T> {",
            "    const url = new URL(path, this.baseUrl);",
            "",
            "    if (options.params) {",
            "      Object.entries(options.params).forEach(([key, value]) => {",
            "        if (value !== undefined && value !== null) {",
            "          url.searchParams.append(key, String(value));",
            "        }",
            "      });",
            "    }",
            "",
            "    const response = await fetch(url.toString(), {",
            "      method,",
            "      headers: {",
            '        "Content-Type": "application/json",',
            "        ...this.headers,",
            "        ...options.headers,",
            "      },",
            "      body: options.body ? JSON.stringify(options.body) : undefined,",
            "    });",
            "",
            "    if (!response.ok) {",
            "      const error = new Error(`HTTP ${response.status}: ${response.statusText}`);",
            "      if (this.onError) {",
            "        this.onError(error);",
            "      }",
            "      throw error;",
            "    }",
            "",
            "    return response.json();",
            "  }",
            "",
            "  async get<T>(path: string, params?: Record<string, any>): Promise<T> {",
            '    return this.request<T>("GET", path, { params });',
            "  }",
            "",
            "  async post<T>(path: string, body?: any): Promise<T> {",
            '    return this.request<T>("POST", path, { body });',
            "  }",
            "",
            "  async put<T>(path: string, body?: any): Promise<T> {",
            '    return this.request<T>("PUT", path, { body });',
            "  }",
            "",
            "  async patch<T>(path: string, body?: any): Promise<T> {",
            '    return this.request<T>("PATCH", path, { body });',
            "  }",
            "",
            "  async delete<T>(path: string): Promise<T> {",
            '    return this.request<T>("DELETE", path);',
            "  }",
            "}",
            "",
            "export const api = new ApiClient();",
        ]

        return "\n".join(lines)

    def _write_output(self, output_path: str, code: str):
        """Write generated code to output file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    def _load_config(self, config_option: bool | str):
        """Load configuration from file."""
        from django_matt.codegen.config import load_config

        if isinstance(config_option, str):
            # Explicit config file path provided
            config = load_config(config_file=config_option)
        else:
            # Auto-discover config
            config = load_config()

        return config

    def _watch_and_generate(
        self,
        target: str,
        output: str | None,
        schemas: list[type[BaseModel]],
        models: list[type],
        interval: float,
        watch_dirs: str | None = None,
        debounce: float = 0.5,
        force_polling: bool = False,
        clear_screen: bool = False,
        **kwargs,
    ):
        """Watch for changes and regenerate using enhanced watcher."""
        from django_matt.codegen.watcher import HAS_WATCHDOG, CodegenWatcher, WatchConfig

        # Determine paths to watch
        watch_paths: set[str] = set()

        # Add explicitly specified watch directories
        if watch_dirs:
            for dir_path in watch_dirs.split(","):
                dir_path = dir_path.strip()
                if Path(dir_path).is_dir():
                    watch_paths.add(dir_path)
                else:
                    self.stderr.write(self.style.WARNING(f"Watch directory not found: {dir_path}"))

        # Auto-detect from schemas and models
        for schema in schemas:
            module = importlib.import_module(schema.__module__)
            if hasattr(module, "__file__") and module.__file__:
                # Watch the parent directory of the module
                parent_dir = os.path.dirname(module.__file__)
                watch_paths.add(parent_dir)

        for model in models:
            module = importlib.import_module(model.__module__)
            if hasattr(module, "__file__") and module.__file__:
                parent_dir = os.path.dirname(module.__file__)
                watch_paths.add(parent_dir)

        if not watch_paths:
            raise CommandError("No paths to watch. Use --watch-dirs or specify --apps/--modules.")

        # Display watch info
        watcher_type = "watchdog" if (HAS_WATCHDOG and not force_polling) else "polling"
        self.stdout.write(self.style.SUCCESS(f"Starting watch mode ({watcher_type})..."))
        self.stdout.write(f"  Debounce: {debounce}s, Poll interval: {interval}s")
        self.stdout.write(f"  Watching {len(watch_paths)} directories:")
        for path in sorted(watch_paths):
            self.stdout.write(f"    - {path}")

        # Track generation count for statistics
        generation_count = [0]
        start_time = datetime.now()

        def on_change(changed_files: list[str]):
            """Handle file changes by regenerating code."""
            generation_count[0] += 1
            timestamp = datetime.now().strftime("%H:%M:%S")

            self.stdout.write(f"\n[{timestamp}] Detected {len(changed_files)} file change(s):")
            for filepath in changed_files[:5]:  # Show first 5
                self.stdout.write(f"  - {Path(filepath).name}")
            if len(changed_files) > 5:
                self.stdout.write(f"  ... and {len(changed_files) - 5} more")

            self.stdout.write("Regenerating...")

            # Reload modules to pick up changes
            for schema in schemas:
                try:
                    module = importlib.import_module(schema.__module__)
                    importlib.reload(module)
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(f"Failed to reload {schema.__module__}: {e}")
                    )
                    return

            for model in models:
                try:
                    module = importlib.import_module(model.__module__)
                    importlib.reload(module)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed to reload {model.__module__}: {e}"))
                    return

            # Regenerate code
            try:
                code = self._generate(
                    target=target,
                    schemas=schemas,
                    models=models,
                    **kwargs,
                )

                if output:
                    self._write_output(output, code)
                    self.stdout.write(
                        self.style.SUCCESS(f"[{timestamp}] Generated {target} types to {output}")
                    )
                else:
                    self.stdout.write(code)

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Generation failed: {e}"))

        def on_start():
            """Called when watcher starts."""
            self.stdout.write(self.style.SUCCESS("Watcher started. Press Ctrl+C to stop."))

        def on_error(e: Exception):
            """Handle watcher errors."""
            self.stderr.write(self.style.ERROR(f"Watcher error: {e}"))

        # Create watcher config
        config = WatchConfig(
            paths=list(watch_paths),
            include_patterns=["*.py"],
            exclude_patterns=["__pycache__", "*.pyc", ".git", ".venv", "venv", "migrations"],
            debounce_delay=debounce,
            poll_interval=interval,
            clear_screen=clear_screen,
            force_polling=force_polling,
        )

        # Create and start watcher
        watcher = CodegenWatcher(
            config=config,
            on_change=on_change,
            on_start=on_start,
            on_error=on_error,
        )

        try:
            # Do initial generation
            self.stdout.write("Performing initial generation...")
            code = self._generate(
                target=target,
                schemas=schemas,
                models=models,
                **kwargs,
            )
            if output:
                self._write_output(output, code)
                self.stdout.write(self.style.SUCCESS(f"Generated {target} types to {output}"))
            else:
                self.stdout.write(code)

            # Start watching
            watcher.start()
            watcher.wait()

        except KeyboardInterrupt:
            pass
        finally:
            watcher.stop()
            elapsed = datetime.now() - start_time
            self.stdout.write(
                f"\nStopped watching. Generated {generation_count[0]} time(s) in {elapsed.seconds}s."
            )
