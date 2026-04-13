"""
Fly.io deployment provider.

Provides deployment to Fly.io with automatic configuration generation.
"""

from typing import Any

import orjson
import toml

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentProvider,
    DeploymentResult,
    DeploymentStatus,
    build_start_command,
    register_provider,
)


@register_provider("fly")
class FlyioProvider(DeploymentProvider):
    """
    Fly.io deployment provider.

    Supports:
    - Automatic fly.toml generation
    - PostgreSQL database provisioning
    - Redis provisioning
    - Secrets management
    - Auto-scaling
    - Health checks
    """

    name = "fly"
    display_name = "Fly.io"

    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self.fly_config: dict[str, Any] = {}

    def validate(self) -> list[str]:
        """Validate configuration for Fly.io deployment."""
        errors = []

        # Check CLI is installed
        if not self.check_cli_installed("flyctl"):
            errors.append(
                "flyctl CLI is not installed. Install from https://fly.io/docs/hands-on/install-flyctl/"
            )

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")
        elif len(self.config.app_name) > 30:
            errors.append("app_name must be 30 characters or less")

        # Check for Django settings
        if not self.config.django_settings_module:
            errors.append("django_settings_module is required")

        return errors

    def generate_config(self) -> dict[str, str]:
        """Generate Fly.io configuration files."""
        files = {}

        # Generate fly.toml
        files["fly.toml"] = self._generate_fly_toml()

        # Generate Dockerfile
        files["Dockerfile"] = self._generate_dockerfile()

        # Generate .dockerignore
        files[".dockerignore"] = self._generate_dockerignore()

        # Generate release script
        files["release.sh"] = self._generate_release_script()

        return files

    def _generate_fly_toml(self) -> str:
        """Generate fly.toml configuration."""
        config = {
            "app": self.config.app_name,
            "primary_region": "iad",  # Default to US East
            "build": {},
            "env": {
                "PORT": str(self.config.port),
                "DJANGO_SETTINGS_MODULE": self.config.django_settings_module,
                "DJANGO_ENV": self.config.environment,
            },
            "http_service": {
                "internal_port": self.config.port,
                "force_https": True,
                "auto_stop_machines": True,
                "auto_start_machines": True,
                "min_machines_running": self.config.min_instances,
                "processes": ["app"],
            },
            "checks": {
                "health": {
                    "type": "http",
                    "path": self.config.health_check_path,
                    "interval": f"{self.config.health_check_interval}s",
                    "timeout": "5s",
                    "grace_period": "10s",
                }
            },
        }

        # Add scaling configuration
        if self.config.auto_scale:
            config["http_service"]["concurrency"] = {
                "type": "connections",
                "hard_limit": 100,
                "soft_limit": 80,
            }

        # Add deploy section
        config["deploy"] = {
            "release_command": "sh release.sh",
        }

        # Add mounts for media files if not using S3
        if not self.config.use_s3:
            config["mounts"] = [
                {
                    "source": "media_data",
                    "destination": f"/app/{self.config.media_root}",
                }
            ]

        return toml.dumps(config)

    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for Fly.io using shared DockerfileGenerator."""
        from django_matt.deploy.docker import DockerfileConfig, DockerfileGenerator

        cfg = DockerfileConfig(
            python_version=self.config.python_version,
            port=self.config.port,
            workers=self.config.workers,
            server_backend=self.config.server_backend,
            health_check_path=self.config.health_check_path,
        )
        return DockerfileGenerator(cfg).generate("production")

    def _generate_dockerignore(self) -> str:
        """Generate .dockerignore file using shared generator."""
        from django_matt.deploy.docker import generate_dockerignore

        return generate_dockerignore()

    def _generate_release_script(self) -> str:
        """Generate release script for migrations."""
        return """#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Release complete!"
"""

    async def deploy(self) -> DeploymentResult:
        """Deploy to Fly.io."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        # Validate first
        errors = self.validate()
        if errors:
            result.status = DeploymentStatus.FAILED
            result.errors = errors
            return result

        try:
            result.status = DeploymentStatus.BUILDING

            # Write configuration files
            self.write_config_files(result)

            # Check if app exists
            check_result = self.run_command(["flyctl", "apps", "list", "--json"])
            apps = orjson.loads(check_result.stdout) if check_result.returncode == 0 else []
            app_exists = any(app.get("Name") == self.config.app_name for app in apps)

            if not app_exists:
                # Create app
                result.add_log(f"Creating app: {self.config.app_name}")
                create_result = self.run_command(
                    [
                        "flyctl",
                        "apps",
                        "create",
                        self.config.app_name,
                        "--org",
                        "personal",
                    ]
                )
                if create_result.returncode != 0:
                    result.status = DeploymentStatus.FAILED
                    result.add_error(f"Failed to create app: {create_result.stderr}")
                    return result

            # Create database if needed
            if self.config.create_database and not self.config.database_url:
                result.add_log("Creating PostgreSQL database...")
                db_result = self.run_command(
                    [
                        "flyctl",
                        "postgres",
                        "create",
                        "--name",
                        f"{self.config.app_name}-db",
                        "--region",
                        "iad",
                        "--vm-size",
                        "shared-cpu-1x",
                        "--volume-size",
                        "1",
                    ]
                )
                if db_result.returncode == 0:
                    # Attach database
                    self.run_command(
                        [
                            "flyctl",
                            "postgres",
                            "attach",
                            f"{self.config.app_name}-db",
                            "--app",
                            self.config.app_name,
                        ]
                    )
                    result.add_log("Database created and attached")

            # Create Redis if needed
            if self.config.create_redis and not self.config.redis_url:
                result.add_log("Creating Redis...")
                redis_result = self.run_command(
                    [
                        "flyctl",
                        "redis",
                        "create",
                        "--name",
                        f"{self.config.app_name}-redis",
                        "--region",
                        "iad",
                    ]
                )
                if redis_result.returncode == 0:
                    result.add_log("Redis created")

            # Set secrets
            result.status = DeploymentStatus.DEPLOYING
            secrets = self.config.get_env_vars()
            if secrets:
                result.add_log("Setting secrets...")
                secrets_args = [f"{k}={v}" for k, v in secrets.items()]
                self.run_command(
                    ["flyctl", "secrets", "set", "--app", self.config.app_name] + secrets_args
                )

            # Deploy
            result.add_log("Deploying application...")
            deploy_result = self.run_command(
                [
                    "flyctl",
                    "deploy",
                    "--app",
                    self.config.app_name,
                    "--remote-only",
                ]
            )

            if deploy_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error(f"Deployment failed: {deploy_result.stderr}")
                return result

            # Get app URL
            result.status = DeploymentStatus.SUCCESS
            result.url = f"https://{self.config.app_name}.fly.dev"
            result.add_log(f"Deployment successful! App available at {result.url}")

            # Get deployment info
            info_result = self.run_command(
                ["flyctl", "info", "--app", self.config.app_name, "--json"]
            )
            if info_result.returncode == 0:
                info = orjson.loads(info_result.stdout)
                result.deployment_id = info.get("ID", "")
                result.metadata = info

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            status_result = self.run_command(
                ["flyctl", "status", "--app", self.config.app_name, "--json"]
            )

            if status_result.returncode == 0:
                status = orjson.loads(status_result.stdout)
                result.deployment_id = deployment_id
                result.metadata = status

                # Determine status from machines
                machines = status.get("Machines", [])
                if machines:
                    all_running = all(m.get("state") == "started" for m in machines)
                    result.status = (
                        DeploymentStatus.SUCCESS if all_running else DeploymentStatus.DEPLOYING
                    )
                else:
                    result.status = DeploymentStatus.PENDING

                result.url = f"https://{self.config.app_name}.fly.dev"
            else:
                result.status = DeploymentStatus.FAILED
                result.add_error(status_result.stderr)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def rollback(self, deployment_id: str) -> DeploymentResult:
        """Rollback to previous deployment."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            # Get previous release
            releases_result = self.run_command(
                ["flyctl", "releases", "--app", self.config.app_name, "--json"]
            )

            if releases_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error("Failed to get releases")
                return result

            releases = orjson.loads(releases_result.stdout)
            if len(releases) < 2:
                result.status = DeploymentStatus.FAILED
                result.add_error("No previous release to rollback to")
                return result

            # Rollback to previous version
            previous = releases[1]
            rollback_result = self.run_command(
                [
                    "flyctl",
                    "deploy",
                    "--app",
                    self.config.app_name,
                    "--image",
                    previous.get("ImageRef", ""),
                ]
            )

            if rollback_result.returncode == 0:
                result.status = DeploymentStatus.SUCCESS
                result.url = f"https://{self.config.app_name}.fly.dev"
                result.add_log(f"Rolled back to version {previous.get('Version', 'unknown')}")
            else:
                result.status = DeploymentStatus.FAILED
                result.add_error(rollback_result.stderr)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def scale(self, instances: int) -> DeploymentResult:
        """Scale the application."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            scale_result = self.run_command(
                [
                    "flyctl",
                    "scale",
                    "count",
                    str(instances),
                    "--app",
                    self.config.app_name,
                ]
            )

            if scale_result.returncode == 0:
                result.status = DeploymentStatus.SUCCESS
                result.add_log(f"Scaled to {instances} instances")
            else:
                result.status = DeploymentStatus.FAILED
                result.add_error(scale_result.stderr)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_logs(self, lines: int = 100) -> list[str]:
        """Get application logs."""
        result = self.run_command(
            [
                "flyctl",
                "logs",
                "--app",
                self.config.app_name,
                "--no-tail",
            ]
        )

        if result.returncode == 0:
            return result.stdout.split("\n")[-lines:]
        return []


__all__ = ["FlyioProvider"]
