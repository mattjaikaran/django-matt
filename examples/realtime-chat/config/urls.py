"""
URL configuration for realtime-chat example.

Includes both REST API and HTML template routes.
"""

from django.contrib import admin
from django.urls import include, path

from chat.controllers import (
    AuthController,
    ChannelController,
    DirectMessageController,
    FileController,
    MessageController,
    SearchController,
    WorkspaceController,
)

from django_matt import MattAPI

# Create the API instance
api = MattAPI(
    title="Real-Time Chat API",
    version="1.0.0",
    description="Slack-like chat application API with WebSocket support",
)

# Register controllers
api.register_controller(AuthController)
api.register_controller(WorkspaceController)
api.register_controller(ChannelController)
api.register_controller(MessageController)
api.register_controller(DirectMessageController)
api.register_controller(FileController)
api.register_controller(SearchController)

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # API endpoints
    path("api/", api.urls),
    # Chat frontend (demo)
    path("chat/", include("chat.urls")),
]
