"""ASGI config for {{ project_name }} with WebSocket support."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi = get_asgi_application()


async def application(scope, receive, send):
    if scope["type"] == "http":
        await django_asgi(scope, receive, send)
    elif scope["type"] == "websocket":
        # WebSocket routing — extend with your consumers

        await send({"type": "websocket.close", "code": 4004})
