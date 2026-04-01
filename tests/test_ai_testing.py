import pytest
from pydantic import BaseModel

from django_matt.ai.base import CompletionResponse, Message, ToolCall, Usage
from django_matt.ai.testing import FakeEmbeddingProvider, FakeProvider


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
        assert r3.content == "A"

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
            if chunk.content:
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

    @pytest.mark.asyncio
    async def test_assert_called(self):
        provider = FakeProvider(responses=["OK"])
        await provider.complete([Message.user("Hello")])
        provider.assert_called()

    @pytest.mark.asyncio
    async def test_assert_called_with_message(self):
        provider = FakeProvider(responses=["OK"])
        await provider.complete([Message.user("Hello world")])
        provider.assert_called_with_message("Hello world")

    def test_assert_not_called(self):
        provider = FakeProvider(responses=["OK"])
        provider.assert_not_called()

    @pytest.mark.asyncio
    async def test_assert_call_count(self):
        provider = FakeProvider(responses=["OK"])
        await provider.complete([Message.user("1")])
        await provider.complete([Message.user("2")])
        provider.assert_call_count(2)

    @pytest.mark.asyncio
    async def test_reset(self):
        provider = FakeProvider(responses=["OK"])
        await provider.complete([Message.user("Hi")])
        provider.reset()
        assert len(provider.calls) == 0


class TestFakeEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_returns_deterministic_embeddings(self):
        provider = FakeEmbeddingProvider(dimensions=4)
        embedding = await provider.embed_single("hello")
        assert len(embedding) == 4
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
        response = await provider.embed(["a", "b", "c"])
        assert len(response.embeddings) == 3
        assert all(len(e) == 3 for e in response.embeddings)
