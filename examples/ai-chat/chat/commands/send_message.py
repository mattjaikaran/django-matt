"""
CQRS command: send a user message and generate AI response.

The handler saves the user message, calls the LLM, and saves the assistant
response. For streaming, see the SSE endpoint in the controller.
"""

from uuid import UUID

from django_matt.cqrs.commands import Command, CommandHandler
from django_matt.events.bus import EventBus

from chat.models import Conversation, Message


class SendMessageCommand(Command):
    conversation_id: UUID
    content: str


class SendMessageHandler(CommandHandler[SendMessageCommand, Message]):
    def __init__(self) -> None:
        self.event_bus = EventBus()

    async def execute(self, command: SendMessageCommand) -> Message:
        conversation = await Conversation.objects.aget(id=command.conversation_id)

        # Save user message
        user_msg = await Message.objects.acreate(
            conversation=conversation,
            role=Message.Role.USER,
            content=command.content,
        )

        # Emit event for analytics / side effects
        await self.event_bus.emit(
            "chat.message.sent",
            conversation_id=str(conversation.id),
            message_id=str(user_msg.id),
            role="user",
        )

        return user_msg
