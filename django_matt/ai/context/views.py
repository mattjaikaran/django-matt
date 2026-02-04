"""
HTTP views for AI context introspection.

Provides a machine-readable JSON endpoint for AI context data.

Add to urls.py:

    from django_matt.ai.context.views import introspection_view

    urlpatterns = [
        ...
        path("_matt/introspection", introspection_view, name="ai-introspection"),
    ]

Or use the included URL patterns:

    from django_matt.ai.context.views import urlpatterns as ai_context_urls

    urlpatterns = [
        ...
        path("", include(ai_context_urls)),
    ]
"""

import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import path
from django.views.decorators.http import require_GET

logger = logging.getLogger("django_matt.ai.context.views")

# Cache timeout in seconds (default: 5 minutes)
CACHE_TIMEOUT = getattr(settings, "AI_CONTEXT_CACHE_TIMEOUT", 300)


def _get_introspection_data() -> dict[str, Any]:
    """
    Get introspection data with caching.

    Data is cached for CACHE_TIMEOUT seconds to avoid
    expensive introspection on every request.
    """
    from django_matt.ai.context import EnhancedIntrospector, JsonIntrospectionGenerator

    introspector = EnhancedIntrospector(
        include_third_party=False,
        include_examples=False,  # Don't include code examples in API response
    )

    generator = JsonIntrospectionGenerator(introspector=introspector)
    return generator.generate()


# Simple time-based cache
_cache: dict[str, Any] = {}
_cache_time: float = 0


def _get_cached_data() -> dict[str, Any]:
    """Get cached introspection data."""
    import time

    global _cache, _cache_time

    current_time = time.time()
    if not _cache or (current_time - _cache_time) > CACHE_TIMEOUT:
        _cache = _get_introspection_data()
        _cache_time = current_time

    return _cache


@require_GET
def introspection_view(request: HttpRequest) -> HttpResponse:
    """
    Machine-readable JSON introspection endpoint.

    Returns comprehensive project introspection data including:
    - Project metadata (name, Python/Django versions)
    - All API endpoints with methods, auth requirements, schemas
    - All Pydantic schemas with field types
    - All Django models with relationships
    - Test patterns

    URL: /_matt/introspection

    Query Parameters:
        - section: Filter to specific section (endpoints, schemas, models, etc.)
        - format: Output format (json, compact)
        - nocache: Set to "1" to bypass cache

    Response:
        200: JSON introspection data
        500: Error generating introspection
    """
    try:
        # Check for cache bypass
        nocache = request.GET.get("nocache", "0") == "1"

        if nocache:
            data = _get_introspection_data()
        else:
            data = _get_cached_data()

        # Filter by section if requested
        section = request.GET.get("section")
        if section and section in data.get("project", {}):
            data = {
                "version": data.get("version", "1.0"),
                "generated_at": data.get("generated_at"),
                section: data["project"].get(section),
            }
        elif section == "summary":
            # Return a summary instead of full data
            project = data.get("project", {})
            data = {
                "version": data.get("version", "1.0"),
                "generated_at": data.get("generated_at"),
                "summary": {
                    "name": project.get("name"),
                    "python_version": project.get("python_version"),
                    "django_version": project.get("django_version"),
                    "endpoints_count": len(project.get("endpoints", [])),
                    "schemas_count": len(project.get("schemas", [])),
                    "models_count": len(project.get("models", [])),
                },
            }

        # Check format
        compact = request.GET.get("format") == "compact"

        if compact:
            content = json.dumps(data, separators=(",", ":"), default=str)
        else:
            content = json.dumps(data, indent=2, default=str)

        return HttpResponse(
            content,
            content_type="application/json",
            headers={
                "Cache-Control": f"max-age={CACHE_TIMEOUT}",
                "X-Django-Matt-Version": "1.0",
            },
        )

    except Exception as e:
        logger.exception("Error generating introspection data")
        return JsonResponse(
            {
                "error": "Failed to generate introspection data",
                "detail": str(e) if settings.DEBUG else None,
            },
            status=500,
        )


@require_GET
def endpoints_view(request: HttpRequest) -> HttpResponse:
    """
    List all API endpoints.

    Returns a simplified list of all endpoints with their methods
    and authentication requirements.

    URL: /_matt/introspection/endpoints
    """
    try:
        data = _get_cached_data()
        endpoints = data.get("project", {}).get("endpoints", [])

        return JsonResponse(
            {
                "count": len(endpoints),
                "endpoints": endpoints,
            }
        )

    except Exception as e:
        logger.exception("Error generating endpoints data")
        return JsonResponse(
            {"error": "Failed to generate endpoints data"},
            status=500,
        )


@require_GET
def schemas_view(request: HttpRequest) -> HttpResponse:
    """
    List all Pydantic schemas.

    Returns a simplified list of all schemas with their fields.

    URL: /_matt/introspection/schemas
    """
    try:
        data = _get_cached_data()
        schemas = data.get("project", {}).get("schemas", [])

        return JsonResponse(
            {
                "count": len(schemas),
                "schemas": schemas,
            }
        )

    except Exception as e:
        logger.exception("Error generating schemas data")
        return JsonResponse(
            {"error": "Failed to generate schemas data"},
            status=500,
        )


@require_GET
def models_view(request: HttpRequest) -> HttpResponse:
    """
    List all Django models.

    Returns a simplified list of all models with their fields
    and relationships.

    URL: /_matt/introspection/models
    """
    try:
        data = _get_cached_data()
        models = data.get("project", {}).get("models", [])

        return JsonResponse(
            {
                "count": len(models),
                "models": models,
            }
        )

    except Exception as e:
        logger.exception("Error generating models data")
        return JsonResponse(
            {"error": "Failed to generate models data"},
            status=500,
        )


def clear_cache():
    """Clear the introspection cache."""
    global _cache, _cache_time
    _cache = {}
    _cache_time = 0


# URL patterns for easy inclusion
urlpatterns = [
    path("_matt/introspection", introspection_view, name="ai-introspection"),
    path("_matt/introspection/endpoints", endpoints_view, name="ai-introspection-endpoints"),
    path("_matt/introspection/schemas", schemas_view, name="ai-introspection-schemas"),
    path("_matt/introspection/models", models_view, name="ai-introspection-models"),
]


__all__ = [
    "clear_cache",
    "endpoints_view",
    "introspection_view",
    "models_view",
    "schemas_view",
    "urlpatterns",
]
