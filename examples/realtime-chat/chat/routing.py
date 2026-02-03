"""
WebSocket URL routing for the chat application.

Defines WebSocket URL patterns that are handled by the ASGI application.
"""

from django.urls import path

from .consumers import ChatConsumer, NotificationConsumer

# WebSocket URL patterns
# These are used in config/asgi.py with URLRouter
websocket_urlpatterns = [
    # Main chat WebSocket - handles channels, messages, typing, presence
    path("ws/chat/", ChatConsumer.as_asgi()),
    # User-specific notifications WebSocket
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
