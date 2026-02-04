"""
Django Matt project health check command.

Performs comprehensive health checks on the project:
- Database connectivity
- Redis/cache connectivity
- Migration status
- Security settings
- Environment information

Usage:
    python manage.py matt_status                # Full health check
    python manage.py matt_status --json         # Output as JSON
    python manage.py matt_status --check db     # Check only database
    python manage.py matt_status --verbose      # Show detailed info
"""

import json
import os
import sys
from typing import Any

from django.conf import settings

from django_matt.cli import MattCommand


class Command(MattCommand):
    """Perform comprehensive project health check."""

    help = "Check project health: database, cache, migrations, security, and environment"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--check",
            "-c",
            choices=["db", "cache", "migrations", "security", "env", "deps", "all"],
            default="all",
            help="Specific check to run (default: all)",
        )
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Show detailed information",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Attempt to fix issues where possible",
        )

    def handle(self, *args, **options):
        output_json = options.get("json", False)
        check = options.get("check", "all")
        verbose = options.get("verbose", False)
        fix = options.get("fix", False)

        # Run checks
        results = {"checks": [], "summary": {}}

        if check in ("all", "db"):
            results["checks"].append(self._check_database(verbose))

        if check in ("all", "cache"):
            results["checks"].append(self._check_cache(verbose))

        if check in ("all", "migrations"):
            results["checks"].append(self._check_migrations(verbose))

        if check in ("all", "security"):
            results["checks"].extend(self._check_security(verbose))

        if check in ("all", "env"):
            results["checks"].append(self._check_environment(verbose))

        if check in ("all", "deps"):
            results["checks"].extend(self._check_dependencies(verbose))

        # Generate summary
        results["summary"] = self._generate_summary(results["checks"])

        # Output results
        if output_json:
            self.stdout.write(json.dumps(results, indent=2, default=str))
        else:
            self._display_results(results, verbose, fix)

    def _check_database(self, verbose: bool = False) -> dict[str, Any]:
        """Check database connectivity and configuration."""
        check = {
            "name": "Database",
            "status": "ok",
            "message": "",
            "details": {},
        }

        try:
            from django.db import connection

            # Test connection
            connection.ensure_connection()

            # Get database info
            db_settings = settings.DATABASES.get("default", {})
            check["details"]["engine"] = db_settings.get("ENGINE", "").split(".")[-1]
            check["details"]["name"] = db_settings.get("NAME", "")
            check["details"]["host"] = db_settings.get("HOST", "localhost") or "localhost"

            # Check if we can execute a query
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    check["message"] = f"Connected to {check['details']['engine']}"

            # Check connection pool if available
            if hasattr(connection, "pool"):
                check["details"]["pool_enabled"] = True

            # Get table count
            with connection.cursor() as cursor:
                if "postgresql" in check["details"]["engine"]:
                    cursor.execute(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                elif "sqlite" in check["details"]["engine"]:
                    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
                else:
                    cursor.execute("SELECT count(*) FROM information_schema.tables")

                check["details"]["table_count"] = cursor.fetchone()[0]

        except Exception as e:
            check["status"] = "error"
            check["message"] = str(e)

        return check

    def _check_cache(self, verbose: bool = False) -> dict[str, Any]:
        """Check cache connectivity and configuration."""
        check = {
            "name": "Cache",
            "status": "ok",
            "message": "",
            "details": {},
        }

        try:
            from django.core.cache import cache

            # Get cache backend info
            cache_settings = settings.CACHES.get("default", {})
            backend = cache_settings.get("BACKEND", "")
            check["details"]["backend"] = backend.split(".")[-1]

            if "LOCATION" in cache_settings:
                location = cache_settings["LOCATION"]
                if isinstance(location, str) and "redis" in location.lower():
                    check["details"]["type"] = "Redis"
                    # Mask credentials in URL
                    if "@" in location:
                        check["details"]["location"] = location.split("@")[-1]
                    else:
                        check["details"]["location"] = location
                else:
                    check["details"]["location"] = str(location)[:50]

            # Test cache operations
            test_key = "_matt_status_test"
            test_value = "test_value"

            cache.set(test_key, test_value, 10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)

            if retrieved == test_value:
                check["message"] = f"Cache working ({check['details']['backend']})"
            else:
                check["status"] = "warning"
                check["message"] = "Cache set/get mismatch"

        except Exception as e:
            check["status"] = "warning"
            check["message"] = f"Cache not configured or unavailable: {e}"

        return check

    def _check_migrations(self, verbose: bool = False) -> dict[str, Any]:
        """Check migration status."""
        check = {
            "name": "Migrations",
            "status": "ok",
            "message": "",
            "details": {},
        }

        try:
            from django.db import connection
            from django.db.migrations.executor import MigrationExecutor

            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

            pending_count = len(plan)
            check["details"]["pending_migrations"] = pending_count

            # Get applied migrations count
            applied = len(executor.loader.applied_migrations)
            check["details"]["applied_migrations"] = applied

            if pending_count > 0:
                check["status"] = "warning"
                check["message"] = f"{pending_count} pending migration(s)"

                if verbose:
                    check["details"]["pending"] = [
                        f"{migration.app_label}.{migration.name}" for migration, _ in plan[:5]
                    ]
            else:
                check["message"] = f"All migrations applied ({applied} total)"

        except Exception as e:
            check["status"] = "error"
            check["message"] = str(e)

        return check

    def _check_security(self, verbose: bool = False) -> list[dict[str, Any]]:
        """Check security settings."""
        checks = []

        # DEBUG mode check
        debug_check = {
            "name": "DEBUG Mode",
            "status": "ok" if not settings.DEBUG else "warning",
            "message": "DEBUG is OFF"
            if not settings.DEBUG
            else "DEBUG is ON (disable in production)",
            "details": {"debug": settings.DEBUG},
        }
        checks.append(debug_check)

        # SECRET_KEY check
        secret_check = {
            "name": "SECRET_KEY",
            "status": "ok",
            "message": "",
            "details": {},
        }

        secret_key = getattr(settings, "SECRET_KEY", "")
        if not secret_key:
            secret_check["status"] = "error"
            secret_check["message"] = "SECRET_KEY not set"
        elif secret_key.startswith("django-insecure"):
            secret_check["status"] = "warning"
            secret_check["message"] = "Using insecure default SECRET_KEY"
        elif len(secret_key) < 50:
            secret_check["status"] = "warning"
            secret_check["message"] = "SECRET_KEY may be too short"
        else:
            secret_check["message"] = "SECRET_KEY configured"

        checks.append(secret_check)

        # ALLOWED_HOSTS check
        hosts_check = {
            "name": "ALLOWED_HOSTS",
            "status": "ok",
            "message": "",
            "details": {},
        }

        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        if not allowed_hosts:
            hosts_check["status"] = "warning" if settings.DEBUG else "error"
            hosts_check["message"] = "ALLOWED_HOSTS is empty"
        elif "*" in allowed_hosts and not settings.DEBUG:
            hosts_check["status"] = "warning"
            hosts_check["message"] = "ALLOWED_HOSTS contains wildcard '*'"
        else:
            hosts_check["message"] = f"{len(allowed_hosts)} host(s) configured"
            hosts_check["details"]["hosts"] = allowed_hosts[:5]

        checks.append(hosts_check)

        # HTTPS settings (production only)
        if not settings.DEBUG:
            ssl_check = {
                "name": "SSL/HTTPS",
                "status": "ok",
                "message": "",
                "details": {},
            }

            issues = []
            if not getattr(settings, "SECURE_SSL_REDIRECT", False):
                issues.append("SECURE_SSL_REDIRECT not enabled")
            if not getattr(settings, "SESSION_COOKIE_SECURE", False):
                issues.append("SESSION_COOKIE_SECURE not enabled")
            if not getattr(settings, "CSRF_COOKIE_SECURE", False):
                issues.append("CSRF_COOKIE_SECURE not enabled")

            if issues:
                ssl_check["status"] = "warning"
                ssl_check["message"] = "; ".join(issues[:2])
                ssl_check["details"]["issues"] = issues
            else:
                ssl_check["message"] = "SSL settings configured"

            checks.append(ssl_check)

        # CORS check
        cors_check = {
            "name": "CORS",
            "status": "ok",
            "message": "",
            "details": {},
        }

        cors_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", None)
        cors_all = getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False)

        if cors_all and not settings.DEBUG:
            cors_check["status"] = "warning"
            cors_check["message"] = "CORS_ALLOW_ALL_ORIGINS is True"
        elif cors_origins:
            cors_check["message"] = f"{len(cors_origins)} origin(s) allowed"
        else:
            cors_check["message"] = "CORS not configured"

        checks.append(cors_check)

        return checks

    def _check_environment(self, verbose: bool = False) -> dict[str, Any]:
        """Check environment information."""
        import platform

        import django

        check = {
            "name": "Environment",
            "status": "ok",
            "message": "",
            "details": {},
        }

        try:
            # Python version
            python_version = (
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            )
            check["details"]["python_version"] = python_version

            # Django version
            check["details"]["django_version"] = django.get_version()

            # django-matt version
            try:
                from django_matt import __version__ as matt_version

                check["details"]["django_matt_version"] = matt_version
            except (ImportError, AttributeError):
                check["details"]["django_matt_version"] = "unknown"

            # Platform info
            check["details"]["platform"] = platform.system()
            check["details"]["platform_version"] = platform.release()

            # Environment name
            env_name = os.environ.get("DJANGO_ENV", os.environ.get("ENVIRONMENT", "development"))
            check["details"]["environment"] = env_name

            # BASE_DIR
            check["details"]["base_dir"] = str(settings.BASE_DIR)

            # Time zone
            check["details"]["timezone"] = str(getattr(settings, "TIME_ZONE", "UTC"))

            check["message"] = f"Python {python_version}, Django {django.get_version()}"

            # Check Python version compatibility
            if sys.version_info < (3, 12):
                check["status"] = "warning"
                check["message"] += " (Python 3.12+ recommended)"

        except Exception as e:
            check["status"] = "error"
            check["message"] = str(e)

        return check

    def _check_dependencies(self, verbose: bool = False) -> list[dict[str, Any]]:
        """Check installed dependencies."""
        checks = []

        # Required dependencies
        required = {
            "django": "Django",
            "pydantic": "Pydantic",
            "rich": "Rich (CLI)",
        }

        for package, name in required.items():
            check = {
                "name": f"Dependency: {name}",
                "status": "ok",
                "message": "",
                "details": {},
            }

            try:
                module = __import__(package)
                version = getattr(module, "__version__", getattr(module, "VERSION", "unknown"))
                if isinstance(version, tuple):
                    version = ".".join(map(str, version))
                check["message"] = f"v{version}"
                check["details"]["version"] = version
            except ImportError:
                check["status"] = "error"
                check["message"] = "Not installed"

            checks.append(check)

        # Optional performance dependencies
        optional = {
            "orjson": "orjson (fast JSON)",
            "ujson": "ujson (fast JSON)",
            "msgpack": "msgpack (binary serialization)",
            "redis": "redis (caching)",
        }

        for package, name in optional.items():
            check = {
                "name": f"Optional: {name}",
                "status": "ok",
                "message": "",
                "details": {},
            }

            try:
                module = __import__(package)
                version = getattr(module, "__version__", getattr(module, "VERSION", "unknown"))
                if isinstance(version, tuple):
                    version = ".".join(map(str, version))
                check["message"] = f"v{version}"
                check["details"]["version"] = version
            except ImportError:
                check["status"] = "info"
                check["message"] = "Not installed (optional)"

            checks.append(check)

        return checks

    def _generate_summary(self, checks: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate summary from checks."""
        ok_count = len([c for c in checks if c["status"] == "ok"])
        warning_count = len([c for c in checks if c["status"] == "warning"])
        error_count = len([c for c in checks if c["status"] == "error"])
        info_count = len([c for c in checks if c["status"] == "info"])

        overall = "healthy"
        if error_count > 0:
            overall = "unhealthy"
        elif warning_count > 0:
            overall = "warnings"

        return {
            "overall": overall,
            "total_checks": len(checks),
            "ok": ok_count,
            "warnings": warning_count,
            "errors": error_count,
            "info": info_count,
        }

    def _display_results(self, results: dict[str, Any], verbose: bool, fix: bool):
        """Display health check results."""
        self.console.banner()
        self.header("Project Health Check", "Comprehensive system status")

        # Display each check
        for check in results["checks"]:
            status = check["status"]
            name = check["name"]
            message = check["message"]

            if status == "ok":
                self.console.success(f"{name}: {message}")
            elif status == "warning":
                self.console.warning(f"{name}: {message}")
            elif status == "error":
                self.console.error(f"{name}: {message}")
            else:
                self.console.info(f"{name}: {message}")

            if verbose and check.get("details"):
                for key, value in check["details"].items():
                    if key not in ("issues",):  # Skip some detailed fields
                        self.console.print(f"    [dim]{key}: {value}[/]")

        # Summary
        summary = results["summary"]
        self.console.newline()

        if summary["overall"] == "healthy":
            self.console.box_success(
                f"All {summary['ok']} checks passed!",
                title="System Health",
            )
        elif summary["overall"] == "warnings":
            self.console.box_warning(
                f"{summary['ok']} passed, {summary['warnings']} warning(s)",
                title="System Health",
            )
        else:
            self.console.box_error(
                f"{summary['errors']} error(s), {summary['warnings']} warning(s)",
                title="System Health",
            )

        # Recommendations
        recommendations = []

        for check in results["checks"]:
            if check["status"] == "error":
                if "Database" in check["name"]:
                    recommendations.append("Run database migrations: python manage.py migrate")
                elif "SECRET_KEY" in check["name"]:
                    recommendations.append("Set a secure SECRET_KEY in your environment")
            elif check["status"] == "warning":
                if "DEBUG" in check["name"]:
                    recommendations.append("Set DEBUG=False in production")
                elif "Migration" in check["name"]:
                    recommendations.append("Run pending migrations: python manage.py migrate")
                elif "orjson" in check["name"] or "ujson" in check["name"]:
                    recommendations.append(
                        "Install orjson for better performance: pip install orjson"
                    )

        if recommendations:
            self.console.newline()
            self.next_steps(recommendations[:5], title="Recommendations")
