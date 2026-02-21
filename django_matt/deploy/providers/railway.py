"""
Railway deployment provider.

Provides deployment to Railway with automatic configuration generation.
"""

import orjson

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentProvider,
    DeploymentResult,
    DeploymentStatus,
    register_provider,
)


@register_provider("railway")
class RailwayProvider(DeploymentProvider):
    """
    Railway deployment provider.

    Supports:
    - Automatic railway.json generation
    - PostgreSQL database provisioning
    - Redis provisioning
    - Secrets management
    - Health checks
    - Preview environments
    """

    name = "railway"
    display_name = "Railway"

    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self.project_id: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration for Railway deployment."""
        errors = []

        # Check CLI is installed
        if not self.check_cli_installed("railway"):
            errors.append(
                "railway CLI is not installed. Install from https://docs.railway.app/develop/cli"
            )

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")

        # Check for Django settings
        if not self.config.django_settings_module:
            errors.append("django_settings_module is required")

        return errors

    def generate_config(self) -> dict[str, str]:
        """Generate Railway configuration files."""
        files = {}

        # Generate railway.json (nixpacks config)
        files["railway.json"] = self._generate_railway_json()

        # Generate Procfile
        files["Procfile"] = self._generate_procfile()

        # Generate nixpacks.toml for custom build
        files["nixpacks.toml"] = self._generate_nixpacks_toml()

        return files

    def _generate_railway_json(self) -> str:
        """Generate railway.json configuration."""
        config = {
            "$schema": "https://railway.app/railway.schema.json",
            "build": {
                "builder": "NIXPACKS",
                "buildCommand": "uv pip install -r requirements.txt && python manage.py collectstatic --noinput",
            },
            "deploy": {
                "startCommand": f"gunicorn {self.config.django_settings_module.rsplit('.', 1)[0]}.wsgi:application --bind 0.0.0.0:$PORT --workers {self.config.workers}",
                "healthcheckPath": self.config.health_check_path,
                "healthcheckTimeout": 30,
                "restartPolicyType": "ON_FAILURE",
                "restartPolicyMaxRetries": 10,
            },
        }

        return orjson.dumps(config, option=orjson.OPT_INDENT_2).decode()

    def _generate_procfile(self) -> str:
        """Generate Procfile for Railway."""
        wsgi_module = f"{self.config.django_settings_module.rsplit('.', 1)[0]}.wsgi:application"

        return f"""web: gunicorn {wsgi_module} --bind 0.0.0.0:$PORT --workers {self.config.workers} --worker-class {self.config.worker_class}
release: python manage.py migrate --noinput
"""

    def _generate_nixpacks_toml(self) -> str:
        """Generate nixpacks.toml for custom build configuration."""
        return f"""[phases.setup]
nixPkgs = ["python313", "postgresql"]

[phases.install]
cmds = ["uv pip install -r requirements.txt"]

[phases.build]
cmds = ["python manage.py collectstatic --noinput"]

[start]
cmd = "gunicorn {self.config.django_settings_module.rsplit(".", 1)[0]}.wsgi:application --bind 0.0.0.0:$PORT --workers {self.config.workers}"
"""

    async def deploy(self) -> DeploymentResult:
        """Deploy to Railway."""
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
            configs = self.generate_config()
            for filename, content in configs.items():
                file_path = self.config.project_dir / filename
                with open(file_path, "w") as f:
                    f.write(content)
                result.add_log(f"Generated {filename}")

            # Check if logged in
            login_check = self.run_command(["railway", "whoami"])
            if login_check.returncode != 0:
                result.add_log("Logging in to Railway...")
                self.run_command(["railway", "login"])

            # Check if project exists or create new one
            project_result = self.run_command(["railway", "status", "--json"])

            if project_result.returncode != 0:
                # Create new project
                result.add_log(f"Creating project: {self.config.app_name}")
                create_result = self.run_command(
                    ["railway", "init", "--name", self.config.app_name]
                )
                if create_result.returncode != 0:
                    result.status = DeploymentStatus.FAILED
                    result.add_error(f"Failed to create project: {create_result.stderr}")
                    return result

            # Create database if needed
            if self.config.create_database and not self.config.database_url:
                result.add_log("Adding PostgreSQL database...")
                db_result = self.run_command(["railway", "add", "--database", "postgres"])
                if db_result.returncode == 0:
                    result.add_log("PostgreSQL database added")
                else:
                    result.add_log(
                        "Note: Database may already exist or couldn't be added automatically"
                    )

            # Create Redis if needed
            if self.config.create_redis and not self.config.redis_url:
                result.add_log("Adding Redis...")
                redis_result = self.run_command(["railway", "add", "--database", "redis"])
                if redis_result.returncode == 0:
                    result.add_log("Redis added")

            # Set environment variables
            result.status = DeploymentStatus.DEPLOYING
            env_vars = self.config.get_env_vars()
            if env_vars:
                result.add_log("Setting environment variables...")
                for key, value in env_vars.items():
                    self.run_command(["railway", "variables", "--set", f"{key}={value}"])

            # Deploy
            result.add_log("Deploying application...")
            deploy_result = self.run_command(["railway", "up", "--detach"])

            if deploy_result.returncode != 0:
                result.status = DeploymentStatus.FAILED
                result.add_error(f"Deployment failed: {deploy_result.stderr}")
                return result

            # Get deployment URL
            domain_result = self.run_command(["railway", "domain"])
            if domain_result.returncode == 0:
                result.url = domain_result.stdout.strip()
                if not result.url.startswith("https://"):
                    result.url = f"https://{result.url}"
            else:
                # Generate domain if not exists
                self.run_command(["railway", "domain", "--generate"])
                domain_result = self.run_command(["railway", "domain"])
                if domain_result.returncode == 0:
                    result.url = domain_result.stdout.strip()
                    if not result.url.startswith("https://"):
                        result.url = f"https://{result.url}"

            result.status = DeploymentStatus.SUCCESS
            result.add_log(f"Deployment successful! App available at {result.url}")

            # Get project info for deployment ID
            status_result = self.run_command(["railway", "status", "--json"])
            if status_result.returncode == 0:
                status = orjson.loads(status_result.stdout)
                result.deployment_id = status.get("deploymentId", "")
                result.metadata = status

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            status_result = self.run_command(["railway", "status", "--json"])

            if status_result.returncode == 0:
                status = orjson.loads(status_result.stdout)
                result.deployment_id = deployment_id
                result.metadata = status

                deployment_status = status.get("status", "").lower()
                if deployment_status == "success" or deployment_status == "deployed":
                    result.status = DeploymentStatus.SUCCESS
                elif deployment_status == "building":
                    result.status = DeploymentStatus.BUILDING
                elif deployment_status == "deploying":
                    result.status = DeploymentStatus.DEPLOYING
                elif deployment_status == "failed":
                    result.status = DeploymentStatus.FAILED
                else:
                    result.status = DeploymentStatus.PENDING

                # Get URL
                domain_result = self.run_command(["railway", "domain"])
                if domain_result.returncode == 0:
                    result.url = domain_result.stdout.strip()
                    if not result.url.startswith("https://"):
                        result.url = f"https://{result.url}"
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
            deployments_result = self.run_command(["railway", "logs", "--deployment"])

            # Railway doesn't have direct rollback, redeploy previous
            result.add_log(
                "Railway doesn't support direct rollback. Redeploy from git commit instead."
            )
            result.status = DeploymentStatus.FAILED
            result.add_error("Rollback not directly supported. Use git-based redeploy.")

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def scale(self, instances: int) -> DeploymentResult:
        """Scale the application."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        # Railway handles scaling automatically via their platform
        result.add_log("Railway handles scaling automatically based on usage.")
        result.add_log("For custom scaling, configure via the Railway dashboard.")
        result.status = DeploymentStatus.SUCCESS

        return result

    async def get_logs(self, lines: int = 100) -> list[str]:
        """Get application logs."""
        result = self.run_command(["railway", "logs", "-n", str(lines)])

        if result.returncode == 0:
            return result.stdout.split("\n")
        return []


__all__ = ["RailwayProvider"]
