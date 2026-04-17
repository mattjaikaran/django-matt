"""
Lightweight development toolbar.

Renders a collapsible panel at the bottom of HTML pages showing
request metrics: timing, SQL queries, cache hits, and warnings.

Only active when DEBUG = True and DJANGO_MATT_INSPECTOR.TOOLBAR = True.

Usage:
    # settings.py
    MIDDLEWARE = [
        "django_matt.inspector.toolbar.ToolbarMiddleware",
        ...
    ]

    DJANGO_MATT_INSPECTOR = {
        "ENABLED": True,
        "TOOLBAR": True,
    }
"""

from __future__ import annotations

import html
import logging
import time
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connection

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("django_matt.inspector.toolbar")


_TOOLBAR_CSS = """
<style id="matt-toolbar-styles">
#matt-toolbar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 99998;
    font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
    font-size: 12px;
    transition: transform 0.2s ease;
}
#matt-toolbar.collapsed { transform: translateY(calc(100% - 32px)); }
#matt-toolbar .toolbar-toggle {
    position: absolute;
    top: -32px;
    right: 16px;
    background: #18181b;
    border: 1px solid #3f3f46;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    color: #a1a1aa;
    cursor: pointer;
    padding: 6px 14px;
    font-family: inherit;
    font-size: 11px;
    display: flex;
    align-items: center;
    gap: 6px;
}
#matt-toolbar .toolbar-toggle:hover { color: #e4e4e7; }
#matt-toolbar .toolbar-bar {
    background: #18181b;
    border-top: 1px solid #3f3f46;
    display: flex;
    align-items: center;
    padding: 0 16px;
    height: 36px;
    gap: 20px;
    overflow-x: auto;
}
#matt-toolbar .toolbar-item {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    color: #a1a1aa;
}
#matt-toolbar .toolbar-item .label { color: #71717a; }
#matt-toolbar .toolbar-item .value { color: #e4e4e7; font-weight: 500; }
#matt-toolbar .toolbar-item .value.ok { color: #4ade80; }
#matt-toolbar .toolbar-item .value.warn { color: #fbbf24; }
#matt-toolbar .toolbar-item .value.error { color: #f87171; }
#matt-toolbar .toolbar-detail {
    background: #09090b;
    border-top: 1px solid #27272a;
    max-height: 300px;
    overflow-y: auto;
    padding: 12px 16px;
    display: none;
}
#matt-toolbar:not(.collapsed) .toolbar-detail.active { display: block; }
#matt-toolbar .query-list { list-style: none; padding: 0; margin: 0; }
#matt-toolbar .query-list li {
    padding: 6px 0;
    border-bottom: 1px solid #1a1a1e;
    display: flex;
    gap: 12px;
}
#matt-toolbar .query-list li:last-child { border-bottom: none; }
#matt-toolbar .query-time { color: #a78bfa; min-width: 60px; text-align: right; }
#matt-toolbar .query-sql { color: #d4d4d8; word-break: break-all; }
#matt-toolbar .query-dup { color: #f87171; font-weight: 600; }
</style>
"""


def _classify_duration(ms: float) -> str:
    if ms < 100:
        return "ok"
    if ms < 500:
        return "warn"
    return "error"


def _classify_query_count(n: int) -> str:
    if n <= 5:
        return "ok"
    if n <= 15:
        return "warn"
    return "error"


def _build_toolbar_html(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    queries: list[dict],
    query_count: int,
    query_time_ms: float,
    n_plus_one: list[str],
) -> str:
    """Build the toolbar HTML."""
    status_cls = "ok" if 200 <= status_code < 400 else ("warn" if status_code < 500 else "error")
    dur_cls = _classify_duration(duration_ms)
    qcount_cls = _classify_query_count(query_count)

    query_items = ""
    for q in queries[:50]:
        sql_escaped = html.escape(q.get("sql", ""))[:200]
        time_str = f"{q.get('time', 0):.1f}ms"
        dup = ' <span class="query-dup">[DUP]</span>' if q.get("duplicate") else ""
        query_items += (
            f'<li><span class="query-time">{time_str}</span>'
            f'<span class="query-sql">{sql_escaped}{dup}</span></li>'
        )

    n_plus_one_html = ""
    if n_plus_one:
        warnings_text = html.escape(", ".join(n_plus_one[:5]))
        n_plus_one_html = (
            f'<div style="color:#fbbf24;margin-top:8px;">N+1 warnings: {warnings_text}</div>'
        )

    n_plus_one_indicator = (
        '<div class="toolbar-item"><span class="value warn">N+1 detected</span></div>'
        if n_plus_one
        else ""
    )

    return f"""
{_TOOLBAR_CSS}
<div id="matt-toolbar" class="collapsed">
    <button class="toolbar-toggle" onclick="document.getElementById('matt-toolbar').classList.toggle('collapsed')">
        django-matt | {html.escape(method)} {html.escape(path)} <span class="value {status_cls}">{status_code}</span>
    </button>
    <div class="toolbar-bar">
        <div class="toolbar-item">
            <span class="label">Status</span>
            <span class="value {status_cls}">{status_code}</span>
        </div>
        <div class="toolbar-item">
            <span class="label">Time</span>
            <span class="value {dur_cls}">{duration_ms:.0f}ms</span>
        </div>
        <div class="toolbar-item" style="cursor:pointer" onclick="document.querySelector('#matt-toolbar .toolbar-detail').classList.toggle('active')">
            <span class="label">SQL</span>
            <span class="value {qcount_cls}">{query_count} queries ({query_time_ms:.0f}ms)</span>
        </div>
        {n_plus_one_indicator}
    </div>
    <div class="toolbar-detail">
        <ul class="query-list">{query_items}</ul>
        {n_plus_one_html}
    </div>
</div>
"""


class ToolbarMiddleware:
    """
    Development toolbar showing request metrics on HTML pages.

    Only active when DEBUG=True and DJANGO_MATT_INSPECTOR.TOOLBAR is truthy.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._is_enabled():
            return self.get_response(request)

        if not self._should_instrument(request):
            return self.get_response(request)

        connection.force_debug_cursor = True
        initial_queries = len(connection.queries)
        start = time.perf_counter()

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start) * 1000

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        if response.streaming:
            return response

        queries_raw = connection.queries[initial_queries:]
        query_count = len(queries_raw)
        query_time_ms = sum(float(q.get("time", 0)) * 1000 for q in queries_raw)

        seen_sql: dict[str, int] = {}
        queries: list[dict] = []
        n_plus_one: list[str] = []
        for q in queries_raw:
            sql = q.get("sql", "")
            seen_sql[sql] = seen_sql.get(sql, 0) + 1
            queries.append(
                {
                    "sql": sql,
                    "time": float(q.get("time", 0)) * 1000,
                    "duplicate": seen_sql[sql] > 1,
                }
            )

        for sql, count in seen_sql.items():
            if count >= 3:
                short = sql[:80]
                n_plus_one.append(f"{short}... (x{count})")

        toolbar_html = _build_toolbar_html(
            method=request.method or "GET",
            path=request.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            queries=queries,
            query_count=query_count,
            query_time_ms=query_time_ms,
            n_plus_one=n_plus_one,
        )

        content = response.content.decode(response.charset or "utf-8")
        if "</body>" in content:
            content = content.replace("</body>", f"{toolbar_html}</body>")
            response.content = content.encode(response.charset or "utf-8")
            response["Content-Length"] = len(response.content)

        return response

    @staticmethod
    def _is_enabled() -> bool:
        if not getattr(settings, "DEBUG", False):
            return False
        config = getattr(settings, "DJANGO_MATT_INSPECTOR", {})
        return bool(config.get("TOOLBAR", config.get("ENABLED", False)))

    @staticmethod
    def _should_instrument(request) -> bool:
        path = request.path
        skip_prefixes = ("/_matt/", "/static/", "/media/", "/__debug__/")
        skip_extensions = (
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".gif",
            ".ico",
            ".woff",
            ".woff2",
            ".svg",
            ".map",
        )
        if any(path.startswith(p) for p in skip_prefixes):
            return False
        if any(path.endswith(ext) for ext in skip_extensions):
            return False
        accept = request.META.get("HTTP_ACCEPT", "")
        if accept and "text/html" not in accept and "*/*" not in accept:
            return False
        return True
