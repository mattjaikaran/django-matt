"""
Health check URL patterns.
"""

from django.http import JsonResponse
from django.urls import path


def health(request):
    """Basic health check endpoint."""
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path("", health),
]
