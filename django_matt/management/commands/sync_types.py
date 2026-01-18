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

    # Watch mode for development
    python manage.py sync_types --target typescript --output frontend/src/types/api.ts --watch

    # Scan specific apps
    python manage.py sync_types --target typescript --apps myapp,otherapp

    # Scan specific schema modules
    python manage.py sync_types --target typescript --modules myapp.schemas,otherapp.schemas
"""

import importlib
import os
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from pydantic import BaseModel


class Command(BaseCommand):
    help = "Generate TypeScript or Swift types from Pydantic schemas and Django models"

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
        target = options["target"]
        output = options["output"]
        apps = options["apps"]
        modules = options["modules"]
        include_models = options["models"]
        watch = options["watch"]
        watch_interval = options["watch_interval"]
        camel_case = options["camel_case"]
        base_url = options["base_url"]
        include_react_query = options["include_react_query"]
        include_swr = options["include_swr"]

        # Normalize target
        if target == "ts":
            target = "typescript"

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
            return generator.generate(schemas)

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

    def _watch_and_generate(
        self,
        target: str,
        output: str | None,
        schemas: list[type[BaseModel]],
        models: list[type],
        interval: float,
        **kwargs,
    ):
        """Watch for changes and regenerate."""
        self.stdout.write(self.style.SUCCESS(f"Watching for changes (interval: {interval}s)..."))

        # Get module files to watch
        watch_files = set()
        for schema in schemas:
            module = importlib.import_module(schema.__module__)
            if hasattr(module, "__file__") and module.__file__:
                watch_files.add(module.__file__)

        for model in models:
            module = importlib.import_module(model.__module__)
            if hasattr(module, "__file__") and module.__file__:
                watch_files.add(module.__file__)

        self.stdout.write(f"Watching {len(watch_files)} files")

        # Get initial mtimes
        mtimes = {}
        for filepath in watch_files:
            try:
                mtimes[filepath] = os.path.getmtime(filepath)
            except OSError:
                pass

        try:
            while True:
                time.sleep(interval)

                # Check for changes
                changed = False
                for filepath in watch_files:
                    try:
                        current_mtime = os.path.getmtime(filepath)
                        if filepath not in mtimes or current_mtime > mtimes[filepath]:
                            mtimes[filepath] = current_mtime
                            changed = True
                            self.stdout.write(f"  Changed: {filepath}")
                    except OSError:
                        pass

                if changed:
                    self.stdout.write("Regenerating...")

                    # Reload modules
                    for schema in schemas:
                        module = importlib.import_module(schema.__module__)
                        importlib.reload(module)

                    # Regenerate
                    code = self._generate(
                        target=target,
                        schemas=schemas,
                        models=models,
                        **kwargs,
                    )

                    if output:
                        self._write_output(output, code)
                        self.stdout.write(
                            self.style.SUCCESS(f"Generated {target} types to {output}")
                        )
                    else:
                        self.stdout.write(code)

        except KeyboardInterrupt:
            self.stdout.write("\nStopped watching.")
