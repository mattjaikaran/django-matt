"""
Hot module reload for Django — React-style HMR experience.

Watches Python, CSS, JS, and template files. Sends typed change events
over WebSocket. CSS changes hot-swap without page reload. Python/template
changes trigger a smooth full reload with visual feedback.

Usage:
    # settings.py
    MIDDLEWARE = [
        "django_matt.utils.hot_reload.HotReloadMiddleware",
        ...
    ]

    # In AppConfig.ready() or manage.py
    from django_matt.utils.hot_reload import start_hot_reloading
    start_hot_reloading()

Settings:
    HOT_RELOAD_WEBSOCKET_PORT = 8001
    HOT_RELOAD_DEBOUNCE_MS = 100
    HOT_RELOAD_WATCH_EXTENSIONS = [".py", ".css", ".js", ".html", ".txt"]
    HOT_RELOAD_WATCH_PATHS = []  # auto-discovers from installed apps
    HOT_RELOAD_ENABLED = DEBUG  # only in development
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from django.apps import apps
from django.conf import settings

logger = logging.getLogger("django_matt.hot_reload")


# ── Change types ──────────────────────────────────────────────────────


class ChangeType(str, Enum):
    CSS = "css"
    JS = "js"
    TEMPLATE = "template"
    PYTHON = "python"
    STATIC = "static"
    UNKNOWN = "unknown"


_EXTENSION_MAP: dict[str, ChangeType] = {
    ".py": ChangeType.PYTHON,
    ".css": ChangeType.CSS,
    ".scss": ChangeType.CSS,
    ".sass": ChangeType.CSS,
    ".less": ChangeType.CSS,
    ".js": ChangeType.JS,
    ".ts": ChangeType.JS,
    ".jsx": ChangeType.JS,
    ".tsx": ChangeType.JS,
    ".html": ChangeType.TEMPLATE,
    ".txt": ChangeType.TEMPLATE,
    ".jinja": ChangeType.TEMPLATE,
    ".jinja2": ChangeType.TEMPLATE,
    ".svg": ChangeType.STATIC,
    ".png": ChangeType.STATIC,
    ".jpg": ChangeType.STATIC,
    ".gif": ChangeType.STATIC,
    ".ico": ChangeType.STATIC,
    ".woff": ChangeType.STATIC,
    ".woff2": ChangeType.STATIC,
}

_DEFAULT_WATCH_EXTENSIONS = {".py", ".css", ".scss", ".sass", ".less", ".js", ".ts", ".html", ".txt", ".jinja", ".jinja2"}


def _classify_change(file_path: str) -> ChangeType:
    _, ext = os.path.splitext(file_path)
    return _EXTENSION_MAP.get(ext.lower(), ChangeType.UNKNOWN)


# ── File watcher ──────────────────────────────────────────────────────


class FileChangeHandler:
    """Debounced file change handler that classifies change types."""

    def __init__(self, callback: Callable[[str, ChangeType], None]) -> None:
        self._callback = callback
        self._last_event: dict[str, float] = {}
        self._debounce_s = getattr(settings, "HOT_RELOAD_DEBOUNCE_MS", 100) / 1000
        self._extensions = _DEFAULT_WATCH_EXTENSIONS | set(
            getattr(settings, "HOT_RELOAD_WATCH_EXTENSIONS", [])
        )

    def _should_handle(self, event: Any) -> bool:
        if event.is_directory:
            return False
        _, ext = os.path.splitext(event.src_path)
        return ext.lower() in self._extensions

    def _debounce(self, path: str) -> bool:
        now = time.monotonic()
        prev = self._last_event.get(path, 0)
        if now - prev < self._debounce_s:
            return False
        self._last_event[path] = now
        return True

    def dispatch(self, event: Any) -> None:
        if not self._should_handle(event):
            return
        path = event.src_path
        if not self._debounce(path):
            return
        change_type = _classify_change(path)
        self._callback(path, change_type)


# ── Module reloader ──────────────────────────────────────────────────


class ModuleReloader:
    """Reloads Python modules when source files change."""

    def __init__(self) -> None:
        self.reload_hooks: list[Callable[[str, ChangeType], None]] = []
        self._observer: Any | None = None
        self._watch_paths: set[str] = set()
        self.is_running = False

    def add_reload_hook(self, hook: Callable[[str, ChangeType], None]) -> None:
        self.reload_hooks.append(hook)

    def _handle_change(self, file_path: str, change_type: ChangeType) -> None:
        if change_type == ChangeType.PYTHON:
            self._reload_python_module(file_path)

        for hook in self.reload_hooks:
            try:
                hook(file_path, change_type)
            except Exception as e:
                logger.error(f"Reload hook error: {e}")

    def _reload_python_module(self, file_path: str) -> None:
        module_name = self._path_to_module(file_path)
        if not module_name or module_name not in sys.modules:
            return

        try:
            module = sys.modules[module_name]
            importlib.reload(module)
            logger.info(f"Reloaded: {module_name}")

            for dep_name in self._find_dependents(module_name):
                try:
                    importlib.reload(sys.modules[dep_name])
                    logger.debug(f"Reloaded dependent: {dep_name}")
                except Exception as e:
                    logger.warning(f"Failed to reload {dep_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to reload {module_name}: {e}")

    def _path_to_module(self, file_path: str) -> str | None:
        abs_path = os.path.abspath(file_path)
        for path in sys.path:
            base = os.path.abspath(path)
            if abs_path.startswith(base + os.sep):
                rel = os.path.relpath(abs_path, base).replace(os.sep, ".")
                if rel.endswith(".py"):
                    rel = rel[:-3]
                return rel
        return None

    def _find_dependents(self, module_name: str) -> list[str]:
        deps = []
        for name, mod in sys.modules.items():
            if mod is None or not hasattr(mod, "__file__") or not mod.__file__:
                continue
            try:
                source = open(mod.__file__).read()  # noqa: SIM115
                if f"import {module_name}" in source or f"from {module_name}" in source:
                    deps.append(name)
            except (OSError, UnicodeDecodeError):
                continue
        return deps

    def start(self, watch_paths: list[str] | None = None) -> None:
        if self.is_running:
            return

        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        if watch_paths is None:
            watch_paths = []
            for app_config in apps.get_app_configs():
                if hasattr(app_config, "path") and app_config.path:
                    watch_paths.append(app_config.path)

            # Also watch template dirs
            for tmpl in getattr(settings, "TEMPLATES", []):
                for d in tmpl.get("DIRS", []):
                    if os.path.exists(d):
                        watch_paths.append(d)

            # Watch staticfiles dirs
            for d in getattr(settings, "STATICFILES_DIRS", []):
                path = d if isinstance(d, str) else d[1] if isinstance(d, (list, tuple)) else str(d)
                if os.path.exists(path):
                    watch_paths.append(path)

        self._watch_paths = set(watch_paths)
        handler = FileChangeHandler(self._handle_change)

        # Wrap our handler to match watchdog's interface
        class _WatchdogBridge(FileSystemEventHandler):
            def on_modified(self, event: Any) -> None:
                handler.dispatch(event)

            def on_created(self, event: Any) -> None:
                handler.dispatch(event)

        self._observer = Observer()
        bridge = _WatchdogBridge()
        for path in self._watch_paths:
            if os.path.exists(path):
                self._observer.schedule(bridge, path, recursive=True)
                logger.debug(f"Watching: {path}")

        self._observer.start()
        self.is_running = True
        logger.info(f"Hot reload active — watching {len(self._watch_paths)} paths")

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self.is_running = False
            logger.info("Hot reload stopped")


# ── WebSocket server ─────────────────────────────────────────────────


class WebSocketReloadServer:
    """WebSocket server that sends typed change events to browser clients."""

    def __init__(self, port: int = 8001) -> None:
        self.port = port
        self.clients: set[Any] = set()
        self._server: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.is_running = False

    def start(self) -> None:
        try:
            import websockets  # noqa: F401
        except ImportError:
            logger.error("Install websockets for hot reload: uv add websockets")
            return

        def run_server() -> None:
            import websockets

            async def handler(websocket: Any, path: str = "/") -> None:
                self.clients.add(websocket)
                try:
                    async for msg in websocket:
                        # Client can send pings, we just ignore
                        pass
                finally:
                    self.clients.discard(websocket)

            async def serve() -> None:
                self._loop = asyncio.get_running_loop()
                self._server = await websockets.serve(handler, "localhost", self.port)
                await self._server.wait_closed()

            asyncio.run(serve())

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

        # Wait briefly for server to start
        time.sleep(0.1)
        self.is_running = True
        logger.info(f"HMR WebSocket on ws://localhost:{self.port}")

    def notify(self, file_path: str, change_type: ChangeType) -> None:
        if not self.is_running or not self.clients or not self._loop:
            return

        import orjson

        rel_path = os.path.relpath(file_path)
        message = orjson.dumps({
            "type": change_type.value,
            "file": rel_path,
            "timestamp": time.time(),
        }).decode()

        async def _send() -> None:
            dead: set[Any] = set()
            for client in self.clients.copy():
                try:
                    await client.send(message)
                except Exception:
                    dead.add(client)
            self.clients -= dead

        # Schedule on the server's event loop (thread-safe)
        asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def stop(self) -> None:
        if self._server:
            self._server.close()
            self.is_running = False
            logger.info("HMR WebSocket stopped")


# ── Middleware ────────────────────────────────────────────────────────


# Minified JS client — handles CSS hot-swap, overlay, exponential backoff
_HMR_CLIENT_JS = """<script data-hmr-client>
(function(){
  var port=__PORT__,
      ws,retries=0,maxRetry=16000,overlay=null,connected=false;

  function createOverlay(){
    if(overlay)return overlay;
    var el=document.createElement('div');
    el.id='__matt_hmr_overlay';
    el.innerHTML='<div style="position:fixed;bottom:20px;right:20px;z-index:2147483647;'
      +'font-family:-apple-system,system-ui,sans-serif;font-size:13px;'
      +'padding:10px 16px;border-radius:8px;color:#fff;'
      +'backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);'
      +'transition:all .3s ease;pointer-events:none;'
      +'box-shadow:0 4px 12px rgba(0,0,0,.15)">'
      +'<span id="__matt_hmr_dot" style="display:inline-block;width:8px;height:8px;'
      +'border-radius:50%;margin-right:8px;vertical-align:middle"></span>'
      +'<span id="__matt_hmr_text"></span></div>';
    document.body.appendChild(el);
    overlay=el.firstChild;
    return overlay;
  }

  function showStatus(text,color,bg,persist){
    var o=createOverlay();
    o.style.background=bg;
    document.getElementById('__matt_hmr_dot').style.background=color;
    document.getElementById('__matt_hmr_text').textContent=text;
    o.style.opacity='1';
    if(!persist) setTimeout(function(){o.style.opacity='0'},2000);
  }

  function hotSwapCSS(file){
    var links=document.querySelectorAll('link[rel="stylesheet"]');
    var swapped=false;
    for(var i=0;i<links.length;i++){
      var href=links[i].getAttribute('href');
      if(href && (href.indexOf(file)!==-1 || file.indexOf(href.split('?')[0].split('/').pop())!==-1)){
        var url=href.split('?')[0]+'?hmr='+Date.now();
        var clone=links[i].cloneNode();
        clone.href=url;
        clone.onload=function(){
          if(links[i]&&links[i].parentNode) links[i].parentNode.removeChild(links[i]);
        };
        links[i].parentNode.insertBefore(clone,links[i].nextSibling);
        swapped=true;
        break;
      }
    }
    if(!swapped){
      // Force reload all stylesheets
      var all=document.querySelectorAll('link[rel="stylesheet"]');
      for(var j=0;j<all.length;j++){
        var h=all[j].getAttribute('href');
        if(h) all[j].href=h.split('?')[0]+'?hmr='+Date.now();
      }
    }
    showStatus('CSS updated','#22c55e','rgba(34,197,94,.15)');
  }

  function hotSwapStatic(){
    // Reload images with cache bust
    var imgs=document.querySelectorAll('img[src]');
    for(var i=0;i<imgs.length;i++){
      var s=imgs[i].getAttribute('src');
      if(s) imgs[i].src=s.split('?')[0]+'?hmr='+Date.now();
    }
    showStatus('Assets updated','#22c55e','rgba(34,197,94,.15)');
  }

  function fullReload(reason){
    showStatus(reason+' — reloading...','#f59e0b','rgba(245,158,11,.18)');
    setTimeout(function(){window.location.reload()},200);
  }

  function connect(){
    try{ws=new WebSocket('ws://localhost:'+port+'/hmr')}
    catch(e){scheduleReconnect();return}

    ws.onopen=function(){
      retries=0;
      connected=true;
      showStatus('HMR connected','#22c55e','rgba(34,197,94,.12)');
    };

    ws.onmessage=function(e){
      try{var d=JSON.parse(e.data)}catch(_){return}
      switch(d.type){
        case 'css':hotSwapCSS(d.file);break;
        case 'static':hotSwapStatic();break;
        case 'js':fullReload('JS changed');break;
        case 'template':fullReload('Template changed');break;
        case 'python':fullReload('Server updated');break;
        default:fullReload('File changed');
      }
    };

    ws.onclose=function(){
      if(connected){
        connected=false;
        showStatus('Reconnecting...','#f59e0b','rgba(245,158,11,.18)',true);
      }
      scheduleReconnect();
    };

    ws.onerror=function(){ws.close()};
  }

  function scheduleReconnect(){
    var delay=Math.min(500*Math.pow(1.5,retries),maxRetry);
    retries++;
    setTimeout(function(){
      // Test if server is back before connecting WS
      fetch(window.location.href,{method:'HEAD',cache:'no-store'})
        .then(function(r){
          if(r.ok){connect()}
          else{scheduleReconnect()}
        })
        .catch(function(){scheduleReconnect()});
    },delay);
  }

  // Auto-start
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',connect);
  }else{connect()}
})();
</script>"""


class HotReloadMiddleware:
    """Injects HMR client into HTML responses for smooth live reloading."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self._port = getattr(settings, "HOT_RELOAD_WEBSOCKET_PORT", 8001)
        self._enabled = getattr(settings, "HOT_RELOAD_ENABLED", getattr(settings, "DEBUG", False))
        self._script = _HMR_CLIENT_JS.replace("__PORT__", str(self._port))

    def __call__(self, request: Any) -> Any:
        response = self.get_response(request)

        if not self._enabled:
            return response

        # Only inject into HTML responses with a body tag
        content_type = getattr(response, "content_type", "") or ""
        if "text/html" not in content_type:
            return response

        if not hasattr(response, "content"):
            return response

        # Don't double-inject
        content = response.content.decode("utf-8")
        if "data-hmr-client" in content:
            return response

        if "</body>" in content:
            content = content.replace("</body>", f"{self._script}</body>")
            response.content = content.encode("utf-8")
            # Update Content-Length if set
            if response.get("Content-Length"):
                response["Content-Length"] = len(response.content)

        return response


# ── Orchestrator ─────────────────────────────────────────────────────


class HotReloader:
    """Coordinates file watching, module reloading, and WebSocket notifications."""

    def __init__(self, websocket_port: int = 8001) -> None:
        self.module_reloader = ModuleReloader()
        self.websocket_server = WebSocketReloadServer(port=websocket_port)

    def start(self, watch_paths: list[str] | None = None) -> None:
        self.module_reloader.add_reload_hook(self.websocket_server.notify)
        self.websocket_server.start()
        self.module_reloader.start(watch_paths)
        logger.info("Django Matt HMR ready")

    def stop(self) -> None:
        self.module_reloader.stop()
        self.websocket_server.stop()


# ── Public API ───────────────────────────────────────────────────────


_hot_reloader: HotReloader | None = None


def start_hot_reloading(
    watch_paths: list[str] | None = None,
    websocket_port: int = 8001,
) -> HotReloader:
    """Start hot reloading for the Django application."""
    global _hot_reloader

    if _hot_reloader is None:
        port = getattr(settings, "HOT_RELOAD_WEBSOCKET_PORT", websocket_port)
        _hot_reloader = HotReloader(websocket_port=port)

    _hot_reloader.start(watch_paths)
    return _hot_reloader


def stop_hot_reloading() -> None:
    """Stop hot reloading."""
    global _hot_reloader

    if _hot_reloader:
        _hot_reloader.stop()
        _hot_reloader = None
