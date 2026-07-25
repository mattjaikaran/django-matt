# file-length-max: 500
"""
Render deployment provider.

Provides deployment to Render with automatic configuration generation.
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


@register_provider("render")
class RenderProvider(DeploymentProvider):
    """
    Render deployment provider.

    Supports:
    - render.yaml (Blueprint) generation
    - PostgreSQL database provisioning
    - Redis provisioning
    - Environment groups
    - Health checks
    - Auto-deploy from Git
    """

    name = "render"
    display_name = "Render"

    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self.api_key: str | None = None

    def validate(self) -> list[str]:
        """Validate configuration for Render deployment."""
        errors = []

        # Render primarily uses render.yaml, but API can be used
        # Check for API key in environment
        import os

        if not os.environ.get("RENDER_API_KEY"):
            errors.append(
                "RENDER_API_KEY environment variable not set (optional for Blueprint deploy)"
            )

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")

        # Check for Django settings
        if not self.config.django_settings_module:
            errors.append("django_settings_module is required")

        return errors

    def generate_config(self) -> dict[str, str]:
        """Generate Render configuration files."""
        files = {}

        # Generate render.yaml (Blueprint)
        files["render.yaml"] = self._generate_render_yaml()

        # Generate build script
        files["build.sh"] = self._generate_build_script()

        return files

    def _generate_render_yaml(self) -> str:
        """Generate render.yaml Blueprint configuration."""
        services = []

        # Web service
        web_service = {
            "type": "web",
            "name": self.config.app_name,
            "runtime": "python",
            "buildCommand": "sh build.sh",
            "startCommand": build_start_command(self.config),
            "healthCheckPath": self.config.health_check_path,
            "envVars": self._get_env_vars_list(),
            "autoDeploy": True,
        }

        # Add scaling if configured
        if self.config.auto_scale:
            web_service["scaling"] = {
                "minInstances": self.config.min_instances,
                "maxInstances": self.config.max_instances,
                "targetMemoryPercent": 80,
                "targetCPUPercent": 80,
            }

        services.append(web_service)

        # Database service
        databases = []
        if self.config.create_database and not self.config.database_url:
            databases.append(
                {
                    "name": f"{self.config.app_name}-db",
                    "databaseName": self.config.app_name.replace("-", "_"),
                    "user": "django",
                    "plan": "starter",
                }
            )

        # Redis service
        if self.config.create_redis and not self.config.redis_url:
            services.append(
                {
                    "type": "redis",
                    "name": f"{self.config.app_name}-redis",
                    "plan": "starter",
                    "maxmemoryPolicy": "allkeys-lru",
                }
            )

        config = {"services": services}
        if databases:
            config["databases"] = databases

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def _get_env_vars_list(self) -> list[dict[str, Any]]:
        """Get environment variables in Render format."""
        env_vars = []

        # Standard Django vars
        env_vars.extend(
            [
                {"key": "DJANGO_SETTINGS_MODULE", "value": self.config.django_settings_module},
                {"key": "DJANGO_ENV", "value": self.config.environment},
                {"key": "DEBUG", "value": str(self.config.debug).lower()},
                {"key": "STATIC_URL", "value": self.config.static_url},
                {"key": "STATIC_ROOT", "value": self.config.static_root},
            ]
        )

        # Database URL from Render's managed database
        if self.config.create_database and not self.config.database_url:
            env_vars.append(
                {
                    "key": "DATABASE_URL",
                    "fromDatabase": {
                        "name": f"{self.config.app_name}-db",
                        "property": "connectionString",
                    },
                }
            )
        elif self.config.database_url:
            env_vars.append({"key": "DATABASE_URL", "value": self.config.database_url})

        # Redis URL
        if self.config.create_redis and not self.config.redis_url:
            env_vars.append(
                {
                    "key": "REDIS_URL",
                    "fromService": {
                        "type": "redis",
                        "name": f"{self.config.app_name}-redis",
                        "property": "connectionString",
                    },
                }
            )
        elif self.config.redis_url:
            env_vars.append({"key": "REDIS_URL", "value": self.config.redis_url})

        # Secret key
        if self.config.secret_key:
            env_vars.append({"key": "SECRET_KEY", "value": self.config.secret_key})
        else:
            env_vars.append({"key": "SECRET_KEY", "generateValue": True})

        # Allowed hosts
        if self.config.allowed_hosts:
            env_vars.append({"key": "ALLOWED_HOSTS", "value": ",".join(self.config.allowed_hosts)})
        else:
            # Render will set this based on the service URL
            env_vars.append({"key": "ALLOWED_HOSTS", "value": ".onrender.com"})

        # Extra environment variables
        for key, value in self.config.extra_env.items():
            env_vars.append({"key": key, "value": value})

        # Secrets
        for key, value in self.config.secrets.items():
            env_vars.append({"key": key, "value": value})

        return env_vars

    def _generate_build_script(self) -> str:
        """Generate build script for Render."""
        return """#!/usr/bin/env bash
set -o errexit

# Install dependencies
uv pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput
"""

    async def deploy(self) -> DeploymentResult:
        """Deploy to Render using Blueprint."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        # Validate first
        errors = self.validate()
        # Filter out API key warning for Blueprint deploy
        errors = [e for e in errors if "RENDER_API_KEY" not in e]
        if errors:
            result.status = DeploymentStatus.FAILED
            result.errors = errors
            return result

        try:
            result.status = DeploymentStatus.BUILDING

            # Write configuration files
            self.write_config_files(result)

            # Make build script executable
            build_script = self.config.project_dir / "build.sh"
            build_script.chmod(0o755)

            result.add_log("Configuration files generated successfully!")
            result.add_log("")
            result.add_log("To deploy to Render:")
            result.add_log("1. Push your code to GitHub/GitLab")
            result.add_log("2. Go to https://dashboard.render.com/blueprints")
            result.add_log("3. Click 'New Blueprint Instance'")
            result.add_log("4. Connect your repository")
            result.add_log("5. Render will automatically detect render.yaml")
            result.add_log("")
            result.add_log("Or use Render CLI: render blueprint launch")

            result.status = DeploymentStatus.SUCCESS
            result.url = f"https://{self.config.app_name}.onrender.com"

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status via API."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        import os

        api_key = os.environ.get("RENDER_API_KEY")

        if not api_key:
            result.add_error("RENDER_API_KEY not set. Cannot check status via API.")
            result.status = DeploymentStatus.FAILED
            return result

        try:
            import urllib.error
            import urllib.request

            url = f"https://api.render.com/v1/services/{deployment_id}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req) as response:
                data = orjson.loads(response.read().decode())

            result.deployment_id = deployment_id
            result.metadata = data

            status = data.get("service", {}).get("suspended", False)
            if status:
                result.status = DeploymentStatus.CANCELLED
            else:
                result.status = DeploymentStatus.SUCCESS

            result.url = f"https://{self.config.app_name}.onrender.com"

        except urllib.error.HTTPError as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(f"API error: {e.code} {e.reason}")
        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def rollback(self, deployment_id: str) -> DeploymentResult:
        """Rollback to a previous deployment via Render API."""
        import os
        import urllib.error
        import urllib.request

        result = DeploymentResult(status=DeploymentStatus.PENDING)

        api_key = os.environ.get("RENDER_API_KEY")
        if not api_key:
            result.status = DeploymentStatus.FAILED
            result.add_error("RENDER_API_KEY required for rollback.")
            return result

        try:
            # List recent deploys for the service
            url = f"https://api.render.com/v1/services/{deployment_id}/deploys?limit=5"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req) as response:
                deploys = orjson.loads(response.read().decode())

            # Find the previous successful deploy
            prev_deploy = None
            for deploy in deploys:
                d = deploy.get("deploy", deploy)
                if d.get("status") == "live" and d.get("id") != deployment_id:
                    prev_deploy = d
                    break

            if not prev_deploy:
                result.status = DeploymentStatus.FAILED
                result.add_error("No previous successful deployment found.")
                return result

            # Trigger redeploy of the previous commit
            redeploy_url = f"https://api.render.com/v1/services/{deployment_id}/deploys"
            data = orjson.dumps({"commitId": prev_deploy.get("commit", {}).get("id", "")})
            req = urllib.request.Request(redeploy_url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req) as response:
                deploy_data = orjson.loads(response.read().decode())

            result.add_log(f"Rollback triggered to deploy {prev_deploy.get('id')}")
            result.deployment_id = deploy_data.get("deploy", {}).get("id")
            result.status = DeploymentStatus.SUCCESS

        except urllib.error.HTTPError as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(f"Render API error: {e.code} {e.reason}")
        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def scale(self, instances: int) -> DeploymentResult:
        """Scale via Render API (Team/Pro plan required)."""
        import os
        import urllib.error
        import urllib.request

        result = DeploymentResult(status=DeploymentStatus.PENDING)

        api_key = os.environ.get("RENDER_API_KEY")
        if not api_key:
            result.add_log("RENDER_API_KEY not set.")
            result.add_log(f"To scale manually, update render.yaml: numInstances: {instances}")
            result.status = DeploymentStatus.SUCCESS
            return result

        try:
            url = f"https://api.render.com/v1/services/{self.config.app_name}/scale"
            data = orjson.dumps({"numInstances": instances})
            req = urllib.request.Request(url, data=data, method="PATCH")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req) as response:
                orjson.loads(response.read().decode())

            result.add_log(f"Scaled to {instances} instance(s)")
            result.status = DeploymentStatus.SUCCESS

        except urllib.error.HTTPError:
            # Scaling API may not be available on all plans
            result.add_log(
                f"API scaling unavailable. Update render.yaml: numInstances: {instances}"
            )
            result.status = DeploymentStatus.SUCCESS
        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def get_logs(self, lines: int = 100) -> list[str]:
        """Get application logs via Render API."""
        import os
        import urllib.error
        import urllib.request

        api_key = os.environ.get("RENDER_API_KEY")
        if not api_key:
            return ["RENDER_API_KEY not set. Set it to fetch logs via API."]

        try:
            url = f"https://api.render.com/v1/services/{self.config.app_name}/logs?limit={lines}"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req) as response:
                data = orjson.loads(response.read().decode())

            log_entries = data if isinstance(data, list) else data.get("logs", [])
            return [entry.get("message", str(entry)) for entry in log_entries[:lines]]

        except urllib.error.HTTPError as e:
            return [f"Render API error: {e.code} {e.reason}"]
        except Exception as e:
            return [f"Failed to fetch logs: {e}"]


__all__ = ["RenderProvider"]
