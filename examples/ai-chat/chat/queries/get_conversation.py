"""
CQRS query: get a single conversation with its messages.
"""

from uuid import UUID

from django_matt.cqrs.queries import Query, QueryHandler

from chat.models import Conversation


class GetConversationQuery(Query):
    conversation_id: UUID


class GetConversationHandler(QueryHandler[GetConversationQuery, Conversation]):
    async def execute(self, query: GetConversationQuery) -> Conversation:
        conversation = await Conversation.objects.aget(id=query.conversation_id)
        # Prefetch messages for the detail view
        conversation.messages_list = [
            msg async for msg in conversation.messages.all()
        ]
        return conversation
