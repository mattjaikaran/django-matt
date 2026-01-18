"""
Deployment management command.

Provides CLI tools for deploying Django applications to various platforms.

Usage:
    # Deploy to a platform
    python manage.py deploy --platform fly
    python manage.py deploy --platform railway
    python manage.py deploy --platform render

    # Generate configuration files only
    python manage.py deploy config --platform fly
    python manage.py deploy config --platform docker

    # Initialize Docker setup
    python manage.py deploy docker --mode production

    # Manage environments
    python manage.py deploy env init --domain example.com
    python manage.py deploy env list
    python manage.py deploy env validate

    # Health check endpoints info
    python manage.py deploy health
"""

import asyncio
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Deploy Django application to cloud platforms"

    def add_arguments(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(dest="subcommand", help="Deployment subcommands")

        # Main deploy command (default)
        parser.add_argument(
            "--platform",
            "-p",
            choices=["fly", "railway", "render", "digitalocean", "aws", "hetzner"],
            help="Target deployment platform",
        )
        parser.add_argument("--app-name", help="Application name")
        parser.add_argument("--settings-module", help="Django settings module")
        parser.add_argument("--dry-run", action="store_true", help="Generate config without deploying")

        # Config subcommand
        config_parser = subparsers.add_parser("config", help="Generate platform configuration")
        config_parser.add_argument(
            "--platform",
            "-p",
            required=True,
            choices=["fly", "railway", "render", "digitalocean", "aws", "hetzner", "docker"],
            help="Target platform",
        )
        config_parser.add_argument("--output", "-o", help="Output directory")
        config_parser.add_argument("--app-name", help="Application name")

        # Docker subcommand
        docker_parser = subparsers.add_parser("docker", help="Generate Docker configuration")
        docker_parser.add_argument(
            "--mode",
            "-m",
            choices=["production", "development", "multistage"],
            default="production",
            help="Docker configuration mode",
        )
        docker_parser.add_argument("--output", "-o", help="Output directory")
        docker_parser.add_argument("--include-db", action="store_true", default=True, help="Include PostgreSQL")
        docker_parser.add_argument("--include-redis", action="store_true", help="Include Redis")
        docker_parser.add_argument("--include-celery", action="store_true", help="Include Celery workers")
        docker_parser.add_argument("--proxy", choices=["caddy", "nginx", "none"], default="caddy", help="Reverse proxy")
        docker_parser.add_argument("--domain", help="Domain for SSL")

        # Env subcommand
        env_parser = subparsers.add_parser("env", help="Manage deployment environments")
        env_subparsers = env_parser.add_subparsers(dest="env_action", help="Environment actions")

        # env init
        env_init = env_subparsers.add_parser("init", help="Initialize environments")
        env_init.add_argument("--domain", required=True, help="Production domain")
        env_init.add_argument("--output", "-o", help="Output directory for env files")

        # env list
        env_subparsers.add_parser("list", help="List configured environments")

        # env validate
        env_validate = env_subparsers.add_parser("validate", help="Validate environment configurations")
        env_validate.add_argument("--env", help="Specific environment to validate")

        # env generate
        env_generate = env_subparsers.add_parser("generate", help="Generate .env files")
        env_generate.add_argument("--output", "-o", help="Output directory")

        # Health subcommand
        health_parser = subparsers.add_parser("health", help="Health check endpoint information")
        health_parser.add_argument("--urls", action="store_true", help="Show URL configuration")

        # Status subcommand
        status_parser = subparsers.add_parser("status", help="Check deployment status")
        status_parser.add_argument("--platform", "-p", required=True, help="Platform to check")
        status_parser.add_argument("--deployment-id", help="Specific deployment ID")

        # Logs subcommand
        logs_parser = subparsers.add_parser("logs", help="View deployment logs")
        logs_parser.add_argument("--platform", "-p", required=True, help="Platform")
        logs_parser.add_argument("--lines", "-n", type=int, default=100, help="Number of lines")

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")

        if subcommand == "config":
            self.handle_config(**options)
        elif subcommand == "docker":
            self.handle_docker(**options)
        elif subcommand == "env":
            self.handle_env(**options)
        elif subcommand == "health":
            self.handle_health(**options)
        elif subcommand == "status":
            self.handle_status(**options)
        elif subcommand == "logs":
            self.handle_logs(**options)
        elif options.get("platform"):
            self.handle_deploy(**options)
        else:
            self.print_help()

    def print_help(self):
        """Print help information."""
        self.stdout.write(self.style.SUCCESS("\nDjango Matt Deployment Tool\n"))
        self.stdout.write("Usage:\n")
        self.stdout.write("  python manage.py deploy --platform <platform>  Deploy to platform\n")
        self.stdout.write("  python manage.py deploy config --platform <platform>  Generate config\n")
        self.stdout.write("  python manage.py deploy docker [--mode production]  Docker setup\n")
        self.stdout.write("  python manage.py deploy env init --domain example.com  Initialize environments\n")
        self.stdout.write("  python manage.py deploy health  Health check info\n")
        self.stdout.write("\nSupported platforms: fly, railway, render, digitalocean, aws, hetzner\n")

    def handle_deploy(self, **options):
        """Handle main deploy command."""
        from django_matt.deploy import (
            DeploymentConfig,
            get_provider,
        )

        platform = options["platform"]
        app_name = options.get("app_name") or self._get_app_name()
        settings_module = options.get("settings_module") or getattr(settings, "SETTINGS_MODULE", "config.settings")
        dry_run = options.get("dry_run", False)

        self.stdout.write(f"\nDeploying to {platform.upper()}...\n")

        # Create config
        config = DeploymentConfig(
            app_name=app_name,
            project_dir=Path.cwd(),
            django_settings_module=settings_module,
        )

        try:
            provider = get_provider(platform, config)
        except ValueError as e:
            raise CommandError(str(e))

        # Validate
        errors = provider.validate()
        if errors:
            self.stdout.write(self.style.ERROR("\nValidation errors:"))
            for error in errors:
                self.stdout.write(f"  - {error}")
            raise CommandError("Validation failed")

        if dry_run:
            # Just generate config files
            self.stdout.write("\nGenerating configuration files (dry run)...\n")
            configs = provider.generate_config()
            for filename, content in configs.items():
                self.stdout.write(f"  Generated: {filename}")
            self.stdout.write(self.style.SUCCESS("\nDry run complete. No deployment made."))
            return

        # Deploy
        self.stdout.write("\nStarting deployment...\n")
        result = asyncio.run(provider.deploy())

        # Show results
        for log in result.logs:
            self.stdout.write(f"  {log}")

        if result.errors:
            self.stdout.write(self.style.ERROR("\nErrors:"))
            for error in result.errors:
                self.stdout.write(f"  - {error}")

        if result.success:
            self.stdout.write(self.style.SUCCESS(f"\nDeployment successful!"))
            if result.url:
                self.stdout.write(f"URL: {result.url}")
        else:
            raise CommandError(f"Deployment failed: {result.status}")

    def handle_config(self, **options):
        """Handle config generation."""
        from django_matt.deploy import (
            DeploymentConfig,
            get_provider,
        )
        from django_matt.deploy.docker import DockerfileGenerator, ComposeGenerator

        platform = options["platform"]
        output_dir = Path(options.get("output") or ".")
        app_name = options.get("app_name") or self._get_app_name()

        self.stdout.write(f"\nGenerating {platform} configuration...\n")

        if platform == "docker":
            # Use Docker generators directly
            dockerfile_gen = DockerfileGenerator()
            compose_gen = ComposeGenerator(app_name=app_name)

            files = {
                "Dockerfile": dockerfile_gen.generate("production"),
                "Dockerfile.dev": dockerfile_gen.generate("development"),
                "docker-compose.yml": compose_gen.generate("production"),
                "docker-compose.dev.yml": compose_gen.generate("development"),
                "Caddyfile": compose_gen.generate_caddyfile(),
                ".dockerignore": compose_gen.generate_dockerignore(),
            }
        else:
            config = DeploymentConfig(
                app_name=app_name,
                project_dir=Path.cwd(),
                django_settings_module=getattr(settings, "SETTINGS_MODULE", "config.settings"),
            )
            provider = get_provider(platform, config)
            files = provider.generate_config()

        # Write files
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            file_path = output_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            self.stdout.write(f"  Created: {file_path}")

        self.stdout.write(self.style.SUCCESS(f"\nConfiguration files generated in {output_dir}"))

    def handle_docker(self, **options):
        """Handle Docker configuration generation."""
        from django_matt.deploy.docker import DockerfileGenerator, DockerfileConfig, ComposeGenerator

        mode = options["mode"]
        output_dir = Path(options.get("output") or ".")
        include_db = options.get("include_db", True)
        include_redis = options.get("include_redis", False)
        include_celery = options.get("include_celery", False)
        proxy = options.get("proxy", "caddy")
        domain = options.get("domain")

        app_name = self._get_app_name()

        self.stdout.write(f"\nGenerating Docker configuration ({mode} mode)...\n")

        # Generate Dockerfile
        dockerfile_config = DockerfileConfig(
            wsgi_module=f"{app_name}.wsgi:application",
            asgi_module=f"{app_name}.asgi:application",
        )
        dockerfile_gen = DockerfileGenerator(dockerfile_config)

        # Generate docker-compose
        compose_gen = ComposeGenerator(
            app_name=app_name,
            include_db=include_db,
            include_redis=include_redis,
            include_celery=include_celery,
            include_proxy=proxy != "none",
            proxy_type=proxy if proxy != "none" else "caddy",
            domain=domain,
        )

        files = {
            "Dockerfile": dockerfile_gen.generate(mode),
            "docker-compose.yml": compose_gen.generate(mode),
            ".dockerignore": compose_gen.generate_dockerignore(),
        }

        if mode == "development":
            files["Dockerfile.dev"] = dockerfile_gen.generate("development")
            files["docker-compose.dev.yml"] = compose_gen.generate("development")

        if proxy == "caddy":
            files["Caddyfile"] = compose_gen.generate_caddyfile()
        elif proxy == "nginx":
            files["nginx.conf"] = compose_gen.generate_nginx_conf()

        # Write files
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            file_path = output_dir / filename
            with open(file_path, "w") as f:
                f.write(content)
            self.stdout.write(f"  Created: {file_path}")

        self.stdout.write(self.style.SUCCESS("\nDocker configuration generated!"))
        self.stdout.write("\nTo start:")
        self.stdout.write("  docker-compose up -d --build")

    def handle_env(self, **options):
        """Handle environment management."""
        from django_matt.deploy.environments import EnvironmentManager, EnvironmentConfig

        action = options.get("env_action")

        if action == "init":
            domain = options["domain"]
            output_dir = Path(options.get("output") or "envs")

            self.stdout.write(f"\nInitializing environments for {domain}...\n")

            manager = EnvironmentManager()
            manager.init_standard_environments(domain)

            # Generate files
            output_dir.mkdir(exist_ok=True)
            manager.generate_env_files(output_dir)

            for env_name in manager.list_environments():
                self.stdout.write(f"  Created: {output_dir}/.env.{env_name}")

            self.stdout.write(self.style.SUCCESS(f"\nEnvironments initialized!"))
            self.stdout.write("\nRemember to:")
            self.stdout.write("  1. Fill in the SECRET_KEY in each .env file")
            self.stdout.write("  2. Update database credentials")
            self.stdout.write("  3. Never commit .env files to git")

        elif action == "list":
            manager = EnvironmentManager()
            manager.init_standard_environments("example.com")

            self.stdout.write("\nConfigured environments:\n")
            for name in manager.list_environments():
                config = manager.get(name)
                self.stdout.write(f"  {name}: {config.display_name}")
                self.stdout.write(f"    DEBUG: {config.debug}")
                self.stdout.write(f"    LOG_LEVEL: {config.log_level}")

        elif action == "validate":
            env_name = options.get("env")
            manager = EnvironmentManager()
            manager.init_standard_environments("example.com")

            if env_name:
                errors = manager.validate(env_name)
                if errors:
                    self.stdout.write(self.style.ERROR(f"\n{env_name} validation errors:"))
                    for error in errors:
                        self.stdout.write(f"  - {error}")
                else:
                    self.stdout.write(self.style.SUCCESS(f"\n{env_name}: Valid"))
            else:
                all_errors = manager.validate_all()
                has_errors = False
                for name, errors in all_errors.items():
                    if errors:
                        has_errors = True
                        self.stdout.write(self.style.ERROR(f"\n{name}:"))
                        for error in errors:
                            self.stdout.write(f"  - {error}")
                    else:
                        self.stdout.write(self.style.SUCCESS(f"\n{name}: Valid"))

                if has_errors:
                    raise CommandError("Validation failed")

        elif action == "generate":
            output_dir = Path(options.get("output") or "envs")
            manager = EnvironmentManager()
            manager.init_standard_environments("example.com")
            manager.generate_env_files(output_dir)
            self.stdout.write(self.style.SUCCESS(f"\nGenerated .env files in {output_dir}"))

        else:
            self.stdout.write("Usage: python manage.py deploy env <init|list|validate|generate>")

    def handle_health(self, **options):
        """Handle health check information."""
        show_urls = options.get("urls", False)

        self.stdout.write(self.style.SUCCESS("\nHealth Check Endpoints\n"))
        self.stdout.write("Django Matt provides built-in health check endpoints:\n")
        self.stdout.write("  /health/  - Full health check (database, cache, custom checks)")
        self.stdout.write("  /ready/   - Kubernetes readiness probe")
        self.stdout.write("  /live/    - Kubernetes liveness probe\n")

        if show_urls:
            self.stdout.write("\nAdd to your urls.py:\n")
            self.stdout.write("""
from django_matt.deploy.health import get_health_urls

urlpatterns = [
    # ... your other urls ...
    *get_health_urls(),
]
""")
        else:
            self.stdout.write("\nUsage in urls.py:")
            self.stdout.write("  from django_matt.deploy.health import get_health_urls")
            self.stdout.write("  urlpatterns = [..., *get_health_urls()]")

        self.stdout.write("\nCustom health checks:")
        self.stdout.write("""
from django_matt.deploy.health import health_check, CheckResult, HealthStatus

@health_check("my_service")
def check_my_service():
    # Check your service
    return CheckResult(
        name="my_service",
        status=HealthStatus.HEALTHY,
        message="Service is up",
    )
""")

    def handle_status(self, **options):
        """Handle deployment status check."""
        from django_matt.deploy import DeploymentConfig, get_provider

        platform = options["platform"]
        deployment_id = options.get("deployment_id")

        config = DeploymentConfig(
            app_name=self._get_app_name(),
            project_dir=Path.cwd(),
        )

        provider = get_provider(platform, config)
        result = asyncio.run(provider.get_status(deployment_id or ""))

        self.stdout.write(f"\nDeployment Status: {result.status.value}")
        if result.url:
            self.stdout.write(f"URL: {result.url}")
        if result.metadata:
            self.stdout.write("\nMetadata:")
            for key, value in result.metadata.items():
                self.stdout.write(f"  {key}: {value}")

    def handle_logs(self, **options):
        """Handle log viewing."""
        from django_matt.deploy import DeploymentConfig, get_provider

        platform = options["platform"]
        lines = options.get("lines", 100)

        config = DeploymentConfig(
            app_name=self._get_app_name(),
            project_dir=Path.cwd(),
        )

        provider = get_provider(platform, config)
        logs = asyncio.run(provider.get_logs(lines))

        self.stdout.write(f"\nLast {lines} lines:\n")
        for line in logs:
            self.stdout.write(line)

    def _get_app_name(self) -> str:
        """Get application name from settings or directory."""
        # Try to get from settings
        if hasattr(settings, "APP_NAME"):
            return settings.APP_NAME

        # Try to get from project directory name
        project_dir = Path.cwd()

        # Look for manage.py to find project root
        if (project_dir / "manage.py").exists():
            return project_dir.name.lower().replace(" ", "-").replace("_", "-")

        return "django-app"
