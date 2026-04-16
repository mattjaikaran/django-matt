"""
API routes — wire up the chat controller.
"""

from django_matt.api import MattAPI

from api.controllers import ChatController

api = MattAPI(
    title="AI Chat API",
    version="1.0.0",
    description="AI-powered chat with SSE streaming and CQRS",
)

api.register_controller(ChatController)
