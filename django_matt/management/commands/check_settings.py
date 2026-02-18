"""Management command to validate Django Matt settings for production readiness."""

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Validate Django Matt settings and check for production-safety issues."

    def add_arguments(self, parser):
        parser.add_argument(
            "--env",
            choices=["development", "production"],
            default=None,
            help="Check settings for a specific environment.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as errors.",
        )

    def handle(self, *args, **options):
        env = options["env"]
        strict = options["strict"]
        errors = []
        warnings = []

        # --- Core Django checks ---
        if not getattr(settings, "SECRET_KEY", None):
            errors.append("SECRET_KEY is not set.")
        elif settings.SECRET_KEY == "django-insecure-":
            warnings.append("SECRET_KEY appears to be a default/insecure value.")

        if env == "production":
            if getattr(settings, "DEBUG", False):
                errors.append("DEBUG is True in production.")
            if not getattr(settings, "ALLOWED_HOSTS", None):
                errors.append("ALLOWED_HOSTS is empty in production.")
            if settings.SECRET_KEY and len(settings.SECRET_KEY) < 50:
                warnings.append("SECRET_KEY is shorter than 50 characters.")

        # --- Database checks ---
        default_db = getattr(settings, "DATABASES", {}).get("default", {})
        engine = default_db.get("ENGINE", "")
        if env == "production" and "sqlite" in engine:
            warnings.append("Using SQLite in production is not recommended.")

        # --- DJANGO_MATT checks ---
        matt_config = getattr(settings, "DJANGO_MATT", {})

        if matt_config:
            # Auth checks
            auth_backend = matt_config.get("AUTH_BACKEND")
            if auth_backend == "jwt":
                jwt_config = matt_config.get("JWT_AUTH", {})
                if not jwt_config:
                    warnings.append("JWT_AUTH config missing; using defaults.")
                lifetime = jwt_config.get("ACCESS_TOKEN_LIFETIME_MINUTES", 60)
                if lifetime > 1440:
                    warnings.append(
                        f"Access token lifetime is {lifetime} minutes (>24h). "
                        "Consider a shorter lifetime."
                    )

            # CORS checks
            cors = matt_config.get("CORS", {})
            if cors.get("ENABLED") and cors.get("ALLOWED_ORIGINS") is True:
                if env == "production":
                    errors.append("CORS allows all origins (*) in production.")
                else:
                    warnings.append("CORS allows all origins (*). Restrict for production.")

            # Middleware stack
            stack = matt_config.get("MIDDLEWARE_STACK")
            if env == "production" and stack == "development":
                warnings.append(
                    "Using development middleware stack in production. "
                    "Consider 'production' for security headers."
                )

            # Throttle
            throttle = matt_config.get("THROTTLE", {})
            if env == "production" and not throttle:
                warnings.append("No throttle/rate limiting configured for production.")
        elif env == "production":
            warnings.append("No DJANGO_MATT config found. Consider using configure().")

        # --- MIDDLEWARE checks ---
        middleware_list = getattr(settings, "MIDDLEWARE", [])
        has_csrf = any("Csrf" in m for m in middleware_list)
        has_security = any("SecurityMiddleware" in m for m in middleware_list)

        if env == "production" and not has_security:
            warnings.append("Django SecurityMiddleware not in MIDDLEWARE.")
        if env == "production" and not has_csrf:
            warnings.append("CSRF middleware not in MIDDLEWARE.")

        # --- Output ---
        if errors:
            for err in errors:
                self.stderr.write(self.style.ERROR(f"ERROR: {err}"))
        if warnings:
            for warn in warnings:
                self.stderr.write(self.style.WARNING(f"WARNING: {warn}"))

        if not errors and not warnings:
            self.stdout.write(self.style.SUCCESS("All settings checks passed."))
        elif errors:
            self.stderr.write(
                self.style.ERROR(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"\n{len(warnings)} warning(s), 0 errors.")
            )

        if strict and warnings:
            raise SystemExit(1)
        if errors:
            raise SystemExit(1)
