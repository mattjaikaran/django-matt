"""
Interactive documentation views for Django Matt.

Provides a modern, interactive documentation UI with:
- API endpoint browser
- Interactive playground
- Request history
- Code snippet generation
"""

import json
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template import Context, Template
from django.urls import path

from .playground import CodeGenerator, PlaygroundSession


class DocsView:
    """
    Interactive documentation view.

    Renders a modern documentation UI with endpoint browser,
    search, and links to the playground.
    """

    def __init__(self, api: Any, title: str | None = None):
        self.api = api
        self.title = title or f"{api.title} - Documentation"

    def get_endpoints(self) -> list[dict]:
        """Extract all endpoints from the API."""
        endpoints = []

        # Get routes from the API
        for route in getattr(self.api, "routes", []):
            endpoints.append(
                {
                    "path": route.get("path", ""),
                    "method": route.get("method", "GET"),
                    "summary": route.get("summary", ""),
                    "description": route.get("description", ""),
                    "tags": route.get("tags", []),
                    "parameters": route.get("parameters", []),
                    "request_body": route.get("request_body"),
                    "responses": route.get("responses", {}),
                }
            )

        # Get routes from controllers
        for controller in getattr(self.api, "controllers", []):
            prefix = getattr(controller, "prefix", "")
            tags = getattr(controller, "tags", [controller.__name__])

            for method_name in dir(controller):
                method = getattr(controller, method_name)
                if hasattr(method, "_route_info"):
                    route_info = method._route_info
                    endpoints.append(
                        {
                            "path": f"{prefix}{route_info.get('path', '')}",
                            "method": route_info.get("method", "GET"),
                            "summary": route_info.get(
                                "summary", method_name.replace("_", " ").title()
                            ),
                            "description": method.__doc__ or "",
                            "tags": route_info.get("tags", tags),
                            "parameters": route_info.get("parameters", []),
                            "request_body": route_info.get("request_body"),
                            "responses": route_info.get("responses", {}),
                        }
                    )

        return endpoints

    def get_tags(self) -> list[str]:
        """Get unique tags from all endpoints."""
        tags = set()
        for endpoint in self.get_endpoints():
            tags.update(endpoint.get("tags", []))
        return sorted(tags)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Render the documentation page."""
        endpoints = self.get_endpoints()
        tags = self.get_tags()

        # Group endpoints by tag
        endpoints_by_tag = {}
        for tag in tags:
            endpoints_by_tag[tag] = [e for e in endpoints if tag in e.get("tags", [])]

        context = {
            "title": self.title,
            "api_title": self.api.title,
            "api_version": self.api.version,
            "api_description": self.api.description,
            "endpoints": endpoints,
            "tags": tags,
            "endpoints_by_tag": endpoints_by_tag,
            "openapi_url": getattr(self.api, "openapi_url", "/openapi.json"),
            "dark_mode": request.COOKIES.get("dark_mode", "auto"),
        }

        html = self._render_template(context)
        return HttpResponse(html, content_type="text/html")

    def _render_template(self, context: dict) -> str:
        """Render the documentation HTML template."""
        template = DOCS_TEMPLATE
        t = Template(template)
        return t.render(Context(context))


class PlaygroundView:
    """
    Interactive API playground view.

    Allows users to:
    - Test API endpoints
    - Authenticate with tokens
    - Save and share requests
    - Generate code snippets
    """

    def __init__(self, api: Any, title: str | None = None):
        self.api = api
        self.title = title or f"{api.title} - Playground"
        self.sessions: dict[str, PlaygroundSession] = {}

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Render the playground page."""
        if request.method == "POST":
            return self._handle_request(request)

        context = {
            "title": self.title,
            "api_title": self.api.title,
            "api_version": self.api.version,
            "openapi_url": getattr(self.api, "openapi_url", "/openapi.json"),
            "dark_mode": request.COOKIES.get("dark_mode", "auto"),
        }

        html = self._render_playground_template(context)
        return HttpResponse(html, content_type="text/html")

    def _handle_request(self, request: HttpRequest) -> JsonResponse:
        """Handle API request from playground."""
        try:
            data = json.loads(request.body)
            method = data.get("method", "GET")
            url = data.get("url", "")
            headers = data.get("headers", {})
            body = data.get("body")

            # Generate code snippets
            code_generator = CodeGenerator(
                method=method,
                url=url,
                headers=headers,
                body=body,
            )

            return JsonResponse(
                {
                    "snippets": {
                        "curl": code_generator.curl(),
                        "python": code_generator.python(),
                        "javascript": code_generator.javascript(),
                        "httpie": code_generator.httpie(),
                    },
                }
            )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    def _render_playground_template(self, context: dict) -> str:
        """Render the playground HTML template."""
        template = PLAYGROUND_TEMPLATE
        t = Template(template)
        return t.render(Context(context))


class SearchView:
    """Search endpoints in the documentation."""

    def __init__(self, api: Any):
        self.api = api
        self.docs_view = DocsView(api)

    def __call__(self, request: HttpRequest) -> JsonResponse:
        """Search endpoints."""
        query = request.GET.get("q", "").lower()
        if not query:
            return JsonResponse({"results": []})

        endpoints = self.docs_view.get_endpoints()
        results = []

        for endpoint in endpoints:
            # Search in path, summary, description, and tags
            searchable = " ".join(
                [
                    endpoint.get("path", ""),
                    endpoint.get("summary", ""),
                    endpoint.get("description", ""),
                    " ".join(endpoint.get("tags", [])),
                ]
            ).lower()

            if query in searchable:
                results.append(
                    {
                        "path": endpoint["path"],
                        "method": endpoint["method"],
                        "summary": endpoint.get("summary", ""),
                        "tags": endpoint.get("tags", []),
                    }
                )

        return JsonResponse({"results": results[:20]})


def get_docs_urls(api: Any) -> list:
    """
    Get URL patterns for documentation views.

    Usage:
        from django_matt.docs import get_docs_urls

        urlpatterns = [
            path("_matt/", include(get_docs_urls(api))),
        ]
    """
    docs_view = DocsView(api)
    playground_view = PlaygroundView(api)
    search_view = SearchView(api)

    return [
        path("docs/", docs_view, name="matt-docs"),
        path("docs/playground/", playground_view, name="matt-playground"),
        path("docs/search/", search_view, name="matt-docs-search"),
    ]


# Convenience functions for direct use
def docs_view(api: Any) -> DocsView:
    """Create a docs view for an API."""
    return DocsView(api)


def playground_view(api: Any) -> PlaygroundView:
    """Create a playground view for an API."""
    return PlaygroundView(api)


# =============================================================================
# HTML Templates
# =============================================================================

DOCS_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="{{ dark_mode }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #e9ecef;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --border-color: #dee2e6;
            --accent-color: #4f46e5;
            --accent-hover: #4338ca;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --error-color: #ef4444;
            --info-color: #3b82f6;
        }

        [data-theme="dark"] {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-tertiary: #0f3460;
            --text-primary: #e4e4e7;
            --text-secondary: #a1a1aa;
            --border-color: #3f3f46;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            display: flex;
            min-height: 100vh;
        }

        .sidebar {
            width: 280px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }

        .main {
            flex: 1;
            margin-left: 280px;
            padding: 40px;
            max-width: 900px;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent-color);
            margin-bottom: 8px;
        }

        .version {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 24px;
        }

        .search-box {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 0.875rem;
            margin-bottom: 24px;
        }

        .search-box:focus {
            outline: none;
            border-color: var(--accent-color);
        }

        .nav-section {
            margin-bottom: 20px;
        }

        .nav-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        .nav-item {
            display: flex;
            align-items: center;
            padding: 8px 12px;
            border-radius: 6px;
            text-decoration: none;
            color: var(--text-primary);
            font-size: 0.875rem;
            margin-bottom: 2px;
            transition: background 0.2s;
        }

        .nav-item:hover {
            background: var(--bg-tertiary);
        }

        .method-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.625rem;
            font-weight: 600;
            text-transform: uppercase;
            margin-right: 8px;
            min-width: 45px;
            text-align: center;
        }

        .method-get { background: #dbeafe; color: #1d4ed8; }
        .method-post { background: #d1fae5; color: #047857; }
        .method-put { background: #fef3c7; color: #b45309; }
        .method-patch { background: #fef3c7; color: #b45309; }
        .method-delete { background: #fee2e2; color: #dc2626; }

        [data-theme="dark"] .method-get { background: #1e3a5f; color: #60a5fa; }
        [data-theme="dark"] .method-post { background: #064e3b; color: #34d399; }
        [data-theme="dark"] .method-put { background: #78350f; color: #fbbf24; }
        [data-theme="dark"] .method-patch { background: #78350f; color: #fbbf24; }
        [data-theme="dark"] .method-delete { background: #7f1d1d; color: #f87171; }

        h1 {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 16px;
        }

        .description {
            color: var(--text-secondary);
            margin-bottom: 40px;
        }

        .endpoint-section {
            margin-bottom: 48px;
        }

        .endpoint-section h2 {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 24px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }

        .endpoint-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }

        .endpoint-header {
            display: flex;
            align-items: center;
            margin-bottom: 12px;
        }

        .endpoint-path {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.875rem;
            color: var(--text-primary);
        }

        .endpoint-summary {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }

        .playground-link {
            margin-left: auto;
            padding: 6px 12px;
            background: var(--accent-color);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .playground-link:hover {
            background: var(--accent-hover);
        }

        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 8px 12px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            cursor: pointer;
            color: var(--text-primary);
        }

        .footer {
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <nav class="sidebar">
            <div class="logo">{{ api_title }}</div>
            <div class="version">v{{ api_version }}</div>

            <input type="text" class="search-box" placeholder="Search endpoints..." id="search">

            {% for tag in tags %}
            <div class="nav-section">
                <div class="nav-title">{{ tag }}</div>
                {% for endpoint in endpoints_by_tag|get:tag %}
                <a href="#{{ endpoint.method|lower }}-{{ endpoint.path|slugify }}" class="nav-item">
                    <span class="method-badge method-{{ endpoint.method|lower }}">{{ endpoint.method }}</span>
                    <span>{{ endpoint.path }}</span>
                </a>
                {% endfor %}
            </div>
            {% endfor %}
        </nav>

        <main class="main">
            <h1>{{ api_title }}</h1>
            <p class="description">{{ api_description }}</p>

            {% for tag in tags %}
            <section class="endpoint-section">
                <h2>{{ tag }}</h2>

                {% for endpoint in endpoints_by_tag|get:tag %}
                <div class="endpoint-card" id="{{ endpoint.method|lower }}-{{ endpoint.path|slugify }}">
                    <div class="endpoint-header">
                        <span class="method-badge method-{{ endpoint.method|lower }}">{{ endpoint.method }}</span>
                        <span class="endpoint-path">{{ endpoint.path }}</span>
                        <a href="playground/?method={{ endpoint.method }}&path={{ endpoint.path|urlencode }}" class="playground-link">Try it</a>
                    </div>
                    <p class="endpoint-summary">{{ endpoint.summary }}</p>
                </div>
                {% endfor %}
            </section>
            {% endfor %}

            <div class="footer">
                Built with django-matt
            </div>
        </main>
    </div>

    <button class="theme-toggle" onclick="toggleTheme()">Toggle Theme</button>

    <script>
        function toggleTheme() {
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            document.cookie = `dark_mode=${next};path=/;max-age=31536000`;
        }

        document.getElementById('search').addEventListener('input', async (e) => {
            const query = e.target.value;
            if (query.length < 2) return;

            const response = await fetch(`search/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            // Handle search results...
        });
    </script>
</body>
</html>"""


PLAYGROUND_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="{{ dark_mode }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #e9ecef;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --border-color: #dee2e6;
            --accent-color: #4f46e5;
            --accent-hover: #4338ca;
            --success-color: #10b981;
            --error-color: #ef4444;
        }

        [data-theme="dark"] {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-tertiary: #0f3460;
            --text-primary: #e4e4e7;
            --text-secondary: #a1a1aa;
            --border-color: #3f3f46;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--accent-color);
        }

        .back-link {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.875rem;
        }

        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            padding: 24px;
            max-width: 1600px;
            margin: 0 auto;
        }

        .panel {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
        }

        .panel-header {
            background: var(--bg-tertiary);
            padding: 12px 16px;
            font-weight: 600;
            font-size: 0.875rem;
            border-bottom: 1px solid var(--border-color);
        }

        .panel-content {
            padding: 16px;
        }

        .request-bar {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }

        .method-select {
            padding: 10px 16px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-weight: 600;
            min-width: 100px;
        }

        .url-input {
            flex: 1;
            padding: 10px 16px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
        }

        .send-btn {
            padding: 10px 24px;
            background: var(--accent-color);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .send-btn:hover {
            background: var(--accent-hover);
        }

        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border-color);
        }

        .tab {
            padding: 10px 16px;
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.875rem;
            border-bottom: 2px solid transparent;
        }

        .tab.active {
            color: var(--accent-color);
            border-bottom-color: var(--accent-color);
        }

        .tab-content {
            display: none;
            padding: 16px;
        }

        .tab-content.active {
            display: block;
        }

        textarea {
            width: 100%;
            min-height: 200px;
            padding: 12px;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
            resize: vertical;
        }

        .response-status {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }

        .status-code {
            padding: 4px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.875rem;
        }

        .status-2xx {
            background: #d1fae5;
            color: #047857;
        }

        .status-4xx {
            background: #fee2e2;
            color: #dc2626;
        }

        .status-5xx {
            background: #fef3c7;
            color: #b45309;
        }

        [data-theme="dark"] .status-2xx { background: #064e3b; color: #34d399; }
        [data-theme="dark"] .status-4xx { background: #7f1d1d; color: #f87171; }
        [data-theme="dark"] .status-5xx { background: #78350f; color: #fbbf24; }

        .response-time {
            color: var(--text-secondary);
            font-size: 0.75rem;
        }

        pre {
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.875rem;
        }

        .snippet-select {
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 0.875rem;
            margin-bottom: 12px;
        }

        .copy-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            padding: 4px 8px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .code-block {
            position: relative;
        }

        .auth-section {
            margin-bottom: 16px;
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }

        .auth-input {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: monospace;
            font-size: 0.875rem;
            margin-top: 8px;
        }

        .theme-toggle {
            margin-left: auto;
            padding: 8px 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            cursor: pointer;
            color: var(--text-primary);
        }
    </style>
</head>
<body>
    <header class="header">
        <span class="logo">{{ api_title }}</span>
        <a href="../" class="back-link">Back to Docs</a>
        <span style="flex: 1;"></span>
        <button class="theme-toggle" onclick="toggleTheme()">Toggle Theme</button>
    </header>

    <div class="container">
        <div class="panel">
            <div class="panel-header">Request</div>
            <div class="panel-content">
                <div class="request-bar">
                    <select class="method-select" id="method">
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="PATCH">PATCH</option>
                        <option value="DELETE">DELETE</option>
                    </select>
                    <input type="text" class="url-input" id="url" placeholder="/api/endpoint">
                    <button class="send-btn" onclick="sendRequest()">Send</button>
                </div>

                <div class="auth-section">
                    <label>
                        <strong>Authorization</strong>
                        <input type="text" class="auth-input" id="auth-token" placeholder="Bearer your-token-here">
                    </label>
                </div>

                <div class="tabs">
                    <button class="tab active" onclick="showTab('body')">Body</button>
                    <button class="tab" onclick="showTab('headers')">Headers</button>
                    <button class="tab" onclick="showTab('params')">Query Params</button>
                </div>

                <div class="tab-content active" id="body-tab">
                    <textarea id="request-body" placeholder='{"key": "value"}'></textarea>
                </div>

                <div class="tab-content" id="headers-tab">
                    <textarea id="request-headers" placeholder="Content-Type: application/json"></textarea>
                </div>

                <div class="tab-content" id="params-tab">
                    <textarea id="request-params" placeholder="key=value"></textarea>
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">Response</div>
            <div class="panel-content">
                <div class="response-status" id="response-status" style="display: none;">
                    <span class="status-code" id="status-code">200</span>
                    <span class="response-time" id="response-time">0ms</span>
                </div>

                <pre id="response-body">// Response will appear here</pre>
            </div>
        </div>

        <div class="panel" style="grid-column: span 2;">
            <div class="panel-header">Code Snippets</div>
            <div class="panel-content">
                <select class="snippet-select" id="snippet-language" onchange="updateSnippet()">
                    <option value="curl">cURL</option>
                    <option value="python">Python (httpx)</option>
                    <option value="javascript">JavaScript (fetch)</option>
                    <option value="httpie">HTTPie</option>
                </select>

                <div class="code-block">
                    <pre id="code-snippet">// Select a language to see the code snippet</pre>
                    <button class="copy-btn" onclick="copySnippet()">Copy</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentSnippets = {};

        function toggleTheme() {
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            document.cookie = `dark_mode=${next};path=/;max-age=31536000`;
        }

        function showTab(name) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`[onclick="showTab('${name}')"]`).classList.add('active');
            document.getElementById(`${name}-tab`).classList.add('active');
        }

        async function sendRequest() {
            const method = document.getElementById('method').value;
            const url = document.getElementById('url').value;
            const authToken = document.getElementById('auth-token').value;
            const body = document.getElementById('request-body').value;

            const headers = {
                'Content-Type': 'application/json',
            };

            if (authToken) {
                headers['Authorization'] = authToken;
            }

            const startTime = performance.now();

            try {
                const options = {
                    method,
                    headers,
                };

                if (method !== 'GET' && body) {
                    options.body = body;
                }

                const response = await fetch(url, options);
                const endTime = performance.now();
                const data = await response.json();

                // Update response display
                document.getElementById('response-status').style.display = 'flex';
                const statusCode = document.getElementById('status-code');
                statusCode.textContent = response.status;
                statusCode.className = `status-code status-${Math.floor(response.status / 100)}xx`;
                document.getElementById('response-time').textContent = `${Math.round(endTime - startTime)}ms`;
                document.getElementById('response-body').textContent = JSON.stringify(data, null, 2);

                // Generate code snippets
                await generateSnippets(method, url, headers, body);
            } catch (error) {
                document.getElementById('response-body').textContent = `Error: ${error.message}`;
            }
        }

        async function generateSnippets(method, url, headers, body) {
            try {
                const response = await fetch('', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ method, url, headers, body }),
                });
                const data = await response.json();
                currentSnippets = data.snippets;
                updateSnippet();
            } catch (error) {
                console.error('Failed to generate snippets:', error);
            }
        }

        function updateSnippet() {
            const language = document.getElementById('snippet-language').value;
            const snippet = currentSnippets[language] || generateLocalSnippet(language);
            document.getElementById('code-snippet').textContent = snippet;
        }

        function generateLocalSnippet(language) {
            const method = document.getElementById('method').value;
            const url = document.getElementById('url').value;
            const body = document.getElementById('request-body').value;
            const authToken = document.getElementById('auth-token').value;

            switch (language) {
                case 'curl':
                    let curl = `curl -X ${method} "${url}"`;
                    if (authToken) curl += ` \\\n  -H "Authorization: ${authToken}"`;
                    curl += ` \\\n  -H "Content-Type: application/json"`;
                    if (body) curl += ` \\\n  -d '${body}'`;
                    return curl;

                case 'python':
                    return `import httpx

response = httpx.${method.toLowerCase()}(
    "${url}",
    headers={
        "Authorization": "${authToken}",
        "Content-Type": "application/json",
    },
    ${body ? `json=${body},` : ''}
)
print(response.json())`;

                case 'javascript':
                    return `const response = await fetch("${url}", {
  method: "${method}",
  headers: {
    "Authorization": "${authToken}",
    "Content-Type": "application/json",
  },
  ${body ? `body: JSON.stringify(${body}),` : ''}
});
const data = await response.json();
console.log(data);`;

                case 'httpie':
                    let httpie = `http ${method} ${url}`;
                    if (authToken) httpie += ` "Authorization:${authToken}"`;
                    return httpie;

                default:
                    return '// Unknown language';
            }
        }

        function copySnippet() {
            const snippet = document.getElementById('code-snippet').textContent;
            navigator.clipboard.writeText(snippet);
        }

        // Initialize from URL params
        const params = new URLSearchParams(window.location.search);
        if (params.get('method')) {
            document.getElementById('method').value = params.get('method');
        }
        if (params.get('path')) {
            document.getElementById('url').value = params.get('path');
        }
    </script>
</body>
</html>"""
