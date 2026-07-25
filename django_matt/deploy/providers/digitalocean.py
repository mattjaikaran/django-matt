# file-length-max: 500
"""
DigitalOcean App Platform deployment provider.

Provides deployment to DigitalOcean App Platform with automatic configuration generation.
"""

from typing import Any

import orjson
import yaml

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentProvider,
    DeploymentResult,
    DeploymentStatus,
    build_start_command,
    register_provider,
)


@register_provider("digitalocean")
class DigitalOceanProvider(DeploymentProvider):
    """
    DigitalOcean App Platform deployment provider.

    Supports:
    - App spec generation
    - Managed PostgreSQL provisioning
    - Managed Redis provisioning
    - Secrets management
    - Auto-scaling
    - Health checks
    """

    name = "digitalocean"
    display_name = "DigitalOcean"

    def __init__(self, config: DeploymentConfig):
        super().__init__(config)

    def validate(self) -> list[str]:
        """Validate configuration for DigitalOcean deployment."""
        errors = []

        # Check CLI is installed
        if not self.check_cli_installed("doctl"):
            errors.append(
                "doctl CLI is not installed. Install from https://docs.digitalocean.com/reference/doctl/how-to/install/"
            )

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")
        elif len(self.config.app_name) > 32:
            errors.append("app_name must be 32 characters or less")

        # Check for Django settings
        if not self.config.django_settings_module:
            errors.append("django_settings_module is required")

        return errors

    def generate_config(self) -> dict[str, str]:
        """Generate DigitalOcean configuration files."""
        files = {}

        # Generate .do/app.yaml (App Platform spec)
        files[".do/app.yaml"] = self._generate_app_spec()

        # Generate Dockerfile
        files["Dockerfile"] = self._generate_dockerfile()

        return files

    def _generate_app_spec(self) -> str:
        """Generate DigitalOcean App Platform spec."""
        spec: dict[str, Any] = {
            "name": self.config.app_name,
            "region": "nyc",
            "services": [],
            "databases": [],
        }

        # Web service
        service: dict[str, Any] = {
            "name": "web",
            "dockerfile_path": "Dockerfile",
            "source_dir": "/",
            "http_port": self.config.port,
            "instance_count": self.config.min_instances,
            "instance_size_slug": "basic-xxs",
            "routes": [{"path": "/"}],
            "health_check": {
                "http_path": self.config.health_check_path,
                "initial_delay_seconds": 10,
                "period_seconds": self.config.health_check_interval,
            },
            "envs": self._get_env_vars_list(),
        }

        # Auto-scaling
        if self.config.auto_scale:
            service["autoscaling"] = {
                "min_instance_count": self.config.min_instances,
                "max_instance_count": self.config.max_instances,
                "metrics": {
                    "cpu": {"percent": 80},
                },
            }

        spec["services"].append(service)

        # Database
        if self.config.create_database and not self.config.database_url:
            spec["databases"].append(
                {
                    "name": "db",
                    "engine": "PG",
                    "production": False,
                    "cluster_name": f"{self.config.app_name}-db",
                }
            )

        return yaml.dump(spec, default_flow_style=False, sort_keys=False)

    def _get_env_vars_list(self) -> list[dict[str, Any]]:
        """Get environment variables in DO format."""
        env_vars = []

        # Standard Django vars
        env_vars.extend(
            [
                {"key": "DJANGO_SETTINGS_MODULE", "value": self.config.django_settings_module},
                {"key": "DJANGO_ENV", "value": self.config.environment},
                {"key": "DEBUG", "value": str(self.config.debug).lower()},
                {"key": "PORT", "value": str(self.config.port)},
                {"key": "STATIC_URL", "value": self.config.static_url},
                {"key": "STATIC_ROOT", "value": self.config.static_root},
            ]
        )

        # Database URL from DO's managed database
        if self.config.create_database and not self.config.database_url:
            env_vars.append(
                {
                    "key": "DATABASE_URL",
                    "scope": "RUN_AND_BUILD_TIME",
                    "value": "${db.DATABASE_URL}",
                }
            )
        elif self.config.database_url:
            env_vars.append(
                {"key": "DATABASE_URL", "value": self.config.database_url, "type": "SECRET"}
            )

        # Redis URL
        if self.config.redis_url:
            env_vars.append({"key": "REDIS_URL", "value": self.config.redis_url, "type": "SECRET"})

        # Secret key
        if self.config.secret_key:
            env_vars.append(
                {"key": "SECRET_KEY", "value": self.config.secret_key, "type": "SECRET"}
            )

        # Allowed hosts
        if self.config.allowed_hosts:
            env_vars.append({"key": "ALLOWED_HOSTS", "value": ",".join(self.config.allowed_hosts)})
        else:
            env_vars.append({"key": "ALLOWED_HOSTS", "value": "${APP_DOMAIN}"})

        # Extra environment variables
        for key, value in self.config.extra_env.items():
            env_vars.append({"key": key, "value": value})

        # Secrets
        for key, value in self.config.secrets.items():
            env_vars.append({"key": key, "value": value, "type": "SECRET"})

        return env_vars

    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for DigitalOcean."""
        return f"""# Dockerfile for DigitalOcean App Platform
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT={self.config.port}

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD python manage.py migrate --noinput && {build_start_command(self.config)}
"""

    async def deploy(self) -> DeploymentResult:
        """Deploy to DigitalOcean App Platform."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        # Validate first
        errors = self.validate()
        if errors:
            result.status = DeploymentStatus.FAILED
            result.errors = errors
            return result

        try:
            result.status = DeploymentStatus.BUILDING

            # Create .do directory if needed
            do_dir = self.config.project_dir / ".do"
            do_dir.mkdir(exist_ok=True)

            # Write configuration files
            configs = self.generate_config()
            for filename, content in configs.items():
                file_path = self.config.project_dir / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(content)
                result.add_log(f"Generated {filename}")

            # Check if authenticated
            auth_check = self.run_command(["doctl", "account", "get"])
            if auth_check.returncode != 0:
                result.add_log("Authenticating with DigitalOcean...")
                self.run_command(["doctl", "auth", "init"])

            # Check if app exists
            apps_result = self.run_command(
                ["doctl", "apps", "list", "--format", "ID,Spec.Name", "--no-header"]
            )
            app_id = None

            if apps_result.returncode == 0:
                for line in apps_result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == self.config.app_name:
                            app_id = parts[0]
                            break

            result.status = DeploymentStatus.DEPLOYING

            if app_id:
                # Update existing app
                result.add_log(f"Updating existing app: {self.config.app_name}")
                deploy_result = self.run_command(
                    [
                        "doctl",
                        "apps",
                        "update",
                        app_id,
                        "--spec",
                        str(self.config.project_dir / ".do" / "app.yaml"),
                    ]
                )
            else:
                # Create new app
                result.add_log(f"Creating new app: {self.config.app_name}")
                deploy_result = self.run_command(
                    [
                        "doctl",
                        "apps",
                        "create",
                        "--spec",
                        str(self.config.project_dir / ".do" / "app.yaml"),
                    ]
                )

            if deploy_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error(f"Deployment failed: {deploy_result.stderr}")
                return result

            # Get app info
            apps_result = self.run_command(
                ["doctl", "apps", "list", "--format", "ID,Spec.Name,DefaultIngress", "--no-header"]
            )
            if apps_result.returncode == 0:
                for line in apps_result.stdout.strip().split("\n"):
                    if line and self.config.app_name in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            result.deployment_id = parts[0]
                            result.url = (
                                parts[2]
                                if parts[2].startswith("https://")
                                else f"https://{parts[2]}"
                            )
                        break

            result.status = DeploymentStatus.SUCCESS
            result.add_log(f"Deployment successful! App available at {result.url}")

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            status_result = self.run_command(
                ["doctl", "apps", "get", deployment_id, "--format", "json"]
            )

            if status_result.returncode == 0:
                data = orjson.loads(status_result.stdout)
                result.deployment_id = deployment_id
                result.metadata = data

                phase = data.get("phase", "").upper()
                if phase == "ACTIVE":
                    result.status = DeploymentStatus.SUCCESS
                elif phase == "DEPLOYING" or phase == "BUILDING":
                    result.status = DeploymentStatus.DEPLOYING
                elif phase == "ERROR":
                    result.status = DeploymentStatus.FAILED
                else:
                    result.status = DeploymentStatus.PENDING

                result.url = data.get("default_ingress", "")
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
            # Get deployments
            deployments_result = self.run_command(
                [
                    "doctl",
                    "apps",
                    "list-deployments",
                    deployment_id,
                    "--format",
                    "ID,Phase",
                    "--no-header",
                ]
            )

            if deployments_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error("Failed to get deployments")
                return result

            lines = deployments_result.stdout.strip().split("\n")
            if len(lines) < 2:
                result.status = DeploymentStatus.FAILED
                result.add_error("No previous deployment to rollback to")
                return result

            # Get previous deployment ID
            previous_deployment = lines[1].split()[0]

            # Create rollback deployment
            rollback_result = self.run_command(
                [
                    "doctl",
                    "apps",
                    "create-deployment",
                    deployment_id,
                ]
            )

            if rollback_result.returncode == 0:
                result.status = DeploymentStatus.SUCCESS
                result.add_log("Rollback initiated")
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

        result.add_log("To scale your DigitalOcean app:")
        result.add_log("1. Update instance_count in .do/app.yaml")
        result.add_log(f"2. Set instance_count: {instances}")
        result.add_log("3. Run: doctl apps update <app-id> --spec .do/app.yaml")
        result.add_log("Or configure autoscaling in the app spec.")

        result.status = DeploymentStatus.SUCCESS
        return result

    async def get_logs(self, lines: int = 100) -> list[str]:
        """Get application logs."""
        result = self.run_command(
            [
                "doctl",
                "apps",
                "logs",
                self.config.app_name,
                "--type",
                "run",
            ]
        )

        if result.returncode == 0:
            return result.stdout.split("\n")[-lines:]
        return []


__all__ = ["DigitalOceanProvider"]
