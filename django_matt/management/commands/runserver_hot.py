import os
import sys

from django.core.management.base import BaseCommand

from django_matt.dev.hot_reload import run_hot_reload


class Command(BaseCommand):
    """
    Management command to run the development server with hot reloading.

    This command starts the Django development server with hot reloading enabled,
    which automatically reloads the server when Python files change and refreshes
    the browser when static files change.
    """

    help = "Runs the development server with hot reloading enabled"

    def add_arguments(self, parser):
        parser.add_argument(
            "addrport",
            nargs="?",
            default="8000",
            help="Optional port number, or ipaddr:port",
        )
        parser.add_argument(
            "--noreload",
            action="store_true",
            dest="noreload",
            help="Disables hot reloading entirely",
        )
        parser.add_argument(
            "--nothreading",
            action="store_true",
            dest="nothreading",
            help="Tells Django to NOT use threading",
        )
        parser.add_argument(
            "--ipv6",
            "-6",
            action="store_true",
            dest="use_ipv6",
            help="Tells Django to use an IPv6 address",
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
        # Set environment variables
        os.environ["DJANGO_DEBUG"] = "True"
        os.environ["LIVE_RELOAD_HOST"] = options["websocket_host"]
        os.environ["LIVE_RELOAD_PORT"] = str(options["websocket_port"])

        # If noreload is specified, just run the regular runserver command
        if options["noreload"]:
            from django.core.management import call_command

            call_command(
                "runserver",
                options["addrport"],
                use_threading=not options["nothreading"],
                use_ipv6=options["use_ipv6"],
            )
            return

        # Parse the address and port
        if ":" in options["addrport"]:
            addr, port = options["addrport"].split(":")
        else:
            addr, port = "127.0.0.1", options["addrport"]

        # Build the server command
        server_command = [
            sys.executable,
            "manage.py",
            "runserver",
            "--noreload",  # We handle reloading ourselves
        ]

        if options["nothreading"]:
            server_command.append("--nothreading")

        if options["use_ipv6"]:
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

        run_hot_reload(project_dir=os.getcwd(), server_command=server_command)
