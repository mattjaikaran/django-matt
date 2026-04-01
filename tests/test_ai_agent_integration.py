"""
End-to-end integration tests for the AI agent framework.

Tests the full Agent -> Provider -> Tool dispatch -> Observability pipeline
using FakeProvider for deterministic, no-API-key-needed testing.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from django_matt.ai.agents import Agent
from django_matt.ai.base import CompletionResponse, ToolCall, Usage
from django_matt.ai.observability import CallbackHook, EventType
from django_matt.ai.testing import FakeProvider
from django_matt.ai.tools import tool

# ---------------------------------------------------------------------------
# Module-level tool definitions
# ---------------------------------------------------------------------------


@tool
def get_customer(customer_id: str) -> str:
    """Look up a customer by ID."""
    customers = {"C001": "Alice", "C002": "Bob"}
    return customers.get(customer_id, "Unknown customer")


@tool
def get_order_status(order_id: str) -> str:
    """Get the status of an order."""
    orders = {"O100": "shipped", "O200": "processing", "O300": "delivered"}
    return orders.get(order_id, "Order not found")


@tool
def cancel_order(order_id: str) -> str:
    """Cancel an order."""
    return f"Order {order_id} cancelled"


# ---------------------------------------------------------------------------
# Agent subclass
# ---------------------------------------------------------------------------


SUPPORT_TOOLS = [get_customer, get_order_status, cancel_order]
SUPPORT_PROMPT = "You are a customer support agent. Use tools to look up information."


def make_support_agent(provider: FakeProvider, **kwargs) -> Agent:
    """Create a SupportAgent with standard config."""
    return Agent(
        provider=provider,
        tools=SUPPORT_TOOLS,
        system_prompt=SUPPORT_PROMPT,
        temperature=0.0,
        max_iterations=5,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simple_query_with_one_tool_call():
    """Agent calls get_order_status, feeds result back, gets final answer."""
    provider = FakeProvider(responses=[
        # 1st call: LLM decides to call get_order_status
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_1", name="get_order_status", arguments={"order_id": "O100"}),
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ),
        # 2nd call: LLM produces final answer after seeing tool result
        "Your order O100 has been shipped.",
    ])

    agent = make_support_agent(provider)
    response = await agent.ahandle("What is the status of order O100?")

    assert response.content == "Your order O100 has been shipped."
    assert len(response.tool_calls_made) == 1
    assert response.tool_calls_made[0].name == "get_order_status"
    assert response.tool_calls_made[0].arguments == {"order_id": "O100"}
    assert response.usage.total_tokens > 0

    # Verify the tool result was fed back into messages
    tool_msgs = [m for m in response.messages if m.role.value == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content == "shipped"


@pytest.mark.asyncio
async def test_multi_step_workflow():
    """Agent chains 3 tool calls: get_customer -> get_order_status -> cancel_order."""
    provider = FakeProvider(responses=[
        # Step 1: look up customer
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_1", name="get_customer", arguments={"customer_id": "C001"}),
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ),
        # Step 2: check order status
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_2", name="get_order_status", arguments={"order_id": "O200"}),
            ],
            usage=Usage(prompt_tokens=20, completion_tokens=5, total_tokens=25),
        ),
        # Step 3: cancel the order
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_3", name="cancel_order", arguments={"order_id": "O200"}),
            ],
            usage=Usage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
        ),
        # Step 4: final answer
        "Done! Customer Alice's order O200 (was processing) has been cancelled.",
    ])

    agent = make_support_agent(provider)
    response = await agent.ahandle("Cancel order O200 for customer C001")

    assert response.content == "Done! Customer Alice's order O200 (was processing) has been cancelled."
    assert len(response.tool_calls_made) == 3

    names = [tc.name for tc in response.tool_calls_made]
    assert names == ["get_customer", "get_order_status", "cancel_order"]

    # Verify tool results in message history
    tool_msgs = [m for m in response.messages if m.role.value == "tool"]
    assert len(tool_msgs) == 3
    assert tool_msgs[0].content == "Alice"
    assert tool_msgs[1].content == "processing"
    assert tool_msgs[2].content == "Order O200 cancelled"

    # Usage accumulated across all 4 provider calls (3 explicit + 1 estimated from string)
    assert response.usage.total_tokens >= 15 + 25 + 35


@pytest.mark.asyncio
async def test_with_observability():
    """Agent emits AGENT_START, LLM_CALL_START/END, TOOL_CALL_START/END, AGENT_END."""
    events: list = []

    provider = FakeProvider(responses=[
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_1", name="get_order_status", arguments={"order_id": "O300"}),
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ),
        "Order O300 has been delivered.",
    ])

    agent = make_support_agent(
        provider,
        hooks=[CallbackHook(lambda e: events.append(e))],
    )
    response = await agent.ahandle("Check order O300")

    assert response.content == "Order O300 has been delivered."

    event_types = [e.event_type for e in events]

    # Verify the full lifecycle
    assert event_types[0] == EventType.AGENT_START
    assert EventType.LLM_CALL_START in event_types
    assert EventType.LLM_CALL_END in event_types
    assert EventType.TOOL_CALL_START in event_types
    assert EventType.TOOL_CALL_END in event_types
    assert event_types[-1] == EventType.AGENT_END

    # Verify ordering: AGENT_START first, then LLM calls, tool calls, AGENT_END last
    start_idx = event_types.index(EventType.AGENT_START)
    end_idx = event_types.index(EventType.AGENT_END)
    tool_start_idx = event_types.index(EventType.TOOL_CALL_START)
    tool_end_idx = event_types.index(EventType.TOOL_CALL_END)
    assert start_idx < tool_start_idx < tool_end_idx < end_idx

    # Check that agent_class is populated
    for e in events:
        assert "Agent" in e.agent_class

    # Verify LLM_CALL_END has duration_ms
    llm_ends = [e for e in events if e.event_type == EventType.LLM_CALL_END]
    assert len(llm_ends) == 2  # two LLM calls
    for e in llm_ends:
        assert "duration_ms" in e.data

    # Verify TOOL_CALL_START has tool name
    tool_starts = [e for e in events if e.event_type == EventType.TOOL_CALL_START]
    assert tool_starts[0].data["tool_name"] == "get_order_status"


@pytest.mark.asyncio
async def test_structured_output():
    """Agent with output_schema returns a validated Pydantic model."""

    class OrderSummary(BaseModel):
        order_id: str
        status: str
        customer: str

    provider = FakeProvider(responses=[
        # LLM calls a tool first
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_1", name="get_order_status", arguments={"order_id": "O100"}),
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ),
        # Then returns structured JSON
        '{"order_id": "O100", "status": "shipped", "customer": "Alice"}',
    ])

    agent = make_support_agent(provider, output_schema=OrderSummary)
    response = await agent.ahandle("Summarize order O100")

    assert response.structured is not None
    assert isinstance(response.structured, OrderSummary)
    assert response.structured.order_id == "O100"
    assert response.structured.status == "shipped"
    assert response.structured.customer == "Alice"
    assert response.content == '{"order_id": "O100", "status": "shipped", "customer": "Alice"}'


@pytest.mark.asyncio
async def test_fake_provider_assertions():
    """FakeProvider assertion helpers work end-to-end with the agent."""
    provider = FakeProvider(responses=[
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_1", name="get_customer", arguments={"customer_id": "C002"}),
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        ),
        "Bob is customer C002.",
    ])

    agent = make_support_agent(provider)
    await agent.ahandle("Who is customer C002?")

    # assert_called
    provider.assert_called()

    # assert_call_count: 2 calls (tool call response + final answer)
    provider.assert_call_count(2)

    # assert_called_with_message: the user message should appear
    provider.assert_called_with_message("Who is customer C002?")

    # Negative assertions
    with pytest.raises(AssertionError, match="No call contained message"):
        provider.assert_called_with_message("nonexistent message")

    # Reset and verify
    provider.reset()
    with pytest.raises(AssertionError, match="never called"):
        provider.assert_called()


@pytest.mark.asyncio
async def test_no_tool_calls_direct_answer():
    """Agent returns a direct answer without any tool calls."""
    provider = FakeProvider(responses=["I can help with order inquiries."])

    agent = make_support_agent(provider)
    response = await agent.ahandle("Hello")

    assert response.content == "I can help with order inquiries."
    assert len(response.tool_calls_made) == 0
    provider.assert_call_count(1)


@pytest.mark.asyncio
async def test_tool_error_handling():
    """Agent handles tool execution errors gracefully."""

    @tool
    def failing_tool(x: str) -> str:
        """A tool that always fails."""
        raise ValueError("Something went wrong")

    provider = FakeProvider(responses=[
        CompletionResponse(
            content="",
            model="fake-model",
            tool_calls=[
                ToolCall(id="call_1", name="failing_tool", arguments={"x": "test"}),
            ],
            usage=Usage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        ),
        "Sorry, I encountered an error.",
    ])

    agent = Agent(
        provider=provider,
        tools=[failing_tool],
        system_prompt="You are helpful.",
        max_iterations=5,
    )
    response = await agent.ahandle("Do the thing")

    assert response.content == "Sorry, I encountered an error."
    # The error message should be in the tool result message
    tool_msgs = [m for m in response.messages if m.role.value == "tool"]
    assert len(tool_msgs) == 1
    assert "ValueError" in tool_msgs[0].content
    assert "Something went wrong" in tool_msgs[0].content
