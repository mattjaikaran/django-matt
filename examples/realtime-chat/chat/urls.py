"""
URL patterns for the chat frontend demo.
"""

from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.index, name="index"),
    path("workspace/<uuid:workspace_id>/", views.workspace, name="workspace"),
    path(
        "workspace/<uuid:workspace_id>/channel/<uuid:channel_id>/",
        views.channel,
        name="channel",
    ),
]
