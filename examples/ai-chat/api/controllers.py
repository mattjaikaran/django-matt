"""
Chat controller — REST endpoints + SSE streaming for AI responses.

Demonstrates:
- django_matt controllers with async endpoints
- CQRS command/query bus pattern
- SSE streaming for real-time AI token delivery
- Event bus for side effects (auto-titling, analytics)
"""

# Defer annotation evaluation — `list` is a method name on this controller and
# would shadow the builtin in eager-evaluated annotations like ``list[Message]``.
from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import orjson
from django.conf import settings
from django.http import HttpRequest

from django_matt.core.controller import APIController
from django_matt.cqrs.commands import CommandBus
from django_matt.cqrs.queries import QueryBus
from django_matt.events.bus import EventBus
from django_matt.streaming.sse import SSEEvent, sse_response

from chat.commands import (
    CreateConversationCommand,
    CreateConversationHandler,
    SendMessageCommand,
    SendMessageHandler,
)
from chat.models import Conversation, Message
from chat.queries import (
    GetConversationQuery,
    GetConversationHandler,
    GetConversationsQuery,
    GetConversationsHandler,
)
from chat.schemas import (
    ConversationDetailSchema,
    ConversationSchema,
    CreateConversationInput,
    MessageSchema,
    SendMessageInput,
)


class ChatController(APIController):
    """AI Chat API with CQRS and SSE streaming."""

    prefix = "/conversations"
    tags = ["Chat"]

    def __init__(self) -> None:
        super().__init__()
        # Wire up CQRS handlers
        self.command_bus = CommandBus()
        self.command_bus.register(CreateConversationCommand, CreateConversationHandler())
        self.command_bus.register(SendMessageCommand, SendMessageHandler())

        self.query_bus = QueryBus()
        self.query_bus.register(GetConversationsQuery, GetConversationsHandler())
        self.query_bus.register(GetConversationQuery, GetConversationHandler())

        self.event_bus = EventBus()

    async def list(self, request: HttpRequest) -> dict:
        """GET / — list conversations."""
        result = await self.query_bus.execute(GetConversationsQuery())
        items = [ConversationSchema.from_orm_fast(conv) for conv in result["items"]]
        return {"items": [item.model_dump() for item in items], "total": result["total"]}

    async def create(self, request: HttpRequest, body: CreateConversationInput) -> dict:
        """POST / — create a new conversation."""
        conversation = await self.command_bus.execute(
            CreateConversationCommand(**body.model_dump(exclude_unset=True))
        )
        return ConversationSchema.from_orm_fast(conversation).model_dump()

    async def read(self, request: HttpRequest, conversation_id: UUID) -> dict:
        """GET /{conversation_id} — get conversation with messages."""
        conversation = await self.query_bus.execute(
            GetConversationQuery(conversation_id=conversation_id)
        )
        schema = ConversationDetailSchema.from_orm_fast(conversation)
        schema.messages = [MessageSchema.from_orm_fast(msg) for msg in conversation.messages_list]
        return schema.model_dump()

    async def send_message(
        self, request: HttpRequest, conversation_id: UUID, body: SendMessageInput
    ) -> dict:
        """POST /{conversation_id}/messages — send message (non-streaming)."""
        # Save user message via command bus
        user_msg = await self.command_bus.execute(
            SendMessageCommand(conversation_id=conversation_id, content=body.content)
        )

        # Generate AI response
        conversation = await Conversation.objects.aget(id=conversation_id)
        messages = [msg async for msg in conversation.messages.all()]
        ai_content = await self._call_llm(conversation, messages)

        # Save assistant message
        assistant_msg = await Message.objects.acreate(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=ai_content,
            model_used=conversation.model,
        )

        await self.event_bus.emit(
            "chat.stream.complete",
            conversation_id=str(conversation_id),
        )

        return MessageSchema.from_orm_fast(assistant_msg).model_dump()

    async def stream_message(
        self, request: HttpRequest, conversation_id: UUID, body: SendMessageInput
    ):
        """POST /{conversation_id}/stream — send message with SSE streaming response.

        This is the main showcase endpoint: user sends a message, and the AI
        response is streamed back token-by-token via Server-Sent Events.
        """
        # Save user message
        await self.command_bus.execute(
            SendMessageCommand(conversation_id=conversation_id, content=body.content)
        )

        conversation = await Conversation.objects.aget(id=conversation_id)
        messages = [msg async for msg in conversation.messages.all()]

        async def generate() -> AsyncIterator[SSEEvent]:
            full_content = []

            async for token in self._stream_llm(conversation, messages):
                full_content.append(token)
                yield SSEEvent(
                    event="chunk",
                    data={"delta": token},
                )

            # Save complete assistant message
            content = "".join(full_content)
            assistant_msg = await Message.objects.acreate(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=content,
                model_used=conversation.model,
            )

            yield SSEEvent(
                event="done",
                data={
                    "message_id": str(assistant_msg.id),
                    "content": content,
                },
            )

            await self.event_bus.emit(
                "chat.stream.complete",
                conversation_id=str(conversation_id),
            )

        return sse_response(generate())

    # ----- LLM helpers -----

    async def _call_llm(self, conversation: Conversation, messages: list[Message]) -> str:
        """Non-streaming LLM call. Returns full response content."""
        api_messages = self._build_api_messages(conversation, messages)
        config = getattr(settings, "MATT_AI", {})

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {config.get('OPENAI_API_KEY', '')}"},
                json={
                    "model": conversation.model,
                    "messages": api_messages,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = orjson.loads(response.content)
            return data["choices"][0]["message"]["content"]

    async def _stream_llm(
        self, conversation: Conversation, messages: list[Message]
    ) -> AsyncIterator[str]:
        """Streaming LLM call. Yields tokens as they arrive."""
        api_messages = self._build_api_messages(conversation, messages)
        config = getattr(settings, "MATT_AI", {})

        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {config.get('OPENAI_API_KEY', '')}"},
                json={
                    "model": conversation.model,
                    "messages": api_messages,
                    "stream": True,
                },
                timeout=120.0,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = orjson.loads(payload)
                if content := chunk.get("choices", [{}])[0].get("delta", {}).get("content"):
                    yield content

    @staticmethod
    def _build_api_messages(
        conversation: Conversation, messages: list[Message]
    ) -> list[dict[str, str]]:
        """Convert DB messages to OpenAI API format."""
        api_messages = [{"role": "system", "content": conversation.system_prompt}]
        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})
        return api_messages
