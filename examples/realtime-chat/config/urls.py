"""
URL configuration for realtime-chat example.

Includes both REST API and HTML template routes.
"""

from django.contrib import admin
from django.urls import include, path

from django_matt import MattAPI

from chat.controllers import (
    AuthController,
    ChannelController,
    DirectMessageController,
    FileController,
    MessageController,
    SearchController,
    WorkspaceController,
)

# Create the API instance
api = MattAPI(
    title="Real-Time Chat API",
    version="1.0.0",
    description="Slack-like chat application API with WebSocket support",
)

# Register controllers
api.register_controller(AuthController, prefix="/auth", tags=["Authentication"])
api.register_controller(WorkspaceController, prefix="/workspaces", tags=["Workspaces"])
api.register_controller(ChannelController, prefix="/channels", tags=["Channels"])
api.register_controller(MessageController, prefix="/messages", tags=["Messages"])
api.register_controller(
    DirectMessageController, prefix="/dm", tags=["Direct Messages"]
)
api.register_controller(FileController, prefix="/files", tags=["Files"])
api.register_controller(SearchController, prefix="/search", tags=["Search"])

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # API endpoints
    path("api/", api.urls),
    # Chat frontend (demo)
    path("chat/", include("chat.urls")),
]
