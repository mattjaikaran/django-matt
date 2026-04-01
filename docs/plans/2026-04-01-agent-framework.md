# Agent Framework Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Django-idiomatic Agent abstraction layer to django-matt's AI module — `@tool` decorator, tool dispatch loop, ORM-backed conversations, `FakeProvider` for testing, and observability hooks.

**Architecture:** Build on the existing `LLMProvider`, `ToolDefinition`, `ToolCall`, and `CompletionResponse` infrastructure in `django_matt/ai/base.py`. The Agent is a class that composes a provider + tools + optional conversation persistence + optional structured output into a single `.handle()` call. Composability via mixins. All async-first.

**Tech Stack:** Python 3.12+, Django 5.2+, Pydantic v2, orjson, existing django-matt AI providers

---

## Task 1: `@tool` Decorator

Converts a plain Python function into a tool the Agent can dispatch. Auto-generates JSON Schema from type hints and docstring.

**Files:**
- Create: `django_matt/ai/tools.py`
- Test: `tests/test_ai_tools.py`

**Step 1: Write the failing tests**

```python
# tests/test_ai_tools.py
import pytest
from django_matt.ai.tools import tool, ToolRegistry


class TestToolDecorator:
    def test_basic_decoration(self):
        @tool
        def get_weather(city: str) -> str:
            """Get the weather for a city."""
            return f"Sunny in {city}"

        assert get_weather._tool_definition is not None
        assert get_weather._tool_definition.name == "get_weather"
        assert get_weather._tool_definition.description == "Get the weather for a city."
        assert "city" in get_weather._tool_definition.parameters["properties"]

    def test_decorated_function_still_callable(self):
        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        assert add(1, 2) == 3

    def test_async_tool(self):
        @tool
        async def fetch_data(url: str) -> str:
            """Fetch data from a URL."""
            return f"data from {url}"

        assert fetch_data._tool_definition is not None
        assert fetch_data._tool_definition.name == "fetch_data"

    def test_tool_with_optional_params(self):
        @tool
        def search(query: str, limit: int = 10) -> list[str]:
            """Search for items."""
            return []

        params = search._tool_definition.parameters
        assert "query" in params["required"]
        assert "limit" not in params["required"]

    def test_tool_with_custom_name_and_description(self):
        @tool(name="custom_name", description="Custom description")
        def my_func(x: int) -> int:
            return x

        assert my_func._tool_definition.name == "custom_name"
        assert my_func._tool_definition.description == "Custom description"


class TestToolRegistry:
    def test_register_and_retrieve(self):
        registry = ToolRegistry()

        @tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello {name}"

        registry.register(greet)
        assert registry.get("greet") is greet
        assert len(registry.definitions) == 1

    def test_register_duplicate_raises(self):
        registry = ToolRegistry()

        @tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello {name}"

        registry.register(greet)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(greet)

    def test_execute_sync_tool(self):
        registry = ToolRegistry()

        @tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        registry.register(multiply)
        result = registry.execute("multiply", {"a": 3, "b": 4})
        assert result == 12

    @pytest.mark.asyncio
    async def test_execute_async_tool(self):
        registry = ToolRegistry()

        @tool
        async def async_add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        registry.register(async_add)
        result = await registry.aexecute("async_add", {"a": 3, "b": 4})
        assert result == 7

    def test_execute_unknown_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="not_registered"):
            registry.execute("not_registered", {})

    def test_definitions_returns_tool_definitions(self):
        registry = ToolRegistry()

        @tool
        def a_tool(x: int) -> int:
            """Tool A."""
            return x

        registry.register(a_tool)
        defs = registry.definitions
        assert len(defs) == 1
        assert defs[0].name == "a_tool"
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ai_tools.py -v
```
Expected: FAIL (ModuleNotFoundError: No module named 'django_matt.ai.tools')

**Step 3: Implement `django_matt/ai/tools.py`**

```python
"""
Tool decorator and registry for AI agents.

Provides @tool decorator to convert Python functions into LLM-callable tools,
and ToolRegistry for managing and dispatching tool calls.
"""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, overload

from django_matt.ai.base import ToolDefinition


@overload
def tool(func: Callable) -> Callable: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable], Callable]: ...


def tool(
    func: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable:
    """
    Decorator that marks a function as an LLM-callable tool.

    Usage:
        @tool
        def get_weather(city: str) -> str:
            '''Get the weather for a city.'''
            return f"Sunny in {city}"

        @tool(name="custom_name", description="Custom description")
        def my_func(x: int) -> int:
            return x
    """

    def decorator(fn: Callable) -> Callable:
        tool_def = ToolDefinition.from_function(
            fn,
            description=description,
        )
        if name:
            tool_def = ToolDefinition(
                name=name,
                description=tool_def.description if not description else description,
                parameters=tool_def.parameters,
            )
        if description and not name:
            tool_def = ToolDefinition(
                name=tool_def.name,
                description=description,
                parameters=tool_def.parameters,
            )

        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)
        else:
            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return fn(*args, **kwargs)

        wrapper._tool_definition = tool_def
        wrapper._is_tool = True
        wrapper._original_func = fn
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def is_tool(func: Any) -> bool:
    """Check if a function is a decorated tool."""
    return getattr(func, "_is_tool", False)


class ToolRegistry:
    """
    Registry for managing and dispatching tool calls.

    Usage:
        registry = ToolRegistry()
        registry.register(my_tool)
        result = registry.execute("my_tool", {"arg": "value"})
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, func: Callable) -> None:
        """Register a @tool-decorated function."""
        if not is_tool(func):
            raise TypeError(f"{func.__name__} is not decorated with @tool")
        tool_name = func._tool_definition.name
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")
        self._tools[tool_name] = func

    def get(self, name: str) -> Callable:
        """Get a registered tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    @property
    def definitions(self) -> list[ToolDefinition]:
        """Return ToolDefinitions for all registered tools."""
        return [func._tool_definition for func in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a sync tool by name with arguments."""
        func = self.get(name)
        return func(**arguments)

    async def aexecute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name with arguments (async-safe)."""
        func = self.get(name)
        original = getattr(func, "_original_func", func)
        if asyncio.iscoroutinefunction(original):
            return await func(**arguments)
        return func(**arguments)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


__all__ = [
    "ToolRegistry",
    "is_tool",
    "tool",
]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ai_tools.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add django_matt/ai/tools.py tests/test_ai_tools.py
git commit -m "feat: add @tool decorator and ToolRegistry for AI agents"
```

---

## Task 2: Agent Base Class with Tool Dispatch Loop

The core Agent class that composes provider + tools + dispatch loop into a single `.handle()` / `.ahandle()` call.

**Files:**
- Create: `django_matt/ai/agents.py`
- Test: `tests/test_ai_agents.py`

**Step 1: Write the failing tests**

```python
# tests/test_ai_agents.py
import pytest
from unittest.mock import AsyncMock
from django_matt.ai.agents import Agent, AgentResponse, AgentConfig
from django_matt.ai.tools import tool
from django_matt.ai.base import (
    CompletionResponse, ToolCall, Usage, Role, Message,
)


def _make_provider(responses: list[CompletionResponse]) -> AsyncMock:
    """Create a mock provider that returns responses in sequence."""
    provider = AsyncMock()
    provider.complete = AsyncMock(side_effect=responses)
    provider.provider_name = "mock"
    provider.default_model = "mock-model"
    return provider


class TestAgentBasic:
    @pytest.mark.asyncio
    async def test_simple_completion(self):
        provider = _make_provider([
            CompletionResponse(content="Hello!", usage=Usage(10, 5, 15)),
        ])

        class MyAgent(Agent):
            system_prompt = "You are helpful."

        agent = MyAgent(provider=provider)
        response = await agent.ahandle("Hi")

        assert response.content == "Hello!"
        assert response.usage.total_tokens == 15
        assert provider.complete.call_count == 1

    @pytest.mark.asyncio
    async def test_system_prompt_sent(self):
        provider = _make_provider([
            CompletionResponse(content="OK"),
        ])

        class MyAgent(Agent):
            system_prompt = "Be concise."

        agent = MyAgent(provider=provider)
        await agent.ahandle("Test")

        call_args = provider.complete.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
        assert messages[0].role == Role.SYSTEM
        assert messages[0].content == "Be concise."

    @pytest.mark.asyncio
    async def test_config_overrides(self):
        provider = _make_provider([
            CompletionResponse(content="OK"),
        ])

        class MyAgent(Agent):
            system_prompt = "Test"
            temperature = 0.2
            max_tokens = 100

        agent = MyAgent(provider=provider)
        await agent.ahandle("Test")

        call_kwargs = provider.complete.call_args[1]
        assert call_kwargs.get("temperature") == 0.2
        assert call_kwargs.get("max_tokens") == 100


class TestAgentToolDispatch:
    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        @tool
        def get_order(order_id: str) -> str:
            """Get order status."""
            return "shipped"

        provider = _make_provider([
            # First call: LLM wants to call get_order
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="get_order", arguments={"order_id": "123"})],
            ),
            # Second call: LLM gives final answer
            CompletionResponse(content="Order 123 has shipped."),
        ])

        class OrderAgent(Agent):
            system_prompt = "Help with orders."
            tools = [get_order]

        agent = OrderAgent(provider=provider)
        response = await agent.ahandle("Where is order 123?")

        assert response.content == "Order 123 has shipped."
        assert provider.complete.call_count == 2
        assert response.tool_calls_made == [{"name": "get_order", "arguments": {"order_id": "123"}, "result": "shipped"}]

    @pytest.mark.asyncio
    async def test_multi_tool_calls(self):
        @tool
        def get_order(order_id: str) -> str:
            """Get order status."""
            return "processing"

        @tool
        def cancel_order(order_id: str) -> str:
            """Cancel an order."""
            return "cancelled"

        provider = _make_provider([
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="get_order", arguments={"order_id": "123"})],
            ),
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc2", name="cancel_order", arguments={"order_id": "123"})],
            ),
            CompletionResponse(content="Order 123 has been cancelled."),
        ])

        class OrderAgent(Agent):
            system_prompt = "Help with orders."
            tools = [get_order, cancel_order]

        agent = OrderAgent(provider=provider)
        response = await agent.ahandle("Cancel order 123")

        assert response.content == "Order 123 has been cancelled."
        assert provider.complete.call_count == 3
        assert len(response.tool_calls_made) == 2

    @pytest.mark.asyncio
    async def test_max_iterations_guard(self):
        @tool
        def loop_tool() -> str:
            """A tool that always gets called."""
            return "again"

        # Provider always requests tool call (infinite loop scenario)
        infinite_tool_response = CompletionResponse(
            content="",
            tool_calls=[ToolCall(id="tc", name="loop_tool", arguments={})],
        )
        provider = _make_provider([infinite_tool_response] * 15)

        class LoopAgent(Agent):
            system_prompt = "Test"
            tools = [loop_tool]
            max_iterations = 3

        agent = LoopAgent(provider=provider)
        response = await agent.ahandle("Go")

        # Should stop after max_iterations, not loop forever
        assert provider.complete.call_count <= 4  # initial + 3 iterations

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        @tool
        def bad_tool() -> str:
            """A tool that raises."""
            raise ValueError("something broke")

        provider = _make_provider([
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="bad_tool", arguments={})],
            ),
            CompletionResponse(content="Sorry, there was an error."),
        ])

        class ErrorAgent(Agent):
            system_prompt = "Test"
            tools = [bad_tool]

        agent = ErrorAgent(provider=provider)
        response = await agent.ahandle("Do the thing")

        # Should feed error back to LLM, not crash
        assert response.content == "Sorry, there was an error."
        assert provider.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_async_tool_dispatch(self):
        @tool
        async def async_lookup(id: str) -> str:
            """Async lookup."""
            return f"found-{id}"

        provider = _make_provider([
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="async_lookup", arguments={"id": "42"})],
            ),
            CompletionResponse(content="Found it: found-42"),
        ])

        class AsyncAgent(Agent):
            system_prompt = "Test"
            tools = [async_lookup]

        agent = AsyncAgent(provider=provider)
        response = await agent.ahandle("Find 42")

        assert response.content == "Found it: found-42"


class TestAgentStructuredOutput:
    @pytest.mark.asyncio
    async def test_structured_output(self):
        from pydantic import BaseModel

        class OrderStatus(BaseModel):
            order_id: str
            status: str

        provider = _make_provider([
            CompletionResponse(content='{"order_id": "123", "status": "shipped"}'),
        ])
        # Also mock complete_structured
        provider.complete_structured = AsyncMock(
            return_value=OrderStatus(order_id="123", status="shipped")
        )

        class StructuredAgent(Agent):
            system_prompt = "Return order status."
            output_schema = OrderStatus

        agent = StructuredAgent(provider=provider)
        response = await agent.ahandle("Order 123 status?")

        assert response.structured is not None
        assert response.structured.order_id == "123"
        assert response.structured.status == "shipped"


class TestAgentResponse:
    def test_response_fields(self):
        response = AgentResponse(
            content="Hello",
            usage=Usage(10, 5, 15),
            model="gpt-4o",
            tool_calls_made=[],
        )
        assert response.content == "Hello"
        assert response.usage.total_tokens == 15
        assert response.model == "gpt-4o"
        assert response.tool_calls_made == []

    def test_response_structured_none_by_default(self):
        response = AgentResponse(content="Hi")
        assert response.structured is None
        assert response.tool_calls_made == []
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ai_agents.py -v
```
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement `django_matt/ai/agents.py`**

```python
"""
Agent framework for building AI agents with tool dispatch.

Provides a declarative Agent class that composes an LLM provider with
tools, conversation memory, and structured output into a single .handle() call.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import orjson
from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    LLMProvider,
    Message,
    Role,
    ToolCall,
    ToolDefinition,
    Usage,
)
from django_matt.ai.tools import ToolRegistry, is_tool

logger = logging.getLogger("django_matt.ai.agents")


@dataclass
class AgentConfig:
    """Configuration for an Agent."""

    temperature: float = 0.7
    max_tokens: int = 2048
    max_iterations: int = 10
    model: str | None = None


@dataclass
class AgentResponse:
    """Response from an Agent.handle() call."""

    content: str
    usage: Usage | None = None
    model: str = ""
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    structured: Any | None = None
    messages: list[Message] = field(default_factory=list)


class Agent:
    """
    Base class for AI agents with tool dispatch.

    Subclass and configure via class attributes:

        class SupportAgent(Agent):
            system_prompt = "You are a helpful support agent."
            tools = [get_order, cancel_order]
            temperature = 0.3
            max_iterations = 5

        agent = SupportAgent(provider=get_provider("anthropic"))
        response = await agent.ahandle("Where is my order?")

    The agent automatically:
    1. Sends system_prompt + user message to the LLM
    2. If the LLM returns tool calls, executes them
    3. Feeds tool results back to the LLM
    4. Repeats until the LLM gives a final text response or max_iterations is hit
    """

    # Class-level configuration (override in subclass)
    system_prompt: str = ""
    tools: list = []
    temperature: float = 0.7
    max_tokens: int = 2048
    max_iterations: int = 10
    model: str | None = None
    output_schema: type[BaseModel] | None = None

    def __init__(
        self,
        provider: LLMProvider,
        *,
        system_prompt: str | None = None,
        tools: list | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
        model: str | None = None,
        output_schema: type[BaseModel] | None = None,
    ) -> None:
        self.provider = provider

        # Instance overrides take precedence over class attributes
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if tools is not None:
            self.tools = tools
        if temperature is not None:
            self.temperature = temperature
        if max_tokens is not None:
            self.max_tokens = max_tokens
        if max_iterations is not None:
            self.max_iterations = max_iterations
        if model is not None:
            self.model = model
        if output_schema is not None:
            self.output_schema = output_schema

        # Build tool registry
        self._registry = ToolRegistry()
        for t in self.tools:
            if is_tool(t):
                self._registry.register(t)

    async def ahandle(self, message: str) -> AgentResponse:
        """Handle a user message asynchronously. Main entry point."""
        messages = self._build_messages(message)
        tool_calls_made: list[dict[str, Any]] = []
        total_usage = Usage()

        # Structured output path (no tool loop)
        if self.output_schema is not None and len(self._registry) == 0:
            return await self._handle_structured(messages)

        # Tool dispatch loop
        tool_defs = self._registry.definitions if len(self._registry) > 0 else None

        for _iteration in range(self.max_iterations + 1):
            response = await self.provider.complete(
                messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=tool_defs,
            )

            total_usage = self._accumulate_usage(total_usage, response.usage)

            if not response.has_tool_calls:
                return AgentResponse(
                    content=response.content,
                    usage=total_usage,
                    model=response.model,
                    tool_calls_made=tool_calls_made,
                    messages=messages,
                )

            # Process tool calls
            # Append assistant message with tool calls
            messages.append(Message.assistant(
                response.content or "",
                tool_calls=[
                    {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": orjson.dumps(tc.arguments).decode()}}
                    for tc in response.tool_calls
                ],
            ))

            for tc in response.tool_calls:
                result = await self._execute_tool(tc)
                tool_calls_made.append({
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": result,
                })
                messages.append(Message.tool(
                    content=str(result),
                    tool_call_id=tc.id,
                ))

        # Hit max iterations — return last response content
        logger.warning(
            "Agent hit max_iterations (%d) for message: %s",
            self.max_iterations,
            message[:100],
        )
        return AgentResponse(
            content=response.content or "",
            usage=total_usage,
            model=response.model,
            tool_calls_made=tool_calls_made,
            messages=messages,
        )

    def handle(self, message: str) -> AgentResponse:
        """Synchronous wrapper for ahandle."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.ahandle(message))
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return loop.run_in_executor(pool, lambda: asyncio.run(self.ahandle(message)))

    async def _handle_structured(self, messages: list[Message]) -> AgentResponse:
        """Handle structured output without tool loop."""
        result = await self.provider.complete_structured(
            messages,
            response_model=self.output_schema,
            model=self.model,
            temperature=self.temperature,
        )
        return AgentResponse(
            content=result.model_dump_json() if isinstance(result, BaseModel) else str(result),
            structured=result,
            messages=messages,
        )

    async def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return the result as a string."""
        try:
            result = await self._registry.aexecute(tool_call.name, tool_call.arguments)
            return str(result) if not isinstance(result, str) else result
        except Exception as e:
            logger.error("Tool '%s' raised: %s", tool_call.name, e)
            return f"Error: {type(e).__name__}: {e}"

    def _build_messages(self, user_message: str) -> list[Message]:
        """Build the initial message list."""
        messages = []
        if self.system_prompt:
            messages.append(Message.system(self.system_prompt))
        messages.append(Message.user(user_message))
        return messages

    @staticmethod
    def _accumulate_usage(total: Usage, new: Usage | None) -> Usage:
        """Accumulate token usage."""
        if new is None:
            return total
        return Usage(
            prompt_tokens=total.prompt_tokens + new.prompt_tokens,
            completion_tokens=total.completion_tokens + new.completion_tokens,
            total_tokens=total.total_tokens + new.total_tokens,
        )


__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResponse",
]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ai_agents.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add django_matt/ai/agents.py tests/test_ai_agents.py
git commit -m "feat: add Agent base class with tool dispatch loop"
```

---

## Task 3: Conversation Persistence (ORM Models)

Django models for persisting agent conversations across requests/sessions.

**Files:**
- Create: `django_matt/ai/models.py`
- Create: `django_matt/ai/migrations/0001_initial.py` (auto-generated)
- Modify: `django_matt/ai/agents.py` (add conversation support)
- Test: `tests/test_ai_conversations.py`

**Step 1: Write the failing tests**

```python
# tests/test_ai_conversations.py
import pytest
from django_matt.ai.models import Conversation, ConversationMessage
from django_matt.ai.agents import Agent, AgentResponse
from django_matt.ai.base import CompletionResponse, Usage, Role
from unittest.mock import AsyncMock


@pytest.mark.django_db
class TestConversationModel:
    async def test_create_conversation(self):
        conv = await Conversation.objects.acreate(
            title="Test conversation",
            metadata={"agent": "SupportAgent"},
        )
        assert conv.id is not None
        assert conv.title == "Test conversation"
        assert conv.metadata == {"agent": "SupportAgent"}

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

    async def test_message_ordering(self):
        conv = await Conversation.objects.acreate(title="Test")
        await ConversationMessage.objects.acreate(conversation=conv, role="user", content="First")
        await ConversationMessage.objects.acreate(conversation=conv, role="assistant", content="Second")
        msgs = [m async for m in ConversationMessage.objects.filter(conversation=conv)]
        assert msgs[0].content == "First"
        assert msgs[1].content == "Second"

    async def test_conversation_message_count(self):
        conv = await Conversation.objects.acreate(title="Test")
        await ConversationMessage.objects.acreate(conversation=conv, role="user", content="Hi")
        await ConversationMessage.objects.acreate(conversation=conv, role="assistant", content="Hello")
        count = await ConversationMessage.objects.filter(conversation=conv).acount()
        assert count == 2

    async def test_conversation_with_user(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = await User.objects.acreate_user(username="testuser", password="pass")
        conv = await Conversation.objects.acreate(title="Test", user=user)
        assert conv.user_id == user.id

    async def test_tool_call_stored(self):
        conv = await Conversation.objects.acreate(title="Test")
        msg = await ConversationMessage.objects.acreate(
            conversation=conv,
            role="assistant",
            content="",
            tool_calls=[{"id": "tc1", "name": "get_order", "arguments": {"id": "123"}}],
        )
        await msg.arefresh_from_db()
        assert msg.tool_calls[0]["name"] == "get_order"

    async def test_tool_result_stored(self):
        conv = await Conversation.objects.acreate(title="Test")
        msg = await ConversationMessage.objects.acreate(
            conversation=conv,
            role="tool",
            content="shipped",
            tool_call_id="tc1",
        )
        assert msg.tool_call_id == "tc1"


@pytest.mark.django_db
class TestAgentWithConversation:
    @pytest.mark.asyncio
    async def test_agent_persists_conversation(self):
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=CompletionResponse(
            content="Hello!",
            usage=Usage(10, 5, 15),
        ))

        class MyAgent(Agent):
            system_prompt = "Be helpful."

        agent = MyAgent(provider=provider)
        conv = await agent.start_conversation(title="Test Chat")
        response = await agent.ahandle("Hi", conversation_id=conv.id)

        assert response.content == "Hello!"
        assert response.conversation_id == conv.id

        # Check messages persisted
        msgs = [m async for m in ConversationMessage.objects.filter(conversation=conv)]
        assert len(msgs) == 2  # user + assistant
        assert msgs[0].role == "user"
        assert msgs[0].content == "Hi"
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "Hello!"

    @pytest.mark.asyncio
    async def test_conversation_history_sent(self):
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value=CompletionResponse(content="OK"))

        class MyAgent(Agent):
            system_prompt = "Test"

        agent = MyAgent(provider=provider)
        conv = await agent.start_conversation()

        # First turn
        await agent.ahandle("Hello", conversation_id=conv.id)
        # Second turn
        await agent.ahandle("What did I say?", conversation_id=conv.id)

        # Second call should include history
        second_call_messages = provider.complete.call_args_list[1][0][0]
        # system + "Hello" + "OK" + "What did I say?"
        assert len(second_call_messages) == 4
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ai_conversations.py -v
```
Expected: FAIL (ImportError)

**Step 3: Implement models**

```python
# django_matt/ai/models.py
"""
ORM models for persistent AI conversations.

Provides Conversation and ConversationMessage models for storing
multi-turn agent interactions in the database.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
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
        ordering = ["-updated_at"]
        verbose_name = "AI Conversation"
        verbose_name_plural = "AI Conversations"

    def __str__(self) -> str:
        return self.title or f"Conversation {self.id}"


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
        Conversation,
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

    def to_message(self) -> "Message":
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
    "Conversation",
    "ConversationMessage",
]
```

**Step 4: Generate migration**

```bash
uv run python manage.py makemigrations django_matt --name ai_conversations
```

Note: This requires `django_matt` to be in `INSTALLED_APPS` and have proper app config. If the app doesn't support migrations directly, these models can be abstract/swappable. Adapt as needed for the project's migration strategy.

**Step 5: Update Agent class with conversation support**

Add these methods to the `Agent` class in `django_matt/ai/agents.py`:

```python
    async def start_conversation(
        self,
        title: str = "",
        user: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Conversation":
        """Create a new persistent conversation."""
        from django_matt.ai.models import Conversation

        return await Conversation.objects.acreate(
            title=title,
            user=user,
            agent_class=f"{type(self).__module__}.{type(self).__qualname__}",
            metadata=metadata or {},
        )
```

Update `ahandle()` signature to accept `conversation_id`:

```python
    async def ahandle(
        self,
        message: str,
        *,
        conversation_id: Any | None = None,
    ) -> AgentResponse:
```

Add conversation loading/saving logic inside `ahandle()`:
- If `conversation_id` is provided, load history from DB before building messages
- After getting response, persist user message + assistant message (and tool messages) to DB
- Set `response.conversation_id = conversation_id`

Add `conversation_id` field to `AgentResponse`:
```python
    conversation_id: Any | None = None
```

**Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_ai_conversations.py -v
```
Expected: ALL PASS

**Step 7: Commit**

```bash
git add django_matt/ai/models.py django_matt/ai/agents.py tests/test_ai_conversations.py
git commit -m "feat: add ORM-backed conversation persistence for AI agents"
```

---

## Task 4: FakeProvider for Testing

A deterministic provider for testing AI-powered code without real API calls.

**Files:**
- Create: `django_matt/ai/testing.py`
- Test: `tests/test_ai_testing.py`

**Step 1: Write the failing tests**

```python
# tests/test_ai_testing.py
import pytest
from pydantic import BaseModel
from django_matt.ai.testing import FakeProvider, FakeEmbeddingProvider
from django_matt.ai.base import Message, CompletionResponse, ToolCall, Usage
from django_matt.ai.tools import tool


class TestFakeProvider:
    @pytest.mark.asyncio
    async def test_returns_preset_responses(self):
        provider = FakeProvider(responses=["Hello!", "How can I help?"])
        r1 = await provider.complete([Message.user("Hi")])
        r2 = await provider.complete([Message.user("Help")])
        assert r1.content == "Hello!"
        assert r2.content == "How can I help?"

    @pytest.mark.asyncio
    async def test_cycles_responses(self):
        provider = FakeProvider(responses=["A", "B"])
        r1 = await provider.complete([Message.user("1")])
        r2 = await provider.complete([Message.user("2")])
        r3 = await provider.complete([Message.user("3")])
        assert r1.content == "A"
        assert r2.content == "B"
        assert r3.content == "A"  # cycles back

    @pytest.mark.asyncio
    async def test_returns_completion_response_directly(self):
        custom = CompletionResponse(
            content="Custom",
            tool_calls=[ToolCall(id="tc1", name="my_tool", arguments={"x": 1})],
        )
        provider = FakeProvider(responses=[custom])
        r = await provider.complete([Message.user("test")])
        assert r.content == "Custom"
        assert r.has_tool_calls

    @pytest.mark.asyncio
    async def test_records_calls(self):
        provider = FakeProvider(responses=["OK"])
        await provider.complete([Message.user("Hello")])
        assert len(provider.calls) == 1
        assert provider.calls[0]["messages"][0].content == "Hello"

    @pytest.mark.asyncio
    async def test_usage_tracking(self):
        provider = FakeProvider(responses=["OK"])
        r = await provider.complete([Message.user("Hi")])
        assert r.usage is not None
        assert r.usage.total_tokens > 0

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        provider = FakeProvider(responses=["Hello world"])
        chunks = []
        async for chunk in provider.stream([Message.user("Hi")]):
            chunks.append(chunk.content)
        assert "".join(chunks) == "Hello world"

    @pytest.mark.asyncio
    async def test_structured_output(self):
        class Person(BaseModel):
            name: str
            age: int

        provider = FakeProvider(responses=['{"name": "Alice", "age": 30}'])
        result = await provider.complete_structured(
            [Message.user("Extract")],
            response_model=Person,
        )
        assert result.name == "Alice"
        assert result.age == 30

    def test_assert_called(self):
        provider = FakeProvider(responses=["OK"])
        import asyncio
        asyncio.run(provider.complete([Message.user("Hello")]))
        provider.assert_called()

    def test_assert_called_with_message(self):
        provider = FakeProvider(responses=["OK"])
        import asyncio
        asyncio.run(provider.complete([Message.user("Hello world")]))
        provider.assert_called_with_message("Hello world")

    def test_assert_not_called(self):
        provider = FakeProvider(responses=["OK"])
        provider.assert_not_called()

    def test_assert_call_count(self):
        provider = FakeProvider(responses=["OK"])
        import asyncio
        asyncio.run(provider.complete([Message.user("1")]))
        asyncio.run(provider.complete([Message.user("2")]))
        provider.assert_call_count(2)

    def test_reset(self):
        provider = FakeProvider(responses=["OK"])
        import asyncio
        asyncio.run(provider.complete([Message.user("Hi")]))
        provider.reset()
        assert len(provider.calls) == 0


class TestFakeProviderWithAgent:
    @pytest.mark.asyncio
    async def test_agent_with_fake_provider(self):
        from django_matt.ai.agents import Agent
        from django_matt.ai.tools import tool

        @tool
        def get_price(item: str) -> str:
            """Get item price."""
            return "$9.99"

        provider = FakeProvider(responses=[
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="get_price", arguments={"item": "widget"})],
            ),
            "The widget costs $9.99.",
        ])

        class ShopAgent(Agent):
            system_prompt = "Help with shopping."
            tools = [get_price]

        agent = ShopAgent(provider=provider)
        response = await agent.ahandle("How much is a widget?")
        assert response.content == "The widget costs $9.99."
        assert len(response.tool_calls_made) == 1
        assert response.tool_calls_made[0]["result"] == "$9.99"


class TestFakeEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_returns_deterministic_embeddings(self):
        provider = FakeEmbeddingProvider(dimensions=4)
        embedding = await provider.embed_single("hello")
        assert len(embedding) == 4
        # Same input = same output
        embedding2 = await provider.embed_single("hello")
        assert embedding == embedding2

    @pytest.mark.asyncio
    async def test_different_inputs_different_embeddings(self):
        provider = FakeEmbeddingProvider(dimensions=4)
        e1 = await provider.embed_single("hello")
        e2 = await provider.embed_single("world")
        assert e1 != e2

    @pytest.mark.asyncio
    async def test_batch_embed(self):
        provider = FakeEmbeddingProvider(dimensions=3)
        embeddings = await provider.embed(["a", "b", "c"])
        assert len(embeddings) == 3
        assert all(len(e) == 3 for e in embeddings)
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ai_testing.py -v
```
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement `django_matt/ai/testing.py`**

```python
"""
Test utilities for AI-powered code.

Provides FakeProvider and FakeEmbeddingProvider for deterministic testing
of agent and LLM-powered features without real API calls.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import AsyncIterator
from typing import Any

import orjson
from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    EmbeddingProvider,
    LLMProvider,
    Message,
    StreamChunk,
    StructuredOutputProvider,
    ToolDefinition,
    Usage,
)


class FakeProvider(LLMProvider, StructuredOutputProvider):
    """
    Deterministic LLM provider for testing.

    Usage:
        provider = FakeProvider(responses=["Hello!", "How can I help?"])
        response = await provider.complete([Message.user("Hi")])
        assert response.content == "Hello!"

        # With tool calls
        from django_matt.ai.base import CompletionResponse, ToolCall
        provider = FakeProvider(responses=[
            CompletionResponse(content="", tool_calls=[ToolCall(...)]),
            "Final answer",
        ])

        # Assertions
        provider.assert_called()
        provider.assert_call_count(2)
        provider.assert_called_with_message("Hi")
    """

    def __init__(
        self,
        responses: list[str | CompletionResponse] | None = None,
        **kwargs: Any,
    ) -> None:
        self._responses = responses or ["OK"]
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []

    @property
    def default_model(self) -> str:
        return "fake-model"

    @property
    def provider_name(self) -> str:
        return "fake"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        self.calls.append({
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "kwargs": kwargs,
        })

        response_item = self._responses[self._call_index % len(self._responses)]
        self._call_index += 1

        if isinstance(response_item, CompletionResponse):
            return response_item

        # Estimate tokens from content length
        total_chars = sum(len(m.content) for m in messages) + len(response_item)
        est_tokens = max(total_chars // 4, 1)

        return CompletionResponse(
            content=response_item,
            model=model or self.default_model,
            finish_reason="stop",
            usage=Usage(
                prompt_tokens=est_tokens // 2,
                completion_tokens=est_tokens // 2,
                total_tokens=est_tokens,
            ),
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        response = await self.complete(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, tools=tools, **kwargs,
        )
        # Yield content word by word
        words = response.content.split(" ") if response.content else [""]
        for i, word in enumerate(words):
            suffix = " " if i < len(words) - 1 else ""
            yield StreamChunk(content=word + suffix)
        yield StreamChunk(finish_reason="stop")

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[BaseModel],
        *,
        model: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        response = await self.complete(
            messages, model=model, temperature=temperature, **kwargs,
        )
        return response_model.model_validate_json(response.content)

    # ---- Assertion helpers ----

    def assert_called(self) -> None:
        """Assert the provider was called at least once."""
        assert len(self.calls) > 0, "FakeProvider was never called"

    def assert_not_called(self) -> None:
        """Assert the provider was never called."""
        assert len(self.calls) == 0, f"FakeProvider was called {len(self.calls)} time(s)"

    def assert_call_count(self, expected: int) -> None:
        """Assert the provider was called exactly N times."""
        actual = len(self.calls)
        assert actual == expected, f"Expected {expected} calls, got {actual}"

    def assert_called_with_message(self, content: str) -> None:
        """Assert any call included a message with the given content."""
        for call in self.calls:
            for msg in call["messages"]:
                if msg.content == content:
                    return
        raise AssertionError(
            f"No call contained message with content: {content!r}"
        )

    def reset(self) -> None:
        """Reset call history and response index."""
        self.calls.clear()
        self._call_index = 0


class FakeEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic embedding provider for testing.

    Generates consistent, hash-based embeddings so the same input
    always produces the same vector. Different inputs produce different vectors.

    Usage:
        provider = FakeEmbeddingProvider(dimensions=384)
        embedding = await provider.embed_single("hello")
        assert len(embedding) == 384
    """

    def __init__(self, dimensions: int = 384, **kwargs: Any) -> None:
        self._dimensions = dimensions

    @property
    def default_model(self) -> str:
        return "fake-embedding"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [self._hash_to_vector(text) for text in texts]

    async def embed_single(self, text: str, **kwargs: Any) -> list[float]:
        return self._hash_to_vector(text)

    def _hash_to_vector(self, text: str) -> list[float]:
        """Generate a deterministic vector from text using SHA-256."""
        h = hashlib.sha256(text.encode()).digest()
        # Extend hash to fill dimensions
        extended = h * ((self._dimensions * 4 // len(h)) + 1)
        floats = []
        for i in range(self._dimensions):
            raw = struct.unpack("f", extended[i * 4 : (i + 1) * 4])[0]
            # Normalize to [-1, 1] range
            floats.append(max(-1.0, min(1.0, raw % 2 - 1)))
        return floats


__all__ = [
    "FakeEmbeddingProvider",
    "FakeProvider",
]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_ai_testing.py -v
```
Expected: ALL PASS

**Step 5: Commit**

```bash
git add django_matt/ai/testing.py tests/test_ai_testing.py
git commit -m "feat: add FakeProvider and FakeEmbeddingProvider for testing AI code"
```

---

## Task 5: Observability Hooks

Pluggable tracing/logging for all agent calls — supports LangSmith, Langfuse, OpenTelemetry, and custom backends.

**Files:**
- Create: `django_matt/ai/observability.py`
- Modify: `django_matt/ai/agents.py` (emit hooks)
- Test: `tests/test_ai_observability.py`

**Step 1: Write the failing tests**

```python
# tests/test_ai_observability.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from django_matt.ai.observability import (
    ObservabilityHook,
    LoggingHook,
    CallbackHook,
    CompositeHook,
    AgentEvent,
    EventType,
)
from django_matt.ai.base import Message, CompletionResponse, Usage, ToolCall


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
        events = []

        async def on_event(event: AgentEvent) -> None:
            events.append(event)

        hook = CallbackHook(on_event)
        await hook.on_event(AgentEvent(
            event_type=EventType.AGENT_START,
            agent_class="Test",
        ))

        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_START

    @pytest.mark.asyncio
    async def test_sync_callback_accepted(self):
        events = []

        def on_event(event: AgentEvent) -> None:
            events.append(event)

        hook = CallbackHook(on_event)
        await hook.on_event(AgentEvent(
            event_type=EventType.AGENT_END,
            agent_class="Test",
        ))

        assert len(events) == 1


class TestCompositeHook:
    @pytest.mark.asyncio
    async def test_dispatches_to_all_hooks(self):
        events_a = []
        events_b = []

        hook = CompositeHook([
            CallbackHook(lambda e: events_a.append(e)),
            CallbackHook(lambda e: events_b.append(e)),
        ])

        await hook.on_event(AgentEvent(
            event_type=EventType.AGENT_START,
            agent_class="Test",
        ))

        assert len(events_a) == 1
        assert len(events_b) == 1

    @pytest.mark.asyncio
    async def test_one_failing_hook_doesnt_break_others(self):
        events = []

        def bad_hook(e):
            raise RuntimeError("oops")

        hook = CompositeHook([
            CallbackHook(bad_hook),
            CallbackHook(lambda e: events.append(e)),
        ])

        await hook.on_event(AgentEvent(
            event_type=EventType.AGENT_START,
            agent_class="Test",
        ))

        # Second hook still received the event
        assert len(events) == 1


class TestLoggingHook:
    @pytest.mark.asyncio
    async def test_logs_events(self, caplog):
        import logging
        hook = LoggingHook(level=logging.INFO)

        with caplog.at_level(logging.INFO, logger="django_matt.ai.observability"):
            await hook.on_event(AgentEvent(
                event_type=EventType.AGENT_START,
                agent_class="TestAgent",
                data={"message": "Hello"},
            ))

        assert "AGENT_START" in caplog.text
        assert "TestAgent" in caplog.text


class TestAgentObservability:
    @pytest.mark.asyncio
    async def test_agent_emits_events(self):
        from django_matt.ai.agents import Agent
        from django_matt.ai.testing import FakeProvider

        events = []
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
        from django_matt.ai.tools import tool
        from django_matt.ai.testing import FakeProvider

        events = []
        hook = CallbackHook(lambda e: events.append(e))

        @tool
        def my_tool() -> str:
            """A tool."""
            return "result"

        provider = FakeProvider(responses=[
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="my_tool", arguments={})],
            ),
            "Done.",
        ])

        class MyAgent(Agent):
            system_prompt = "Test"
            tools = [my_tool]
            hooks = [hook]

        agent = MyAgent(provider=provider)
        await agent.ahandle("Go")

        event_types = [e.event_type for e in events]
        assert EventType.TOOL_CALL_START in event_types
        assert EventType.TOOL_CALL_END in event_types
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ai_observability.py -v
```
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement `django_matt/ai/observability.py`**

```python
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
```

**Step 4: Update Agent class to emit events**

Add `hooks` class attribute and `_emit` method to `Agent` in `django_matt/ai/agents.py`:

```python
    # Class-level (add to existing class attributes)
    hooks: list = []

    # In __init__, add:
    if hooks is not None:
        self.hooks = hooks
    self._hook = CompositeHook([
        h if isinstance(h, ObservabilityHook) else CallbackHook(h)
        for h in self.hooks
    ]) if self.hooks else None

    # Helper method
    async def _emit(self, event_type: EventType, **data: Any) -> None:
        if self._hook:
            await self._hook.on_event(AgentEvent(
                event_type=event_type,
                agent_class=f"{type(self).__module__}.{type(self).__qualname__}",
                data=data,
            ))
```

Then instrument `ahandle()`:
- Emit `AGENT_START` at the top
- Emit `LLM_CALL_START` / `LLM_CALL_END` around `provider.complete()`
- Emit `TOOL_CALL_START` / `TOOL_CALL_END` / `TOOL_ERROR` around tool execution
- Emit `AGENT_END` before returning
- Emit `MAX_ITERATIONS` when the guard triggers

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_ai_observability.py -v
```
Expected: ALL PASS

**Step 6: Commit**

```bash
git add django_matt/ai/observability.py django_matt/ai/agents.py tests/test_ai_observability.py
git commit -m "feat: add observability hooks for AI agent tracing"
```

---

## Task 6: Wire Exports and Update `__init__.py`

Export all new symbols from `django_matt/ai/__init__.py`.

**Files:**
- Modify: `django_matt/ai/__init__.py`
- Test: `tests/test_ai_exports.py`

**Step 1: Write the failing test**

```python
# tests/test_ai_exports.py
def test_agent_exports():
    from django_matt.ai import Agent, AgentResponse, AgentConfig
    assert Agent is not None
    assert AgentResponse is not None
    assert AgentConfig is not None

def test_tool_exports():
    from django_matt.ai import tool, ToolRegistry, is_tool
    assert tool is not None
    assert ToolRegistry is not None
    assert is_tool is not None

def test_testing_exports():
    from django_matt.ai.testing import FakeProvider, FakeEmbeddingProvider
    assert FakeProvider is not None
    assert FakeEmbeddingProvider is not None

def test_observability_exports():
    from django_matt.ai import (
        ObservabilityHook, CallbackHook, LoggingHook,
        CompositeHook, AgentEvent, EventType,
    )
    assert ObservabilityHook is not None
    assert EventType.AGENT_START is not None

def test_conversation_model_exports():
    from django_matt.ai.models import Conversation, ConversationMessage
    assert Conversation is not None
    assert ConversationMessage is not None
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ai_exports.py -v
```

**Step 3: Add imports to `django_matt/ai/__init__.py`**

Add these import blocks after the existing imports:

```python
# Agents
from django_matt.ai.agents import Agent, AgentConfig, AgentResponse

# Tools
from django_matt.ai.tools import ToolRegistry, is_tool, tool

# Observability
from django_matt.ai.observability import (
    AgentEvent,
    CallbackHook,
    CompositeHook,
    EventType,
    LoggingHook,
    ObservabilityHook,
)
```

Add to `__all__`:

```python
    # Agents
    "Agent",
    "AgentConfig",
    "AgentResponse",
    # Tools
    "tool",
    "ToolRegistry",
    "is_tool",
    # Observability
    "ObservabilityHook",
    "CallbackHook",
    "CompositeHook",
    "LoggingHook",
    "AgentEvent",
    "EventType",
```

Note: `FakeProvider` and `FakeEmbeddingProvider` are intentionally NOT exported from `django_matt.ai` — they live in `django_matt.ai.testing` to keep test deps separate from production code.

**Step 4: Run tests**

```bash
uv run pytest tests/test_ai_exports.py -v
```
Expected: ALL PASS

**Step 5: Run full AI test suite to verify nothing broke**

```bash
uv run pytest tests/test_ai*.py -v
```
Expected: ALL PASS

**Step 6: Commit**

```bash
git add django_matt/ai/__init__.py tests/test_ai_exports.py
git commit -m "feat: export agent framework from django_matt.ai"
```

---

## Task 7: Integration Test — End-to-End Agent

A full integration test proving all pieces work together.

**Files:**
- Test: `tests/test_ai_agent_integration.py`

**Step 1: Write the integration test**

```python
# tests/test_ai_agent_integration.py
"""End-to-end integration test for the Agent framework."""
import pytest
from pydantic import BaseModel

from django_matt.ai import Agent, tool, AgentResponse, EventType
from django_matt.ai.testing import FakeProvider
from django_matt.ai.observability import CallbackHook, AgentEvent
from django_matt.ai.base import CompletionResponse, ToolCall, Usage


# ---- Tools ----

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


# ---- Agent ----

class SupportAgent(Agent):
    system_prompt = (
        "You are a customer support agent. Use tools to look up "
        "information before answering. Be concise."
    )
    tools = [get_customer, get_order_status, cancel_order]
    temperature = 0.0
    max_iterations = 5


class TestEndToEndAgent:
    @pytest.mark.asyncio
    async def test_simple_query(self):
        """Agent answers a simple question with one tool call."""
        provider = FakeProvider(responses=[
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="get_order_status", arguments={"order_id": "O100"})],
                usage=Usage(50, 10, 60),
            ),
            CompletionResponse(
                content="Order O100 has been shipped.",
                usage=Usage(80, 15, 95),
            ),
        ])

        agent = SupportAgent(provider=provider)
        response = await agent.ahandle("What's the status of order O100?")

        assert response.content == "Order O100 has been shipped."
        assert len(response.tool_calls_made) == 1
        assert response.tool_calls_made[0]["name"] == "get_order_status"
        assert response.tool_calls_made[0]["result"] == "shipped"
        assert response.usage.total_tokens == 155

    @pytest.mark.asyncio
    async def test_multi_step_workflow(self):
        """Agent chains multiple tool calls."""
        provider = FakeProvider(responses=[
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="get_customer", arguments={"customer_id": "C001"})],
            ),
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc2", name="get_order_status", arguments={"order_id": "O200"})],
            ),
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc3", name="cancel_order", arguments={"order_id": "O200"})],
            ),
            CompletionResponse(
                content="Hi Alice, I've cancelled order O200 which was still processing.",
            ),
        ])

        agent = SupportAgent(provider=provider)
        response = await agent.ahandle("I'm customer C001, cancel my order O200")

        assert "cancelled" in response.content.lower()
        assert len(response.tool_calls_made) == 3
        tool_names = [tc["name"] for tc in response.tool_calls_made]
        assert tool_names == ["get_customer", "get_order_status", "cancel_order"]

    @pytest.mark.asyncio
    async def test_with_observability(self):
        """Agent emits events that observability hooks can capture."""
        events: list[AgentEvent] = []
        hook = CallbackHook(lambda e: events.append(e))

        provider = FakeProvider(responses=[
            CompletionResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="get_order_status", arguments={"order_id": "O100"})],
            ),
            "Shipped.",
        ])

        agent = SupportAgent(provider=provider, hooks=[hook])
        await agent.ahandle("Status of O100?")

        event_types = [e.event_type for e in events]
        assert EventType.AGENT_START in event_types
        assert EventType.LLM_CALL_START in event_types
        assert EventType.LLM_CALL_END in event_types
        assert EventType.TOOL_CALL_START in event_types
        assert EventType.TOOL_CALL_END in event_types
        assert EventType.AGENT_END in event_types

    @pytest.mark.asyncio
    async def test_structured_output_agent(self):
        """Agent with output_schema returns validated Pydantic model."""

        class OrderInfo(BaseModel):
            order_id: str
            status: str
            customer: str

        provider = FakeProvider(responses=[
            '{"order_id": "O100", "status": "shipped", "customer": "Alice"}'
        ])
        provider.complete_structured = provider.complete_structured  # Uses built-in

        class InfoAgent(Agent):
            system_prompt = "Extract order info."
            output_schema = OrderInfo

        agent = InfoAgent(provider=provider)
        response = await agent.ahandle("Order O100 for Alice, shipped")

        assert response.structured is not None
        assert response.structured.order_id == "O100"
        assert response.structured.status == "shipped"

    @pytest.mark.asyncio
    async def test_fake_provider_assertions(self):
        """FakeProvider assertion helpers work end-to-end."""
        provider = FakeProvider(responses=["Hi there!"])

        agent = SupportAgent(provider=provider)
        await agent.ahandle("Hello")

        provider.assert_called()
        provider.assert_call_count(1)
        provider.assert_called_with_message("Hello")
```

**Step 2: Run the integration test**

```bash
uv run pytest tests/test_ai_agent_integration.py -v
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_ai_agent_integration.py
git commit -m "test: add end-to-end integration tests for agent framework"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | `@tool` decorator + `ToolRegistry` | `django_matt/ai/tools.py` | `tests/test_ai_tools.py` |
| 2 | `Agent` class + dispatch loop | `django_matt/ai/agents.py` | `tests/test_ai_agents.py` |
| 3 | `Conversation` + `ConversationMessage` ORM | `django_matt/ai/models.py` | `tests/test_ai_conversations.py` |
| 4 | `FakeProvider` + `FakeEmbeddingProvider` | `django_matt/ai/testing.py` | `tests/test_ai_testing.py` |
| 5 | Observability hooks + events | `django_matt/ai/observability.py` | `tests/test_ai_observability.py` |
| 6 | Wire exports in `__init__.py` | `django_matt/ai/__init__.py` | `tests/test_ai_exports.py` |
| 7 | End-to-end integration test | — | `tests/test_ai_agent_integration.py` |

**Dependency order:** Task 1 -> Task 2 -> Task 3 (depends on 2) -> Task 4 (independent) -> Task 5 (depends on 2) -> Task 6 (depends on all) -> Task 7 (depends on all)

Tasks 3, 4, and 5 can be parallelized after Task 2 is complete.
