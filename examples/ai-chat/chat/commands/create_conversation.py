"""
CQRS command: create a new conversation.
"""

from dataclasses import dataclass, field

from django_matt.cqrs.commands import Command, CommandHandler

from chat.models import Conversation


@dataclass
class CreateConversationCommand(Command):
    title: str = ""
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-4o-mini"


class CreateConversationHandler(CommandHandler[CreateConversationCommand]):
    async def handle(self, command: CreateConversationCommand) -> Conversation:
        return await Conversation.objects.acreate(
            title=command.title,
            system_prompt=command.system_prompt,
            model=command.model,
        )
