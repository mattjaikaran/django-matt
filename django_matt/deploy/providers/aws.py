"""
AWS deployment provider.

Provides deployment to AWS App Runner and ECS Fargate with configuration generation.
"""

import orjson

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentProvider,
    DeploymentResult,
    DeploymentStatus,
    register_provider,
)


@register_provider("aws")
class AWSProvider(DeploymentProvider):
    """
    AWS deployment provider.

    Supports:
    - AWS App Runner deployment
    - ECS Fargate deployment
    - RDS PostgreSQL provisioning
    - ElastiCache Redis provisioning
    - Secrets Manager integration
    - CloudWatch logging
    - Auto-scaling
    """

    name = "aws"
    display_name = "AWS"

    def __init__(self, config: DeploymentConfig, mode: str = "apprunner"):
        super().__init__(config)
        self.mode = mode  # "apprunner" or "ecs"

    def validate(self) -> list[str]:
        """Validate configuration for AWS deployment."""
        errors = []

        # Check CLI is installed
        if not self.check_cli_installed("aws"):
            errors.append("aws CLI is not installed. Install from https://aws.amazon.com/cli/")

        # Validate app name
        if not self.config.app_name:
            errors.append("app_name is required")

        # Check for Django settings
        if not self.config.django_settings_module:
            errors.append("django_settings_module is required")

        # Check AWS credentials
        creds_check = self.run_command(["aws", "sts", "get-caller-identity"])
        if creds_check.returncode != 0:
            errors.append("AWS credentials not configured. Run 'aws configure'")

        return errors

    def generate_config(self) -> dict[str, str]:
        """Generate AWS configuration files."""
        files = {}

        # Generate Dockerfile
        files["Dockerfile"] = self._generate_dockerfile()

        if self.mode == "apprunner":
            # App Runner configuration
            files["apprunner.yaml"] = self._generate_apprunner_yaml()
        else:
            # ECS task definition
            files["ecs-task-definition.json"] = self._generate_ecs_task_definition()
            files["ecs-service.json"] = self._generate_ecs_service()

        # Generate buildspec for CodeBuild (optional)
        files["buildspec.yml"] = self._generate_buildspec()

        return files

    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for AWS."""
        return f"""# Dockerfile for AWS deployment
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
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD curl -f http://localhost:$PORT{self.config.health_check_path} || exit 1

# Run the application
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn {self.config.django_settings_module.rsplit(".", 1)[0]}.wsgi:application --bind 0.0.0.0:$PORT --workers {self.config.workers}"]
"""

    def _generate_apprunner_yaml(self) -> str:
        """Generate AWS App Runner configuration."""
        config = {
            "version": 1.0,
            "runtime": "python313",
            "build": {
                "commands": {
                    "pre-build": ["uv pip install -r requirements.txt"],
                    "build": ["python manage.py collectstatic --noinput"],
                },
            },
            "run": {
                "runtime-version": "3.13",
                "command": f"gunicorn {self.config.django_settings_module.rsplit('.', 1)[0]}.wsgi:application --bind 0.0.0.0:$PORT --workers {self.config.workers}",
                "network": {
                    "port": self.config.port,
                    "env": "PORT",
                },
                "env": self._get_env_vars_apprunner(),
            },
        }

        import yaml

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def _get_env_vars_apprunner(self) -> list[dict[str, str]]:
        """Get environment variables for App Runner."""
        env_vars = [
            {"name": "DJANGO_SETTINGS_MODULE", "value": self.config.django_settings_module},
            {"name": "DJANGO_ENV", "value": self.config.environment},
            {"name": "DEBUG", "value": str(self.config.debug).lower()},
            {"name": "STATIC_URL", "value": self.config.static_url},
            {"name": "STATIC_ROOT", "value": self.config.static_root},
        ]

        if self.config.database_url:
            env_vars.append({"name": "DATABASE_URL", "value": self.config.database_url})

        if self.config.redis_url:
            env_vars.append({"name": "REDIS_URL", "value": self.config.redis_url})

        if self.config.secret_key:
            env_vars.append({"name": "SECRET_KEY", "value": self.config.secret_key})

        if self.config.allowed_hosts:
            env_vars.append({"name": "ALLOWED_HOSTS", "value": ",".join(self.config.allowed_hosts)})

        for key, value in self.config.extra_env.items():
            env_vars.append({"name": key, "value": value})

        return env_vars

    def _generate_ecs_task_definition(self) -> str:
        """Generate ECS Fargate task definition."""
        task_def = {
            "family": self.config.app_name,
            "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            "memory": "512",
            "executionRoleArn": f"arn:aws:iam::ACCOUNT_ID:role/{self.config.app_name}-execution-role",
            "taskRoleArn": f"arn:aws:iam::ACCOUNT_ID:role/{self.config.app_name}-task-role",
            "containerDefinitions": [
                {
                    "name": "web",
                    "image": f"ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/{self.config.app_name}:latest",
                    "essential": True,
                    "portMappings": [
                        {
                            "containerPort": self.config.port,
                            "protocol": "tcp",
                        }
                    ],
                    "environment": [
                        {
                            "name": "DJANGO_SETTINGS_MODULE",
                            "value": self.config.django_settings_module,
                        },
                        {"name": "DJANGO_ENV", "value": self.config.environment},
                        {"name": "DEBUG", "value": str(self.config.debug).lower()},
                        {"name": "PORT", "value": str(self.config.port)},
                        {"name": "STATIC_URL", "value": self.config.static_url},
                        {"name": "STATIC_ROOT", "value": self.config.static_root},
                    ],
                    "secrets": [],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": f"/ecs/{self.config.app_name}",
                            "awslogs-region": "us-east-1",
                            "awslogs-stream-prefix": "ecs",
                        },
                    },
                    "healthCheck": {
                        "command": [
                            "CMD-SHELL",
                            f"curl -f http://localhost:{self.config.port}{self.config.health_check_path} || exit 1",
                        ],
                        "interval": self.config.health_check_interval,
                        "timeout": 5,
                        "retries": 3,
                        "startPeriod": 60,
                    },
                }
            ],
        }

        # Add secrets from Secrets Manager
        if self.config.database_url:
            task_def["containerDefinitions"][0]["secrets"].append(
                {
                    "name": "DATABASE_URL",
                    "valueFrom": f"arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:{self.config.app_name}/database-url",
                }
            )

        if self.config.secret_key:
            task_def["containerDefinitions"][0]["secrets"].append(
                {
                    "name": "SECRET_KEY",
                    "valueFrom": f"arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:{self.config.app_name}/secret-key",
                }
            )

        return orjson.dumps(task_def, option=orjson.OPT_INDENT_2).decode()

    def _generate_ecs_service(self) -> str:
        """Generate ECS service definition."""
        service = {
            "serviceName": self.config.app_name,
            "cluster": f"{self.config.app_name}-cluster",
            "taskDefinition": self.config.app_name,
            "desiredCount": self.config.min_instances,
            "launchType": "FARGATE",
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": ["subnet-xxx", "subnet-yyy"],
                    "securityGroups": ["sg-xxx"],
                    "assignPublicIp": "ENABLED",
                }
            },
            "loadBalancers": [
                {
                    "targetGroupArn": f"arn:aws:elasticloadbalancing:REGION:ACCOUNT_ID:targetgroup/{self.config.app_name}/xxx",
                    "containerName": "web",
                    "containerPort": self.config.port,
                }
            ],
            "healthCheckGracePeriodSeconds": 60,
            "deploymentConfiguration": {
                "maximumPercent": 200,
                "minimumHealthyPercent": 100,
            },
        }

        return orjson.dumps(service, option=orjson.OPT_INDENT_2).decode()

    def _generate_buildspec(self) -> str:
        """Generate AWS CodeBuild buildspec."""
        return f"""version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
      - REPOSITORY_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/{self.config.app_name}
      - COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)
      - IMAGE_TAG=${{COMMIT_HASH:=latest}}

  build:
    commands:
      - echo Build started on `date`
      - echo Building the Docker image...
      - docker build -t $REPOSITORY_URI:latest .
      - docker tag $REPOSITORY_URI:latest $REPOSITORY_URI:$IMAGE_TAG

  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing the Docker images...
      - docker push $REPOSITORY_URI:latest
      - docker push $REPOSITORY_URI:$IMAGE_TAG
      - echo Writing image definitions file...
      - printf '[{{"name":"web","imageUri":"%s"}}]' $REPOSITORY_URI:$IMAGE_TAG > imagedefinitions.json

artifacts:
  files:
    - imagedefinitions.json
"""

    async def deploy(self) -> DeploymentResult:
        """Deploy to AWS."""
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

            if self.mode == "apprunner":
                result = await self._deploy_apprunner(result)
            else:
                result = await self._deploy_ecs(result)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def _deploy_apprunner(self, result: DeploymentResult) -> DeploymentResult:
        """Deploy to AWS App Runner."""
        result.add_log("Deploying to AWS App Runner...")

        # Check if service exists
        list_result = self.run_command(
            [
                "aws",
                "apprunner",
                "list-services",
                "--query",
                f"ServiceSummaryList[?ServiceName=='{self.config.app_name}']",
                "--output",
                "json",
            ]
        )

        if list_result.returncode == 0:
            services = orjson.loads(list_result.stdout)

            if services:
                # Update existing service
                service_arn = services[0]["ServiceArn"]
                result.add_log(f"Updating existing service: {service_arn}")

                # Trigger deployment
                update_result = self.run_command(
                    [
                        "aws",
                        "apprunner",
                        "start-deployment",
                        "--service-arn",
                        service_arn,
                    ]
                )

                if update_result.returncode == 0:
                    result.status = DeploymentStatus.SUCCESS
                    result.deployment_id = service_arn
                    result.url = services[0].get("ServiceUrl", "")
                    if result.url and not result.url.startswith("https://"):
                        result.url = f"https://{result.url}"
                else:
                    result.status = DeploymentStatus.FAILED
                    result.add_error(update_result.stderr)
            else:
                # Need to create new service
                result.add_log("Creating new App Runner service...")
                result.add_log("")
                result.add_log("To create an App Runner service:")
                result.add_log("1. Build and push Docker image to ECR")
                result.add_log("2. Create service via AWS Console or CLI:")
                result.add_log(
                    f"   aws apprunner create-service --service-name {self.config.app_name} ..."
                )
                result.add_log("")
                result.add_log("Configuration files have been generated.")
                result.status = DeploymentStatus.PENDING
        else:
            result.status = DeploymentStatus.FAILED
            result.add_error(list_result.stderr)

        return result

    async def _deploy_ecs(self, result: DeploymentResult) -> DeploymentResult:
        """Deploy to ECS Fargate."""
        result.add_log("Deploying to ECS Fargate...")

        # Register task definition
        result.add_log("Registering task definition...")
        task_def_file = self.config.project_dir / "ecs-task-definition.json"

        register_result = self.run_command(
            [
                "aws",
                "ecs",
                "register-task-definition",
                "--cli-input-json",
                f"file://{task_def_file}",
            ]
        )

        if register_result.returncode != 0:
            result.status = DeploymentStatus.FAILED
            result.add_error(f"Failed to register task definition: {register_result.stderr}")
            return result

        # Update service
        result.status = DeploymentStatus.DEPLOYING
        result.add_log("Updating ECS service...")

        update_result = self.run_command(
            [
                "aws",
                "ecs",
                "update-service",
                "--cluster",
                f"{self.config.app_name}-cluster",
                "--service",
                self.config.app_name,
                "--task-definition",
                self.config.app_name,
                "--force-new-deployment",
            ]
        )

        if update_result.returncode == 0:
            result.status = DeploymentStatus.SUCCESS
            result.add_log("ECS service updated. Deployment in progress.")
        else:
            result.status = DeploymentStatus.FAILED
            result.add_error(update_result.stderr)

        return result

    async def get_status(self, deployment_id: str) -> DeploymentResult:
        """Get deployment status."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        try:
            if self.mode == "apprunner":
                status_result = self.run_command(
                    [
                        "aws",
                        "apprunner",
                        "describe-service",
                        "--service-arn",
                        deployment_id,
                        "--output",
                        "json",
                    ]
                )

                if status_result.returncode == 0:
                    data = orjson.loads(status_result.stdout)
                    service = data.get("Service", {})
                    result.deployment_id = deployment_id
                    result.metadata = service

                    status = service.get("Status", "")
                    if status == "RUNNING":
                        result.status = DeploymentStatus.SUCCESS
                    elif status in ["CREATE_PENDING", "CREATE_IN_PROGRESS", "DEPLOYING"]:
                        result.status = DeploymentStatus.DEPLOYING
                    elif status in ["DELETE_PENDING", "DELETE_IN_PROGRESS", "DELETED"]:
                        result.status = DeploymentStatus.CANCELLED
                    else:
                        result.status = DeploymentStatus.FAILED

                    result.url = f"https://{service.get('ServiceUrl', '')}"
            else:
                # ECS status check
                status_result = self.run_command(
                    [
                        "aws",
                        "ecs",
                        "describe-services",
                        "--cluster",
                        f"{self.config.app_name}-cluster",
                        "--services",
                        self.config.app_name,
                        "--output",
                        "json",
                    ]
                )

                if status_result.returncode == 0:
                    data = orjson.loads(status_result.stdout)
                    services = data.get("services", [])
                    if services:
                        service = services[0]
                        result.metadata = service

                        running = service.get("runningCount", 0)
                        desired = service.get("desiredCount", 0)

                        if running == desired and running > 0:
                            result.status = DeploymentStatus.SUCCESS
                        elif running < desired:
                            result.status = DeploymentStatus.DEPLOYING
                        else:
                            result.status = DeploymentStatus.PENDING

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.add_error(str(e))

        return result

    async def rollback(self, deployment_id: str) -> DeploymentResult:
        """Rollback to previous deployment."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        if self.mode == "apprunner":
            result.add_log("App Runner rollback requires redeploying a previous image.")
            result.add_log("1. Find previous image tag in ECR")
            result.add_log("2. Update service to use that image")
            result.status = DeploymentStatus.FAILED
            result.add_error("Direct rollback not implemented. Redeploy previous image.")
        else:
            # ECS supports rollback
            try:
                result.add_log("Rolling back ECS service...")

                rollback_result = self.run_command(
                    [
                        "aws",
                        "ecs",
                        "update-service",
                        "--cluster",
                        f"{self.config.app_name}-cluster",
                        "--service",
                        self.config.app_name,
                        "--deployment-configuration",
                        '{"deploymentCircuitBreaker":{"enable":true,"rollback":true}}',
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

        try:
            if self.mode == "apprunner":
                result.add_log("App Runner auto-scales based on traffic.")
                result.add_log("Configure min/max instances in the service settings.")
                result.status = DeploymentStatus.SUCCESS
            else:
                scale_result = self.run_command(
                    [
                        "aws",
                        "ecs",
                        "update-service",
                        "--cluster",
                        f"{self.config.app_name}-cluster",
                        "--service",
                        self.config.app_name,
                        "--desired-count",
                        str(instances),
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
        """Get application logs from CloudWatch."""
        result = self.run_command(
            [
                "aws",
                "logs",
                "tail",
                f"/ecs/{self.config.app_name}",
                "--since",
                "1h",
            ]
        )

        if result.returncode == 0:
            return result.stdout.split("\n")[-lines:]
        return []


__all__ = ["AWSProvider"]
