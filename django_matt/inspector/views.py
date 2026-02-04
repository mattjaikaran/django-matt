"""
Django views for the Request Inspector dashboard.

Provides HTML views for browsing and inspecting captured requests.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .export import export_request
from .storage import CapturedRequest, get_storage

if TYPE_CHECKING:
    from django.http import HttpRequest


class InspectorAccessMixin:
    """Mixin for checking inspector access permissions."""

    def check_access(self, request: HttpRequest) -> bool:
        """Check if user has access to the inspector."""
        config = getattr(settings, "DJANGO_MATT_INSPECTOR", {})

        # Check if inspector is enabled
        if not config.get("ENABLED", getattr(settings, "DEBUG", False)):
            return False

        # Check if staff access is required
        if config.get("REQUIRE_STAFF", False):
            if not request.user.is_authenticated:
                return False
            if not request.user.is_staff:
                return False

        return True


def _format_timestamp(timestamp: float) -> str:
    """Format a unix timestamp as a human-readable string."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _format_duration(duration_ms: float) -> str:
    """Format duration in milliseconds."""
    if duration_ms < 1:
        return f"{duration_ms * 1000:.2f}us"
    if duration_ms < 1000:
        return f"{duration_ms:.2f}ms"
    return f"{duration_ms / 1000:.2f}s"


def _get_status_color(status: int) -> str:
    """Get Tailwind color class for status code."""
    if status < 300:
        return "text-green-400"
    if status < 400:
        return "text-blue-400"
    if status < 500:
        return "text-yellow-400"
    return "text-red-400"


def _get_status_bg_color(status: int) -> str:
    """Get Tailwind background color class for status code."""
    if status < 300:
        return "bg-green-500/20 text-green-400"
    if status < 400:
        return "bg-blue-500/20 text-blue-400"
    if status < 500:
        return "bg-yellow-500/20 text-yellow-400"
    return "bg-red-500/20 text-red-400"


def _get_method_color(method: str) -> str:
    """Get Tailwind color class for HTTP method."""
    colors = {
        "GET": "bg-blue-500/20 text-blue-400",
        "POST": "bg-green-500/20 text-green-400",
        "PUT": "bg-yellow-500/20 text-yellow-400",
        "PATCH": "bg-orange-500/20 text-orange-400",
        "DELETE": "bg-red-500/20 text-red-400",
        "HEAD": "bg-purple-500/20 text-purple-400",
        "OPTIONS": "bg-gray-500/20 text-gray-400",
    }
    return colors.get(method, "bg-gray-500/20 text-gray-400")


class InspectorDashboardView(InspectorAccessMixin, View):
    """
    Main inspector dashboard view.

    Displays a list of captured requests with filtering and search.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        if not self.check_access(request):
            return HttpResponse("Access denied", status=403)

        html = self._render_dashboard()
        return HttpResponse(html, content_type="text/html")

    def _render_dashboard(self) -> str:
        """Render the dashboard HTML."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Request Inspector - Django Matt</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .request-row:hover { background-color: rgba(255, 255, 255, 0.05); }
        .json-key { color: #93c5fd; }
        .json-string { color: #86efac; }
        .json-number { color: #fcd34d; }
        .json-boolean { color: #c084fc; }
        .json-null { color: #9ca3af; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
        .tab-active { border-bottom: 2px solid #3b82f6; color: #3b82f6; }
        .spinner { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
    <div class="flex h-screen">
        <!-- Sidebar / Request List -->
        <div class="w-1/3 border-r border-gray-700 flex flex-col">
            <!-- Header -->
            <div class="p-4 border-b border-gray-700">
                <h1 class="text-xl font-bold flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    Request Inspector
                </h1>
                <p class="text-sm text-gray-400 mt-1">Django Matt Debug Tool</p>
            </div>

            <!-- Stats Bar -->
            <div id="statsBar" class="px-4 py-2 bg-gray-800 border-b border-gray-700 flex gap-4 text-sm">
                <span class="text-gray-400">Total: <span id="totalCount" class="text-white">0</span></span>
                <span class="text-gray-400">Success: <span id="successCount" class="text-green-400">0</span></span>
                <span class="text-gray-400">Errors: <span id="errorCount" class="text-red-400">0</span></span>
                <span class="text-gray-400">Avg: <span id="avgDuration" class="text-white">0ms</span></span>
            </div>

            <!-- Filters -->
            <div class="p-4 border-b border-gray-700 space-y-3">
                <div class="flex gap-2">
                    <input type="text" id="searchInput" placeholder="Search path..."
                           class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                    <select id="methodFilter" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                        <option value="">All Methods</option>
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="PATCH">PATCH</option>
                        <option value="DELETE">DELETE</option>
                    </select>
                </div>
                <div class="flex gap-2">
                    <select id="statusFilter" class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
                        <option value="">All Status</option>
                        <option value="success">2xx Success</option>
                        <option value="redirect">3xx Redirect</option>
                        <option value="client_error">4xx Client Error</option>
                        <option value="server_error">5xx Server Error</option>
                    </select>
                    <button id="clearBtn" class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-sm">Clear All</button>
                </div>
            </div>

            <!-- Capture Controls -->
            <div class="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span id="captureIndicator" class="w-2 h-2 rounded-full bg-green-500"></span>
                    <span id="captureStatus" class="text-sm text-gray-400">Capturing</span>
                </div>
                <div class="flex gap-2">
                    <button id="pauseBtn" class="text-sm px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded">Pause</button>
                    <button id="refreshBtn" class="text-sm px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded">Refresh</button>
                </div>
            </div>

            <!-- Request List -->
            <div id="requestList" class="flex-1 overflow-y-auto">
                <div class="text-center py-8 text-gray-500">Loading requests...</div>
            </div>
        </div>

        <!-- Detail Panel -->
        <div class="flex-1 flex flex-col">
            <div id="detailPanel" class="flex-1 overflow-y-auto">
                <div class="flex items-center justify-center h-full text-gray-500">
                    <div class="text-center">
                        <svg class="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                        </svg>
                        <p>Select a request to view details</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = window.location.pathname.replace(/\\/$/, '') + '/api';
        let selectedRequestId = null;
        let isCapturing = true;
        let refreshInterval = null;

        // Format JSON with syntax highlighting
        function formatJson(obj) {
            if (typeof obj === 'string') {
                try {
                    obj = JSON.parse(obj);
                } catch (e) {
                    return escapeHtml(obj);
                }
            }
            return syntaxHighlight(JSON.stringify(obj, null, 2));
        }

        function syntaxHighlight(json) {
            json = escapeHtml(json);
            return json.replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
                       .replace(/"([^"]+)"/g, '<span class="json-string">"$1"</span>')
                       .replace(/\\b(true|false)\\b/g, '<span class="json-boolean">$1</span>')
                       .replace(/\\bnull\\b/g, '<span class="json-null">null</span>')
                       .replace(/\\b(\\d+)\\b/g, '<span class="json-number">$1</span>');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Format duration
        function formatDuration(ms) {
            if (ms < 1) return `${(ms * 1000).toFixed(2)}us`;
            if (ms < 1000) return `${ms.toFixed(2)}ms`;
            return `${(ms / 1000).toFixed(2)}s`;
        }

        // Get method badge HTML
        function getMethodBadge(method) {
            const colors = {
                'GET': 'bg-blue-500/20 text-blue-400',
                'POST': 'bg-green-500/20 text-green-400',
                'PUT': 'bg-yellow-500/20 text-yellow-400',
                'PATCH': 'bg-orange-500/20 text-orange-400',
                'DELETE': 'bg-red-500/20 text-red-400',
                'HEAD': 'bg-purple-500/20 text-purple-400',
                'OPTIONS': 'bg-gray-500/20 text-gray-400',
            };
            return `<span class="px-2 py-0.5 rounded text-xs font-medium ${colors[method] || colors['GET']}">${method}</span>`;
        }

        // Get status badge HTML
        function getStatusBadge(status) {
            let color;
            if (status < 300) color = 'bg-green-500/20 text-green-400';
            else if (status < 400) color = 'bg-blue-500/20 text-blue-400';
            else if (status < 500) color = 'bg-yellow-500/20 text-yellow-400';
            else color = 'bg-red-500/20 text-red-400';
            return `<span class="px-2 py-0.5 rounded text-xs font-medium ${color}">${status}</span>`;
        }

        // Load requests
        async function loadRequests() {
            const method = document.getElementById('methodFilter').value;
            const status = document.getElementById('statusFilter').value;
            const search = document.getElementById('searchInput').value;

            let url = `${API_BASE}/requests?page_size=100`;
            if (method) url += `&method=${method}`;
            if (search) url += `&path=${encodeURIComponent(search)}`;
            if (status === 'success') url += '&status_min=200&status_max=300';
            else if (status === 'redirect') url += '&status_min=300&status_max=400';
            else if (status === 'client_error') url += '&status_min=400&status_max=500';
            else if (status === 'server_error') url += '&status_min=500';

            try {
                const response = await fetch(url);
                const data = await response.json();
                renderRequestList(data.items);
            } catch (error) {
                console.error('Failed to load requests:', error);
            }
        }

        // Load stats
        async function loadStats() {
            try {
                const response = await fetch(`${API_BASE}/stats`);
                const data = await response.json();
                document.getElementById('totalCount').textContent = data.total_requests;
                document.getElementById('successCount').textContent = data.success_count;
                document.getElementById('errorCount').textContent = data.error_count;
                document.getElementById('avgDuration').textContent = formatDuration(data.avg_duration_ms);

                isCapturing = data.is_capturing;
                updateCaptureUI();
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        }

        // Update capture UI
        function updateCaptureUI() {
            const indicator = document.getElementById('captureIndicator');
            const status = document.getElementById('captureStatus');
            const btn = document.getElementById('pauseBtn');

            if (isCapturing) {
                indicator.className = 'w-2 h-2 rounded-full bg-green-500';
                status.textContent = 'Capturing';
                btn.textContent = 'Pause';
            } else {
                indicator.className = 'w-2 h-2 rounded-full bg-red-500';
                status.textContent = 'Paused';
                btn.textContent = 'Resume';
            }
        }

        // Render request list
        function renderRequestList(requests) {
            const container = document.getElementById('requestList');

            if (!requests || requests.length === 0) {
                container.innerHTML = '<div class="text-center py-8 text-gray-500">No requests captured</div>';
                return;
            }

            container.innerHTML = requests.map(req => `
                <div class="request-row border-b border-gray-800 p-3 cursor-pointer ${req.id === selectedRequestId ? 'bg-gray-800' : ''}"
                     onclick="selectRequest('${req.id}')">
                    <div class="flex items-center justify-between mb-1">
                        <div class="flex items-center gap-2">
                            ${getMethodBadge(req.method)}
                            ${getStatusBadge(req.response_status)}
                        </div>
                        <span class="text-xs text-gray-500">${formatDuration(req.duration_ms)}</span>
                    </div>
                    <div class="text-sm truncate" title="${escapeHtml(req.path)}">
                        ${escapeHtml(req.path)}
                    </div>
                    <div class="text-xs text-gray-500 mt-1">
                        ${req.timestamp_formatted || new Date(req.timestamp * 1000).toLocaleString()}
                    </div>
                </div>
            `).join('');
        }

        // Select a request
        async function selectRequest(id) {
            selectedRequestId = id;

            // Update list selection
            document.querySelectorAll('.request-row').forEach(row => {
                row.classList.remove('bg-gray-800');
                if (row.onclick.toString().includes(id)) {
                    row.classList.add('bg-gray-800');
                }
            });

            // Load request detail
            try {
                const response = await fetch(`${API_BASE}/requests/${id}`);
                const data = await response.json();
                renderRequestDetail(data);
            } catch (error) {
                console.error('Failed to load request detail:', error);
            }
        }

        // Render request detail
        function renderRequestDetail(req) {
            const container = document.getElementById('detailPanel');

            container.innerHTML = `
                <div class="p-4 border-b border-gray-700 bg-gray-800/50">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-3">
                            ${getMethodBadge(req.method)}
                            ${getStatusBadge(req.response_status)}
                            <span class="text-gray-400">${formatDuration(req.duration_ms)}</span>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="exportRequest('curl')" class="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded">curl</button>
                            <button onclick="exportRequest('httpie')" class="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded">httpie</button>
                            <button onclick="exportRequest('python')" class="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded">Python</button>
                            <button onclick="exportRequest('fetch')" class="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded">fetch</button>
                        </div>
                    </div>
                    <div class="font-mono text-sm break-all">${escapeHtml(req.full_url || req.path)}</div>
                    <div class="text-xs text-gray-500 mt-2">
                        ${req.timestamp_formatted || new Date(req.timestamp * 1000).toLocaleString()}
                        ${req.client_ip ? ` - ${req.client_ip}` : ''}
                        ${req.user_email ? ` - ${req.user_email}` : ''}
                    </div>
                </div>

                <!-- Tabs -->
                <div class="border-b border-gray-700 flex">
                    <button class="tab-btn tab-active px-4 py-2 text-sm" onclick="showTab('request')">Request</button>
                    <button class="tab-btn px-4 py-2 text-sm text-gray-400 hover:text-white" onclick="showTab('response')">Response</button>
                    ${req.exception ? '<button class="tab-btn px-4 py-2 text-sm text-red-400 hover:text-red-300" onclick="showTab(\'exception\')">Exception</button>' : ''}
                </div>

                <!-- Tab Content -->
                <div id="tabContent" class="p-4 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                    ${renderRequestTab(req)}
                </div>
            `;
        }

        // Render request tab
        function renderRequestTab(req) {
            let html = '<div class="space-y-4">';

            // Headers
            html += '<div><h3 class="text-sm font-medium text-gray-400 mb-2">Headers</h3>';
            if (req.request_headers && Object.keys(req.request_headers).length > 0) {
                html += '<div class="bg-gray-800 rounded p-3 font-mono text-sm">';
                for (const [key, value] of Object.entries(req.request_headers)) {
                    html += `<div><span class="text-blue-400">${escapeHtml(key)}:</span> ${escapeHtml(value)}</div>`;
                }
                html += '</div>';
            } else {
                html += '<div class="text-gray-500 text-sm">No headers</div>';
            }
            html += '</div>';

            // Body
            html += '<div><h3 class="text-sm font-medium text-gray-400 mb-2">Body</h3>';
            if (req.request_body) {
                html += `<pre class="bg-gray-800 rounded p-3 font-mono text-sm overflow-x-auto">${formatJson(req.request_body)}</pre>`;
            } else {
                html += '<div class="text-gray-500 text-sm">No body</div>';
            }
            html += '</div>';

            html += '</div>';
            return html;
        }

        // Render response tab
        function renderResponseTab(req) {
            let html = '<div class="space-y-4">';

            // Status
            html += `<div><h3 class="text-sm font-medium text-gray-400 mb-2">Status</h3>`;
            html += `<div class="flex items-center gap-2">${getStatusBadge(req.response_status)} <span>${req.response_status}</span></div></div>`;

            // Headers
            html += '<div><h3 class="text-sm font-medium text-gray-400 mb-2">Headers</h3>';
            if (req.response_headers && Object.keys(req.response_headers).length > 0) {
                html += '<div class="bg-gray-800 rounded p-3 font-mono text-sm">';
                for (const [key, value] of Object.entries(req.response_headers)) {
                    html += `<div><span class="text-blue-400">${escapeHtml(key)}:</span> ${escapeHtml(value)}</div>`;
                }
                html += '</div>';
            } else {
                html += '<div class="text-gray-500 text-sm">No headers</div>';
            }
            html += '</div>';

            // Body
            html += '<div><h3 class="text-sm font-medium text-gray-400 mb-2">Body</h3>';
            if (req.response_body) {
                html += `<pre class="bg-gray-800 rounded p-3 font-mono text-sm overflow-x-auto">${formatJson(req.response_body)}</pre>`;
            } else {
                html += '<div class="text-gray-500 text-sm">No body</div>';
            }
            html += '</div>';

            html += '</div>';
            return html;
        }

        // Render exception tab
        function renderExceptionTab(req) {
            let html = '<div class="space-y-4">';

            html += '<div><h3 class="text-sm font-medium text-red-400 mb-2">Exception</h3>';
            html += `<div class="bg-red-900/20 border border-red-800 rounded p-3 font-mono text-sm text-red-300">${escapeHtml(req.exception)}</div></div>`;

            if (req.traceback) {
                html += '<div><h3 class="text-sm font-medium text-gray-400 mb-2">Traceback</h3>';
                html += `<pre class="bg-gray-800 rounded p-3 font-mono text-xs overflow-x-auto text-gray-300">${escapeHtml(req.traceback)}</pre></div>`;
            }

            html += '</div>';
            return html;
        }

        // Show tab
        let currentRequest = null;
        async function showTab(tab) {
            // Update tab buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('tab-active');
                btn.classList.add('text-gray-400');
            });
            event.target.classList.add('tab-active');
            event.target.classList.remove('text-gray-400');

            // Get current request if not cached
            if (!currentRequest && selectedRequestId) {
                const response = await fetch(`${API_BASE}/requests/${selectedRequestId}`);
                currentRequest = await response.json();
            }

            const container = document.getElementById('tabContent');
            if (tab === 'request') {
                container.innerHTML = renderRequestTab(currentRequest);
            } else if (tab === 'response') {
                container.innerHTML = renderResponseTab(currentRequest);
            } else if (tab === 'exception') {
                container.innerHTML = renderExceptionTab(currentRequest);
            }
        }

        // Export request
        async function exportRequest(format) {
            if (!selectedRequestId) return;

            try {
                const response = await fetch(`${API_BASE}/requests/${selectedRequestId}/export`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ format, include_response: true })
                });
                const data = await response.json();

                // Copy to clipboard
                await navigator.clipboard.writeText(data.content);

                // Show toast
                showToast(`Copied ${format} command to clipboard`);
            } catch (error) {
                console.error('Failed to export request:', error);
                showToast('Failed to export request', true);
            }
        }

        // Show toast notification
        function showToast(message, isError = false) {
            const toast = document.createElement('div');
            toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg text-sm ${isError ? 'bg-red-600' : 'bg-green-600'} text-white shadow-lg z-50`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }

        // Clear all requests
        async function clearAll() {
            if (!confirm('Are you sure you want to clear all captured requests?')) return;

            try {
                await fetch(`${API_BASE}/requests`, { method: 'DELETE' });
                selectedRequestId = null;
                currentRequest = null;
                loadRequests();
                loadStats();
                document.getElementById('detailPanel').innerHTML = `
                    <div class="flex items-center justify-center h-full text-gray-500">
                        <div class="text-center">
                            <svg class="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                            </svg>
                            <p>Select a request to view details</p>
                        </div>
                    </div>
                `;
                showToast('All requests cleared');
            } catch (error) {
                console.error('Failed to clear requests:', error);
                showToast('Failed to clear requests', true);
            }
        }

        // Toggle capture
        async function toggleCapture() {
            const endpoint = isCapturing ? 'pause' : 'resume';
            try {
                await fetch(`${API_BASE}/${endpoint}`, { method: 'POST' });
                isCapturing = !isCapturing;
                updateCaptureUI();
                showToast(isCapturing ? 'Capture resumed' : 'Capture paused');
            } catch (error) {
                console.error('Failed to toggle capture:', error);
                showToast('Failed to toggle capture', true);
            }
        }

        // Event listeners
        document.getElementById('clearBtn').addEventListener('click', clearAll);
        document.getElementById('pauseBtn').addEventListener('click', toggleCapture);
        document.getElementById('refreshBtn').addEventListener('click', () => {
            loadRequests();
            loadStats();
        });
        document.getElementById('methodFilter').addEventListener('change', loadRequests);
        document.getElementById('statusFilter').addEventListener('change', loadRequests);

        let searchTimeout;
        document.getElementById('searchInput').addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(loadRequests, 300);
        });

        // Initial load
        loadRequests();
        loadStats();

        // Auto-refresh every 5 seconds when capturing
        refreshInterval = setInterval(() => {
            if (isCapturing) {
                loadRequests();
                loadStats();
            }
        }, 5000);
    </script>
</body>
</html>"""


@method_decorator(csrf_exempt, name="dispatch")
class InspectorAPIView(InspectorAccessMixin, View):
    """
    JSON API endpoints for the inspector dashboard.

    These endpoints are used by the dashboard JavaScript.
    """

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not self.check_access(request):
            return JsonResponse({"error": "Access denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, action: str = "", request_id: str = "") -> JsonResponse:
        storage = get_storage()

        if action == "requests" and request_id:
            # Get single request
            captured = storage.get(request_id)
            if not captured:
                return JsonResponse({"error": "Request not found"}, status=404)
            return JsonResponse(self._request_to_dict(captured))

        if action == "requests":
            # List requests with filters
            page = int(request.GET.get("page", 1))
            page_size = min(int(request.GET.get("page_size", 50)), 100)
            offset = (page - 1) * page_size

            method = request.GET.get("method")
            status = request.GET.get("status")
            status_min = request.GET.get("status_min")
            status_max = request.GET.get("status_max")
            path_contains = request.GET.get("path")

            if status:
                status = int(status)
            if status_min:
                status_min = int(status_min)
            if status_max:
                status_max = int(status_max)

            requests_list = storage.list(
                limit=page_size + 1,
                offset=offset,
                method=method,
                status=status,
                status_min=status_min,
                status_max=status_max,
                path_contains=path_contains,
            )

            has_next = len(requests_list) > page_size
            if has_next:
                requests_list = requests_list[:page_size]

            return JsonResponse(
                {
                    "items": [self._request_to_dict(r) for r in requests_list],
                    "total": storage.count(),
                    "page": page,
                    "page_size": page_size,
                    "has_next": has_next,
                    "has_prev": page > 1,
                }
            )

        if action == "stats":
            all_requests = storage.list(limit=1000)
            total = len(all_requests)
            success_count = sum(1 for r in all_requests if r.is_success)
            error_count = sum(1 for r in all_requests if r.is_client_error or r.is_server_error)

            durations = [r.duration_ms for r in all_requests if r.duration_ms > 0]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

            return JsonResponse(
                {
                    "total_requests": total,
                    "success_count": success_count,
                    "error_count": error_count,
                    "avg_duration_ms": round(avg_duration, 2),
                    "is_capturing": storage.is_capturing(),
                }
            )

        if action == "status":
            from .storage import RedisStorage

            storage_type = "redis" if isinstance(storage, RedisStorage) else "memory"
            return JsonResponse(
                {
                    "is_capturing": storage.is_capturing(),
                    "storage_type": storage_type,
                    "request_count": storage.count(),
                    "max_requests": getattr(storage, "max_requests", 100),
                }
            )

        return JsonResponse({"error": "Unknown action"}, status=400)

    def post(self, request: HttpRequest, action: str = "", request_id: str = "") -> JsonResponse:
        storage = get_storage()

        if action == "export" and request_id:
            captured = storage.get(request_id)
            if not captured:
                return JsonResponse({"error": "Request not found"}, status=404)

            try:
                body = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                body = {}

            export_format = body.get("format", "curl")
            include_response = body.get("include_response", False)

            try:
                content = export_request(
                    captured, format=export_format, include_response=include_response
                )
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)

            return JsonResponse({"format": export_format, "content": content})

        if action == "pause":
            storage.pause_capture()
            return JsonResponse({"message": "Capture paused"})

        if action == "resume":
            storage.resume_capture()
            return JsonResponse({"message": "Capture resumed"})

        return JsonResponse({"error": "Unknown action"}, status=400)

    def delete(self, request: HttpRequest, action: str = "", request_id: str = "") -> JsonResponse:
        storage = get_storage()

        if action == "requests" and not request_id:
            count = storage.clear()
            return JsonResponse({"message": f"Cleared {count} requests"})

        return JsonResponse({"error": "Unknown action"}, status=400)

    def _request_to_dict(self, req: CapturedRequest) -> dict[str, Any]:
        """Convert a CapturedRequest to a dictionary."""
        return {
            "id": req.id,
            "timestamp": req.timestamp,
            "timestamp_formatted": datetime.fromtimestamp(req.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "method": req.method,
            "path": req.path,
            "full_url": req.full_url,
            "query_string": req.query_string,
            "request_headers": req.request_headers,
            "request_body": req.request_body,
            "request_content_type": req.request_content_type,
            "response_status": req.response_status,
            "response_headers": req.response_headers,
            "response_body": req.response_body,
            "response_content_type": req.response_content_type,
            "duration_ms": req.duration_ms,
            "client_ip": req.client_ip,
            "user_id": req.user_id,
            "user_email": req.user_email,
            "exception": req.exception,
            "traceback": req.traceback,
            "status_category": req.status_category,
            "is_success": req.is_success,
            "is_error": req.is_client_error or req.is_server_error,
        }


def include_inspector():
    """
    Include inspector URLs in your urlpatterns.

    Usage:
        from django_matt.inspector import include_inspector

        urlpatterns = [
            path("_matt/inspector/", include_inspector()),
        ]
    """
    return [
        path("", InspectorDashboardView.as_view(), name="inspector-dashboard"),
        path(
            "api/requests",
            InspectorAPIView.as_view(),
            {"action": "requests"},
            name="inspector-list",
        ),
        path(
            "api/requests/<str:request_id>",
            InspectorAPIView.as_view(),
            {"action": "requests"},
            name="inspector-detail",
        ),
        path(
            "api/requests/<str:request_id>/export",
            InspectorAPIView.as_view(),
            {"action": "export"},
            name="inspector-export",
        ),
        path("api/stats", InspectorAPIView.as_view(), {"action": "stats"}, name="inspector-stats"),
        path(
            "api/status", InspectorAPIView.as_view(), {"action": "status"}, name="inspector-status"
        ),
        path("api/pause", InspectorAPIView.as_view(), {"action": "pause"}, name="inspector-pause"),
        path(
            "api/resume", InspectorAPIView.as_view(), {"action": "resume"}, name="inspector-resume"
        ),
    ]


# URL patterns for direct inclusion
urlpatterns = include_inspector()


__all__ = [
    "InspectorDashboardView",
    "InspectorAPIView",
    "include_inspector",
    "urlpatterns",
]
