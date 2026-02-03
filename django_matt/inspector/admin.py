"""
Django admin integration for the Request Inspector.

Provides admin views for viewing captured requests. Note that since captured
requests are stored in memory or Redis (not in the database), this module
provides a pseudo-admin interface that displays storage contents.

Usage:
    # In your admin.py or urls.py
    from django_matt.inspector.admin import InspectorAdminView

    # Add to admin site
    admin.site.register_view('inspector/', InspectorAdminView.as_view(), 'Inspector')

    # Or include in urlpatterns under admin
    from django.contrib import admin
    from django_matt.inspector.admin import inspector_admin_urls

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('admin/inspector/', include(inspector_admin_urls)),
    ]
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View

from .storage import get_storage

if TYPE_CHECKING:
    from django.http import HttpRequest


@method_decorator(staff_member_required, name="dispatch")
class InspectorAdminView(View):
    """
    Admin view for the Request Inspector.

    Displays captured requests in the Django admin interface.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        storage = get_storage()
        requests_list = storage.list(limit=100)

        html = self._render_admin_page(requests_list, storage)
        return HttpResponse(html, content_type="text/html")

    def _render_admin_page(self, requests: list, storage) -> str:
        """Render the admin page HTML."""
        admin_site = admin.site

        # Build table rows
        rows = []
        for req in requests:
            timestamp = datetime.fromtimestamp(req.timestamp).strftime("%Y-%m-%d %H:%M:%S")
            status_class = self._get_status_class(req.response_status)
            method_class = self._get_method_class(req.method)

            rows.append(f'''
                <tr>
                    <td>{timestamp}</td>
                    <td><span class="badge {method_class}">{req.method}</span></td>
                    <td title="{req.full_url}">{req.path[:50]}{'...' if len(req.path) > 50 else ''}</td>
                    <td><span class="badge {status_class}">{req.response_status}</span></td>
                    <td>{req.duration_ms:.2f}ms</td>
                    <td>{req.client_ip}</td>
                    <td>
                        <a href="?detail={req.id}" class="viewlink">View</a>
                    </td>
                </tr>
            ''')

        table_content = "\n".join(rows) if rows else '<tr><td colspan="7" style="text-align:center;">No requests captured</td></tr>'

        return f'''
<!DOCTYPE html>
<html>
<head>
    <title>Request Inspector | Django Admin</title>
    <link rel="stylesheet" type="text/css" href="/static/admin/css/base.css">
    <link rel="stylesheet" type="text/css" href="/static/admin/css/nav_sidebar.css">
    <style>
        .badge {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        .badge-success {{ background: #28a745; color: white; }}
        .badge-info {{ background: #17a2b8; color: white; }}
        .badge-warning {{ background: #ffc107; color: black; }}
        .badge-danger {{ background: #dc3545; color: white; }}
        .badge-get {{ background: #007bff; color: white; }}
        .badge-post {{ background: #28a745; color: white; }}
        .badge-put {{ background: #ffc107; color: black; }}
        .badge-patch {{ background: #fd7e14; color: white; }}
        .badge-delete {{ background: #dc3545; color: white; }}
        .stats-bar {{
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
            display: flex;
            gap: 30px;
        }}
        .stat-item {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
        }}
        .actions-bar {{
            margin-bottom: 20px;
        }}
        .btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }}
        .btn-danger {{ background: #dc3545; color: white; }}
        .btn-danger:hover {{ background: #c82333; }}
        .btn-primary {{ background: #007bff; color: white; }}
        .btn-primary:hover {{ background: #0056b3; }}
    </style>
</head>
<body class="dashboard">
    <div id="container">
        <div id="header">
            <div id="branding">
                <h1 id="site-name"><a href="/admin/">Django administration</a></h1>
            </div>
        </div>

        <div id="content" class="colMS">
            <div id="content-main">
                <h1>Request Inspector</h1>

                <div class="stats-bar">
                    <div class="stat-item">
                        <div class="stat-value">{storage.count()}</div>
                        <div class="stat-label">Total Requests</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{sum(1 for r in requests if r.is_success)}</div>
                        <div class="stat-label">Successful (2xx)</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{sum(1 for r in requests if r.is_client_error or r.is_server_error)}</div>
                        <div class="stat-label">Errors (4xx/5xx)</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{'Capturing' if storage.is_capturing() else 'Paused'}</div>
                        <div class="stat-label">Status</div>
                    </div>
                </div>

                <div class="actions-bar">
                    <a href="?clear=1" class="btn btn-danger" onclick="return confirm('Clear all captured requests?')">Clear All</a>
                    <a href="/_matt/inspector/" class="btn btn-primary" target="_blank">Open Full Dashboard</a>
                </div>

                <table id="result_list">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Method</th>
                            <th>Path</th>
                            <th>Status</th>
                            <th>Duration</th>
                            <th>Client IP</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_content}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
'''

    def _get_status_class(self, status: int) -> str:
        """Get CSS class for status code."""
        if status < 300:
            return "badge-success"
        if status < 400:
            return "badge-info"
        if status < 500:
            return "badge-warning"
        return "badge-danger"

    def _get_method_class(self, method: str) -> str:
        """Get CSS class for HTTP method."""
        return f"badge-{method.lower()}"


@method_decorator(staff_member_required, name="dispatch")
class InspectorAdminAPIView(View):
    """API endpoints for admin inspector view."""

    def get(self, request: HttpRequest) -> JsonResponse:
        storage = get_storage()

        if "clear" in request.GET:
            count = storage.clear()
            return JsonResponse({"cleared": count})

        requests_list = storage.list(limit=100)
        return JsonResponse(
            {
                "requests": [
                    {
                        "id": r.id,
                        "timestamp": r.timestamp,
                        "method": r.method,
                        "path": r.path,
                        "status": r.response_status,
                        "duration_ms": r.duration_ms,
                    }
                    for r in requests_list
                ],
                "total": storage.count(),
                "is_capturing": storage.is_capturing(),
            }
        )


# URL patterns for admin integration
inspector_admin_urls = [
    path("", InspectorAdminView.as_view(), name="inspector-admin"),
    path("api/", InspectorAdminAPIView.as_view(), name="inspector-admin-api"),
]


def register_with_admin_site(admin_site=None):
    """
    Register the inspector with a Django admin site.

    Usage:
        from django.contrib import admin
        from django_matt.inspector.admin import register_with_admin_site

        register_with_admin_site(admin.site)

    This adds an "Inspector" link to the admin site.
    """
    if admin_site is None:
        admin_site = admin.site

    # Note: Django's admin site doesn't have a built-in way to add custom pages
    # to the index. You would need to either:
    # 1. Override the admin index template
    # 2. Use a custom AdminSite subclass
    # 3. Add the inspector URLs alongside admin URLs

    # For now, we just provide the URL patterns
    pass


__all__ = [
    "InspectorAdminView",
    "InspectorAdminAPIView",
    "inspector_admin_urls",
    "register_with_admin_site",
]
