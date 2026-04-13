"""URL routes for {{ project_name }} API."""

from django.urls import path

from . import controllers

urlpatterns = [
    path("health/", controllers.health),
    path("conversations/", controllers.list_conversations),
    path("conversations/create/", controllers.create_conversation),
    path("conversations/<int:conversation_id>/messages/", controllers.send_message),
    path("documents/", controllers.list_documents),
    path("documents/upload/", controllers.upload_document),
]
