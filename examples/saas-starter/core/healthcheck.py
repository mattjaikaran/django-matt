"""
Health check URL patterns.
"""

from django.urls import path
from django.http import JsonResponse


def health(request):
    """Basic health check endpoint."""
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path("", health),
]
