"""
Deployment management command.

Provides CLI tools for deploying Django applications to various platforms.

Usage:
    # Deploy to a platform
    python manage.py deploy --platform fly
    python manage.py deploy --platform railway
    python manage.py deploy --platform render
    python manage.py deploy --platform k3s

    # Generate configuration files only
    python manage.py deploy config --platform fly
    python manage.py deploy config --platform docker

    # Initialize Docker setup
    python manage.py deploy docker --mode production

    # Kubernetes/Helm deployment
    python manage.py deploy kubernetes helm --output ./charts
    python manage.py deploy kubernetes manifests --output ./k8s
    python manage.py deploy kubernetes kustomize --output ./k8s

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

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Deploy Django application to cloud platforms"

    def add_arguments(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(dest="subcommand", help="Deployment subcommands")

        # Main deploy command (default)
        parser.add_argument(
            "--platform",
            "-p",
            choices=["fly", "railway", "render", "digitalocean", "aws", "hetzner", "k3s"],
            help="Target deployment platform",
        )
        parser.add_argument("--app-name", help="Application name")
        parser.add_argument("--settings-module", help="Django settings module")
        parser.add_argument(
            "--dry-run", action="store_true", help="Generate config without deploying"
        )

        # Config subcommand
        config_parser = subparsers.add_parser("config", help="Generate platform configuration")
        config_parser.add_argument(
            "--platform",
            "-p",
            required=True,
            choices=["fly", "railway", "render", "digitalocean", "aws", "hetzner", "docker", "k3s"],
            help="Target platform",
        )
        config_parser.add_argument("--output", "-o", help="Output directory")
        config_parser.add_argument("--app-name", help="Application name")
        config_parser.add_argument(
            "--server",
            choices=["uvicorn", "gunicorn", "granian", "robyn"],
            default="granian",
            help="ASGI/WSGI server backend (docker platform only, default: granian)",
        )

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
        docker_parser.add_argument(
            "--include-db", action="store_true", default=True, help="Include PostgreSQL"
        )
        docker_parser.add_argument("--include-redis", action="store_true", help="Include Redis")
        docker_parser.add_argument(
            "--include-celery", action="store_true", help="Include Celery workers"
        )
        docker_parser.add_argument(
            "--proxy", choices=["caddy", "nginx", "none"], default="caddy", help="Reverse proxy"
        )
        docker_parser.add_argument("--domain", help="Domain for SSL")
        docker_parser.add_argument(
            "--server",
            choices=["uvicorn", "gunicorn", "granian", "robyn"],
            default="granian",
            help="ASGI/WSGI server backend (default: granian)",
        )

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
        env_validate = env_subparsers.add_parser(
            "validate", help="Validate environment configurations"
        )
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

        # Kubernetes subcommand
        k8s_parser = subparsers.add_parser("kubernetes", help="Kubernetes deployment tools")
        k8s_subparsers = k8s_parser.add_subparsers(dest="k8s_action", help="Kubernetes actions")

        # kubernetes helm
        k8s_helm = k8s_subparsers.add_parser("helm", help="Generate Helm chart")
        k8s_helm.add_argument("--output", "-o", default="./charts", help="Output directory")
        k8s_helm.add_argument("--app-name", help="Application name")
        k8s_helm.add_argument("--version", default="0.1.0", help="Chart version")
        k8s_helm.add_argument("--app-version", default="1.0.0", help="Application version")
        k8s_helm.add_argument("--description", help="Chart description")
        k8s_helm.add_argument("--image", help="Container image repository")

        # kubernetes manifests
        k8s_manifests = k8s_subparsers.add_parser("manifests", help="Generate Kubernetes manifests")
        k8s_manifests.add_argument("--output", "-o", default="./k8s", help="Output directory")
        k8s_manifests.add_argument("--app-name", help="Application name")
        k8s_manifests.add_argument("--namespace", default="default", help="Kubernetes namespace")
        k8s_manifests.add_argument("--image", help="Container image (e.g., myapp:latest)")
        k8s_manifests.add_argument("--replicas", type=int, default=2, help="Number of replicas")
        k8s_manifests.add_argument("--port", type=int, default=8000, help="Container port")
        k8s_manifests.add_argument("--host", help="Ingress hostname")
        k8s_manifests.add_argument(
            "--ingress-class",
            choices=["nginx", "traefik", "contour", "istio"],
            default="nginx",
            help="Ingress controller class",
        )
        k8s_manifests.add_argument("--no-hpa", action="store_true", help="Disable HPA generation")
        k8s_manifests.add_argument("--no-pdb", action="store_true", help="Disable PDB generation")
        k8s_manifests.add_argument("--no-ingress", action="store_true", help="Disable ingress")

        # kubernetes kustomize
        k8s_kustomize = k8s_subparsers.add_parser(
            "kustomize", help="Generate Kustomize configuration"
        )
        k8s_kustomize.add_argument("--output", "-o", default=".", help="Output directory")
        k8s_kustomize.add_argument("--app-name", help="Application name")
        k8s_kustomize.add_argument("--namespace", default="default", help="Base namespace")

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
        elif subcommand == "kubernetes":
            self.handle_kubernetes(**options)
        elif options.get("platform"):
            self.handle_deploy(**options)
        else:
            self.print_help()

    def print_help(self):
        """Print help information."""
        self.stdout.write(self.style.SUCCESS("\nDjango Matt Deployment Tool\n"))
        self.stdout.write("Usage:\n")
        self.stdout.write("  python manage.py deploy --platform <platform>  Deploy to platform\n")
        self.stdout.write(
            "  python manage.py deploy config --platform <platform>  Generate config\n"
        )
        self.stdout.write("  python manage.py deploy docker [--mode production]  Docker setup\n")
        self.stdout.write(
            "  python manage.py deploy env init --domain example.com  Initialize environments\n"
        )
        self.stdout.write("  python manage.py deploy health  Health check info\n")
        self.stdout.write("\nKubernetes commands:\n")
        self.stdout.write("  python manage.py deploy kubernetes helm      Generate Helm chart\n")
        self.stdout.write("  python manage.py deploy kubernetes manifests Generate K8s manifests\n")
        self.stdout.write(
            "  python manage.py deploy kubernetes kustomize Generate Kustomize config\n"
        )
        self.stdout.write(
            "\nSupported platforms: fly, railway, render, digitalocean, aws, hetzner, k3s\n"
        )

    def handle_deploy(self, **options):
        """Handle main deploy command."""
        from django_matt.deploy import (
            DeploymentConfig,
            get_provider,
        )

        platform = options["platform"]
        app_name = options.get("app_name") or self._get_app_name()
        settings_module = options.get("settings_module") or getattr(
            settings, "SETTINGS_MODULE", "config.settings"
        )
        dry_run = options.get("dry_run", False)

        # Register K3s provider if needed
        if platform == "k3s":
            from django_matt.deployment import register_k3s_provider

            register_k3s_provider()

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
            self.stdout.write(self.style.SUCCESS("\nDeployment successful!"))
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
        from django_matt.deploy.docker import ComposeGenerator, DockerfileGenerator

        platform = options["platform"]
        output_dir = Path(options.get("output") or ".")
        app_name = options.get("app_name") or self._get_app_name()

        # Register K3s provider if needed
        if platform == "k3s":
            from django_matt.deployment import register_k3s_provider

            register_k3s_provider()

        self.stdout.write(f"\nGenerating {platform} configuration...\n")

        if platform == "docker":
            # Use Docker generators directly
            from django_matt.deploy.base import ServerBackend
            from django_matt.deploy.docker import DockerfileConfig

            server_backend = ServerBackend(options.get("server", "granian"))
            dockerfile_gen = DockerfileGenerator(
                DockerfileConfig(server_backend=server_backend)
            )
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
        from django_matt.deploy.base import ServerBackend
        from django_matt.deploy.docker import (
            ComposeGenerator,
            DockerfileConfig,
            DockerfileGenerator,
        )

        mode = options["mode"]
        output_dir = Path(options.get("output") or ".")
        include_db = options.get("include_db", True)
        include_redis = options.get("include_redis", False)
        include_celery = options.get("include_celery", False)
        proxy = options.get("proxy", "caddy")
        domain = options.get("domain")
        server_backend = ServerBackend(options.get("server", "granian"))

        app_name = self._get_app_name()

        self.stdout.write(
            f"\nGenerating Docker configuration ({mode} mode, {server_backend.value} backend)...\n"
        )

        # Generate Dockerfile
        dockerfile_config = DockerfileConfig(
            wsgi_module=f"{app_name}.wsgi:application",
            asgi_module=f"{app_name}.asgi:application",
            server_backend=server_backend,
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
        from django_matt.deploy.environments import EnvironmentManager

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

            self.stdout.write(self.style.SUCCESS("\nEnvironments initialized!"))
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

        # Register K3s provider if needed
        if platform == "k3s":
            from django_matt.deployment import register_k3s_provider

            register_k3s_provider()

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

        # Register K3s provider if needed
        if platform == "k3s":
            from django_matt.deployment import register_k3s_provider

            register_k3s_provider()

        config = DeploymentConfig(
            app_name=self._get_app_name(),
            project_dir=Path.cwd(),
        )

        provider = get_provider(platform, config)
        logs = asyncio.run(provider.get_logs(lines))

        self.stdout.write(f"\nLast {lines} lines:\n")
        for line in logs:
            self.stdout.write(line)

    def handle_kubernetes(self, **options):
        """Handle Kubernetes deployment commands."""
        action = options.get("k8s_action")

        if action == "helm":
            self.handle_k8s_helm(**options)
        elif action == "manifests":
            self.handle_k8s_manifests(**options)
        elif action == "kustomize":
            self.handle_k8s_kustomize(**options)
        else:
            self.stdout.write(
                "Usage: python manage.py deploy kubernetes <helm|manifests|kustomize>"
            )

    def handle_k8s_helm(self, **options):
        """Generate Helm chart."""
        from django_matt.deployment import HelmValues, generate_helm_chart

        output_dir = Path(options.get("output") or "./charts")
        app_name = options.get("app_name") or self._get_app_name()
        version = options.get("version", "0.1.0")
        app_version = options.get("app_version", "1.0.0")
        description = options.get("description") or f"Helm chart for {app_name}"
        image = options.get("image") or app_name

        self.stdout.write(f"\nGenerating Helm chart for {app_name}...\n")

        # Create custom values if image is specified
        values = HelmValues(image_repository=image)

        chart_path = generate_helm_chart(
            app_name=app_name,
            output_dir=output_dir,
            version=version,
            app_version=app_version,
            description=description,
            values=values,
        )

        self.stdout.write(f"  Created: {chart_path}/Chart.yaml")
        self.stdout.write(f"  Created: {chart_path}/values.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/deployment.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/service.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/ingress.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/configmap.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/secret.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/hpa.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/pdb.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/serviceaccount.yaml")
        self.stdout.write(f"  Created: {chart_path}/templates/_helpers.tpl")
        self.stdout.write(f"  Created: {chart_path}/templates/NOTES.txt")

        self.stdout.write(self.style.SUCCESS(f"\nHelm chart generated in {chart_path}"))
        self.stdout.write("\nTo install:")
        self.stdout.write(f"  helm install {app_name} {chart_path}")
        self.stdout.write("\nTo upgrade:")
        self.stdout.write(f"  helm upgrade {app_name} {chart_path}")

    def handle_k8s_manifests(self, **options):
        """Generate Kubernetes manifests."""
        from django_matt.deployment import (
            IngressClass,
            KubernetesConfig,
            KubernetesManifestGenerator,
        )

        output_dir = Path(options.get("output") or "./k8s")
        app_name = options.get("app_name") or self._get_app_name()
        namespace = options.get("namespace", "default")
        image = options.get("image") or f"{app_name}:latest"
        replicas = options.get("replicas", 2)
        port = options.get("port", 8000)
        host = options.get("host", "")
        ingress_class_str = options.get("ingress_class", "nginx")
        no_hpa = options.get("no_hpa", False)
        no_pdb = options.get("no_pdb", False)
        no_ingress = options.get("no_ingress", False)

        # Parse image into repository and tag
        image_parts = image.rsplit(":", 1)
        image_name = image_parts[0]
        image_tag = image_parts[1] if len(image_parts) > 1 else "latest"

        # Map ingress class string to enum
        ingress_class_map = {
            "nginx": IngressClass.NGINX,
            "traefik": IngressClass.TRAEFIK,
            "contour": IngressClass.CONTOUR,
            "istio": IngressClass.ISTIO,
        }
        ingress_class = ingress_class_map.get(ingress_class_str, IngressClass.NGINX)

        self.stdout.write(f"\nGenerating Kubernetes manifests for {app_name}...\n")

        config = KubernetesConfig(
            app_name=app_name,
            namespace=namespace,
            image=image_name,
            image_tag=image_tag,
            replicas=replicas,
            port=port,
            ingress_enabled=not no_ingress and bool(host),
            ingress_host=host,
            ingress_class=ingress_class,
            hpa_enabled=not no_hpa,
            pdb_enabled=not no_pdb,
        )

        generator = KubernetesManifestGenerator(config)
        manifests = generator.generate_all()

        # Write manifests
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in manifests.items():
            file_path = output_dir / filename
            with open(file_path, "w") as f:
                f.write(content)
            self.stdout.write(f"  Created: {file_path}")

        self.stdout.write(self.style.SUCCESS(f"\nKubernetes manifests generated in {output_dir}"))
        self.stdout.write("\nTo apply:")
        self.stdout.write(f"  kubectl apply -f {output_dir}")

    def handle_k8s_kustomize(self, **options):
        """Generate Kustomize configuration."""
        from django_matt.deployment import generate_kustomization

        output_dir = Path(options.get("output") or ".")
        app_name = options.get("app_name") or self._get_app_name()
        namespace = options.get("namespace", "default")

        self.stdout.write(f"\nGenerating Kustomize configuration for {app_name}...\n")

        kustomize_dir = generate_kustomization(
            app_name=app_name,
            output_dir=output_dir,
            namespace=namespace,
        )

        self.stdout.write(f"  Created: {kustomize_dir}/base/kustomization.yaml")
        self.stdout.write(f"  Created: {kustomize_dir}/base/deployment.yaml")
        self.stdout.write(f"  Created: {kustomize_dir}/base/service.yaml")
        self.stdout.write(f"  Created: {kustomize_dir}/base/configmap.yaml")
        self.stdout.write(f"  Created: {kustomize_dir}/overlays/dev/kustomization.yaml")
        self.stdout.write(f"  Created: {kustomize_dir}/overlays/staging/kustomization.yaml")
        self.stdout.write(f"  Created: {kustomize_dir}/overlays/prod/kustomization.yaml")

        self.stdout.write(
            self.style.SUCCESS(f"\nKustomize configuration generated in {kustomize_dir}")
        )
        self.stdout.write("\nTo apply:")
        self.stdout.write(f"  kubectl apply -k {kustomize_dir}/overlays/dev     # Development")
        self.stdout.write(f"  kubectl apply -k {kustomize_dir}/overlays/staging # Staging")
        self.stdout.write(f"  kubectl apply -k {kustomize_dir}/overlays/prod    # Production")

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
