"""
Experiment middleware.

Provides middleware for setting up experiment context on each request.

Usage:
    # In settings.py
    MIDDLEWARE = [
        ...
        'django_matt.experiments.ExperimentMiddleware',
        ...
    ]

    # Then in views:
    from django_matt.experiments import get_variant
    variant = get_variant("my_experiment")
"""

import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

from django_matt.experiments.context import ExperimentContext, set_current_context

logger = logging.getLogger("django_matt.experiments")


class ExperimentMiddleware:
    """
    Middleware that sets up experiment context for each request.

    Creates an ExperimentContext from the request and sets it as the current
    context for the duration of the request.

    This middleware should be placed after authentication middleware
    so that request.user is available.

    Configuration (in settings.py):
        EXPERIMENT_MIDDLEWARE = {
            "anonymous_id_cookie": "experiment_id",  # Cookie name for anonymous ID
            "cookie_max_age": 365 * 24 * 60 * 60,    # Cookie max age (1 year)
            "cookie_secure": True,                    # Secure cookie flag
            "cookie_httponly": True,                  # HttpOnly flag
            "cookie_samesite": "Lax",                 # SameSite attribute
            "expose_header": True,                    # Add X-Experiment-Assignments header
            "auto_assign": False,                     # Auto-assign to all running experiments
        }
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

        # Load configuration
        from django.conf import settings

        config = getattr(settings, "EXPERIMENT_MIDDLEWARE", {})
        self.anonymous_id_cookie = config.get("anonymous_id_cookie", "experiment_id")
        self.cookie_max_age = config.get("cookie_max_age", 365 * 24 * 60 * 60)
        self.cookie_secure = config.get("cookie_secure", not settings.DEBUG)
        self.cookie_httponly = config.get("cookie_httponly", True)
        self.cookie_samesite = config.get("cookie_samesite", "Lax")
        self.expose_header = config.get("expose_header", False)
        self.auto_assign = config.get("auto_assign", False)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        import secrets

        # Get or create anonymous ID
        anonymous_id = request.COOKIES.get(self.anonymous_id_cookie)
        new_anonymous_id = None

        if not anonymous_id and not (hasattr(request, "user") and request.user.is_authenticated):
            anonymous_id = secrets.token_hex(16)
            new_anonymous_id = anonymous_id

        # Create experiment context
        ctx = ExperimentContext.from_request(request)
        if anonymous_id:
            ctx.anonymous_id = anonymous_id

        # Set as current context
        set_current_context(ctx)

        # Store on request for easy access
        request.experiment_context = ctx  # type: ignore

        try:
            # Auto-assign to running experiments if enabled
            if self.auto_assign:
                self._auto_assign(ctx)

            response = self.get_response(request)

            # Set anonymous ID cookie if new
            if new_anonymous_id:
                response.set_cookie(
                    self.anonymous_id_cookie,
                    new_anonymous_id,
                    max_age=self.cookie_max_age,
                    secure=self.cookie_secure,
                    httponly=self.cookie_httponly,
                    samesite=self.cookie_samesite,
                )

            # Add experiments header if enabled
            if self.expose_header:
                self._add_experiments_header(response, ctx)

            return response
        finally:
            # Clear context
            set_current_context(None)

    def _auto_assign(self, ctx: ExperimentContext):
        """Auto-assign user to all running experiments."""
        try:
            from django_matt.experiments.models import Experiment, ExperimentStatus

            experiments = Experiment.objects.filter(status=ExperimentStatus.RUNNING.value)

            for exp in experiments:
                # This will create assignment if not exists
                ctx.get_assignment(exp.key, create=True)
        except Exception as e:
            logger.warning(f"Failed to auto-assign experiments: {e}")

    def _add_experiments_header(self, response: HttpResponse, ctx: ExperimentContext):
        """Add X-Experiment-Assignments header to response."""
        try:
            # Get all assignments from cache
            assignments = []
            for key, assignment in ctx._assignment_cache.items():
                if assignment:
                    exp_key = assignment.experiment.key
                    variant_key = assignment.variant.key if assignment.variant else "holdout"
                    assignments.append(f"{exp_key}={variant_key}")

            if assignments:
                response["X-Experiment-Assignments"] = ",".join(assignments)
        except Exception as e:
            logger.warning(f"Failed to add experiments header: {e}")


class AsyncExperimentMiddleware:
    """
    Async version of ExperimentMiddleware.

    Use this with ASGI applications.
    """

    def __init__(self, get_response: Callable):
        self.get_response = get_response

        from django.conf import settings

        config = getattr(settings, "EXPERIMENT_MIDDLEWARE", {})
        self.anonymous_id_cookie = config.get("anonymous_id_cookie", "experiment_id")
        self.cookie_max_age = config.get("cookie_max_age", 365 * 24 * 60 * 60)
        self.cookie_secure = config.get("cookie_secure", not settings.DEBUG)
        self.cookie_httponly = config.get("cookie_httponly", True)
        self.cookie_samesite = config.get("cookie_samesite", "Lax")
        self.expose_header = config.get("expose_header", False)
        self.auto_assign = config.get("auto_assign", False)

    async def __call__(self, request: HttpRequest) -> HttpResponse:
        import secrets

        # Get or create anonymous ID
        anonymous_id = request.COOKIES.get(self.anonymous_id_cookie)
        new_anonymous_id = None

        if not anonymous_id and not (hasattr(request, "user") and request.user.is_authenticated):
            anonymous_id = secrets.token_hex(16)
            new_anonymous_id = anonymous_id

        # Create experiment context
        ctx = ExperimentContext.from_request(request)
        if anonymous_id:
            ctx.anonymous_id = anonymous_id

        # Set as current context
        set_current_context(ctx)

        # Store on request
        request.experiment_context = ctx  # type: ignore

        try:
            if self.auto_assign:
                await self._auto_assign_async(ctx)

            response = await self.get_response(request)

            if new_anonymous_id:
                response.set_cookie(
                    self.anonymous_id_cookie,
                    new_anonymous_id,
                    max_age=self.cookie_max_age,
                    secure=self.cookie_secure,
                    httponly=self.cookie_httponly,
                    samesite=self.cookie_samesite,
                )

            if self.expose_header:
                self._add_experiments_header(response, ctx)

            return response
        finally:
            set_current_context(None)

    async def _auto_assign_async(self, ctx: ExperimentContext):
        """Auto-assign user to all running experiments (async)."""
        try:
            from django_matt.experiments.models import Experiment, ExperimentStatus

            async for exp in Experiment.objects.filter(status=ExperimentStatus.RUNNING.value):
                ctx.get_assignment(exp.key, create=True)
        except Exception as e:
            logger.warning(f"Failed to auto-assign experiments: {e}")

    def _add_experiments_header(self, response: HttpResponse, ctx: ExperimentContext):
        """Add X-Experiment-Assignments header to response."""
        try:
            assignments = []
            for key, assignment in ctx._assignment_cache.items():
                if assignment:
                    exp_key = assignment.experiment.key
                    variant_key = assignment.variant.key if assignment.variant else "holdout"
                    assignments.append(f"{exp_key}={variant_key}")

            if assignments:
                response["X-Experiment-Assignments"] = ",".join(assignments)
        except Exception as e:
            logger.warning(f"Failed to add experiments header: {e}")


__all__ = [
    "ExperimentMiddleware",
    "AsyncExperimentMiddleware",
]
