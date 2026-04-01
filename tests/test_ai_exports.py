def test_agent_exports():
    from django_matt.ai import Agent, AgentConfig, AgentResponse

    assert Agent is not None
    assert AgentResponse is not None
    assert AgentConfig is not None


def test_tool_exports():
    from django_matt.ai import ToolRegistry, is_tool, tool

    assert tool is not None
    assert ToolRegistry is not None
    assert is_tool is not None


def test_testing_exports():
    from django_matt.ai.testing import FakeEmbeddingProvider, FakeProvider

    assert FakeProvider is not None
    assert FakeEmbeddingProvider is not None


def test_observability_exports():
    from django_matt.ai import (
        AgentEvent,
        CallbackHook,
        CompositeHook,
        EventType,
        LoggingHook,
        ObservabilityHook,
    )

    assert ObservabilityHook is not None
    assert EventType.AGENT_START is not None


def test_conversation_model_exports():
    from django_matt.ai.models import Conversation, ConversationMessage

    assert Conversation is not None
    assert ConversationMessage is not None
