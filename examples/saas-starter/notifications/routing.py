"""
WebSocket URL routing for real-time features.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # User notifications
    re_path(r"ws/notifications/$", consumers.NotificationConsumer.as_asgi()),

    # Project room for real-time task updates
    re_path(r"ws/projects/(?P<project_id>[0-9a-f-]+)/$", consumers.ProjectConsumer.as_asgi()),

    # Task room for real-time comments
    re_path(r"ws/tasks/(?P<task_id>[0-9a-f-]+)/$", consumers.TaskConsumer.as_asgi()),
]
