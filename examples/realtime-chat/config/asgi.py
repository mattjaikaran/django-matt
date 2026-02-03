"""
ASGI config for realtime-chat example.

Configures both HTTP and WebSocket protocols using Django Channels.
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from django_matt.websockets import AuthMiddlewareStack

from chat.routing import websocket_urlpatterns

# Get the standard Django ASGI application for HTTP requests
django_asgi_app = get_asgi_application()

# Create the main ASGI application
application = ProtocolTypeRouter(
    {
        # HTTP requests go to Django's ASGI handler
        "http": django_asgi_app,
        # WebSocket connections go through auth middleware then to URL router
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
