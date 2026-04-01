import pytest

from django_matt.ai.tools import ToolRegistry, tool


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
