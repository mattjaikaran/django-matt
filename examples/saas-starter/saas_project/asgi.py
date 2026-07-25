"""
ASGI config for SaaS Starter project.

Exposes the ASGI callable as a module-level variable named ``application``.
Supports HTTP and WebSocket protocols.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saas_project.settings")

# Initialize Django ASGI application early to ensure apps are loaded
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django_matt.websockets import AuthMiddlewareStack  # noqa: E402

from notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
