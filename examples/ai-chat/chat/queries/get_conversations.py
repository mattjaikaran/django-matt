"""
CQRS query: list all conversations.
"""

from django.db.models import Count

from django_matt.cqrs.queries import Query, QueryHandler

from chat.models import Conversation


class GetConversationsQuery(Query):
    limit: int = 50
    offset: int = 0


class GetConversationsHandler(QueryHandler[GetConversationsQuery, dict]):
    async def execute(self, query: GetConversationsQuery) -> dict:
        qs = Conversation.objects.annotate(message_count=Count("messages"))
        total = await qs.acount()
        conversations = [conv async for conv in qs[query.offset : query.offset + query.limit]]
        return {"items": conversations, "total": total}
