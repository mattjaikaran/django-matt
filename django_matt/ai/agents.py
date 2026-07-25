# file-length-max: 450
"""
Agent framework with tool dispatch loop for AI/LLM integration.

Provides an Agent class that orchestrates LLM calls with automatic tool
dispatch, supporting multi-step reasoning and structured output.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, TypeVar

import orjson
from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    LLMProvider,
    Message,
    ToolCall,
    ToolDefinition,
    Usage,
)
from django_matt.ai.tools import ToolRegistry, is_tool

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentConfig:
    """Configuration for an Agent instance."""

    temperature: float = 0.7
    max_tokens: int | None = None
    max_iterations: int = 10
    model: str | None = None


@dataclass
class AgentResponse:
    """Response from an Agent.ahandle() call."""

    content: str
    usage: Usage
    model: str
    tool_calls_made: list[ToolCall] = field(default_factory=list)
    structured: BaseModel | None = None
    messages: list[Message] = field(default_factory=list)
    conversation_id: Any | None = field(default_factory=lambda: uuid.uuid4().hex)


class Agent:
    """
    LLM agent with automatic tool dispatch loop.

    Accepts a provider and optional tools, executes a message loop that
    automatically dispatches tool calls until the LLM produces a final
    text response or max_iterations is reached.

    Usage:
        from django_matt.ai import OpenAIProvider
        from django_matt.ai.tools import tool
        from django_matt.ai.agents import Agent

        @tool
        def get_weather(city: str) -> str:
            '''Get the weather for a city.'''
            return f"Sunny in {city}"

        agent = Agent(
            provider=OpenAIProvider(),
            tools=[get_weather],
            system_prompt="You are a helpful assistant.",
        )
        response = await agent.ahandle("What's the weather in Tokyo?")
    """

    # Class-level defaults (can be overridden per-instance)
    temperature: float = 0.7
    max_tokens: int | None = None
    max_iterations: int = 10
    model: str | None = None
    system_prompt: str | None = None
    hooks: list = []

    def __init__(
        self,
        provider: LLMProvider,
        *,
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        config: AgentConfig | None = None,
        output_schema: type[T] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
        model: str | None = None,
        hooks: list[Any] | None = None,
    ) -> None:
        self.provider = provider
        self.output_schema = output_schema

        # Build tool registry
        self._registry = ToolRegistry()
        for t in tools or []:
            if is_tool(t):
                self._registry.register(t)

        # Apply config, then per-instance overrides, falling back to class defaults
        if config:
            self.temperature = config.temperature
            self.max_tokens = config.max_tokens
            self.max_iterations = config.max_iterations
            self.model = config.model

        if system_prompt is not None:
            self.system_prompt = system_prompt
        if temperature is not None:
            self.temperature = temperature
        if max_tokens is not None:
            self.max_tokens = max_tokens
        if max_iterations is not None:
            self.max_iterations = max_iterations
        if model is not None:
            self.model = model

        # Build observability hook
        if hooks is not None:
            self.hooks = hooks
        from django_matt.ai.observability import (
            CallbackHook,
            CompositeHook,
            ObservabilityHook,
        )

        self._hook = (
            CompositeHook(
                [h if isinstance(h, ObservabilityHook) else CallbackHook(h) for h in self.hooks]
            )
            if self.hooks
            else None
        )

    @property
    def tool_definitions(self) -> list[ToolDefinition]:
        """Return tool definitions for registered tools."""
        return self._registry.definitions

    async def _emit(self, event_type: Any, **data: Any) -> None:
        """Emit an observability event if hooks are configured."""
        if self._hook:
            from django_matt.ai.observability import AgentEvent

            await self._hook.on_event(
                AgentEvent(
                    event_type=event_type,
                    agent_class=f"{type(self).__module__}.{type(self).__qualname__}",
                    data=data,
                )
            )

    async def start_conversation(
        self,
        title: str = "",
        user: Any = None,
        metadata: dict | None = None,
    ) -> Any:
        """Create a new persistent conversation for this agent."""
        from django_matt.ai.models import AIConversation

        return await AIConversation.objects.acreate(
            title=title,
            user=user,
            agent_class=f"{type(self).__module__}.{type(self).__qualname__}",
            metadata=metadata or {},
        )

    async def _load_conversation_history(self, conversation_id: Any) -> list[Message]:
        """Load previous messages from a persisted conversation."""
        from django_matt.ai.models import ConversationMessage

        messages: list[Message] = []
        async for msg in ConversationMessage.objects.filter(
            conversation_id=conversation_id
        ).order_by("created_at"):
            messages.append(msg.to_message())
        return messages

    async def _save_conversation_messages(
        self,
        conversation_id: Any,
        new_messages: list[Message],
    ) -> None:
        """Persist new messages to the conversation."""
        from django_matt.ai.models import ConversationMessage

        for msg in new_messages:
            await ConversationMessage.objects.acreate(
                conversation_id=conversation_id,
                role=msg.role.value,
                content=msg.content,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id or "",
            )

    async def ahandle(
        self,
        message: str,
        *,
        conversation_id: Any | None = None,
    ) -> AgentResponse:
        """
        Handle a user message with automatic tool dispatch.

        Builds the message list, calls the provider, dispatches any tool
        calls, feeds results back, and loops until a final text response
        or max_iterations is reached.

        If conversation_id is provided, loads previous messages from DB
        and persists new messages after completion.
        """
        from django_matt.ai.observability import EventType

        messages: list[Message] = []

        await self._emit(EventType.AGENT_START, message=message)

        # System prompt
        if self.system_prompt:
            messages.append(Message.system(self.system_prompt))

        # Output schema instruction
        if self.output_schema:
            schema_json = orjson.dumps(self.output_schema.model_json_schema()).decode()
            messages.append(
                Message.system(f"Respond with JSON matching this schema: {schema_json}")
            )

        # Load conversation history if persisting
        if conversation_id is not None:
            history = await self._load_conversation_history(conversation_id)
            messages.extend(history)

        # User message
        messages.append(Message.user(message))

        # Track where new messages start (for saving to DB later)
        _new_msg_start = len(messages) - 1  # from user message onward

        # Tool definitions for the provider
        tool_defs = self.tool_definitions if len(self._registry) > 0 else None

        # Accumulate usage and tool calls
        total_usage = Usage()
        all_tool_calls: list[ToolCall] = []

        # Completion kwargs
        complete_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            complete_kwargs["max_tokens"] = self.max_tokens
        if self.model is not None:
            complete_kwargs["model"] = self.model

        for _iteration in range(self.max_iterations + 1):
            await self._emit(EventType.LLM_CALL_START, iteration=_iteration)
            _llm_start = time.monotonic()
            response: CompletionResponse = await self.provider.complete(
                messages,
                tools=tool_defs,
                **complete_kwargs,
            )
            _llm_ms = (time.monotonic() - _llm_start) * 1000
            await self._emit(
                EventType.LLM_CALL_END,
                iteration=_iteration,
                duration_ms=_llm_ms,
                has_tool_calls=response.has_tool_calls,
            )

            # Accumulate usage
            if response.usage:
                total_usage.prompt_tokens += response.usage.prompt_tokens
                total_usage.completion_tokens += response.usage.completion_tokens
                total_usage.total_tokens += response.usage.total_tokens

            if not response.has_tool_calls:
                # Final response
                structured = None
                if self.output_schema and response.content:
                    try:
                        data = orjson.loads(response.content)
                        structured = self.output_schema.model_validate(data)
                    except Exception:
                        pass

                await self._emit(
                    EventType.AGENT_END,
                    tool_calls_count=len(all_tool_calls),
                )

                # Persist new messages if conversation is active
                if conversation_id is not None:
                    to_save = list(messages[_new_msg_start:])
                    to_save.append(Message.assistant(response.content))
                    await self._save_conversation_messages(conversation_id, to_save)

                resp = AgentResponse(
                    content=response.content,
                    usage=total_usage,
                    model=response.model,
                    tool_calls_made=all_tool_calls,
                    structured=structured,
                    messages=messages,
                )
                if conversation_id is not None:
                    resp.conversation_id = conversation_id
                return resp

            # Append assistant message with tool calls
            tool_calls = response.tool_calls or []
            tool_call_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": orjson.dumps(tc.arguments).decode(),
                    },
                }
                for tc in tool_calls
            ]
            messages.append(Message.assistant(response.content or "", tool_calls=tool_call_dicts))

            # Execute each tool call
            for tc in tool_calls:
                all_tool_calls.append(tc)
                await self._emit(
                    EventType.TOOL_CALL_START,
                    tool_name=tc.name,
                    tool_call_id=tc.id,
                    arguments=tc.arguments,
                )
                _tool_start = time.monotonic()
                try:
                    result = await self._registry.aexecute(tc.name, tc.arguments)
                    result_str = (
                        result if isinstance(result, str) else orjson.dumps(result).decode()
                    )
                    _tool_ms = (time.monotonic() - _tool_start) * 1000
                    await self._emit(
                        EventType.TOOL_CALL_END,
                        tool_name=tc.name,
                        tool_call_id=tc.id,
                        duration_ms=_tool_ms,
                    )
                except Exception as exc:
                    _tool_ms = (time.monotonic() - _tool_start) * 1000
                    await self._emit(
                        EventType.TOOL_ERROR,
                        tool_name=tc.name,
                        tool_call_id=tc.id,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        duration_ms=_tool_ms,
                    )
                    result_str = f"Error: {type(exc).__name__}: {exc}"

                messages.append(Message.tool(result_str, tool_call_id=tc.id))

        # Max iterations exceeded — return last content
        await self._emit(
            EventType.MAX_ITERATIONS,
            max_iterations=self.max_iterations,
            tool_calls_count=len(all_tool_calls),
        )
        await self._emit(
            EventType.AGENT_END,
            tool_calls_count=len(all_tool_calls),
            max_iterations_reached=True,
        )

        # Persist new messages if conversation is active
        if conversation_id is not None:
            await self._save_conversation_messages(conversation_id, messages[_new_msg_start:])

        resp = AgentResponse(
            content=response.content or "",
            usage=total_usage,
            model=response.model,
            tool_calls_made=all_tool_calls,
            messages=messages,
        )
        if conversation_id is not None:
            resp.conversation_id = conversation_id
        return resp

    def handle(self, message: str) -> AgentResponse:
        """Synchronous wrapper around ahandle()."""
        return asyncio.run(self.ahandle(message))


__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResponse",
]
