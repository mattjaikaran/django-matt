"""
URL configuration for the Request Inspector.

Usage in your project's urls.py:

    from django.urls import include, path

    urlpatterns = [
        ...
        path("_matt/inspector/", include("django_matt.inspector.urls")),
    ]

This provides:
    - GET  /_matt/inspector/              - Dashboard view
    - GET  /_matt/inspector/api/requests  - List requests (JSON)
    - GET  /_matt/inspector/api/requests/{id} - Get request detail (JSON)
    - DELETE /_matt/inspector/api/requests - Clear all requests
    - POST /_matt/inspector/api/requests/{id}/export - Export request
    - GET  /_matt/inspector/api/stats     - Get statistics
    - GET  /_matt/inspector/api/status    - Get capture status
    - POST /_matt/inspector/api/pause     - Pause capture
    - POST /_matt/inspector/api/resume    - Resume capture
"""

from django.urls import path

from .views import InspectorAPIView, InspectorDashboardView

app_name = "inspector"

urlpatterns = [
    # Dashboard
    path("", InspectorDashboardView.as_view(), name="dashboard"),
    # API endpoints
    path("api/requests", InspectorAPIView.as_view(), {"action": "requests"}, name="list"),
    path(
        "api/requests/<str:request_id>",
        InspectorAPIView.as_view(),
        {"action": "requests"},
        name="detail",
    ),
    path(
        "api/requests/<str:request_id>/export",
        InspectorAPIView.as_view(),
        {"action": "export"},
        name="export",
    ),
    path("api/stats", InspectorAPIView.as_view(), {"action": "stats"}, name="stats"),
    path("api/status", InspectorAPIView.as_view(), {"action": "status"}, name="status"),
    path("api/pause", InspectorAPIView.as_view(), {"action": "pause"}, name="pause"),
    path("api/resume", InspectorAPIView.as_view(), {"action": "resume"}, name="resume"),
]
