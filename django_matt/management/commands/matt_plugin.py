"""Management command for django-matt plugin operations.

Usage:
    python manage.py matt_plugin list
    python manage.py matt_plugin info <name>
    python manage.py matt_plugin create <name> [--author <author>] [--output <dir>]
    python manage.py matt_plugin check
    python manage.py matt_plugin enable <name>
    python manage.py matt_plugin disable <name>
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Manage django-matt plugins"

    def add_arguments(self, parser: Any) -> None:
        subparsers = parser.add_subparsers(dest="subcommand")

        # list
        subparsers.add_parser("list", help="List installed plugins")

        # info
        info_parser = subparsers.add_parser("info", help="Show plugin details")
        info_parser.add_argument("name", type=str)

        # create
        create_parser = subparsers.add_parser("create", help="Scaffold a new plugin")
        create_parser.add_argument("name", type=str)
        create_parser.add_argument("--author", type=str, default="")
        create_parser.add_argument(
            "--output", type=str, default=".", help="Output directory"
        )
        create_parser.add_argument("--description", type=str, default="")

        # check
        subparsers.add_parser("check", help="Validate all plugins")

        # enable
        enable_parser = subparsers.add_parser("enable", help="Enable a plugin")
        enable_parser.add_argument("name", type=str)

        # disable
        disable_parser = subparsers.add_parser("disable", help="Disable a plugin")
        disable_parser.add_argument("name", type=str)

    def handle(self, *args: Any, **options: Any) -> str | None:
        subcommand = options.get("subcommand")
        if not subcommand:
            self.stderr.write("Usage: matt_plugin <list|info|create|check|enable|disable>")
            return None

        handler = getattr(self, f"_handle_{subcommand}", None)
        if handler:
            return handler(**options)

        self.stderr.write(f"Unknown subcommand: {subcommand}")
        return None

    def _handle_list(self, **options: Any) -> None:
        from django_matt.plugins.registry import get_plugin_registry

        registry = get_plugin_registry()
        plugins = registry.list_plugins()

        if not plugins:
            self.stdout.write("No plugins registered.")
            return

        self.stdout.write(
            f"{'Name':<25} {'Version':<10} {'Status':<12} {'Dependencies'}"
        )
        self.stdout.write("-" * 75)

        for plugin in plugins:
            status = registry.get_status(plugin.name).value
            deps = ", ".join(plugin.dependencies) if plugin.dependencies else "-"
            self.stdout.write(
                f"{plugin.name:<25} {plugin.version:<10} {status:<12} {deps}"
            )

    def _handle_info(self, **options: Any) -> None:
        from django_matt.plugins.registry import (
            PluginNotFoundError,
            get_plugin_registry,
        )

        name = options["name"]
        registry = get_plugin_registry()

        try:
            plugin = registry.get_plugin(name)
        except PluginNotFoundError:
            self.stderr.write(f"Plugin {name!r} not found.")
            return

        status = registry.get_status(name)
        error = registry.get_error(name)

        self.stdout.write(f"Name:         {plugin.name}")
        self.stdout.write(f"Version:      {plugin.version}")
        self.stdout.write(f"Description:  {plugin.description}")
        self.stdout.write(f"Author:       {plugin.author}")
        self.stdout.write(f"Class:        {plugin.__class__.__qualname__}")
        self.stdout.write(f"Status:       {status.value}")
        self.stdout.write(f"Min version:  {plugin.django_matt_version}")
        self.stdout.write(f"Settings:     {plugin.settings_prefix or 'none'}")
        self.stdout.write(
            f"Dependencies: {', '.join(plugin.dependencies) or 'none'}"
        )
        self.stdout.write(f"URLs:         {len(plugin.get_urls())} patterns")
        self.stdout.write(f"Middleware:    {len(plugin.get_middleware())} classes")

        if error:
            self.stdout.write(f"Error:        {error}")

        checks = plugin.check()
        if checks:
            self.stdout.write(f"Checks:       {len(checks)} issues")
            for check in checks:
                self.stdout.write(f"  [{check.level}] {check.msg}")

    def _handle_create(self, **options: Any) -> None:
        from django_matt.plugins.scaffold import PluginScaffolder

        scaffolder = PluginScaffolder(
            name=options["name"],
            author=options.get("author", ""),
            description=options.get("description", ""),
        )
        created = scaffolder.generate(options["output"])

        self.stdout.write(f"Created plugin project: {options['name']}")
        for f in created:
            self.stdout.write(f"  {f}")

    def _handle_check(self, **options: Any) -> None:
        from django_matt.plugins.registry import get_plugin_registry

        registry = get_plugin_registry()
        plugins = registry.list_plugins()
        issues: list[str] = []

        for plugin in plugins:
            # Check dependencies
            for dep in plugin.dependencies:
                if not registry.is_registered(dep):
                    issues.append(
                        f"Plugin {plugin.name!r} depends on {dep!r}, "
                        f"which is not registered"
                    )

            # Run plugin checks
            checks = plugin.check()
            for check in checks:
                if check.is_serious():
                    issues.append(
                        f"Plugin {plugin.name!r}: [{check.level}] {check.msg}"
                    )

            # Check for errors
            error = registry.get_error(plugin.name)
            if error:
                issues.append(f"Plugin {plugin.name!r}: {error}")

        if not issues:
            self.stdout.write("All plugins OK.")
        else:
            for issue in issues:
                self.stderr.write(f"  ERROR: {issue}")

    def _handle_enable(self, **options: Any) -> None:
        from django_matt.plugins.registry import (
            PluginNotFoundError,
            get_plugin_registry,
        )

        name = options["name"]
        registry = get_plugin_registry()

        try:
            registry.enable(name)
            self.stdout.write(f"Enabled plugin: {name}")
        except PluginNotFoundError:
            self.stderr.write(f"Plugin {name!r} not found.")

    def _handle_disable(self, **options: Any) -> None:
        from django_matt.plugins.registry import (
            PluginNotFoundError,
            get_plugin_registry,
        )

        name = options["name"]
        registry = get_plugin_registry()

        try:
            registry.disable(name)
            self.stdout.write(f"Disabled plugin: {name}")
        except PluginNotFoundError:
            self.stderr.write(f"Plugin {name!r} not found.")
