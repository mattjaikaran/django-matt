"""Tests for AI conversation persistence models and Agent integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from django_matt.ai.agents import Agent
from django_matt.ai.base import CompletionResponse, Usage
from django_matt.ai.models import Conversation, ConversationMessage


@pytest.mark.django_db
class TestConversationModel:
    @pytest.mark.asyncio
    async def test_create_conversation(self):
        conv = await Conversation.objects.acreate(
            title="Test conversation",
            metadata={"agent": "SupportAgent"},
        )
        assert conv.id is not None
        assert conv.title == "Test conversation"
        assert conv.metadata == {"agent": "SupportAgent"}

    @pytest.mark.asyncio
    async def test_add_messages(self):
        conv = await Conversation.objects.acreate(title="Test")
        msg = await ConversationMessage.objects.acreate(
            conversation=conv,
            role="user",
            content="Hello",
        )
        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "Hello"

    @pytest.mark.asyncio
    async def test_message_ordering(self):
        conv = await Conversation.objects.acreate(title="Test")
        await ConversationMessage.objects.acreate(
            conversation=conv, role="user", content="First"
        )
        await ConversationMessage.objects.acreate(
            conversation=conv, role="assistant", content="Second"
        )
        msgs = [
            m
            async for m in ConversationMessage.objects.filter(conversation=conv)
        ]
        assert msgs[0].content == "First"
        assert msgs[1].content == "Second"

    @pytest.mark.asyncio
    async def test_conversation_with_user(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = await User.objects.acreate_user(
            username="ai_conv_testuser", password="pass"
        )
        conv = await Conversation.objects.acreate(title="Test", user=user)
        assert conv.user_id == user.id

    @pytest.mark.asyncio
    async def test_tool_call_stored(self):
        conv = await Conversation.objects.acreate(title="Test")
        msg = await ConversationMessage.objects.acreate(
            conversation=conv,
            role="assistant",
            content="",
            tool_calls=[
                {"id": "tc1", "name": "get_order", "arguments": {"id": "123"}}
            ],
        )
        await msg.arefresh_from_db()
        assert msg.tool_calls[0]["name"] == "get_order"

    @pytest.mark.asyncio
    async def test_to_message(self):
        conv = await Conversation.objects.acreate(title="Test")
        msg = await ConversationMessage.objects.acreate(
            conversation=conv, role="user", content="Hello"
        )
        base_msg = msg.to_message()
        assert base_msg.content == "Hello"
        assert base_msg.role.value == "user"


@pytest.mark.django_db
class TestAgentWithConversation:
    @pytest.mark.asyncio
    async def test_agent_persists_conversation(self):
        provider = AsyncMock()
        provider.complete = AsyncMock(
            return_value=CompletionResponse(
                content="Hello!",
                usage=Usage(10, 5, 15),
            )
        )

        class MyAgent(Agent):
            system_prompt = "Be helpful."

        agent = MyAgent(provider=provider)
        conv = await agent.start_conversation(title="Test Chat")
        response = await agent.ahandle("Hi", conversation_id=conv.id)

        assert response.content == "Hello!"
        assert response.conversation_id == conv.id

        msgs = [
            m
            async for m in ConversationMessage.objects.filter(conversation=conv)
        ]
        assert len(msgs) == 2  # user + assistant
        assert msgs[0].role == "user"
        assert msgs[0].content == "Hi"
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "Hello!"

    @pytest.mark.asyncio
    async def test_conversation_history_sent(self):
        provider = AsyncMock()
        provider.complete = AsyncMock(
            return_value=CompletionResponse(content="OK")
        )

        class MyAgent(Agent):
            system_prompt = "Test"

        agent = MyAgent(provider=provider)
        conv = await agent.start_conversation()

        await agent.ahandle("Hello", conversation_id=conv.id)
        await agent.ahandle("What did I say?", conversation_id=conv.id)

        # Second call should include history:
        # system + "Hello" + "OK" + "What did I say?"
        second_call_messages = provider.complete.call_args_list[1][0][0]
        assert len(second_call_messages) == 4
