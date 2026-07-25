# file-length-max: 500
"""
Together AI provider implementation.

Supports a wide variety of open-source models including LLaMA, Mistral, and more.
"""

import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import orjson
from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    EmbeddingProvider,
    EmbeddingResponse,
    LLMProvider,
    Message,
    Role,
    StreamChunk,
    StructuredOutputProvider,
    ToolCall,
    ToolDefinition,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class TogetherProvider(LLMProvider, StructuredOutputProvider):
    """
    Together AI LLM provider.

    Provides access to many open-source models with competitive pricing.

    Usage:
        from django_matt.ai import TogetherProvider, Message

        llm = TogetherProvider(api_key="...")
        # Or use TOGETHER_API_KEY env var

        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ])
        print(response.content)

        # Use specific models
        llm = TogetherProvider(model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")

        # Streaming
        async for chunk in llm.stream([Message.user("Tell me a story")]):
            print(chunk.content, end="", flush=True)
    """

    # Popular models on Together AI
    MODELS = {
        "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": "LLaMA 3.1 405B",
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": "LLaMA 3.1 70B",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": "LLaMA 3.1 8B",
        "mistralai/Mixtral-8x22B-Instruct-v0.1": "Mixtral 8x22B",
        "mistralai/Mistral-7B-Instruct-v0.3": "Mistral 7B",
        "Qwen/Qwen2.5-72B-Instruct-Turbo": "Qwen 2.5 72B",
        "deepseek-ai/deepseek-llm-67b-chat": "DeepSeek 67B",
        "databricks/dbrx-instruct": "DBRX",
    }

    @property
    def default_model(self) -> str:
        return "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"

    @property
    def provider_name(self) -> str:
        return "together"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("Together API key required. Pass api_key or set TOGETHER_API_KEY.")

        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.together.xyz/v1",
            **kwargs,
        )
        self._client = None

    def _get_client(self):
        """Get or create the HTTP client."""
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError(
                    "httpx is required for Together provider. Install with: uv add httpx"
                )

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to OpenAI-compatible format."""
        result = []
        for msg in messages:
            d = {"role": msg.role.value, "content": msg.content}
            if msg.name:
                d["name"] = msg.name
            if msg.tool_call_id:
                d["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                d["tool_calls"] = msg.tool_calls
            result.append(d)
        return result

    def _convert_tools(self, tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
        """Convert tools to OpenAI format."""
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """Generate a completion."""
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        payload.update(kwargs)

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        # Parse tool calls if present
        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc.get("id", f"call_{i}"),
                    name=tc["function"]["name"],
                    arguments=orjson.loads(tc["function"]["arguments"]),
                )
                for i, tc in enumerate(message["tool_calls"])
            ]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"]["prompt_tokens"],
                completion_tokens=data["usage"]["completion_tokens"],
                total_tokens=data["usage"]["total_tokens"],
            )

        return CompletionResponse(
            content=message.get("content", ""),
            role=Role.ASSISTANT,
            model=data.get("model", model or self.model),
            finish_reason=choice.get("finish_reason"),
            tool_calls=tool_calls,
            usage=usage,
            raw_response=data,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion."""
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        payload.update(kwargs)

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or line == "data: [DONE]":
                    continue

                if line.startswith("data: "):
                    data = orjson.loads(line[6:])
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})

                    yield StreamChunk(
                        content=delta.get("content", ""),
                        role=Role(delta["role"]) if "role" in delta else None,
                        finish_reason=choice.get("finish_reason"),
                    )

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        **kwargs,
    ) -> T:
        """Generate a structured response matching the Pydantic model."""
        schema = response_model.model_json_schema()
        schema_str = orjson.dumps(schema, option=orjson.OPT_INDENT_2).decode()

        system_msg = Message.system(
            f"You must respond with valid JSON matching this schema:\n{schema_str}\n"
            "Do not include any other text, only the JSON object."
        )

        augmented_messages = [system_msg] + messages

        for attempt in range(max_retries):
            try:
                response = await self.complete(
                    augmented_messages,
                    model=model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                data = orjson.loads(response.content)
                return response_model.model_validate(data)

            except (orjson.JSONDecodeError, Exception) as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )
                augmented_messages.append(
                    Message.assistant(response.content if "response" in dir() else "")
                )
                augmented_messages.append(
                    Message.user(f"That was invalid. Error: {e}. Please try again with valid JSON.")
                )

    @classmethod
    def list_models(cls) -> dict[str, str]:
        """List popular Together AI models."""
        return cls.MODELS.copy()


class TogetherEmbeddings(EmbeddingProvider):
    """
    Together AI embedding provider.

    Usage:
        from django_matt.ai import TogetherEmbeddings

        embedder = TogetherEmbeddings(api_key="...")

        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings
    """

    DIMENSIONS = {
        "togethercomputer/m2-bert-80M-8k-retrieval": 768,
        "togethercomputer/m2-bert-80M-32k-retrieval": 768,
        "BAAI/bge-large-en-v1.5": 1024,
        "BAAI/bge-base-en-v1.5": 768,
    }

    @property
    def default_model(self) -> str:
        return "BAAI/bge-large-en-v1.5"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS.get(self.model, 1024)

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("Together API key required. Pass api_key or set TOGETHER_API_KEY.")

        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = base_url or "https://api.together.xyz/v1"
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError("httpx is required. Install with: uv add httpx")

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """Generate embeddings for texts."""
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "input": texts,
        }

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        embeddings = [item["embedding"] for item in data["data"]]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"].get("prompt_tokens", 0),
                total_tokens=data["usage"].get("total_tokens", 0),
            )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=data.get("model", model or self.model),
            usage=usage,
        )


__all__ = [
    "TogetherEmbeddings",
    "TogetherProvider",
]
