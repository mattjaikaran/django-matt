"""
Tests for the deployment module in Django Matt.
"""

import json
import tempfile
from pathlib import Path

from django.test import RequestFactory, TestCase

from django_matt.deploy.base import (
    DeploymentConfig,
    DeploymentResult,
    DeploymentStatus,
    SecretManager,
    get_provider,
    list_providers,
)
from django_matt.deploy.docker import (
    ComposeGenerator,
    DockerfileConfig,
    DockerfileGenerator,
)
from django_matt.deploy.environments import (
    Environment,
    EnvironmentConfig,
    EnvironmentManager,
)
from django_matt.deploy.health import (
    CheckResult,
    HealthCheck,
    HealthCheckResponse,
    HealthStatus,
    get_uptime,
    health_check_view,
    liveness_check_view,
)

# =============================================================================
# Base Classes Tests
# =============================================================================


class TestDeploymentStatus(TestCase):
    """Tests for DeploymentStatus enum."""

    def test_status_values(self):
        """Test that all status values exist."""
        self.assertEqual(DeploymentStatus.PENDING.value, "pending")
        self.assertEqual(DeploymentStatus.BUILDING.value, "building")
        self.assertEqual(DeploymentStatus.DEPLOYING.value, "deploying")
        self.assertEqual(DeploymentStatus.SUCCESS.value, "success")
        self.assertEqual(DeploymentStatus.FAILED.value, "failed")
        self.assertEqual(DeploymentStatus.CANCELLED.value, "cancelled")

    def test_status_is_string(self):
        """Test that status values are strings."""
        for status in DeploymentStatus:
            self.assertIsInstance(status.value, str)


class TestDeploymentConfig(TestCase):
    """Tests for DeploymentConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DeploymentConfig(app_name="test-app")

        self.assertEqual(config.app_name, "test-app")
        self.assertEqual(config.python_version, "3.13")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.workers, 4)
        self.assertFalse(config.debug)
        self.assertEqual(config.environment, "production")

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DeploymentConfig(
            app_name="my-app",
            python_version="3.12",
            port=9000,
            workers=8,
            debug=True,
            environment="staging",
            database_url="postgres://localhost/db",
            redis_url="redis://localhost:6379/0",
        )

        self.assertEqual(config.app_name, "my-app")
        self.assertEqual(config.python_version, "3.12")
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.workers, 8)
        self.assertTrue(config.debug)
        self.assertEqual(config.environment, "staging")
        self.assertEqual(config.database_url, "postgres://localhost/db")
        self.assertEqual(config.redis_url, "redis://localhost:6379/0")

    def test_get_env_vars(self):
        """Test environment variable generation."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            database_url="postgres://localhost/db",
            redis_url="redis://localhost:6379/0",
            secret_key="my-secret-key",
            allowed_hosts=["example.com", "www.example.com"],
        )

        env_vars = config.get_env_vars()

        self.assertEqual(env_vars["DJANGO_SETTINGS_MODULE"], "config.settings")
        self.assertEqual(env_vars["DATABASE_URL"], "postgres://localhost/db")
        self.assertEqual(env_vars["REDIS_URL"], "redis://localhost:6379/0")
        self.assertEqual(env_vars["SECRET_KEY"], "my-secret-key")
        self.assertEqual(env_vars["ALLOWED_HOSTS"], "example.com,www.example.com")
        self.assertEqual(env_vars["DEBUG"], "false")

    def test_get_env_vars_with_extra(self):
        """Test environment variables with extra settings."""
        config = DeploymentConfig(
            app_name="test-app",
            extra_env={"CUSTOM_VAR": "custom_value"},
            secrets={"API_KEY": "secret-api-key"},
        )

        env_vars = config.get_env_vars()

        self.assertEqual(env_vars["CUSTOM_VAR"], "custom_value")
        self.assertEqual(env_vars["API_KEY"], "secret-api-key")


class TestDeploymentResult(TestCase):
    """Tests for DeploymentResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)

        self.assertEqual(result.status, DeploymentStatus.PENDING)
        self.assertIsNone(result.url)
        self.assertIsNone(result.deployment_id)
        self.assertEqual(result.logs, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.metadata, {})

    def test_success_property(self):
        """Test the success property."""
        success_result = DeploymentResult(status=DeploymentStatus.SUCCESS)
        failed_result = DeploymentResult(status=DeploymentStatus.FAILED)

        self.assertTrue(success_result.success)
        self.assertFalse(failed_result.success)

    def test_add_log(self):
        """Test adding logs."""
        result = DeploymentResult(status=DeploymentStatus.PENDING)
        result.add_log("Starting deployment")
        result.add_log("Deployment in progress")

        self.assertEqual(len(result.logs), 2)
        self.assertIn("Starting deployment", result.logs)
        self.assertIn("Deployment in progress", result.logs)

    def test_add_error(self):
        """Test adding errors."""
        result = DeploymentResult(status=DeploymentStatus.FAILED)
        result.add_error("Connection failed")
        result.add_error("Timeout error")

        self.assertEqual(len(result.errors), 2)
        self.assertIn("Connection failed", result.errors)
        self.assertIn("Timeout error", result.errors)


class TestSecretManager(TestCase):
    """Tests for SecretManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)
        self.manager = SecretManager(self.project_dir)

    def test_set_and_get(self):
        """Test setting and getting secrets."""
        self.manager.set("API_KEY", "secret-value")
        self.assertEqual(self.manager.get("API_KEY"), "secret-value")

    def test_get_default(self):
        """Test getting with default value."""
        self.assertEqual(self.manager.get("MISSING_KEY", "default"), "default")

    def test_get_all(self):
        """Test getting all secrets."""
        self.manager.set("KEY1", "value1")
        self.manager.set("KEY2", "value2")

        all_secrets = self.manager.get_all()
        self.assertEqual(all_secrets["KEY1"], "value1")
        self.assertEqual(all_secrets["KEY2"], "value2")

    def test_load_from_dotenv(self):
        """Test loading from .env file."""
        env_content = """
# Comment
DATABASE_URL=postgres://localhost/db
SECRET_KEY='my-secret'
DEBUG=true
"""
        env_file = self.project_dir / ".env"
        env_file.write_text(env_content)

        secrets = self.manager.load_from_dotenv()

        self.assertEqual(secrets["DATABASE_URL"], "postgres://localhost/db")
        self.assertEqual(secrets["SECRET_KEY"], "my-secret")
        self.assertEqual(secrets["DEBUG"], "true")

    def test_generate_secret_key(self):
        """Test secret key generation."""
        key1 = self.manager.generate_secret_key()
        key2 = self.manager.generate_secret_key()

        self.assertEqual(len(key1), 50)
        self.assertEqual(len(key2), 50)
        self.assertNotEqual(key1, key2)

    def test_generate_secret_key_custom_length(self):
        """Test secret key generation with custom length."""
        key = self.manager.generate_secret_key(length=100)
        self.assertEqual(len(key), 100)

    def test_export_to_file(self):
        """Test exporting secrets to file."""
        self.manager.set("KEY1", "value1")
        self.manager.set("KEY2", "value2")

        self.manager.export_to_file(".env.export")

        export_file = self.project_dir / ".env.export"
        self.assertTrue(export_file.exists())

        content = export_file.read_text()
        self.assertIn("KEY1=value1", content)
        self.assertIn("KEY2=value2", content)


# =============================================================================
# Docker Generator Tests
# =============================================================================


class TestDockerfileConfig(TestCase):
    """Tests for DockerfileConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DockerfileConfig()

        self.assertEqual(config.python_version, "3.13")
        self.assertEqual(config.working_dir, "/app")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.workers, 4)
        self.assertTrue(config.use_asgi)  # ASGI by default (Django #33497)

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DockerfileConfig(
            python_version="3.12",
            port=9000,
            workers=8,
            use_asgi=True,
            wsgi_module="myapp.wsgi:application",
            asgi_module="myapp.asgi:application",
        )

        self.assertEqual(config.python_version, "3.12")
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.workers, 8)
        self.assertTrue(config.use_asgi)


class TestDockerfileGenerator(TestCase):
    """Tests for DockerfileGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = DockerfileGenerator()

    def test_generate_production(self):
        """Test production Dockerfile generation."""
        dockerfile = self.generator.generate("production")

        self.assertIn("FROM python:3.13-slim", dockerfile)
        self.assertIn("WORKDIR /app", dockerfile)
        self.assertIn("pip install", dockerfile)
        self.assertIn("collectstatic", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("useradd", dockerfile)  # Non-root user

    def test_generate_development(self):
        """Test development Dockerfile generation."""
        dockerfile = self.generator.generate("development")

        self.assertIn("FROM python:3.13-slim", dockerfile)
        self.assertIn("runserver", dockerfile)
        self.assertNotIn("HEALTHCHECK", dockerfile)

    def test_generate_multistage(self):
        """Test multi-stage Dockerfile generation."""
        dockerfile = self.generator.generate("multistage")

        self.assertIn("AS builder", dockerfile)
        self.assertIn("AS runtime", dockerfile)
        self.assertIn("COPY --from=builder", dockerfile)

    def test_custom_config(self):
        """Test Dockerfile with custom config."""
        config = DockerfileConfig(
            python_version="3.12",
            port=9000,
            workers=8,
        )
        generator = DockerfileGenerator(config)
        dockerfile = generator.generate("production")

        self.assertIn("FROM python:3.12-slim", dockerfile)
        self.assertIn("PORT=9000", dockerfile)

    def test_asgi_config(self):
        """Test Dockerfile with ASGI config uses configured server backend."""
        config = DockerfileConfig(
            use_asgi=True,
            asgi_module="myapp.asgi:application",
        )
        generator = DockerfileGenerator(config)
        dockerfile = generator.generate("production")

        # Default backend is granian
        self.assertIn("granian", dockerfile)
        self.assertIn("myapp.asgi:application", dockerfile)

    def test_asgi_config_uvicorn(self):
        """Test Dockerfile with uvicorn backend."""
        from django_matt.deploy.base import ServerBackend

        config = DockerfileConfig(
            use_asgi=True,
            asgi_module="myapp.asgi:application",
            server_backend=ServerBackend.UVICORN,
        )
        generator = DockerfileGenerator(config)
        dockerfile = generator.generate("production")

        self.assertIn("uvicorn", dockerfile)
        self.assertIn("myapp.asgi:application", dockerfile)

    def test_backend_install_granian(self):
        """Granian Dockerfile installs the granian wheel and CMDs into granian."""
        from django_matt.deploy.base import ServerBackend

        config = DockerfileConfig(server_backend=ServerBackend.GRANIAN)
        dockerfile = DockerfileGenerator(config).generate("production")

        self.assertIn("uv pip install --no-cache-dir granian", dockerfile)
        self.assertIn("granian --interface asgi", dockerfile)
        self.assertIn("(granian backend)", dockerfile)
        self.assertIn(f"EXPOSE {config.port}", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)

    def test_backend_install_robyn(self):
        """Robyn Dockerfile installs robyn and CMDs into the robyn entrypoint."""
        from django_matt.deploy.base import ServerBackend

        config = DockerfileConfig(server_backend=ServerBackend.ROBYN)
        dockerfile = DockerfileGenerator(config).generate("production")

        self.assertIn("uv pip install --no-cache-dir robyn", dockerfile)
        self.assertIn("python -m robyn", dockerfile)
        self.assertIn("(robyn backend)", dockerfile)

    def test_backend_install_gunicorn_pairs_uvicorn(self):
        """Gunicorn install line pulls uvicorn[standard] for the worker class."""
        from django_matt.deploy.base import ServerBackend

        config = DockerfileConfig(server_backend=ServerBackend.GUNICORN)
        dockerfile = DockerfileGenerator(config).generate("production")

        self.assertIn(
            "uv pip install --no-cache-dir gunicorn 'uvicorn[standard]'", dockerfile
        )
        self.assertIn("--worker-class uvicorn.workers.UvicornWorker", dockerfile)

    def test_backend_install_uvicorn_extras(self):
        """Uvicorn install line uses the [standard] extra for httptools/uvloop."""
        from django_matt.deploy.base import ServerBackend

        config = DockerfileConfig(server_backend=ServerBackend.UVICORN)
        dockerfile = DockerfileGenerator(config).generate("production")

        self.assertIn("uv pip install --no-cache-dir uvicorn[standard]", dockerfile)
        self.assertIn("uvicorn ", dockerfile)

    def test_multistage_includes_backend_install(self):
        """Multi-stage Dockerfile installs the backend in the builder stage."""
        from django_matt.deploy.base import ServerBackend

        for backend in (ServerBackend.GRANIAN, ServerBackend.ROBYN, ServerBackend.UVICORN):
            with self.subTest(backend=backend):
                dockerfile = DockerfileGenerator(
                    DockerfileConfig(server_backend=backend)
                ).generate("multistage")

                self.assertIn(backend.get_install_package(), dockerfile)
                self.assertIn("AS builder", dockerfile)
                self.assertIn("AS runtime", dockerfile)
                self.assertIn(f"({backend.value} backend)", dockerfile)


class TestComposeGenerator(TestCase):
    """Tests for ComposeGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.generator = ComposeGenerator(
            app_name="test-app",
            include_db=True,
            include_redis=True,
        )

    def test_generate_production(self):
        """Test production docker-compose generation."""
        compose = self.generator.generate("production")

        self.assertIn("version:", compose)
        self.assertIn("services:", compose)
        self.assertIn("web:", compose)
        self.assertIn("db:", compose)
        self.assertIn("redis:", compose)
        self.assertIn("postgres:", compose)

    def test_generate_development(self):
        """Test development docker-compose generation."""
        compose = self.generator.generate("development")

        self.assertIn("version:", compose)
        self.assertIn("services:", compose)
        self.assertIn("web:", compose)
        self.assertIn("DEBUG", compose)

    def test_without_db(self):
        """Test generation without database."""
        generator = ComposeGenerator(
            app_name="test-app",
            include_db=False,
        )
        compose = generator.generate("production")

        self.assertIn("web:", compose)
        self.assertNotIn("postgres:", compose)

    def test_with_celery(self):
        """Test generation with Celery workers."""
        generator = ComposeGenerator(
            app_name="test-app",
            include_celery=True,
            include_redis=True,
        )
        compose = generator.generate("production")

        self.assertIn("celery_worker:", compose)
        self.assertIn("celery_beat:", compose)

    def test_generate_caddyfile(self):
        """Test Caddyfile generation."""
        generator = ComposeGenerator(
            app_name="test-app",
            domain="example.com",
        )
        caddyfile = generator.generate_caddyfile()

        self.assertIn("example.com", caddyfile)
        self.assertIn("reverse_proxy", caddyfile)
        self.assertIn("/static/", caddyfile)
        self.assertIn("/media/", caddyfile)

    def test_generate_nginx_conf(self):
        """Test nginx.conf generation."""
        generator = ComposeGenerator(
            app_name="test-app",
            domain="example.com",
        )
        nginx_conf = generator.generate_nginx_conf()

        self.assertIn("example.com", nginx_conf)
        self.assertIn("upstream django", nginx_conf)
        self.assertIn("location /static/", nginx_conf)

    def test_generate_dockerignore(self):
        """Test .dockerignore generation."""
        dockerignore = self.generator.generate_dockerignore()

        self.assertIn("__pycache__", dockerignore)
        self.assertIn(".git/", dockerignore)
        self.assertIn("*.py[cod]", dockerignore)
        self.assertIn(".env", dockerignore)


# =============================================================================
# Environment Management Tests
# =============================================================================


class TestEnvironment(TestCase):
    """Tests for Environment enum."""

    def test_environment_values(self):
        """Test that all environment values exist."""
        self.assertEqual(Environment.DEVELOPMENT.value, "development")
        self.assertEqual(Environment.STAGING.value, "staging")
        self.assertEqual(Environment.PRODUCTION.value, "production")
        self.assertEqual(Environment.TESTING.value, "testing")
        self.assertEqual(Environment.LOCAL.value, "local")


class TestEnvironmentConfig(TestCase):
    """Tests for EnvironmentConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = EnvironmentConfig(name="test")

        self.assertEqual(config.name, "test")
        self.assertEqual(config.display_name, "Test")
        self.assertFalse(config.debug)
        self.assertEqual(config.log_level, "INFO")

    def test_development_preset(self):
        """Test development environment preset."""
        config = EnvironmentConfig.development()

        self.assertEqual(config.name, "development")
        self.assertTrue(config.debug)
        self.assertIn("localhost", config.allowed_hosts)
        self.assertEqual(config.log_level, "DEBUG")

    def test_staging_preset(self):
        """Test staging environment preset."""
        config = EnvironmentConfig.staging(domain="staging.example.com")

        self.assertEqual(config.name, "staging")
        self.assertFalse(config.debug)
        self.assertIn("staging.example.com", config.allowed_hosts)
        self.assertTrue(config.secure_ssl_redirect)
        self.assertTrue(config.session_cookie_secure)

    def test_production_preset(self):
        """Test production environment preset."""
        config = EnvironmentConfig.production(domain="example.com")

        self.assertEqual(config.name, "production")
        self.assertFalse(config.debug)
        self.assertIn("example.com", config.allowed_hosts)
        self.assertTrue(config.secure_ssl_redirect)
        self.assertTrue(config.session_cookie_secure)
        self.assertTrue(config.csrf_cookie_secure)
        self.assertEqual(config.secure_hsts_seconds, 31536000)

    def test_to_env_file(self):
        """Test .env file generation."""
        config = EnvironmentConfig(
            name="test",
            debug=True,
            database_url="postgres://localhost/db",
            secret_key="test-secret",
        )

        env_content = config.to_env_file()

        self.assertIn("DJANGO_ENV=test", env_content)
        self.assertIn("DEBUG=true", env_content)
        self.assertIn("DATABASE_URL=postgres://localhost/db", env_content)
        self.assertIn("SECRET_KEY=test-secret", env_content)

    def test_to_django_settings(self):
        """Test Django settings dictionary generation."""
        config = EnvironmentConfig(
            name="test",
            debug=True,
            allowed_hosts=["localhost"],
            secret_key="test-secret",
        )

        settings = config.to_django_settings()

        self.assertTrue(settings["DEBUG"])
        self.assertEqual(settings["ALLOWED_HOSTS"], ["localhost"])
        self.assertEqual(settings["SECRET_KEY"], "test-secret")


class TestEnvironmentManager(TestCase):
    """Tests for EnvironmentManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = EnvironmentManager(Path(self.temp_dir))

    def test_add_and_get(self):
        """Test adding and getting environments."""
        config = EnvironmentConfig(name="test")
        self.manager.add(config)

        retrieved = self.manager.get("test")
        self.assertEqual(retrieved.name, "test")

    def test_remove(self):
        """Test removing environments."""
        config = EnvironmentConfig(name="test")
        self.manager.add(config)
        self.manager.remove("test")

        self.assertIsNone(self.manager.get("test"))

    def test_list_environments(self):
        """Test listing all environments."""
        self.manager.add(EnvironmentConfig(name="dev"))
        self.manager.add(EnvironmentConfig(name="prod"))

        envs = self.manager.list_environments()

        self.assertIn("dev", envs)
        self.assertIn("prod", envs)

    def test_init_standard_environments(self):
        """Test initializing standard environments."""
        self.manager.init_standard_environments("example.com")

        self.assertIsNotNone(self.manager.get("development"))
        self.assertIsNotNone(self.manager.get("staging"))
        self.assertIsNotNone(self.manager.get("production"))

    def test_validate_production(self):
        """Test production environment validation."""
        # Invalid production config (debug=True)
        config = EnvironmentConfig(
            name="production",
            debug=True,
            allowed_hosts=["example.com"],
        )
        self.manager.add(config)

        errors = self.manager.validate("production")

        self.assertTrue(any("DEBUG" in e for e in errors))

    def test_validate_all(self):
        """Test validating all environments."""
        self.manager.init_standard_environments("example.com")

        all_errors = self.manager.validate_all()

        self.assertIn("development", all_errors)
        self.assertIn("staging", all_errors)
        self.assertIn("production", all_errors)

    def test_diff(self):
        """Test comparing two environments."""
        self.manager.add(EnvironmentConfig(name="env1", debug=True, log_level="DEBUG"))
        self.manager.add(EnvironmentConfig(name="env2", debug=False, log_level="INFO"))

        diffs = self.manager.diff("env1", "env2")

        self.assertIn("debug", diffs)
        self.assertEqual(diffs["debug"], (True, False))
        self.assertIn("log_level", diffs)

    def test_to_json(self):
        """Test JSON export."""
        self.manager.add(EnvironmentConfig(name="test", debug=True))

        json_str = self.manager.to_json()
        data = json.loads(json_str)

        self.assertIn("test", data)
        self.assertTrue(data["test"]["debug"])

    def test_from_json(self):
        """Test JSON import."""
        json_str = json.dumps(
            {
                "test": {
                    "name": "test",
                    "display_name": "Test",
                    "debug": True,
                    "allowed_hosts": ["localhost"],
                    "database_url": None,
                    "redis_url": None,
                    "cache_backend": "django.core.cache.backends.locmem.LocMemCache",
                    "email_backend": "django.core.mail.backends.console.EmailBackend",
                    "use_s3": False,
                    "log_level": "DEBUG",
                    "secure_ssl_redirect": False,
                    "session_cookie_secure": False,
                    "csrf_cookie_secure": False,
                    "secure_hsts_seconds": 0,
                    "extra_settings": {},
                    "env_vars": {},
                }
            }
        )

        manager = EnvironmentManager.from_json(json_str)

        self.assertIsNotNone(manager.get("test"))
        self.assertTrue(manager.get("test").debug)


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthStatus(TestCase):
    """Tests for HealthStatus enum."""

    def test_status_values(self):
        """Test that all status values exist."""
        self.assertEqual(HealthStatus.HEALTHY.value, "healthy")
        self.assertEqual(HealthStatus.UNHEALTHY.value, "unhealthy")
        self.assertEqual(HealthStatus.DEGRADED.value, "degraded")


class TestCheckResult(TestCase):
    """Tests for CheckResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = CheckResult(name="test", status=HealthStatus.HEALTHY)

        self.assertEqual(result.name, "test")
        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertEqual(result.message, "")
        self.assertEqual(result.duration_ms, 0.0)
        self.assertEqual(result.metadata, {})

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = CheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connection successful",
            duration_ms=5.5,
            metadata={"engine": "postgresql"},
        )

        data = result.to_dict()

        self.assertEqual(data["name"], "database")
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["message"], "Connection successful")
        self.assertEqual(data["duration_ms"], 5.5)
        self.assertEqual(data["metadata"]["engine"], "postgresql")


class TestHealthCheckResponse(TestCase):
    """Tests for HealthCheckResponse dataclass."""

    def test_default_values(self):
        """Test default response values."""
        response = HealthCheckResponse(status=HealthStatus.HEALTHY)

        self.assertEqual(response.status, HealthStatus.HEALTHY)
        self.assertEqual(response.checks, [])
        self.assertEqual(response.version, "")

    def test_to_dict(self):
        """Test dictionary conversion."""
        response = HealthCheckResponse(
            status=HealthStatus.HEALTHY,
            checks=[
                CheckResult(name="db", status=HealthStatus.HEALTHY),
                CheckResult(name="cache", status=HealthStatus.HEALTHY),
            ],
            version="1.0.0",
            uptime_seconds=3600.5,
        )

        data = response.to_dict()

        self.assertEqual(data["status"], "healthy")
        self.assertEqual(len(data["checks"]), 2)
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["uptime_seconds"], 3600.5)


class TestHealthCheck(TestCase):
    """Tests for HealthCheck class."""

    def setUp(self):
        """Set up test fixtures."""
        self.health = HealthCheck(
            include_db=False,
            include_cache=False,
        )

    def test_default_config(self):
        """Test default health check configuration."""
        health = HealthCheck()

        self.assertTrue(health.include_db)
        self.assertTrue(health.include_cache)
        self.assertFalse(health.include_migrations)

    def test_add_custom_check(self):
        """Test adding a custom health check."""

        def my_check():
            return CheckResult(
                name="my_check",
                status=HealthStatus.HEALTHY,
                message="All good",
            )

        self.health.add_check("my_check", my_check)
        response = self.health.run_checks()

        self.assertEqual(response.status, HealthStatus.HEALTHY)
        self.assertTrue(any(c.name == "my_check" for c in response.checks))

    def test_failing_custom_check(self):
        """Test a failing custom health check."""

        def failing_check():
            return CheckResult(
                name="failing",
                status=HealthStatus.UNHEALTHY,
                message="Service down",
            )

        self.health.add_check("failing", failing_check)
        response = self.health.run_checks()

        self.assertEqual(response.status, HealthStatus.UNHEALTHY)

    def test_degraded_check(self):
        """Test a degraded health check."""

        def degraded_check():
            return CheckResult(
                name="degraded",
                status=HealthStatus.DEGRADED,
                message="Running slowly",
            )

        self.health.add_check("degraded", degraded_check)
        response = self.health.run_checks()

        self.assertEqual(response.status, HealthStatus.DEGRADED)

    def test_remove_check(self):
        """Test removing a health check."""

        def my_check():
            return CheckResult(name="my_check", status=HealthStatus.HEALTHY)

        self.health.add_check("my_check", my_check)
        self.health.remove_check("my_check")

        response = self.health.run_checks()
        self.assertFalse(any(c.name == "my_check" for c in response.checks))

    def test_exception_in_check(self):
        """Test handling exceptions in health checks."""

        def bad_check():
            raise Exception("Something went wrong")

        self.health.add_check("bad", bad_check)
        response = self.health.run_checks()

        self.assertEqual(response.status, HealthStatus.UNHEALTHY)
        bad_result = next(c for c in response.checks if c.name == "bad")
        self.assertEqual(bad_result.status, HealthStatus.UNHEALTHY)
        self.assertIn("Something went wrong", bad_result.message)


class TestHealthCheckViews(TestCase):
    """Tests for health check view functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_liveness_view(self):
        """Test liveness check view."""
        request = self.factory.get("/live/")
        response = liveness_check_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("uptime_seconds", data)

    def test_health_view_status_code(self):
        """Test health check view returns correct status codes."""
        # The actual response depends on DB/cache availability
        request = self.factory.get("/health/")
        response = health_check_view(request)

        # Should return either 200 (healthy) or 503 (unhealthy)
        self.assertIn(response.status_code, [200, 503])


class TestGetUptime(TestCase):
    """Tests for get_uptime function."""

    def test_uptime_is_positive(self):
        """Test that uptime is a positive number."""
        uptime = get_uptime()
        self.assertGreater(uptime, 0)

    def test_uptime_is_float(self):
        """Test that uptime is a float."""
        uptime = get_uptime()
        self.assertIsInstance(uptime, float)


# =============================================================================
# Provider Tests
# =============================================================================


class TestProviderRegistry(TestCase):
    """Tests for provider registration and lookup."""

    def test_list_providers(self):
        """Test listing registered providers."""
        providers = list_providers()

        # Check that our providers are registered
        self.assertIn("fly", providers)
        self.assertIn("railway", providers)
        self.assertIn("render", providers)
        self.assertIn("digitalocean", providers)
        self.assertIn("aws", providers)
        self.assertIn("hetzner", providers)

    def test_get_provider(self):
        """Test getting a provider by name."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
        )

        provider = get_provider("fly", config)
        self.assertEqual(provider.name, "fly")
        self.assertEqual(provider.display_name, "Fly.io")

    def test_get_unknown_provider(self):
        """Test getting an unknown provider raises error."""
        config = DeploymentConfig(app_name="test-app")

        with self.assertRaises(ValueError) as ctx:
            get_provider("unknown", config)

        self.assertIn("Unknown provider", str(ctx.exception))


class TestFlyioProvider(TestCase):
    """Tests for Fly.io provider."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        self.provider = get_provider("fly", self.config)

    def test_validate_missing_settings(self):
        """Test validation catches missing settings."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="",
        )
        provider = get_provider("fly", config)

        errors = provider.validate()
        self.assertTrue(any("django_settings_module" in e for e in errors))

    def test_validate_app_name_too_long(self):
        """Test validation catches too long app name."""
        config = DeploymentConfig(
            app_name="a" * 35,
            django_settings_module="config.settings",
        )
        provider = get_provider("fly", config)

        errors = provider.validate()
        self.assertTrue(any("30 characters" in e for e in errors))

    def test_generate_config_files(self):
        """Test configuration file generation."""
        configs = self.provider.generate_config()

        self.assertIn("fly.toml", configs)
        self.assertIn("Dockerfile", configs)
        self.assertIn(".dockerignore", configs)
        self.assertIn("release.sh", configs)

    def test_fly_toml_content(self):
        """Test fly.toml content."""
        configs = self.provider.generate_config()
        fly_toml = configs["fly.toml"]

        self.assertIn("test-app", fly_toml)
        self.assertIn("http_service", fly_toml)
        self.assertIn("health", fly_toml)


class TestRailwayProvider(TestCase):
    """Tests for Railway provider."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        self.provider = get_provider("railway", self.config)

    def test_generate_config_files(self):
        """Test configuration file generation."""
        configs = self.provider.generate_config()

        self.assertIn("railway.json", configs)
        self.assertIn("Procfile", configs)
        self.assertIn("nixpacks.toml", configs)

    def test_procfile_content(self):
        """Test Procfile content."""
        configs = self.provider.generate_config()
        procfile = configs["Procfile"]

        self.assertIn("web:", procfile)
        # Default server backend is granian
        self.assertIn("granian", procfile)
        self.assertIn("release:", procfile)


class TestRenderProvider(TestCase):
    """Tests for Render provider."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        self.provider = get_provider("render", self.config)

    def test_generate_config_files(self):
        """Test configuration file generation."""
        configs = self.provider.generate_config()

        self.assertIn("render.yaml", configs)
        self.assertIn("build.sh", configs)

    def test_render_yaml_content(self):
        """Test render.yaml content."""
        configs = self.provider.generate_config()
        render_yaml = configs["render.yaml"]

        self.assertIn("test-app", render_yaml)
        self.assertIn("services:", render_yaml)
        self.assertIn("healthCheckPath", render_yaml)


class TestDigitalOceanProvider(TestCase):
    """Tests for DigitalOcean provider."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        self.provider = get_provider("digitalocean", self.config)

    def test_validate_app_name_too_long(self):
        """Test validation catches too long app name."""
        config = DeploymentConfig(
            app_name="a" * 35,
            django_settings_module="config.settings",
        )
        provider = get_provider("digitalocean", config)

        errors = provider.validate()
        self.assertTrue(any("32 characters" in e for e in errors))

    def test_generate_config_files(self):
        """Test configuration file generation."""
        configs = self.provider.generate_config()

        self.assertIn(".do/app.yaml", configs)
        self.assertIn("Dockerfile", configs)


class TestAWSProvider(TestCase):
    """Tests for AWS provider."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        self.provider = get_provider("aws", self.config)

    def test_generate_config_files(self):
        """Test configuration file generation."""
        configs = self.provider.generate_config()

        self.assertIn("Dockerfile", configs)
        self.assertIn("apprunner.yaml", configs)
        self.assertIn("buildspec.yml", configs)

    def test_buildspec_content(self):
        """Test buildspec.yml content."""
        configs = self.provider.generate_config()
        buildspec = configs["buildspec.yml"]

        self.assertIn("version: 0.2", buildspec)
        self.assertIn("pre_build", buildspec)
        self.assertIn("build", buildspec)
        self.assertIn("post_build", buildspec)


class TestHetznerProvider(TestCase):
    """Tests for Hetzner provider."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
            allowed_hosts=["example.com"],
        )
        self.provider = get_provider("hetzner", self.config)

    def test_validate_missing_allowed_hosts(self):
        """Test validation catches missing allowed_hosts."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            allowed_hosts=[],
        )
        provider = get_provider("hetzner", config)

        errors = provider.validate()
        self.assertTrue(any("allowed_hosts" in e for e in errors))

    def test_generate_config_files(self):
        """Test configuration file generation."""
        configs = self.provider.generate_config()

        self.assertIn("docker-compose.yml", configs)
        self.assertIn("Dockerfile", configs)
        self.assertIn("Caddyfile", configs)
        self.assertIn("cloud-init.yml", configs)
        self.assertIn("deploy.sh", configs)
        self.assertIn(".env.production", configs)

    def test_caddyfile_content(self):
        """Test Caddyfile content."""
        configs = self.provider.generate_config()
        caddyfile = configs["Caddyfile"]

        self.assertIn("example.com", caddyfile)
        self.assertIn("reverse_proxy", caddyfile)
        self.assertIn("encode gzip", caddyfile)


# =============================================================================
# CONN_MAX_AGE Enforcement Tests
# =============================================================================


class TestConnMaxAgeEnforcement(TestCase):
    """
    Tests that CONN_MAX_AGE=0 is enforced across all deployment providers,
    environment configs, and settings files.

    Django ticket #33497: persistent connections leak under ASGI.
    """

    # ---- Environment Config Presets ----

    def test_production_env_config_conn_max_age_zero(self):
        """Production EnvironmentConfig preset must have conn_max_age=0."""
        config = EnvironmentConfig.production(domain="example.com")
        self.assertEqual(config.conn_max_age, 0)

    def test_staging_env_config_conn_max_age_zero(self):
        """Staging EnvironmentConfig preset must have conn_max_age=0."""
        config = EnvironmentConfig.staging(domain="staging.example.com")
        self.assertEqual(config.conn_max_age, 0)

    def test_development_env_config_conn_max_age_zero(self):
        """Development EnvironmentConfig preset must have conn_max_age=0."""
        config = EnvironmentConfig.development()
        self.assertEqual(config.conn_max_age, 0)

    def test_default_env_config_conn_max_age_zero(self):
        """Default EnvironmentConfig must have conn_max_age=0."""
        config = EnvironmentConfig(name="any")
        self.assertEqual(config.conn_max_age, 0)

    def test_production_to_django_settings_conn_max_age(self):
        """Production env to_django_settings() must pass conn_max_age=0 to dj_database_url."""
        import pytest

        pytest.importorskip("dj_database_url")
        config = EnvironmentConfig.production(
            domain="example.com",
            database_url="postgres://user:pass@host:5432/db",
        )
        settings = config.to_django_settings()
        # dj_database_url.parse receives conn_max_age=0
        self.assertEqual(
            settings["DATABASES"]["default"].get("CONN_MAX_AGE", None),
            0,
        )

    # ---- Docker Template ----

    def test_docker_default_uses_asgi(self):
        """DockerfileConfig must default to ASGI (use_asgi=True)."""
        config = DockerfileConfig()
        self.assertTrue(config.use_asgi)

    def test_docker_production_uses_granian(self):
        """Production Dockerfile CMD must use granian (default ASGI server)."""
        config = DockerfileConfig()  # use_asgi=True by default
        generator = DockerfileGenerator(config)
        dockerfile = generator.generate("production")
        self.assertIn("granian", dockerfile)

    def test_docker_multistage_uses_granian(self):
        """Multi-stage Dockerfile CMD must use granian (default ASGI server)."""
        config = DockerfileConfig()
        generator = DockerfileGenerator(config)
        dockerfile = generator.generate("multistage")
        self.assertIn("granian", dockerfile)

    # ---- config/components/database.py ----

    def test_get_database_config_default_conn_max_age_zero(self):
        """get_database_config() with no env vars must return CONN_MAX_AGE=0."""
        import os
        # Clear relevant env vars to test defaults
        env_backup = {}
        for key in ["DB_CONN_MAX_AGE", "DJANGO_ENV"]:
            env_backup[key] = os.environ.pop(key, None)

        try:
            from django_matt.config.components.database import get_connection_pool_config

            pool_config = get_connection_pool_config()
            self.assertEqual(pool_config["CONN_MAX_AGE"], 0)
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val

    # ---- Provider configs (verify no non-zero CONN_MAX_AGE in generated output) ----

    def test_flyio_provider_no_nonzero_conn_max_age(self):
        """Fly.io provider config must not set CONN_MAX_AGE to a non-zero value."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        provider = get_provider("fly", config)
        configs = provider.generate_config()
        for filename, content in configs.items():
            if "CONN_MAX_AGE" in content:
                # If CONN_MAX_AGE appears, it must be 0
                self.assertIn("CONN_MAX_AGE=0", content.replace(" ", "").replace('"', '').replace("'", ""),
                              msg=f"{filename} sets CONN_MAX_AGE to non-zero")

    def test_railway_provider_no_nonzero_conn_max_age(self):
        """Railway provider config must not set CONN_MAX_AGE to a non-zero value."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        provider = get_provider("railway", config)
        configs = provider.generate_config()
        for filename, content in configs.items():
            if "CONN_MAX_AGE" in content:
                self.assertIn("CONN_MAX_AGE=0", content.replace(" ", "").replace('"', '').replace("'", ""),
                              msg=f"{filename} sets CONN_MAX_AGE to non-zero")

    def test_render_provider_no_nonzero_conn_max_age(self):
        """Render provider config must not set CONN_MAX_AGE to a non-zero value."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        provider = get_provider("render", config)
        configs = provider.generate_config()
        for filename, content in configs.items():
            if "CONN_MAX_AGE" in content:
                self.assertIn("CONN_MAX_AGE=0", content.replace(" ", "").replace('"', '').replace("'", ""),
                              msg=f"{filename} sets CONN_MAX_AGE to non-zero")

    def test_aws_provider_no_nonzero_conn_max_age(self):
        """AWS provider config must not set CONN_MAX_AGE to a non-zero value."""
        config = DeploymentConfig(
            app_name="test-app",
            django_settings_module="config.settings",
            project_dir=Path(tempfile.mkdtemp()),
        )
        provider = get_provider("aws", config)
        configs = provider.generate_config()
        for filename, content in configs.items():
            if "CONN_MAX_AGE" in content:
                self.assertIn("CONN_MAX_AGE=0", content.replace(" ", "").replace('"', '').replace("'", ""),
                              msg=f"{filename} sets CONN_MAX_AGE to non-zero")
