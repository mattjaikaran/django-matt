"""
Browser error overlay for development.

Injects a full-screen error overlay into HTML responses when the server
returns a 500 error. Only active when DEBUG=True.

Usage:
    # settings.py
    MIDDLEWARE = [
        "django_matt.dev.error_overlay.ErrorOverlayMiddleware",
        ...
    ]
"""

from __future__ import annotations

import html
import logging
import traceback
from typing import Any

from django.conf import settings

logger = logging.getLogger("django_matt.dev")


_OVERLAY_CSS = """
#matt-error-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    background: #1a1a2e;
    color: #e0e0e0;
    font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace;
    font-size: 14px;
    overflow-y: auto;
    padding: 0;
}
#matt-error-overlay .matt-header {
    background: #c0392b;
    padding: 20px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
#matt-error-overlay .matt-header h1 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #fff;
}
#matt-error-overlay .matt-close {
    background: rgba(255,255,255,0.2);
    border: none;
    color: #fff;
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
}
#matt-error-overlay .matt-close:hover {
    background: rgba(255,255,255,0.3);
}
#matt-error-overlay .matt-body {
    padding: 24px 32px;
}
#matt-error-overlay .matt-error-type {
    color: #e74c3c;
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 8px 0;
}
#matt-error-overlay .matt-error-msg {
    color: #f5f5f5;
    font-size: 16px;
    margin: 0 0 24px 0;
    line-height: 1.5;
}
#matt-error-overlay .matt-section {
    margin-bottom: 24px;
}
#matt-error-overlay .matt-section-title {
    color: #888;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}
#matt-error-overlay .matt-traceback {
    background: #0d0d1a;
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    line-height: 1.6;
}
#matt-error-overlay .matt-frame {
    padding: 8px 0;
    border-bottom: 1px solid #222;
}
#matt-error-overlay .matt-frame:last-child {
    border-bottom: none;
}
#matt-error-overlay .matt-frame-file {
    color: #3498db;
}
#matt-error-overlay .matt-frame-line {
    color: #e67e22;
}
#matt-error-overlay .matt-frame-func {
    color: #2ecc71;
}
#matt-error-overlay .matt-frame-code {
    color: #bbb;
    margin-top: 4px;
    padding-left: 16px;
}
#matt-error-overlay .matt-request-info {
    background: #0d0d1a;
    border-radius: 8px;
    padding: 16px;
}
#matt-error-overlay .matt-request-info dt {
    color: #888;
    font-size: 12px;
    margin-top: 8px;
}
#matt-error-overlay .matt-request-info dd {
    color: #e0e0e0;
    margin: 2px 0 0 0;
}
"""

_OVERLAY_JS = """
document.getElementById('matt-error-close').addEventListener('click', function() {
    document.getElementById('matt-error-overlay').remove();
});
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var overlay = document.getElementById('matt-error-overlay');
        if (overlay) overlay.remove();
    }
});
"""


def _format_traceback_html(exc_info: tuple) -> str:
    """Format exception traceback as styled HTML."""
    exc_type, exc_value, exc_tb = exc_info
    frames = traceback.extract_tb(exc_tb)

    parts: list[str] = []
    for frame in frames:
        file_html = html.escape(frame.filename)
        line_html = html.escape(str(frame.lineno))
        func_html = html.escape(frame.name)
        code_html = html.escape(frame.line or "")

        parts.append(
            f'<div class="matt-frame">'
            f'<span class="matt-frame-file">{file_html}</span>'
            f':<span class="matt-frame-line">{line_html}</span>'
            f' in <span class="matt-frame-func">{func_html}</span>'
        )
        if code_html:
            parts.append(f'<div class="matt-frame-code">{code_html}</div>')
        parts.append("</div>")

    return "\n".join(parts)


def _build_overlay_html(
    exc_type: str,
    exc_message: str,
    traceback_html: str,
    method: str = "",
    path: str = "",
    status_code: int = 500,
) -> str:
    """Build the complete error overlay HTML."""
    return f"""
<div id="matt-error-overlay">
  <style>{_OVERLAY_CSS}</style>
  <div class="matt-header">
    <h1>{status_code} Server Error</h1>
    <button id="matt-error-close" class="matt-close">Dismiss (Esc)</button>
  </div>
  <div class="matt-body">
    <p class="matt-error-type">{html.escape(exc_type)}</p>
    <p class="matt-error-msg">{html.escape(exc_message)}</p>

    <div class="matt-section">
      <div class="matt-section-title">Traceback</div>
      <div class="matt-traceback">{traceback_html}</div>
    </div>

    <div class="matt-section">
      <div class="matt-section-title">Request</div>
      <dl class="matt-request-info">
        <dt>Method</dt><dd>{html.escape(method)}</dd>
        <dt>Path</dt><dd>{html.escape(path)}</dd>
      </dl>
    </div>
  </div>
  <script>{_OVERLAY_JS}</script>
</div>
"""


class ErrorOverlayMiddleware:
    """
    Middleware that injects an error overlay into HTML responses on 500 errors.

    Only active when DEBUG=True. On 500 errors, replaces the response body
    with a styled error overlay showing the exception type, message, and
    traceback with syntax highlighting.

    Configuration:
        DJANGO_MATT_ERROR_OVERLAY = {
            "ENABLED": True,           # Enable/disable (default: True in DEBUG)
            "SHOW_LOCALS": False,      # Show local variables (default: False)
            "CATCH_4XX": False,        # Also show overlay for 4xx errors
        }
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._config = self._get_config()

    def _get_config(self) -> dict[str, Any]:
        config = getattr(settings, "DJANGO_MATT_ERROR_OVERLAY", {})
        return {
            "enabled": config.get("ENABLED", getattr(settings, "DEBUG", False)),
            "catch_4xx": config.get("CATCH_4XX", False),
        }

    def __call__(self, request):
        if not self._config["enabled"]:
            return self.get_response(request)

        try:
            response = self.get_response(request)
        except Exception:
            import sys

            exc_info = sys.exc_info()
            return self._build_error_response(request, exc_info)

        # Check if we should overlay on this response
        if response.status_code >= 500:
            exc_info = getattr(request, "_matt_exc_info", None)
            if exc_info:
                return self._build_error_response(request, exc_info, response.status_code)

        return response

    def process_exception(self, request, exception):
        """Capture exception info for the overlay."""
        import sys

        request._matt_exc_info = sys.exc_info()

    def _build_error_response(self, request, exc_info, status_code: int = 500):
        """Build an HTTP response with the error overlay."""
        from django.http import HttpResponse

        exc_type, exc_value, exc_tb = exc_info
        type_name = exc_type.__name__ if exc_type else "Unknown Error"
        message = str(exc_value) if exc_value else "An unexpected error occurred"
        tb_html = _format_traceback_html(exc_info) if exc_tb else ""

        overlay = _build_overlay_html(
            exc_type=type_name,
            exc_message=message,
            traceback_html=tb_html,
            method=request.method,
            path=request.get_full_path(),
            status_code=status_code,
        )

        html_body = (
            f"<!DOCTYPE html>\n"
            f'<html><head><meta charset="utf-8">'
            f"<title>{status_code} Error</title></head>\n"
            f'<body style="margin:0;padding:0">{overlay}</body></html>'
        )

        return HttpResponse(html_body, status=status_code, content_type="text/html")
