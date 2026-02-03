"""
WSGI config for realtime-chat example.

This is a fallback for HTTP-only deployments.
For WebSocket support, use the ASGI configuration instead.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
