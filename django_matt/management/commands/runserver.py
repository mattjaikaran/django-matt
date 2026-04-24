"""
Enhanced runserver command with hot reloading enabled by default.

This overrides Django's built-in runserver to add hot reloading support.
Hot reloading automatically refreshes the browser when files change.

Usage:
    python manage.py runserver              # Hot reload enabled (default)
    python manage.py runserver --no-hot     # Standard Django behavior
    python manage.py runserver 8080         # Custom port with hot reload
"""

import os
import sys

from django.core.management.commands.runserver import Command as BaseRunserverCommand


class Command(BaseRunserverCommand):
    """
    Enhanced runserver with hot reloading enabled by default.

    This provides the standard Django runserver functionality plus:
    - Automatic browser refresh on file changes
    - WebSocket-based live reloading
    - Configurable hot reload settings

    Use --no-hot to disable hot reloading and get standard Django behavior.
    """

    help = "Starts the development server with hot reloading enabled by default"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--no-hot",
            action="store_true",
            dest="no_hot",
            help="Disable hot reloading (use standard Django runserver)",
        )
        parser.add_argument(
            "--websocket-host",
            default="localhost",
            help="Host for the WebSocket server (default: localhost)",
        )
        parser.add_argument(
            "--websocket-port",
            type=int,
            default=35729,
            help="Port for the WebSocket server (default: 35729)",
        )

    def handle(self, *args, **options):
        """Start the server, delegating to hot reload or standard runserver."""
        # If --no-hot is specified or --noreload is used, run standard Django runserver
        if options.get("no_hot") or options.get("use_reloader") is False:
            return super().handle(*args, **options)

        # Set environment variables for hot reload
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ["LIVE_RELOAD_HOST"] = options["websocket_host"]
        os.environ["LIVE_RELOAD_PORT"] = str(options["websocket_port"])

        # Import hot reload module
        try:
            from django_matt.dev.hot_reload import run_hot_reload
        except ImportError:
            self.stderr.write(
                self.style.WARNING(
                    "Hot reload module not available. Falling back to standard runserver."
                )
            )
            return super().handle(*args, **options)

        # Parse the address and port
        addrport = options.get("addrport") or "8000"
        if ":" in addrport:
            addr, port = addrport.split(":")
        else:
            addr, port = "127.0.0.1", addrport

        # Build the server command (we need to bypass ourselves to avoid recursion)
        server_command = [
            sys.executable,
            "manage.py",
            "runserver",
            "--no-hot",  # Use our flag to prevent recursion
            "--noreload",  # We handle reloading ourselves
        ]

        if options.get("nothreading"):
            server_command.append("--nothreading")

        if options.get("use_ipv6"):
            server_command.append("--ipv6")

        server_command.append(f"{addr}:{port}")

        # Run the hot reloader
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting development server with hot reloading at http://{addr}:{port}/"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"WebSocket server for live reloading at ws://{options['websocket_host']}:{options['websocket_port']}/"
            )
        )
        self.stdout.write(self.style.NOTICE("Use --no-hot to disable hot reloading"))
        self.stdout.write("")

        run_hot_reload(project_dir=os.getcwd(), server_command=server_command)
