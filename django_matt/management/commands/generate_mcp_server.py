"""
Management command to generate an MCP server from project introspection.

Usage:
    python manage.py generate_mcp_server
    python manage.py generate_mcp_server --output my_mcp_server.py
    python manage.py generate_mcp_server --base-url https://api.example.com
    python manage.py generate_mcp_server --name my-project --dry-run
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Generate an MCP server from project introspection for LLM tool integration."""

    help = "Generate an MCP (Model Context Protocol) server from project introspection"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            default="mcp_server.py",
            help="Output file path (default: mcp_server.py)",
        )
        parser.add_argument(
            "--base-url",
            default="http://localhost:8000",
            help="Base URL of the Django API server (default: http://localhost:8000)",
        )
        parser.add_argument(
            "--name",
            default=None,
            help="MCP server name (default: auto-detected from project)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print generated code to stdout instead of writing to file",
        )

    def handle(self, *args, **options):
        """Generate MCP server code from project introspection."""
        from django_matt.ai.context.mcp import generate_mcp_server, write_mcp_server

        base_url = options["base_url"]
        server_name = options["name"]
        output = options["output"]
        dry_run = options["dry_run"]

        self.stdout.write("Introspecting project...")

        if dry_run:
            content = generate_mcp_server(
                base_url=base_url,
                server_name=server_name,
            )
            self.stdout.write(content)
        else:
            path = write_mcp_server(
                output_path=output,
                base_url=base_url,
                server_name=server_name,
            )
            self.stdout.write(self.style.SUCCESS(f"MCP server written to {path}"))
            self.stdout.write("\nTo run:")
            self.stdout.write("  uv add mcp httpx")
            self.stdout.write(f"  python {path}")
            self.stdout.write("\nTo configure in Claude Desktop / Cursor:")
            self.stdout.write(f'  "command": "python", "args": ["{path}"]')
