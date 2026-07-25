# file-length-max: 600
"""
Management command for component operations.

Provides CLI tools for:
- Listing available components
- Previewing components in terminal
- Exporting components to different frameworks
- Generating component documentation
"""

from django.core.management.base import BaseCommand, CommandError, CommandParser

import orjson


class Command(BaseCommand):
    """List, preview, export, and document backend-served UI components."""

    help = "Manage and inspect UI components"

    def add_arguments(self, parser: CommandParser):
        subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

        # list command
        list_parser = subparsers.add_parser("list", help="List all registered components")
        list_parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON",
        )
        list_parser.add_argument(
            "--type",
            help="Filter by component type",
        )

        # show command
        show_parser = subparsers.add_parser("show", help="Show component details")
        show_parser.add_argument(
            "name",
            help="Component name",
        )
        show_parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON",
        )

        # preview command
        preview_parser = subparsers.add_parser("preview", help="Preview a component")
        preview_parser.add_argument(
            "name",
            help="Component name",
        )
        preview_parser.add_argument(
            "--props",
            default="{}",
            help="Props as JSON string",
        )
        preview_parser.add_argument(
            "--renderer",
            choices=["html", "json", "react"],
            default="html",
            help="Renderer to use",
        )
        preview_parser.add_argument(
            "--output",
            "-o",
            help="Output file path",
        )

        # export command
        export_parser = subparsers.add_parser("export", help="Export components")
        export_parser.add_argument(
            "--framework",
            choices=["react", "vue", "svelte", "html"],
            default="react",
            help="Target framework",
        )
        export_parser.add_argument(
            "--output",
            "-o",
            default="./components",
            help="Output directory",
        )
        export_parser.add_argument(
            "--component",
            help="Export specific component (all if not specified)",
        )

        # docs command
        docs_parser = subparsers.add_parser("docs", help="Generate component documentation")
        docs_parser.add_argument(
            "--format",
            choices=["markdown", "html", "json"],
            default="markdown",
            help="Documentation format",
        )
        docs_parser.add_argument(
            "--output",
            "-o",
            default="./docs/components",
            help="Output directory",
        )

        # playground command
        subparsers.add_parser("playground", help="Launch component playground server")

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")

        if not subcommand:
            self.print_help("manage.py", "components")
            return

        handler = getattr(self, f"handle_{subcommand}", None)
        if handler:
            handler(**options)
        else:
            raise CommandError(f"Unknown subcommand: {subcommand}")

    def handle_list(self, **options):
        """List all registered components."""
        from django_matt.components.base import registry

        components = []
        type_filter = options.get("type")

        for name in sorted(registry.list()):
            cls = registry.get(name)
            if cls:
                component_type = getattr(cls, "__name__", "Unknown")

                if type_filter and type_filter.lower() not in component_type.lower():
                    continue

                components.append(
                    {
                        "name": name,
                        "type": component_type,
                        "module": cls.__module__,
                    }
                )

        if options.get("json"):
            self.stdout.write(orjson.dumps(components, option=orjson.OPT_INDENT_2).decode())
        else:
            self.stdout.write(self.style.SUCCESS(f"\nRegistered Components ({len(components)})\n"))
            self.stdout.write("-" * 60)

            for comp in components:
                self.stdout.write(f"\n  {self.style.WARNING(comp['name'])}")
                self.stdout.write(f"    Type: {comp['type']}")
                self.stdout.write(f"    Module: {comp['module']}")

            self.stdout.write("\n")

    def handle_show(self, **options):
        """Show component details."""
        from django_matt.components.base import registry

        name = options["name"]
        cls = registry.get(name)

        if not cls:
            raise CommandError(f"Unknown component: {name}")

        # Get component info
        info = {
            "name": name,
            "type": cls.__name__,
            "module": cls.__module__,
            "docstring": cls.__doc__ or "",
            "props": {},
        }

        # Get props schema
        for prop_name, field in cls.model_fields.items():
            if prop_name.startswith("_"):
                continue

            prop_info = {
                "required": field.is_required(),
                "description": field.description or "",
            }

            annotation = field.annotation
            if annotation:
                prop_info["type"] = getattr(annotation, "__name__", str(annotation))

            if field.default is not None:
                prop_info["default"] = str(field.default)

            info["props"][prop_name] = prop_info

        if options.get("json"):
            self.stdout.write(orjson.dumps(info, option=orjson.OPT_INDENT_2).decode())
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{info['name']}"))
            self.stdout.write("-" * 40)
            self.stdout.write(f"Type: {info['type']}")
            self.stdout.write(f"Module: {info['module']}")

            if info["docstring"]:
                self.stdout.write(f"\nDescription:\n{info['docstring'][:500]}")

            self.stdout.write(self.style.WARNING("\n\nProps:"))
            for prop_name, prop_info in info["props"].items():
                required = "*" if prop_info.get("required") else ""
                default = f" = {prop_info['default']}" if "default" in prop_info else ""
                self.stdout.write(
                    f"  {prop_name}{required}: {prop_info.get('type', 'any')}{default}"
                )
                if prop_info.get("description"):
                    self.stdout.write(f"    {prop_info['description']}")

            self.stdout.write("\n")

    def handle_preview(self, **options):
        """Preview a component."""
        from django_matt.components.base import registry
        from django_matt.components.renderers import HTMLRenderer, JSONRenderer, ReactRenderer

        name = options["name"]
        cls = registry.get(name)

        if not cls:
            raise CommandError(f"Unknown component: {name}")

        # Parse props
        try:
            props = orjson.loads(options["props"])
        except orjson.JSONDecodeError as e:
            raise CommandError(f"Invalid props JSON: {e}")

        # Create component
        try:
            component = cls(**props)
        except Exception as e:
            raise CommandError(f"Failed to create component: {e}")

        # Select renderer
        renderers = {
            "html": HTMLRenderer(),
            "json": JSONRenderer(indent=2),
            "react": ReactRenderer(),
        }
        renderer = renderers[options["renderer"]]

        # Render
        output = renderer.render(component)

        # Output
        if options.get("output"):
            with open(options["output"], "w") as f:
                f.write(output.content)
            self.stdout.write(self.style.SUCCESS(f"Written to {options['output']}"))
        else:
            self.stdout.write(output.content)

    def handle_export(self, **options):
        """Export components to target framework."""
        import os

        from django_matt.components.base import registry

        framework = options["framework"]
        output_dir = options["output"]
        component_filter = options.get("component")

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Get components to export
        if component_filter:
            names = [component_filter] if registry.get(component_filter) else []
        else:
            names = registry.list()

        if not names:
            raise CommandError("No components to export")

        exported = 0

        for name in names:
            cls = registry.get(name)
            if not cls:
                continue

            try:
                if framework == "react":
                    content = self._export_react(name, cls)
                    filename = f"{name.replace('_', '-')}.tsx"
                elif framework == "vue":
                    content = self._export_vue(name, cls)
                    filename = f"{name.replace('_', '-')}.vue"
                elif framework == "svelte":
                    content = self._export_svelte(name, cls)
                    filename = f"{name.replace('_', '-')}.svelte"
                else:
                    content = self._export_html(name, cls)
                    filename = f"{name.replace('_', '-')}.html"

                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w") as f:
                    f.write(content)

                exported += 1
                self.stdout.write(f"  Exported: {filename}")

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  Failed: {name} - {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nExported {exported} components to {output_dir}"))

    def _export_react(self, name: str, cls) -> str:
        """Generate React component wrapper."""
        component_name = "".join(word.title() for word in name.split("_"))

        # Get props
        props_interface = []
        for prop_name, field in cls.model_fields.items():
            if prop_name.startswith("_"):
                continue

            ts_type = "any"
            annotation = field.annotation
            if annotation == str:
                ts_type = "string"
            elif annotation == int or annotation == float:
                ts_type = "number"
            elif annotation == bool:
                ts_type = "boolean"
            elif annotation == list:
                ts_type = "any[]"
            elif annotation == dict:
                ts_type = "Record<string, any>"

            optional = "?" if not field.is_required() else ""
            props_interface.append(f"  {prop_name}{optional}: {ts_type};")

        props_str = "\n".join(props_interface)

        return f"""import React from 'react';
import {{ useComponent }} from '@django-matt/react';

export interface {component_name}Props {{
{props_str}
}}

export function {component_name}(props: {component_name}Props) {{
  return useComponent('{name}', props);
}}

export default {component_name};
"""

    def _export_vue(self, name: str, cls) -> str:
        """Generate Vue component wrapper."""
        component_name = "".join(word.title() for word in name.split("_"))

        return f"""<script setup lang="ts">
import {{ useComponent }} from '@django-matt/vue';

const props = defineProps<{{
  // Add props here
}}>();

const component = useComponent('{name}', props);
</script>

<template>
  <component :is="component" />
</template>
"""

    def _export_svelte(self, name: str, cls) -> str:
        """Generate Svelte component wrapper."""
        return f"""<script lang="ts">
  import {{ useComponent }} from '@django-matt/svelte';

  // Add props here
  export let props = {{}};

  const component = useComponent('{name}', props);
</script>

{{@html $component}}
"""

    def _export_html(self, name: str, cls) -> str:
        """Generate HTML with component placeholder."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{name} Component</title>
  <script src="/static/matt-components.js"></script>
</head>
<body>
  <matt-component name="{name}">
    <!-- Component renders here -->
  </matt-component>
</body>
</html>
'''

    def handle_docs(self, **options):
        """Generate component documentation."""
        import os

        from django_matt.components.base import registry

        output_dir = options["output"]
        format_type = options["format"]

        os.makedirs(output_dir, exist_ok=True)

        components = []
        for name in sorted(registry.list()):
            cls = registry.get(name)
            if cls:
                components.append(
                    {
                        "name": name,
                        "cls": cls,
                    }
                )

        if format_type == "markdown":
            self._generate_markdown_docs(components, output_dir)
        elif format_type == "html":
            self._generate_html_docs(components, output_dir)
        else:
            self._generate_json_docs(components, output_dir)

        self.stdout.write(self.style.SUCCESS(f"Documentation generated in {output_dir}"))

    def _generate_markdown_docs(self, components: list[dict], output_dir: str):
        """Generate Markdown documentation."""
        import os

        # Index file
        index_content = "# Component Library\n\n"
        index_content += "## Available Components\n\n"

        for comp in components:
            name = comp["name"]
            cls = comp["cls"]
            index_content += f"- [{name}](./{name}.md) - {cls.__doc__.split(chr(10))[0] if cls.__doc__ else 'No description'}\n"

        with open(os.path.join(output_dir, "README.md"), "w") as f:
            f.write(index_content)

        # Individual component docs
        for comp in components:
            name = comp["name"]
            cls = comp["cls"]

            content = f"# {name}\n\n"
            content += f"{cls.__doc__ or 'No description available.'}\n\n"

            content += "## Props\n\n"
            content += "| Name | Type | Required | Default | Description |\n"
            content += "|------|------|----------|---------|-------------|\n"

            for prop_name, field in cls.model_fields.items():
                if prop_name.startswith("_"):
                    continue

                annotation = field.annotation
                type_name = (
                    getattr(annotation, "__name__", str(annotation)) if annotation else "any"
                )
                required = "Yes" if field.is_required() else "No"
                default = str(field.default) if field.default is not None else "-"
                description = field.description or "-"

                content += (
                    f"| {prop_name} | {type_name} | {required} | {default} | {description} |\n"
                )

            content += "\n## Usage\n\n```python\n"
            content += f"from django_matt.components import {cls.__name__}\n\n"
            content += f"component = {cls.__name__}(\n    # Add props here\n)\n"
            content += "```\n"

            with open(os.path.join(output_dir, f"{name}.md"), "w") as f:
                f.write(content)

    def _generate_html_docs(self, components: list[dict], output_dir: str):
        """Generate HTML documentation."""
        # Would generate full HTML docs
        # For now, just call markdown generator
        self._generate_markdown_docs(components, output_dir)

    def _generate_json_docs(self, components: list[dict], output_dir: str):
        """Generate JSON documentation."""
        import os

        docs = []

        for comp in components:
            name = comp["name"]
            cls = comp["cls"]

            doc = {
                "name": name,
                "type": cls.__name__,
                "description": cls.__doc__ or "",
                "props": {},
            }

            for prop_name, field in cls.model_fields.items():
                if prop_name.startswith("_"):
                    continue

                annotation = field.annotation
                doc["props"][prop_name] = {
                    "type": getattr(annotation, "__name__", str(annotation))
                    if annotation
                    else "any",
                    "required": field.is_required(),
                    "default": field.default if field.default is not None else None,
                    "description": field.description or "",
                }

            docs.append(doc)

        with open(os.path.join(output_dir, "components.json"), "w") as f:
            f.write(orjson.dumps(docs, option=orjson.OPT_INDENT_2, default=str).decode())

    def handle_playground(self, **options):
        """Launch the component playground."""
        self.stdout.write(
            self.style.WARNING("\nTo use the playground, add this to your urls.py:\n")
        )
        self.stdout.write("""
    from django_matt.components.playground import PlaygroundView

    urlpatterns = [
        ...
        path('playground/', PlaygroundView.as_view(), name='component-playground'),
    ]
""")
        self.stdout.write(
            self.style.SUCCESS("\nThen visit http://localhost:8000/playground/ in your browser.\n")
        )
