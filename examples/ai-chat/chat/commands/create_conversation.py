"""
CQRS command: create a new conversation.
"""

from django_matt.cqrs.commands import Command, CommandHandler

from chat.models import Conversation


class CreateConversationCommand(Command):
    title: str = ""
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-4o-mini"


class CreateConversationHandler(CommandHandler[CreateConversationCommand, Conversation]):
    async def execute(self, command: CreateConversationCommand) -> Conversation:
        return await Conversation.objects.acreate(
            title=command.title,
            system_prompt=command.system_prompt,
            model=command.model,
        )
