"""
Views for the performance dashboard.

Provides both HTML dashboard view and JSON API endpoints for metrics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django_matt.dashboard.collector import get_collector

if TYPE_CHECKING:
    from django.http import HttpRequest


class DashboardAccessMixin:
    """Mixin for checking dashboard access permissions."""

    def check_access(self, request: HttpRequest) -> bool:
        """Check if user has access to the dashboard."""
        config = getattr(settings, "DJANGO_MATT_DASHBOARD", {})

        # Check if dashboard is enabled
        if not config.get("ENABLED", True):
            return False

        # Check if staff access is required
        if config.get("REQUIRE_STAFF", True):
            if not request.user.is_authenticated:
                return False
            if not request.user.is_staff:
                return False

        return True


class DashboardView(DashboardAccessMixin, View):
    """
    Main dashboard view with HTML interface.

    Displays performance metrics in a visual dashboard with:
    - Summary statistics (requests, errors, response times)
    - Time series charts
    - Top endpoints
    - Slowest endpoints
    - Error endpoints
    - Recent requests
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        if not self.check_access(request):
            return HttpResponse("Access denied", status=403)

        collector = get_collector()
        summary = collector.get_summary()

        html = self._render_dashboard(summary)
        return HttpResponse(html, content_type="text/html")

    def _render_dashboard(self, summary: dict[str, Any]) -> str:
        """Render the dashboard HTML."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Django Matt Performance Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .metric-card.green {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .metric-card.orange {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .metric-card.blue {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8">
            <h1 class="text-3xl font-bold">Performance Dashboard</h1>
            <p class="text-gray-400">Uptime: {summary["uptime_formatted"]}</p>
        </header>

        <!-- Summary Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="metric-card rounded-lg p-6 text-white">
                <h3 class="text-sm font-medium opacity-80">Total Requests</h3>
                <p class="text-3xl font-bold mt-2">{summary["total_requests"]:,}</p>
                <p class="text-sm opacity-60 mt-1">{summary["requests_per_minute"]:.1f} req/min</p>
            </div>
            <div class="metric-card green rounded-lg p-6 text-white">
                <h3 class="text-sm font-medium opacity-80">Avg Response Time</h3>
                <p class="text-3xl font-bold mt-2">{summary["avg_response_time_ms"]:.1f}ms</p>
                <p class="text-sm opacity-60 mt-1">p95: {summary["p95_response_time_ms"]:.1f}ms</p>
            </div>
            <div class="metric-card orange rounded-lg p-6 text-white">
                <h3 class="text-sm font-medium opacity-80">Error Rate</h3>
                <p class="text-3xl font-bold mt-2">{summary["error_rate"]:.2f}%</p>
                <p class="text-sm opacity-60 mt-1">{summary["total_errors"]:,} errors</p>
            </div>
            <div class="metric-card blue rounded-lg p-6 text-white">
                <h3 class="text-sm font-medium opacity-80">p99 Response Time</h3>
                <p class="text-3xl font-bold mt-2">{summary["p99_response_time_ms"]:.1f}ms</p>
                <p class="text-sm opacity-60 mt-1">p50: {summary["p50_response_time_ms"]:.1f}ms</p>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div class="bg-gray-800 rounded-lg p-6">
                <h3 class="text-lg font-semibold mb-4">Requests Over Time</h3>
                <canvas id="requestsChart" height="200"></canvas>
            </div>
            <div class="bg-gray-800 rounded-lg p-6">
                <h3 class="text-lg font-semibold mb-4">Response Times</h3>
                <canvas id="responseTimeChart" height="200"></canvas>
            </div>
        </div>

        <!-- Status Codes -->
        <div class="bg-gray-800 rounded-lg p-6 mb-8">
            <h3 class="text-lg font-semibold mb-4">Status Codes</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {self._render_status_codes(summary["status_codes"])}
            </div>
        </div>

        <!-- Tables Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Top Endpoints -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h3 class="text-lg font-semibold mb-4">Top Endpoints</h3>
                <div id="topEndpoints" class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-gray-400 text-left">
                                <th class="pb-2">Endpoint</th>
                                <th class="pb-2">Requests</th>
                                <th class="pb-2">Avg Time</th>
                            </tr>
                        </thead>
                        <tbody id="topEndpointsBody"></tbody>
                    </table>
                </div>
            </div>

            <!-- Slowest Endpoints -->
            <div class="bg-gray-800 rounded-lg p-6">
                <h3 class="text-lg font-semibold mb-4">Slowest Endpoints</h3>
                <div id="slowEndpoints" class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-gray-400 text-left">
                                <th class="pb-2">Endpoint</th>
                                <th class="pb-2">Avg Time</th>
                                <th class="pb-2">p95 Time</th>
                            </tr>
                        </thead>
                        <tbody id="slowEndpointsBody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Recent Requests -->
        <div class="bg-gray-800 rounded-lg p-6">
            <h3 class="text-lg font-semibold mb-4">Recent Requests</h3>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="text-gray-400 text-left">
                            <th class="pb-2">Time</th>
                            <th class="pb-2">Method</th>
                            <th class="pb-2">Path</th>
                            <th class="pb-2">Status</th>
                            <th class="pb-2">Duration</th>
                            <th class="pb-2">DB Queries</th>
                        </tr>
                    </thead>
                    <tbody id="recentRequestsBody"></tbody>
                </table>
            </div>
        </div>

        <!-- Actions -->
        <div class="mt-8 flex gap-4">
            <button onclick="refreshData()" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                Refresh
            </button>
            <button onclick="resetMetrics()" class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded">
                Reset Metrics
            </button>
        </div>
    </div>

    <script>
        const apiBase = window.location.pathname.replace(/\\/$/, '') + '/api';
        let requestsChart, responseTimeChart;

        // Initialize charts
        function initCharts() {{
            const ctx1 = document.getElementById('requestsChart').getContext('2d');
            requestsChart = new Chart(ctx1, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Requests',
                        data: [],
                        borderColor: '#4facfe',
                        backgroundColor: 'rgba(79, 172, 254, 0.1)',
                        fill: true,
                        tension: 0.4
                    }}, {{
                        label: 'Errors',
                        data: [],
                        borderColor: '#f5576c',
                        backgroundColor: 'rgba(245, 87, 108, 0.1)',
                        fill: true,
                        tension: 0.4
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{ beginAtZero: true, grid: {{ color: '#374151' }} }},
                        x: {{ grid: {{ color: '#374151' }} }}
                    }},
                    plugins: {{ legend: {{ labels: {{ color: '#9ca3af' }} }} }}
                }}
            }});

            const ctx2 = document.getElementById('responseTimeChart').getContext('2d');
            responseTimeChart = new Chart(ctx2, {{
                type: 'line',
                data: {{
                    labels: [],
                    datasets: [{{
                        label: 'Avg Response Time (ms)',
                        data: [],
                        borderColor: '#38ef7d',
                        backgroundColor: 'rgba(56, 239, 125, 0.1)',
                        fill: true,
                        tension: 0.4
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{ beginAtZero: true, grid: {{ color: '#374151' }} }},
                        x: {{ grid: {{ color: '#374151' }} }}
                    }},
                    plugins: {{ legend: {{ labels: {{ color: '#9ca3af' }} }} }}
                }}
            }});
        }}

        // Update charts with time series data
        function updateCharts(timeSeries) {{
            const labels = timeSeries.map(t => t.timestamp.split(' ')[1]);
            const requests = timeSeries.map(t => t.request_count);
            const errors = timeSeries.map(t => t.error_count);
            const avgDuration = timeSeries.map(t => t.avg_duration_ms);

            requestsChart.data.labels = labels;
            requestsChart.data.datasets[0].data = requests;
            requestsChart.data.datasets[1].data = errors;
            requestsChart.update();

            responseTimeChart.data.labels = labels;
            responseTimeChart.data.datasets[0].data = avgDuration;
            responseTimeChart.update();
        }}

        // Update endpoints tables
        function updateEndpoints(top, slow) {{
            const topBody = document.getElementById('topEndpointsBody');
            topBody.innerHTML = top.map(e => `
                <tr class="border-t border-gray-700">
                    <td class="py-2"><span class="text-gray-400">${{e.method}}</span> ${{e.path}}</td>
                    <td class="py-2">${{e.request_count}}</td>
                    <td class="py-2">${{e.avg_duration_ms.toFixed(1)}}ms</td>
                </tr>
            `).join('');

            const slowBody = document.getElementById('slowEndpointsBody');
            slowBody.innerHTML = slow.map(e => `
                <tr class="border-t border-gray-700">
                    <td class="py-2"><span class="text-gray-400">${{e.method}}</span> ${{e.path}}</td>
                    <td class="py-2">${{e.avg_duration_ms.toFixed(1)}}ms</td>
                    <td class="py-2">${{e.p95_duration_ms.toFixed(1)}}ms</td>
                </tr>
            `).join('');
        }}

        // Update recent requests table
        function updateRecentRequests(requests) {{
            const body = document.getElementById('recentRequestsBody');
            body.innerHTML = requests.slice(0, 20).map(r => {{
                const statusClass = r.status_code >= 500 ? 'text-red-400' :
                                   r.status_code >= 400 ? 'text-yellow-400' : 'text-green-400';
                return `
                    <tr class="border-t border-gray-700">
                        <td class="py-2 text-gray-400">${{r.timestamp.split('T')[1].split('.')[0]}}</td>
                        <td class="py-2">${{r.method}}</td>
                        <td class="py-2">${{r.path}}</td>
                        <td class="py-2 ${{statusClass}}">${{r.status_code}}</td>
                        <td class="py-2">${{r.duration_ms.toFixed(1)}}ms</td>
                        <td class="py-2">${{r.db_query_count}}</td>
                    </tr>
                `;
            }}).join('');
        }}

        // Fetch and update all data
        async function refreshData() {{
            try {{
                const [summaryRes, timeSeriesRes, endpointsRes, slowRes, recentRes] = await Promise.all([
                    fetch(apiBase + '/summary'),
                    fetch(apiBase + '/time-series'),
                    fetch(apiBase + '/endpoints'),
                    fetch(apiBase + '/endpoints/slow'),
                    fetch(apiBase + '/requests')
                ]);

                const timeSeries = await timeSeriesRes.json();
                const endpoints = await endpointsRes.json();
                const slow = await slowRes.json();
                const recent = await recentRes.json();

                updateCharts(timeSeries);
                updateEndpoints(endpoints, slow);
                updateRecentRequests(recent);
            }} catch (err) {{
                console.error('Failed to refresh data:', err);
            }}
        }}

        // Reset metrics
        async function resetMetrics() {{
            if (!confirm('Are you sure you want to reset all metrics?')) return;
            try {{
                await fetch(apiBase + '/reset', {{ method: 'POST' }});
                location.reload();
            }} catch (err) {{
                console.error('Failed to reset metrics:', err);
            }}
        }}

        // Initialize
        initCharts();
        refreshData();
        setInterval(refreshData, 10000);  // Refresh every 10 seconds
    </script>
</body>
</html>"""

    def _render_status_codes(self, status_codes: dict[int, int]) -> str:
        """Render status code badges."""
        badges = []
        for code, count in sorted(status_codes.items()):
            if code < 300:
                color = "bg-green-600"
            elif code < 400:
                color = "bg-blue-600"
            elif code < 500:
                color = "bg-yellow-600"
            else:
                color = "bg-red-600"

            badges.append(
                f'<div class="{color} rounded px-3 py-2 text-center">'
                f'<span class="font-bold">{code}</span>'
                f'<span class="text-sm opacity-80 ml-2">{count:,}</span>'
                f"</div>"
            )
        return "\n".join(badges) if badges else '<p class="text-gray-500">No requests yet</p>'


@method_decorator(csrf_exempt, name="dispatch")
class MetricsAPIView(DashboardAccessMixin, View):
    """
    JSON API endpoints for dashboard metrics.

    Endpoints:
    - GET /summary - Summary statistics
    - GET /endpoints - Top endpoints by request count
    - GET /endpoints/slow - Slowest endpoints
    - GET /endpoints/errors - Endpoints with errors
    - GET /requests - Recent requests
    - GET /time-series - Time series data for charts
    - POST /reset - Reset all metrics
    """

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not self.check_access(request):
            return JsonResponse({"error": "Access denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, action: str = "summary") -> JsonResponse:
        collector = get_collector()

        if action == "summary":
            return JsonResponse(collector.get_summary())
        if action == "endpoints":
            return JsonResponse(collector.get_endpoints(), safe=False)
        if action == "slow":
            return JsonResponse(collector.get_slowest_endpoints(), safe=False)
        if action == "errors":
            return JsonResponse(collector.get_error_endpoints(), safe=False)
        if action == "requests":
            limit = int(request.GET.get("limit", 100))
            return JsonResponse(collector.get_recent_requests(limit), safe=False)
        if action == "time-series":
            minutes = int(request.GET.get("minutes", 60))
            return JsonResponse(collector.get_time_series(minutes), safe=False)
        return JsonResponse({"error": "Unknown action"}, status=400)

    def post(self, request: HttpRequest, action: str = "") -> JsonResponse:
        if action == "reset":
            collector = get_collector()
            collector.reset()
            return JsonResponse({"status": "ok", "message": "Metrics reset"})
        return JsonResponse({"error": "Unknown action"}, status=400)


def include_dashboard():
    """
    Include dashboard URLs in your urlpatterns.

    Usage:
        from django_matt.dashboard import include_dashboard

        urlpatterns = [
            path("_dashboard/", include_dashboard()),
        ]
    """
    return [
        path("", DashboardView.as_view(), name="dashboard"),
        path(
            "api/summary", MetricsAPIView.as_view(), {"action": "summary"}, name="dashboard-summary"
        ),
        path(
            "api/endpoints",
            MetricsAPIView.as_view(),
            {"action": "endpoints"},
            name="dashboard-endpoints",
        ),
        path(
            "api/endpoints/slow",
            MetricsAPIView.as_view(),
            {"action": "slow"},
            name="dashboard-slow",
        ),
        path(
            "api/endpoints/errors",
            MetricsAPIView.as_view(),
            {"action": "errors"},
            name="dashboard-errors",
        ),
        path(
            "api/requests",
            MetricsAPIView.as_view(),
            {"action": "requests"},
            name="dashboard-requests",
        ),
        path(
            "api/time-series",
            MetricsAPIView.as_view(),
            {"action": "time-series"},
            name="dashboard-time-series",
        ),
        path("api/reset", MetricsAPIView.as_view(), {"action": "reset"}, name="dashboard-reset"),
    ]


__all__ = [
    "DashboardView",
    "MetricsAPIView",
    "include_dashboard",
]
