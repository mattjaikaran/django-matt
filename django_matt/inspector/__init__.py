"""
Django Matt Request Inspector - Debug and inspect HTTP requests/responses.

The Request Inspector provides a web UI to capture, view, and replay HTTP requests
during development. It includes request/response logging, timing information,
and export capabilities.

Usage:
    # settings.py
    MIDDLEWARE = [
        'django_matt.inspector.RequestCaptureMiddleware',
        ...
    ]

    DJANGO_MATT_INSPECTOR = {
        'ENABLED': DEBUG,
        'MAX_REQUESTS': 100,
        'MAX_BODY_SIZE': 65536,
        'IGNORE_PATHS': ['/_matt/', '/static/', '/media/'],
        'IGNORE_EXTENSIONS': ['.css', '.js', '.png', '.jpg', '.gif', '.ico'],
        'CAPTURE_HEADERS': True,
        'CAPTURE_BODY': True,
        'CAPTURE_RESPONSE': True,
        'REQUIRE_STAFF': False,  # Require staff access for dashboard
        'STORAGE_BACKEND': 'memory',  # or 'redis'
        'REDIS_URL': 'redis://localhost:6379/0',
        'TTL_SECONDS': 3600,  # For Redis storage
    }

    # urls.py
    from django.urls import include, path

    urlpatterns = [
        ...
        path("_matt/inspector/", include("django_matt.inspector.urls")),
    ]

Access the inspector at: http://localhost:8000/_matt/inspector/

API Endpoints (for programmatic access):
    GET    /_matt/inspector/api/requests              - List captured requests
    GET    /_matt/inspector/api/requests/{id}         - Get request detail
    DELETE /_matt/inspector/api/requests              - Clear all requests
    POST   /_matt/inspector/api/requests/{id}/export  - Export request
    GET    /_matt/inspector/api/stats                 - Get statistics
    GET    /_matt/inspector/api/status                - Get capture status
    POST   /_matt/inspector/api/pause                 - Pause capture
    POST   /_matt/inspector/api/resume                - Resume capture

Using with MattAPI:
    from django_matt import MattAPI
    from django_matt.inspector import InspectorController

    api = MattAPI()
    api.register_controller(InspectorController)
"""

from django_matt.inspector.controllers import InspectorController
from django_matt.inspector.export import (
    ExportFormat,
    export_as_curl,
    export_as_fetch,
    export_as_httpie,
    export_as_python,
    export_request,
)
from django_matt.inspector.middleware import RequestCaptureMiddleware
from django_matt.inspector.schemas import (
    CapturedRequestListSchema,
    CapturedRequestSchema,
    CaptureStatusSchema,
    ErrorResponseSchema,
    ExportRequestSchema,
    ExportResponseSchema,
    InspectorStatsSchema,
    MessageResponseSchema,
)
from django_matt.inspector.storage import (
    CapturedRequest,
    InspectorStorage,
    MemoryStorage,
    RedisStorage,
    get_storage,
    reset_storage,
)
from django_matt.inspector.views import (
    InspectorAPIView,
    InspectorDashboardView,
    include_inspector,
    urlpatterns,
)

__all__ = [
    # Middleware
    "RequestCaptureMiddleware",
    # Storage
    "CapturedRequest",
    "InspectorStorage",
    "MemoryStorage",
    "RedisStorage",
    "get_storage",
    "reset_storage",
    # Export
    "ExportFormat",
    "export_as_curl",
    "export_as_httpie",
    "export_as_python",
    "export_as_fetch",
    "export_request",
    # Controllers
    "InspectorController",
    # Views
    "InspectorDashboardView",
    "InspectorAPIView",
    "include_inspector",
    "urlpatterns",
    # Schemas
    "CapturedRequestSchema",
    "CapturedRequestListSchema",
    "InspectorStatsSchema",
    "ExportRequestSchema",
    "ExportResponseSchema",
    "MessageResponseSchema",
    "ErrorResponseSchema",
    "CaptureStatusSchema",
]
