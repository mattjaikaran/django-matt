from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

import orjson

from django_matt.schema_designer.analyzer import SchemaAnalyzer
from django_matt.schema_designer.optimizer import SchemaOptimizer
from django_matt.schema_designer.visualizer import generate_mermaid

if TYPE_CHECKING:
    from django.http import HttpRequest


class SchemaAccessMixin:
    def check_access(self, request: HttpRequest) -> bool:
        config = getattr(settings, "DJANGO_MATT_SCHEMA_DESIGNER", {})
        if not config.get("ENABLED", True):
            return False
        if config.get("REQUIRE_STAFF", True):
            if not request.user.is_authenticated:
                return False
            if not request.user.is_staff:
                return False
        return True


class SchemaDesignerView(SchemaAccessMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        if not self.check_access(request):
            return HttpResponse("Access denied", status=403)
        html = self._render_dashboard()
        return HttpResponse(html, content_type="text/html")

    def _render_dashboard(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schema Designer - Django Matt</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        .severity-error { color: #ef4444; }
        .severity-warning { color: #f59e0b; }
        .severity-info { color: #3b82f6; }
        .badge-error { background: #7f1d1d; color: #fca5a5; }
        .badge-warning { background: #78350f; color: #fcd34d; }
        .badge-info { background: #1e3a5f; color: #93c5fd; }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8">
            <h1 class="text-3xl font-bold">Schema Designer</h1>
            <p class="text-gray-400">Database visualization, analysis, and optimization</p>
        </header>

        <!-- Filter bar -->
        <div class="bg-gray-800 rounded-lg p-4 mb-6 flex gap-4 items-center">
            <input type="text" id="searchInput" placeholder="Search models or fields..."
                   class="bg-gray-700 text-white px-4 py-2 rounded flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <select id="appFilter" class="bg-gray-700 text-white px-4 py-2 rounded focus:outline-none">
                <option value="">All apps</option>
            </select>
            <button onclick="runAnalysis()" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded font-medium">
                Analyze
            </button>
            <button onclick="showOptimizations()" class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded font-medium">
                Optimize
            </button>
        </div>

        <!-- Summary cards -->
        <div id="summaryCards" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6"></div>

        <!-- ER Diagram -->
        <div class="bg-gray-800 rounded-lg p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">ER Diagram</h2>
            <div id="mermaidDiagram" class="overflow-auto bg-gray-900 rounded p-4"></div>
        </div>

        <!-- Analysis Results -->
        <div id="analysisSection" class="bg-gray-800 rounded-lg p-6 mb-6 hidden">
            <h2 class="text-xl font-semibold mb-4">Analysis Results</h2>
            <div id="analysisResults"></div>
        </div>

        <!-- Optimization Suggestions -->
        <div id="optimizeSection" class="bg-gray-800 rounded-lg p-6 mb-6 hidden">
            <h2 class="text-xl font-semibold mb-4">Optimization Suggestions</h2>
            <div id="optimizeResults"></div>
        </div>

        <!-- Model List -->
        <div class="bg-gray-800 rounded-lg p-6">
            <h2 class="text-xl font-semibold mb-4">Models</h2>
            <div id="modelList" class="space-y-4"></div>
        </div>
    </div>

    <script>
        mermaid.initialize({ startOnLoad: false, theme: 'dark' });
        const apiBase = window.location.pathname.replace(/\\/$/, '') + '/api';
        let allModels = [];

        async function loadModels() {
            const res = await fetch(apiBase + '/models/');
            const data = await res.json();
            allModels = data.models || [];
            renderModelList(allModels);
            populateAppFilter(allModels);
        }

        async function loadDiagram() {
            const res = await fetch(apiBase + '/diagram/');
            const data = await res.json();
            const el = document.getElementById('mermaidDiagram');
            try {
                const { svg } = await mermaid.render('erDiag', data.diagram);
                el.innerHTML = svg;
            } catch(e) {
                el.innerHTML = '<pre class="text-gray-400">' + data.diagram + '</pre>';
            }
        }

        async function runAnalysis() {
            const res = await fetch(apiBase + '/analyze/');
            const data = await res.json();
            const section = document.getElementById('analysisSection');
            const results = document.getElementById('analysisResults');
            section.classList.remove('hidden');

            document.getElementById('summaryCards').innerHTML = `
                <div class="bg-gray-700 rounded-lg p-4">
                    <p class="text-gray-400 text-sm">Total Issues</p>
                    <p class="text-2xl font-bold">${data.total_issues}</p>
                </div>
                <div class="bg-gray-700 rounded-lg p-4">
                    <p class="text-gray-400 text-sm">Errors</p>
                    <p class="text-2xl font-bold text-red-400">${data.total_errors}</p>
                </div>
                <div class="bg-gray-700 rounded-lg p-4">
                    <p class="text-gray-400 text-sm">Warnings</p>
                    <p class="text-2xl font-bold text-yellow-400">${data.total_warnings}</p>
                </div>
                <div class="bg-gray-700 rounded-lg p-4">
                    <p class="text-gray-400 text-sm">Info</p>
                    <p class="text-2xl font-bold text-blue-400">${data.total_info}</p>
                </div>
            `;

            let html = '';
            for (const model of data.models) {
                if (model.issues.length === 0) continue;
                html += `<div class="mb-4"><h3 class="font-medium text-lg mb-2">${model.full_name}</h3>`;
                for (const issue of model.issues) {
                    const cls = 'badge-' + issue.severity;
                    html += `<div class="flex items-start gap-3 mb-2 ml-4">
                        <span class="px-2 py-0.5 rounded text-xs font-medium ${cls}">${issue.severity.toUpperCase()}</span>
                        <div>
                            <span class="text-gray-300">${issue.field_name}:</span>
                            <span class="text-gray-100">${issue.issue}</span>
                            <p class="text-gray-500 text-sm">${issue.suggestion}</p>
                        </div>
                    </div>`;
                }
                html += '</div>';
            }
            results.innerHTML = html || '<p class="text-gray-500">No issues found.</p>';
        }

        async function showOptimizations() {
            const res = await fetch(apiBase + '/optimize/', { method: 'POST' });
            const data = await res.json();
            const section = document.getElementById('optimizeSection');
            const results = document.getElementById('optimizeResults');
            section.classList.remove('hidden');

            let html = '';
            if (data.index_suggestions && data.index_suggestions.length) {
                html += '<h3 class="font-medium mb-2">Index Suggestions</h3>';
                for (const s of data.index_suggestions) {
                    html += `<div class="bg-gray-700 rounded p-3 mb-2">
                        <p class="font-medium">${s.model_name}.${s.field_name}</p>
                        <p class="text-gray-400 text-sm">${s.reason}</p>
                        <code class="text-green-400 text-xs block mt-1">${s.migration_code}</code>
                    </div>`;
                }
            }
            if (data.migration_code) {
                html += '<h3 class="font-medium mb-2 mt-4">Generated Migration</h3>';
                html += `<pre class="bg-gray-900 rounded p-4 text-sm text-green-400 overflow-auto">${data.migration_code}</pre>`;
            }
            results.innerHTML = html || '<p class="text-gray-500">No optimizations suggested.</p>';
        }

        function renderModelList(models) {
            const el = document.getElementById('modelList');
            const search = (document.getElementById('searchInput').value || '').toLowerCase();
            const appFilter = document.getElementById('appFilter').value;

            let filtered = models;
            if (search) {
                filtered = filtered.filter(m =>
                    m.full_name.toLowerCase().includes(search) ||
                    m.fields.some(f => f.name.toLowerCase().includes(search))
                );
            }
            if (appFilter) {
                filtered = filtered.filter(m => m.app_label === appFilter);
            }

            el.innerHTML = filtered.map(m => `
                <details class="bg-gray-700 rounded-lg">
                    <summary class="px-4 py-3 cursor-pointer hover:bg-gray-600 rounded-lg flex justify-between items-center">
                        <span class="font-medium">${m.full_name}</span>
                        <span class="text-gray-400 text-sm">${m.field_count} fields, ${m.relationships.length} relationships</span>
                    </summary>
                    <div class="px-4 pb-4">
                        <table class="w-full text-sm mt-2">
                            <thead><tr class="text-gray-400 text-left">
                                <th class="pb-1">Field</th><th class="pb-1">Type</th><th class="pb-1">Attrs</th>
                            </tr></thead>
                            <tbody>${m.fields.map(f => `
                                <tr class="border-t border-gray-600">
                                    <td class="py-1">${f.name}</td>
                                    <td class="py-1 text-gray-400">${f.type}</td>
                                    <td class="py-1 text-gray-500 text-xs">${
                                        [f.null ? 'NULL' : '', f.db_index ? 'IDX' : '', f.unique ? 'UQ' : '', f.has_default ? 'DEF' : ''].filter(Boolean).join(' ')
                                    }</td>
                                </tr>
                            `).join('')}</tbody>
                        </table>
                        ${m.relationships.length ? `
                            <p class="text-gray-400 text-sm mt-3 mb-1">Relationships:</p>
                            ${m.relationships.map(r => `
                                <span class="inline-block bg-gray-600 rounded px-2 py-0.5 text-xs mr-1 mb-1">
                                    ${r.type.toUpperCase()} ${r.field} → ${r.related_model}
                                </span>
                            `).join('')}
                        ` : ''}
                    </div>
                </details>
            `).join('');
        }

        function populateAppFilter(models) {
            const apps = [...new Set(models.map(m => m.app_label))].sort();
            const select = document.getElementById('appFilter');
            for (const app of apps) {
                const opt = document.createElement('option');
                opt.value = app;
                opt.textContent = app;
                select.appendChild(opt);
            }
        }

        document.getElementById('searchInput').addEventListener('input', () => renderModelList(allModels));
        document.getElementById('appFilter').addEventListener('change', () => renderModelList(allModels));

        loadModels();
        loadDiagram();
    </script>
</body>
</html>"""


@method_decorator(csrf_exempt, name="dispatch")
class SchemaAPIView(SchemaAccessMixin, View):
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not self.check_access(request):
            return JsonResponse({"error": "Access denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, action: str = "models") -> JsonResponse:
        analyzer = SchemaAnalyzer()

        if action == "models":
            report = analyzer.analyze_all()
            data = orjson.loads(report.model_dump_json())
            return JsonResponse(data, safe=False)

        if action == "model_detail":
            app_model = request.GET.get("name", "")
            try:
                from django.apps import apps

                app_label, model_name = app_model.split(".")
                model = apps.get_model(app_label, model_name)
                model_report = analyzer.analyze_model(model)
                data = orjson.loads(model_report.model_dump_json())
                return JsonResponse(data)
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)

        if action == "analyze":
            report = analyzer.analyze_all()
            data = orjson.loads(report.model_dump_json())
            return JsonResponse(data)

        if action == "diagram":
            app_filter = request.GET.get("app")
            app_labels = [app_filter] if app_filter else None
            diagram = generate_mermaid(app_labels=app_labels)
            return JsonResponse({"diagram": diagram})

        return JsonResponse({"error": "Unknown action"}, status=400)

    def post(self, request: HttpRequest, action: str = "") -> JsonResponse:
        if action == "optimize":
            from django.apps import apps as django_apps

            optimizer = SchemaOptimizer()
            all_suggestions: list[dict[str, Any]] = []

            for model in django_apps.get_models():
                for s in optimizer.suggest_indexes(model):
                    all_suggestions.append(orjson.loads(s.model_dump_json()))

            migration_code = ""
            if all_suggestions:
                from django_matt.schema_designer.optimizer import IndexSuggestion

                idx_objs = [IndexSuggestion(**s) for s in all_suggestions]
                migration_code = optimizer.generate_migration(idx_objs)

            return JsonResponse(
                {
                    "index_suggestions": all_suggestions,
                    "migration_code": migration_code,
                }
            )

        return JsonResponse({"error": "Unknown action"}, status=400)


def include_schema_designer():
    return [
        path("", SchemaDesignerView.as_view(), name="schema-designer"),
        path("api/models/", SchemaAPIView.as_view(), {"action": "models"}, name="schema-models"),
        path(
            "api/models/detail/",
            SchemaAPIView.as_view(),
            {"action": "model_detail"},
            name="schema-model-detail",
        ),
        path("api/analyze/", SchemaAPIView.as_view(), {"action": "analyze"}, name="schema-analyze"),
        path("api/diagram/", SchemaAPIView.as_view(), {"action": "diagram"}, name="schema-diagram"),
        path(
            "api/optimize/", SchemaAPIView.as_view(), {"action": "optimize"}, name="schema-optimize"
        ),
    ]


__all__ = [
    "SchemaDesignerView",
    "SchemaAPIView",
    "include_schema_designer",
]
