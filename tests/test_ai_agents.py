"""Tests for django_matt.ai.agents — Agent base class with tool dispatch loop."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from django_matt.ai.agents import Agent, AgentConfig, AgentResponse
from django_matt.ai.base import CompletionResponse, Role, ToolCall, Usage
from django_matt.ai.tools import tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(responses: list[CompletionResponse]) -> AsyncMock:
    """Create a mock LLMProvider with preset responses."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=responses)
    provider.model = "test-model"
    return provider


def _text_response(content: str, model: str = "test-model") -> CompletionResponse:
    """Create a simple text CompletionResponse."""
    return CompletionResponse(
        content=content,
        model=model,
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _tool_call_response(
    calls: list[ToolCall],
    content: str = "",
    model: str = "test-model",
) -> CompletionResponse:
    """Create a CompletionResponse with tool calls."""
    return CompletionResponse(
        content=content,
        model=model,
        tool_calls=calls,
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


# ---------------------------------------------------------------------------
# Tools for testing
# ---------------------------------------------------------------------------


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"


@tool
def failing_tool(x: str) -> str:
    """A tool that always raises."""
    raise ValueError(f"bad input: {x}")


@tool
async def async_multiply(a: int, b: int) -> int:
    """Multiply two numbers asynchronously."""
    return a * b


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simple_completion():
    """Agent returns text response when LLM has no tool calls."""
    provider = _make_provider([_text_response("Hello!")])
    agent = Agent(provider=provider)

    result = await agent.ahandle("Hi")

    assert result.content == "Hello!"
    assert result.tool_calls_made == []
    assert isinstance(result, AgentResponse)
    provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_system_prompt_sent():
    """System prompt is included in messages sent to the provider."""
    provider = _make_provider([_text_response("OK")])
    agent = Agent(provider=provider, system_prompt="You are a helpful bot.")

    await agent.ahandle("Hi")

    call_args = provider.complete.call_args
    messages = call_args[0][0]
    assert messages[0].role == Role.SYSTEM
    assert messages[0].content == "You are a helpful bot."
    assert messages[1].role == Role.USER
    assert messages[1].content == "Hi"


@pytest.mark.asyncio
async def test_config_overrides():
    """AgentConfig overrides class-level defaults."""
    provider = _make_provider([_text_response("OK")])
    config = AgentConfig(temperature=0.2, max_tokens=100, model="custom-model")
    agent = Agent(provider=provider, config=config)

    await agent.ahandle("Hi")

    call_kwargs = provider.complete.call_args[1]
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["max_tokens"] == 100
    assert call_kwargs["model"] == "custom-model"


@pytest.mark.asyncio
async def test_single_tool_call_dispatch():
    """Agent dispatches a single tool call and feeds result back."""
    tc = ToolCall(id="call_1", name="add_numbers", arguments={"a": 2, "b": 3})

    provider = _make_provider(
        [
            _tool_call_response([tc]),
            _text_response("The sum is 5"),
        ]
    )
    agent = Agent(provider=provider, tools=[add_numbers])

    result = await agent.ahandle("Add 2 and 3")

    assert result.content == "The sum is 5"
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0].name == "add_numbers"
    # Provider called twice: first with tool call, second with tool result
    assert provider.complete.call_count == 2

    # Verify tool result message was sent
    second_call_messages = provider.complete.call_args_list[1][0][0]
    tool_msg = [m for m in second_call_messages if m.role == Role.TOOL]
    assert len(tool_msg) == 1
    assert tool_msg[0].content == "5"
    assert tool_msg[0].tool_call_id == "call_1"


@pytest.mark.asyncio
async def test_multi_step_tool_calls():
    """Agent handles 3 sequential tool call rounds."""
    tc1 = ToolCall(id="call_1", name="get_weather", arguments={"city": "Tokyo"})
    tc2 = ToolCall(id="call_2", name="get_weather", arguments={"city": "London"})
    tc3 = ToolCall(id="call_3", name="add_numbers", arguments={"a": 1, "b": 2})

    provider = _make_provider(
        [
            _tool_call_response([tc1]),
            _tool_call_response([tc2]),
            _tool_call_response([tc3]),
            _text_response("Done comparing weather and math"),
        ]
    )
    agent = Agent(provider=provider, tools=[get_weather, add_numbers])

    result = await agent.ahandle("Compare weather and do math")

    assert result.content == "Done comparing weather and math"
    assert len(result.tool_calls_made) == 3
    assert provider.complete.call_count == 4


@pytest.mark.asyncio
async def test_max_iterations_guard():
    """Agent stops after max_iterations even if LLM keeps calling tools."""
    tc = ToolCall(id="call_loop", name="add_numbers", arguments={"a": 1, "b": 1})

    # Return tool calls forever — more than max_iterations + 1
    responses = [_tool_call_response([tc]) for _ in range(20)]
    provider = _make_provider(responses)
    agent = Agent(provider=provider, tools=[add_numbers], max_iterations=3)

    result = await agent.ahandle("Loop forever")

    # max_iterations=3 means 4 calls (0..3 inclusive), then return
    assert provider.complete.call_count == 4
    assert len(result.tool_calls_made) == 4


@pytest.mark.asyncio
async def test_tool_error_handling():
    """Tool errors are caught and fed back to the LLM as error strings."""
    tc = ToolCall(id="call_err", name="failing_tool", arguments={"x": "oops"})

    provider = _make_provider(
        [
            _tool_call_response([tc]),
            _text_response("I see the tool failed"),
        ]
    )
    agent = Agent(provider=provider, tools=[failing_tool])

    result = await agent.ahandle("Try the failing tool")

    assert result.content == "I see the tool failed"
    # Verify the error message was sent back
    second_call_messages = provider.complete.call_args_list[1][0][0]
    tool_msg = [m for m in second_call_messages if m.role == Role.TOOL]
    assert len(tool_msg) == 1
    assert "Error: ValueError: bad input: oops" in tool_msg[0].content


@pytest.mark.asyncio
async def test_async_tool_dispatch():
    """Async tools are awaited correctly."""
    tc = ToolCall(id="call_async", name="async_multiply", arguments={"a": 4, "b": 5})

    provider = _make_provider(
        [
            _tool_call_response([tc]),
            _text_response("Result is 20"),
        ]
    )
    agent = Agent(provider=provider, tools=[async_multiply])

    result = await agent.ahandle("Multiply 4 and 5")

    assert result.content == "Result is 20"
    second_call_messages = provider.complete.call_args_list[1][0][0]
    tool_msg = [m for m in second_call_messages if m.role == Role.TOOL]
    assert tool_msg[0].content == "20"


@pytest.mark.asyncio
async def test_structured_output():
    """Agent parses JSON response into output_schema Pydantic model."""

    class WeatherResult(BaseModel):
        city: str
        temperature: float
        condition: str

    json_content = '{"city": "Tokyo", "temperature": 22.5, "condition": "sunny"}'
    provider = _make_provider([_text_response(json_content)])
    agent = Agent(provider=provider, output_schema=WeatherResult)

    result = await agent.ahandle("Weather in Tokyo")

    assert result.structured is not None
    assert isinstance(result.structured, WeatherResult)
    assert result.structured.city == "Tokyo"
    assert result.structured.temperature == 22.5
    assert result.structured.condition == "sunny"

    # Verify schema instruction was sent as system message
    call_messages = provider.complete.call_args[0][0]
    system_msgs = [m for m in call_messages if m.role == Role.SYSTEM]
    assert any("schema" in m.content.lower() for m in system_msgs)


@pytest.mark.asyncio
async def test_agent_response_fields():
    """AgentResponse has all expected fields populated."""
    provider = _make_provider(
        [
            _text_response("Hello", model="gpt-4"),
        ]
    )
    agent = Agent(provider=provider)

    result = await agent.ahandle("Hi")

    assert result.content == "Hello"
    assert result.model == "gpt-4"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.tool_calls_made == []
    assert result.structured is None
    assert len(result.messages) == 1  # just the user message
    assert result.messages[0].role == Role.USER
    assert isinstance(result.conversation_id, str)
    assert len(result.conversation_id) > 0


@pytest.mark.asyncio
async def test_usage_accumulates_across_iterations():
    """Usage tokens accumulate across multiple LLM calls."""
    tc = ToolCall(id="call_1", name="add_numbers", arguments={"a": 1, "b": 2})

    provider = _make_provider(
        [
            _tool_call_response([tc]),
            _text_response("3"),
        ]
    )
    agent = Agent(provider=provider, tools=[add_numbers])

    result = await agent.ahandle("Add")

    # Two calls, each with 10+5+15
    assert result.usage.prompt_tokens == 20
    assert result.usage.completion_tokens == 10
    assert result.usage.total_tokens == 30


@pytest.mark.asyncio
async def test_per_instance_overrides():
    """Per-instance kwargs override class defaults and config."""
    provider = _make_provider([_text_response("OK")])
    config = AgentConfig(temperature=0.5)
    agent = Agent(provider=provider, config=config, temperature=0.1)

    await agent.ahandle("Hi")

    call_kwargs = provider.complete.call_args[1]
    assert call_kwargs["temperature"] == 0.1
