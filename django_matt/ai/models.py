"""
ORM models for persistent AI conversations.

Provides Conversation and ConversationMessage models for storing
multi-turn agent interactions in the database.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from django_matt.ai.base import Message


class AIConversation(models.Model):
    """A persistent conversation with an AI agent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    agent_class = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_matt"
        db_table = "django_matt_ai_conversation"
        ordering = ["-updated_at"]
        verbose_name = "AI Conversation"
        verbose_name_plural = "AI Conversations"

    def __str__(self) -> str:
        return self.title or f"Conversation {self.id}"


# Backwards-compatible alias
Conversation = AIConversation


class ConversationMessage(models.Model):
    """A single message in a conversation."""

    ROLE_CHOICES = [
        ("system", "System"),
        ("user", "User"),
        ("assistant", "Assistant"),
        ("tool", "Tool"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    tool_calls = models.JSONField(null=True, blank=True)
    tool_call_id = models.CharField(max_length=255, blank=True, default="")
    token_count = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "django_matt"
        ordering = ["created_at"]
        verbose_name = "Conversation Message"
        verbose_name_plural = "Conversation Messages"

    def __str__(self) -> str:
        preview = self.content[:50] if self.content else "(empty)"
        return f"{self.role}: {preview}"

    def to_message(self) -> Message:
        """Convert to a django_matt.ai.base.Message."""
        from django_matt.ai.base import Message, Role

        role_map = {
            "system": Role.SYSTEM,
            "user": Role.USER,
            "assistant": Role.ASSISTANT,
            "tool": Role.TOOL,
        }
        return Message(
            role=role_map[self.role],
            content=self.content,
            tool_call_id=self.tool_call_id or None,
            tool_calls=self.tool_calls,
        )


__all__ = [
    "AIConversation",
    "Conversation",
    "ConversationMessage",
]
