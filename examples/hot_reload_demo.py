"""
Example demonstrating Django Matt's hot reloading feature.

This example shows how to use the hot reloading feature of Django Matt
to automatically reload code changes without restarting the server.

To run this example:
1. Install Django and Django Matt
2. Install the websockets package: pip install websockets
3. Run this script with Python
4. Make changes to the example_module.py file to see hot reloading in action

"""

import os
import sys

import django
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.urls import path

# Add the parent directory to the path so we can import django_matt
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Create an example module that we'll modify to demonstrate hot reloading
example_module_path = os.path.join(os.path.dirname(__file__), "example_module.py")
if not os.path.exists(example_module_path):
    with open(example_module_path, "w") as f:
        f.write(
            """
def get_message():
    return "This is the original message. Edit this file to see hot reloading in action!"
"""
        )

# Configure Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="django-matt-example",
        ROOT_URLCONF=__name__,
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
            "django_matt.utils.hot_reload.HotReloadMiddleware",
        ],
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
            }
        ],
        HOT_RELOAD_WEBSOCKET_PORT=8001,
    )
    django.setup()

# Import Django Matt components
from django_matt import APIRouter, start_hot_reloading

# Start hot reloading
watch_paths = [os.path.dirname(__file__)]
hot_reloader = start_hot_reloading(watch_paths=watch_paths)

# Import our example module (that we'll modify to demonstrate hot reloading)
sys.path.insert(0, os.path.dirname(__file__))
import example_module

# Create a router
router = APIRouter()


# Example endpoint that returns data from the example module
@router.get("api/message/")
async def get_message(request):
    """Get a message from the example module."""
    # Reload the module to get the latest changes
    import importlib

    importlib.reload(example_module)

    # Get the message from the module
    message = example_module.get_message()

    return {"message": message, "timestamp": import_time}


# Create URL patterns
urlpatterns = router.get_urls()


# Add a simple HTML page to demonstrate hot reloading
def index_view(request):
    """Simple HTML page to demonstrate hot reloading."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Django Matt Hot Reload Demo</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .card { background: #f5f5f5; padding: 20px; margin-bottom: 20px; border-radius: 5px; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 15px; cursor: pointer; }
            pre { background: #f9f9f9; padding: 10px; overflow: auto; }
            #message { margin-top: 20px; font-size: 18px; }
            .instructions { background: #fffde7; padding: 15px; border-left: 4px solid #ffd600; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>Django Matt Hot Reload Demo</h1>
        
        <div class="instructions">
            <h3>Instructions:</h3>
            <ol>
                <li>This page will automatically reload when you make changes to the code.</li>
                <li>Open the file <code>example_module.py</code> in your editor.</li>
                <li>Modify the <code>get_message()</code> function to return a different message.</li>
                <li>Save the file and watch this page automatically reload.</li>
                <li>Click the "Get Message" button to see the updated message.</li>
            </ol>
        </div>
        
        <div class="card">
            <h2>Message from Example Module:</h2>
            <button onclick="getMessage()">Get Message</button>
            <div id="message"></div>
        </div>
        
        <script>
            async function getMessage() {
                try {
                    const response = await fetch('/api/message/');
                    const data = await response.json();
                    document.getElementById('message').textContent = data.message;
                } catch (error) {
                    document.getElementById('message').textContent = 'Error: ' + error.toString();
                }
            }
            
            // Get the message when the page loads
            getMessage();
        </script>
    </body>
    </html>
    """
    return HttpResponse(html)


urlpatterns.append(path("", index_view))

# Track when the module was imported
import time

import_time = time.time()

# Run the application
if __name__ == "__main__":
    print("\n=== Django Matt Hot Reload Demo ===")
    print("Open your browser at http://localhost:8000")
    print("Edit the file 'example_module.py' to see hot reloading in action!")
    print("===================================\n")

    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])
else:
    # For WSGI servers
    application = get_wsgi_application()
