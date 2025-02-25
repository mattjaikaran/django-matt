import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("django_matt.hot_reload")


class HotReloadEventHandler(FileSystemEventHandler):
    """
    File system event handler for hot reloading.

    This handler watches for file changes and triggers a reload when needed.
    """

    def __init__(
        self,
        reload_callback: Callable,
        watched_extensions: set[str] = None,
        ignored_dirs: set[str] = None,
        ignored_files: set[str] = None,
        debounce_seconds: float = 0.5,
    ):
        self.reload_callback = reload_callback
        self.watched_extensions = watched_extensions or {".py", ".html", ".js", ".css"}
        self.ignored_dirs = ignored_dirs or {
            "__pycache__",
            ".git",
            ".vscode",
            ".idea",
            "node_modules",
            "venv",
            "env",
            ".env",
        }
        self.ignored_files = ignored_files or {"*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll"}
        self.debounce_seconds = debounce_seconds
        self.last_event_time = 0
        self.pending_reload = False
        self.reload_timer = None

    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event."""
        # Skip directory events
        if event.is_directory:
            return

        # Skip events for ignored directories
        for ignored_dir in self.ignored_dirs:
            if ignored_dir in event.src_path:
                return

        # Skip events for ignored files
        for ignored_file in self.ignored_files:
            if ignored_file.replace("*", "") in event.src_path:
                return

        # Skip events for non-watched extensions
        _, ext = os.path.splitext(event.src_path)
        if ext not in self.watched_extensions:
            return

        # Debounce events
        current_time = time.time()
        if current_time - self.last_event_time < self.debounce_seconds:
            # If we already have a pending reload, just update the time
            self.last_event_time = current_time
            return

        self.last_event_time = current_time

        # Cancel any pending reload
        if self.reload_timer:
            self.reload_timer.cancel()

        # Schedule a reload after the debounce period
        self.reload_timer = threading.Timer(self.debounce_seconds, self._trigger_reload, args=[event])
        self.reload_timer.daemon = True
        self.reload_timer.start()

    def _trigger_reload(self, event: FileSystemEvent):
        """Trigger a reload after the debounce period."""
        logger.info(f"File changed: {event.src_path}")
        self.reload_callback(event.src_path)


class WebSocketServer:
    """
    WebSocket server for communicating with the browser.

    This server sends messages to the browser when files change,
    allowing for live reloading of the page.
    """

    def __init__(self, host: str = "localhost", port: int = 35729):
        self.host = host
        self.port = port
        self.clients = set()
        self.server_socket = None
        self.running = False
        self.thread = None

    def start(self):
        """Start the WebSocket server."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()

        logger.info(f"WebSocket server started on {self.host}:{self.port}")

    def stop(self):
        """Stop the WebSocket server."""
        self.running = False

        if self.server_socket:
            self.server_socket.close()

        if self.thread:
            self.thread.join(timeout=1)

        logger.info("WebSocket server stopped")

    def _run_server(self):
        """Run the WebSocket server."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    client_thread = threading.Thread(target=self._handle_client, args=(client_socket, addr))
                    client_thread.daemon = True
                    client_thread.start()
                except TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def _handle_client(self, client_socket, addr):
        """Handle a client connection."""
        try:
            self.clients.add(client_socket)
            logger.info(f"Client connected: {addr}")

            # Keep the connection open
            while self.running:
                try:
                    # Just check if the client is still connected
                    data = client_socket.recv(1024)
                    if not data:
                        break
                except:
                    break
        finally:
            client_socket.close()
            self.clients.remove(client_socket)
            logger.info(f"Client disconnected: {addr}")

    def send_reload_message(self, file_path: str):
        """Send a reload message to all connected clients."""
        message = {"command": "reload", "path": file_path, "time": time.time()}

        message_json = json.dumps(message)
        message_bytes = f"data: {message_json}\n\n".encode()

        disconnected_clients = set()

        for client in self.clients:
            try:
                client.sendall(message_bytes)
            except:
                disconnected_clients.add(client)

        # Remove disconnected clients
        for client in disconnected_clients:
            try:
                client.close()
            except:
                pass
            self.clients.remove(client)


class HotReloader:
    """
    Hot reloader for Django Matt.

    This class watches for file changes and reloads the server or notifies
    the browser to reload when files change.
    """

    def __init__(
        self,
        project_dir: str,
        watched_extensions: set[str] = None,
        ignored_dirs: set[str] = None,
        ignored_files: set[str] = None,
        reload_delay: float = 0.5,
        use_websocket: bool = True,
        websocket_host: str = "localhost",
        websocket_port: int = 35729,
    ):
        self.project_dir = Path(project_dir)
        self.watched_extensions = watched_extensions or {".py", ".html", ".js", ".css"}
        self.ignored_dirs = ignored_dirs or {
            "__pycache__",
            ".git",
            ".vscode",
            ".idea",
            "node_modules",
            "venv",
            "env",
            ".env",
        }
        self.ignored_files = ignored_files or {"*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll"}
        self.reload_delay = reload_delay
        self.use_websocket = use_websocket
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port

        self.observer = None
        self.websocket_server = None
        self.server_process = None
        self.running = False

    def start(self, server_command: list[str] = None):
        """
        Start the hot reloader.

        Args:
            server_command: Command to start the server (e.g., ["python", "manage.py", "runserver"])
        """
        if self.running:
            return

        self.running = True

        # Start the WebSocket server if enabled
        if self.use_websocket:
            self.websocket_server = WebSocketServer(host=self.websocket_host, port=self.websocket_port)
            self.websocket_server.start()

        # Start the file system observer
        self.observer = Observer()
        event_handler = HotReloadEventHandler(
            reload_callback=self._handle_reload,
            watched_extensions=self.watched_extensions,
            ignored_dirs=self.ignored_dirs,
            ignored_files=self.ignored_files,
            debounce_seconds=self.reload_delay,
        )

        self.observer.schedule(event_handler, self.project_dir, recursive=True)
        self.observer.start()

        # Start the server if a command is provided
        if server_command:
            self._start_server(server_command)

        logger.info(f"Hot reloader started for {self.project_dir}")

        # Register signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def stop(self):
        """Stop the hot reloader."""
        if not self.running:
            return

        self.running = False

        # Stop the observer
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=1)

        # Stop the WebSocket server
        if self.websocket_server:
            self.websocket_server.stop()

        # Stop the server process
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()

        logger.info("Hot reloader stopped")

    def _start_server(self, command: list[str]):
        """Start the server process."""
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()

        logger.info(f"Starting server: {' '.join(command)}")

        self.server_process = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr, cwd=self.project_dir)

    def _handle_reload(self, file_path: str):
        """Handle a file change event."""
        _, ext = os.path.splitext(file_path)

        # For Python files, restart the server
        if ext == ".py" and self.server_process:
            logger.info(f"Python file changed: {file_path}")
            logger.info("Restarting server...")

            # Restart the server
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()

            # Start the server with the same command
            self._start_server(self.server_process.args)

        # For other files, just notify the browser
        elif self.use_websocket and self.websocket_server:
            logger.info(f"Static file changed: {file_path}")
            logger.info("Notifying browser to reload...")

            # Send a reload message to the browser
            self.websocket_server.send_reload_message(file_path)

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)


# Helper function to inject the live reload script into HTML responses
def inject_live_reload_script(response, host="localhost", port=35729):
    """
    Inject the live reload script into HTML responses.

    This function should be used as middleware to add the live reload script
    to HTML responses during development.
    """
    if not response.get("Content-Type", "").startswith("text/html"):
        return response

    content = response.content.decode("utf-8")

    # Create the live reload script
    script = f"""
    <script>
    (function() {{
        const socket = new WebSocket('ws://{host}:{port}');
        
        socket.onopen = function() {{
            console.log('Live reload connected');
        }};
        
        socket.onmessage = function(event) {{
            const data = JSON.parse(event.data);
            
            if (data.command === 'reload') {{
                console.log('Reloading page...');
                window.location.reload();
            }}
        }};
        
        socket.onclose = function() {{
            console.log('Live reload disconnected');
            
            // Try to reconnect after a delay
            setTimeout(function() {{
                window.location.reload();
            }}, 2000);
        }};
    }})();
    </script>
    """

    # Inject the script before the closing </body> tag
    if "</body>" in content:
        content = content.replace("</body>", f"{script}</body>")
    else:
        content += script

    response.content = content.encode("utf-8")
    return response


class LiveReloadMiddleware:
    """
    Middleware for injecting the live reload script into HTML responses.

    This middleware should be used during development to enable live reloading.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.host = os.environ.get("LIVE_RELOAD_HOST", "localhost")
        self.port = int(os.environ.get("LIVE_RELOAD_PORT", "35729"))

    def __call__(self, request):
        response = self.get_response(request)

        # Only inject the script in debug mode
        if not os.environ.get("DJANGO_DEBUG", "False").lower() == "true":
            return response

        # Only inject the script in HTML responses
        if not response.get("Content-Type", "").startswith("text/html"):
            return response

        return inject_live_reload_script(response, self.host, self.port)


# Command to run the hot reloader
def run_hot_reload(project_dir=None, server_command=None):
    """
    Run the hot reloader.

    This function can be used as a management command to start the hot reloader.

    Args:
        project_dir: The project directory to watch (defaults to current directory)
        server_command: The command to start the server (defaults to "python manage.py runserver")
    """
    if project_dir is None:
        project_dir = os.getcwd()

    if server_command is None:
        server_command = ["python", "manage.py", "runserver"]

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler()]
    )

    # Start the hot reloader
    reloader = HotReloader(project_dir=project_dir)

    try:
        reloader.start(server_command=server_command)

        # Keep the main thread alive
        while reloader.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        reloader.stop()


if __name__ == "__main__":
    # If run directly, start the hot reloader
    run_hot_reload()
