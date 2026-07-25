import logging

import pytest

from django_matt.ai.base import CompletionResponse, ToolCall
from django_matt.ai.observability import (
    AgentEvent,
    CallbackHook,
    CompositeHook,
    EventType,
    LoggingHook,
    ObservabilityHook,
)


class TestEventType:
    def test_event_types_exist(self):
        assert EventType.AGENT_START
        assert EventType.AGENT_END
        assert EventType.LLM_CALL_START
        assert EventType.LLM_CALL_END
        assert EventType.TOOL_CALL_START
        assert EventType.TOOL_CALL_END
        assert EventType.TOOL_ERROR
        assert EventType.MAX_ITERATIONS


class TestAgentEvent:
    def test_event_creation(self):
        event = AgentEvent(
            event_type=EventType.AGENT_START,
            agent_class="MyAgent",
            data={"message": "Hello"},
        )
        assert event.event_type == EventType.AGENT_START
        assert event.agent_class == "MyAgent"
        assert event.data["message"] == "Hello"
        assert event.timestamp is not None


class TestCallbackHook:
    @pytest.mark.asyncio
    async def test_callback_invoked(self):
        events: list[AgentEvent] = []

        async def on_event(event: AgentEvent) -> None:
            events.append(event)

        hook = CallbackHook(on_event)
        await hook.on_event(
            AgentEvent(
                event_type=EventType.AGENT_START,
                agent_class="Test",
            )
        )

        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_START

    @pytest.mark.asyncio
    async def test_sync_callback_accepted(self):
        events: list[AgentEvent] = []

        def on_event(event: AgentEvent) -> None:
            events.append(event)

        hook = CallbackHook(on_event)
        await hook.on_event(
            AgentEvent(
                event_type=EventType.AGENT_END,
                agent_class="Test",
            )
        )

        assert len(events) == 1


class TestCompositeHook:
    @pytest.mark.asyncio
    async def test_dispatches_to_all_hooks(self):
        events_a: list[AgentEvent] = []
        events_b: list[AgentEvent] = []

        hook = CompositeHook(
            [
                CallbackHook(lambda e: events_a.append(e)),
                CallbackHook(lambda e: events_b.append(e)),
            ]
        )

        await hook.on_event(
            AgentEvent(
                event_type=EventType.AGENT_START,
                agent_class="Test",
            )
        )

        assert len(events_a) == 1
        assert len(events_b) == 1

    @pytest.mark.asyncio
    async def test_one_failing_hook_doesnt_break_others(self):
        events: list[AgentEvent] = []

        def bad_hook(e: AgentEvent) -> None:
            raise RuntimeError("oops")

        hook = CompositeHook(
            [
                CallbackHook(bad_hook),
                CallbackHook(lambda e: events.append(e)),
            ]
        )

        await hook.on_event(
            AgentEvent(
                event_type=EventType.AGENT_START,
                agent_class="Test",
            )
        )

        assert len(events) == 1


class TestLoggingHook:
    @pytest.mark.asyncio
    async def test_logs_events(self, caplog):
        hook = LoggingHook(level=logging.INFO)

        with caplog.at_level(logging.INFO, logger="django_matt.ai.observability"):
            await hook.on_event(
                AgentEvent(
                    event_type=EventType.AGENT_START,
                    agent_class="TestAgent",
                    data={"message": "Hello"},
                )
            )

        assert "AGENT_START" in caplog.text
        assert "TestAgent" in caplog.text


class TestAgentObservability:
    @pytest.mark.asyncio
    async def test_agent_emits_events(self):
        from django_matt.ai.agents import Agent
        from django_matt.ai.testing import FakeProvider

        events: list[AgentEvent] = []
        hook = CallbackHook(lambda e: events.append(e))

        provider = FakeProvider(responses=["Hello!"])

        class MyAgent(Agent):
            system_prompt = "Test"
            hooks = [hook]

        agent = MyAgent(provider=provider)
        await agent.ahandle("Hi")

        event_types = [e.event_type for e in events]
        assert EventType.AGENT_START in event_types
        assert EventType.AGENT_END in event_types
        assert EventType.LLM_CALL_START in event_types
        assert EventType.LLM_CALL_END in event_types

    @pytest.mark.asyncio
    async def test_agent_emits_tool_events(self):
        from django_matt.ai.agents import Agent
        from django_matt.ai.testing import FakeProvider
        from django_matt.ai.tools import tool

        events: list[AgentEvent] = []
        hook = CallbackHook(lambda e: events.append(e))

        @tool
        def my_tool() -> str:
            """A tool."""
            return "result"

        provider = FakeProvider(
            responses=[
                CompletionResponse(
                    content="",
                    tool_calls=[ToolCall(id="tc1", name="my_tool", arguments={})],
                ),
                "Done.",
            ]
        )

        class MyAgent(Agent):
            system_prompt = "Test"
            hooks = [hook]

        agent = MyAgent(provider=provider, tools=[my_tool])
        await agent.ahandle("Go")

        event_types = [e.event_type for e in events]
        assert EventType.TOOL_CALL_START in event_types
        assert EventType.TOOL_CALL_END in event_types
