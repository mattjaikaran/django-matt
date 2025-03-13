import importlib
import logging
import os
import sys
import threading
import time
from collections.abc import Callable

from django.apps import apps
from django.conf import settings
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("django_matt.hot_reload")


class FileChangeHandler(FileSystemEventHandler):
    """
    Handler for file system change events.

    This class detects changes to Python files and triggers reloading
    of the affected modules.
    """

    def __init__(self, reload_callback: Callable[[str], None]):
        self.reload_callback = reload_callback
        self.last_reload_time = {}
        self.debounce_time = 0.5  # seconds

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith(".py"):
            # Debounce to prevent multiple reloads for the same file
            current_time = time.time()
            if event.src_path in self.last_reload_time:
                if (
                    current_time - self.last_reload_time[event.src_path]
                    < self.debounce_time
                ):
                    return

            self.last_reload_time[event.src_path] = current_time
            self.reload_callback(event.src_path)

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith(".py"):
            self.reload_callback(event.src_path)


class ModuleReloader:
    """
    Class to handle reloading of Python modules.

    This class provides functionality to reload modules when their source files change,
    allowing for hot reloading of code without restarting the server.
    """

    def __init__(self):
        self.watched_modules = {}
        self.module_dependencies = {}
        self.reload_hooks = []
        self.observer = None
        self.watch_paths = set()
        self.is_running = False

    def add_reload_hook(self, hook: Callable[[], None]):
        """Add a hook to be called after modules are reloaded."""
        self.reload_hooks.append(hook)

    def _get_module_name_from_path(self, file_path: str) -> str | None:
        """Convert a file path to a module name."""
        file_path = os.path.abspath(file_path)

        # Check if the file is in the Python path
        for path in sys.path:
            path = os.path.abspath(path)
            if file_path.startswith(path):
                rel_path = os.path.relpath(file_path, path)
                module_path = rel_path.replace(os.path.sep, ".")

                # Remove .py extension
                if module_path.endswith(".py"):
                    module_path = module_path[:-3]

                return module_path

        return None

    def _find_dependent_modules(self, module_name: str) -> list[str]:
        """Find modules that depend on the given module."""
        dependent_modules = []

        for name, module in sys.modules.items():
            if module is None:
                continue

            # Check if this module imports the changed module
            try:
                if hasattr(module, "__file__") and module.__file__:
                    with open(module.__file__) as f:
                        content = f.read()
                        # Simple check for imports (could be improved)
                        if (
                            f"import {module_name}" in content
                            or f"from {module_name}" in content
                        ):
                            dependent_modules.append(name)
            except (OSError, UnicodeDecodeError):
                continue

        return dependent_modules

    def _reload_module(self, module_name: str):
        """Reload a module and its dependents."""
        try:
            # Check if the module is loaded
            if module_name in sys.modules:
                logger.info(f"Reloading module: {module_name}")

                # Reload the module
                module = sys.modules[module_name]
                importlib.reload(module)

                # Find and reload dependent modules
                dependent_modules = self._find_dependent_modules(module_name)
                for dep_module_name in dependent_modules:
                    if dep_module_name in sys.modules:
                        try:
                            logger.info(
                                f"Reloading dependent module: {dep_module_name}"
                            )
                            importlib.reload(sys.modules[dep_module_name])
                        except Exception as e:
                            logger.error(
                                f"Error reloading dependent module {dep_module_name}: {str(e)}"
                            )

                # Call reload hooks
                for hook in self.reload_hooks:
                    try:
                        hook()
                    except Exception as e:
                        logger.error(f"Error in reload hook: {str(e)}")

                logger.info(f"Successfully reloaded module: {module_name}")
                return True
            else:
                # Try to import the module if it's not loaded
                try:
                    importlib.import_module(module_name)
                    logger.info(f"Imported new module: {module_name}")
                    return True
                except ImportError as e:
                    logger.error(f"Error importing module {module_name}: {str(e)}")
                    return False
        except Exception as e:
            logger.error(f"Error reloading module {module_name}: {str(e)}")
            return False

    def handle_file_change(self, file_path: str):
        """Handle a file change event."""
        module_name = self._get_module_name_from_path(file_path)
        if module_name:
            self._reload_module(module_name)

    def start(self, watch_paths: list[str] | None = None):
        """Start watching for file changes."""
        if self.is_running:
            return

        if watch_paths is None:
            # Default to watching all installed apps
            watch_paths = []
            for app_config in apps.get_app_configs():
                if hasattr(app_config, "path") and app_config.path:
                    watch_paths.append(app_config.path)

        self.watch_paths = set(watch_paths)

        # Create and start the file system observer
        self.observer = Observer()
        handler = FileChangeHandler(self.handle_file_change)

        for path in self.watch_paths:
            if os.path.exists(path):
                self.observer.schedule(handler, path, recursive=True)
                logger.info(f"Watching directory for changes: {path}")

        self.observer.start()
        self.is_running = True
        logger.info("Hot reloading is active")

    def stop(self):
        """Stop watching for file changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            logger.info("Hot reloading stopped")


class HotReloadMiddleware:
    """
    Middleware to inject hot reloading client code into HTML responses.

    This middleware adds a small JavaScript snippet to HTML responses
    that connects to a WebSocket server to receive reload notifications.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.websocket_port = getattr(settings, "HOT_RELOAD_WEBSOCKET_PORT", 8001)

    def __call__(self, request):
        response = self.get_response(request)

        # Only modify HTML responses
        if (
            hasattr(response, "content_type")
            and response.content_type
            and "text/html" in response.content_type
        ):
            # Add the hot reload script to the response
            script = f"""
            <script>
                // Django Matt Hot Reload Client
                (function() {{
                    const socket = new WebSocket('ws://localhost:{self.websocket_port}/hot-reload');
                    
                    socket.onopen = function() {{
                        console.log('Django Matt Hot Reload connected');
                    }};
                    
                    socket.onmessage = function(event) {{
                        const data = JSON.parse(event.data);
                        if (data.type === 'reload') {{
                            console.log('Reloading page due to code changes');
                            window.location.reload();
                        }}
                    }};
                    
                    socket.onclose = function() {{
                        console.log('Django Matt Hot Reload disconnected. Attempting to reconnect...');
                        setTimeout(function() {{
                            window.location.reload();
                        }}, 2000);
                    }};
                }})();
            </script>
            """

            # Insert the script before the closing body tag
            if hasattr(response, "content"):
                content = response.content.decode("utf-8")
                if "</body>" in content:
                    content = content.replace("</body>", f"{script}</body>")
                    response.content = content.encode("utf-8")

        return response


class WebSocketReloadServer:
    """
    WebSocket server to notify clients about code changes.

    This server sends reload notifications to connected clients
    when code changes are detected.
    """

    def __init__(self, port: int = 8001):
        self.port = port
        self.clients = set()
        self.server = None
        self.is_running = False

    def start(self):
        """Start the WebSocket server."""
        try:
            import asyncio

            import websockets

            async def handler(websocket, path):
                # Register client
                self.clients.add(websocket)
                try:
                    await websocket.wait_closed()
                finally:
                    # Unregister client
                    self.clients.remove(websocket)

            async def server_loop():
                self.server = await websockets.serve(handler, "localhost", self.port)
                await self.server.wait_closed()

            # Start the server in a separate thread
            def run_server():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(server_loop())

            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()

            self.is_running = True
            logger.info(f"WebSocket reload server started on port {self.port}")

        except ImportError:
            logger.error("websockets package is required for WebSocket reload server")

    def notify_clients(self):
        """Notify all connected clients to reload."""
        if not self.is_running:
            return

        try:
            import asyncio

            async def send_reload():
                if not self.clients:
                    return

                message = '{"type": "reload"}'
                await asyncio.gather(*[client.send(message) for client in self.clients])

            # Run the coroutine in the event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_reload())

        except Exception as e:
            logger.error(f"Error notifying WebSocket clients: {str(e)}")

    def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            self.is_running = False
            logger.info("WebSocket reload server stopped")


class HotReloader:
    """
    Main hot reloader class for Django Matt framework.

    This class coordinates the module reloader and WebSocket server
    to provide hot reloading functionality.
    """

    def __init__(self, websocket_port: int = 8001):
        self.module_reloader = ModuleReloader()
        self.websocket_server = WebSocketReloadServer(port=websocket_port)

    def start(self, watch_paths: list[str] | None = None):
        """Start the hot reloader."""
        # Add a reload hook to notify WebSocket clients
        self.module_reloader.add_reload_hook(self.websocket_server.notify_clients)

        # Start the WebSocket server
        self.websocket_server.start()

        # Start the module reloader
        self.module_reloader.start(watch_paths)

    def stop(self):
        """Stop the hot reloader."""
        self.module_reloader.stop()
        self.websocket_server.stop()


# Singleton instance
hot_reloader = None


def start_hot_reloading(
    watch_paths: list[str] | None = None, websocket_port: int = 8001
):
    """Start hot reloading for the Django application."""
    global hot_reloader

    if hot_reloader is None:
        hot_reloader = HotReloader(websocket_port=websocket_port)

    hot_reloader.start(watch_paths)
    return hot_reloader


def stop_hot_reloading():
    """Stop hot reloading."""
    global hot_reloader

    if hot_reloader:
        hot_reloader.stop()
        hot_reloader = None
