"""
Observability hooks for AI agents.

Provides a pluggable event system for tracing, logging, and monitoring
agent behavior. Supports custom callbacks, logging, and integration
with LangSmith, Langfuse, and OpenTelemetry.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("django_matt.ai.observability")


class EventType(str, Enum):
    """Types of agent lifecycle events."""

    AGENT_START = "AGENT_START"
    AGENT_END = "AGENT_END"
    LLM_CALL_START = "LLM_CALL_START"
    LLM_CALL_END = "LLM_CALL_END"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_ERROR = "TOOL_ERROR"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    CONVERSATION_LOADED = "CONVERSATION_LOADED"
    CONVERSATION_SAVED = "CONVERSATION_SAVED"


@dataclass
class AgentEvent:
    """An event emitted during agent execution."""

    event_type: EventType
    agent_class: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None


class ObservabilityHook:
    """Base class for observability hooks."""

    async def on_event(self, event: AgentEvent) -> None:
        """Handle an agent event. Override in subclass."""


class CallbackHook(ObservabilityHook):
    """Hook that calls a callback function for each event."""

    def __init__(self, callback: Callable) -> None:
        self._callback = callback

    async def on_event(self, event: AgentEvent) -> None:
        if asyncio.iscoroutinefunction(self._callback):
            await self._callback(event)
        else:
            self._callback(event)


class CompositeHook(ObservabilityHook):
    """Dispatches events to multiple hooks. One failing hook doesn't break others."""

    def __init__(self, hooks: list[ObservabilityHook]) -> None:
        self._hooks = hooks

    async def on_event(self, event: AgentEvent) -> None:
        for hook in self._hooks:
            try:
                await hook.on_event(event)
            except Exception as e:
                logger.warning("Observability hook %s failed: %s", type(hook).__name__, e)


class LoggingHook(ObservabilityHook):
    """Hook that logs events via Python logging."""

    def __init__(self, level: int = logging.DEBUG) -> None:
        self._level = level

    async def on_event(self, event: AgentEvent) -> None:
        duration = f" ({event.duration_ms:.1f}ms)" if event.duration_ms else ""
        logger.log(
            self._level,
            "[%s] %s%s %s",
            event.event_type,
            event.agent_class,
            duration,
            {k: v for k, v in event.data.items() if k != "messages"},
        )


__all__ = [
    "AgentEvent",
    "CallbackHook",
    "CompositeHook",
    "EventType",
    "LoggingHook",
    "ObservabilityHook",
]
