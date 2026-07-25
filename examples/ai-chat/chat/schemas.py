"""
Pydantic schemas for the chat API.
"""


from django_matt.core.schema import ModelSchema

from chat.models import Conversation, Message


class MessageSchema(ModelSchema):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "model_used", "tokens_used", "created_at"]


class ConversationSchema(ModelSchema):
    message_count: int = 0

    class Meta:
        model = Conversation
        fields = ["id", "title", "system_prompt", "model", "created_at", "updated_at"]


class ConversationDetailSchema(ConversationSchema):
    messages: list[MessageSchema] = []


class CreateConversationInput(ModelSchema):
    class Meta:
        model = Conversation
        fields = ["title", "system_prompt", "model"]
        fields_optional = ["title", "system_prompt", "model"]


class SendMessageInput(ModelSchema):
    class Meta:
        model = Message
        fields = ["content"]


class ChatStreamEvent(ModelSchema):
    """Schema for SSE stream events."""

    class Meta:
        model = Message
        fields = ["id", "role", "content"]

    event: str = "chunk"
    delta: str = ""
    done: bool = False
