"""
Cohere provider implementation.

Supports Command R, Command R+, and other Cohere models.
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


class CohereProvider(LLMProvider, StructuredOutputProvider):
    """
    Cohere LLM provider.

    Supports Command R+, Command R, and other Cohere models.

    Usage:
        from django_matt.ai import CohereProvider, Message

        llm = CohereProvider(api_key="...")
        # Or use COHERE_API_KEY env var

        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ])
        print(response.content)

        # Streaming
        async for chunk in llm.stream([Message.user("Tell me a story")]):
            print(chunk.content, end="", flush=True)
    """

    @property
    def default_model(self) -> str:
        return "command-r-plus"

    @property
    def provider_name(self) -> str:
        return "cohere"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise ValueError("Cohere API key required. Pass api_key or set COHERE_API_KEY.")

        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.cohere.ai/v1",
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
                    "httpx is required for Cohere provider. Install with: uv add httpx"
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

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]], str]:
        """
        Convert messages to Cohere format.

        Cohere uses a different format with preamble (system), chat_history, and message.
        Returns (preamble, chat_history, message)
        """
        preamble = None
        chat_history = []
        last_user_message = ""

        for i, msg in enumerate(messages):
            if msg.role == Role.SYSTEM:
                preamble = msg.content
            elif msg.role == Role.USER:
                if i == len(messages) - 1:
                    last_user_message = msg.content
                else:
                    chat_history.append({"role": "USER", "message": msg.content})
            elif msg.role == Role.ASSISTANT:
                chat_history.append({"role": "CHATBOT", "message": msg.content})
            elif msg.role == Role.TOOL:
                chat_history.append(
                    {
                        "role": "TOOL",
                        "tool_results": [
                            {
                                "call": {"name": "tool"},
                                "outputs": [{"result": msg.content}],
                            }
                        ],
                    }
                )

        return preamble, chat_history, last_user_message

    def _convert_tools(self, tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
        """Convert tools to Cohere format."""
        if not tools:
            return None
        result = []
        for tool in tools:
            params = tool.parameters.get("properties", {})
            required = tool.parameters.get("required", [])
            param_defs = []
            for name, prop in params.items():
                param_defs.append(
                    {
                        "name": name,
                        "description": prop.get("description", ""),
                        "type": prop.get("type", "string"),
                        "required": name in required,
                    }
                )
            result.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameter_definitions": param_defs,
                }
            )
        return result

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

        preamble, chat_history, message = self._convert_messages(messages)

        payload = {
            "model": model or self.model,
            "message": message,
            "temperature": temperature,
        }

        if preamble:
            payload["preamble"] = preamble
        if chat_history:
            payload["chat_history"] = chat_history
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop_sequences"] = stop

        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools

        payload.update(kwargs)

        response = await client.post("/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        # Parse tool calls if present
        tool_calls = None
        if data.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=f"call_{i}",
                    name=tc["name"],
                    arguments=tc.get("parameters", {}),
                )
                for i, tc in enumerate(data["tool_calls"])
            ]

        usage = None
        if "meta" in data and "tokens" in data["meta"]:
            tokens = data["meta"]["tokens"]
            usage = Usage(
                prompt_tokens=tokens.get("input_tokens", 0),
                completion_tokens=tokens.get("output_tokens", 0),
                total_tokens=tokens.get("input_tokens", 0) + tokens.get("output_tokens", 0),
            )

        return CompletionResponse(
            content=data.get("text", ""),
            role=Role.ASSISTANT,
            model=model or self.model,
            finish_reason=data.get("finish_reason"),
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

        preamble, chat_history, message = self._convert_messages(messages)

        payload = {
            "model": model or self.model,
            "message": message,
            "temperature": temperature,
            "stream": True,
        }

        if preamble:
            payload["preamble"] = preamble
        if chat_history:
            payload["chat_history"] = chat_history
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop_sequences"] = stop

        payload.update(kwargs)

        async with client.stream("POST", "/chat", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                try:
                    data = orjson.loads(line)
                    event_type = data.get("event_type")

                    if event_type == "text-generation":
                        yield StreamChunk(content=data.get("text", ""))
                    elif event_type == "stream-end":
                        yield StreamChunk(finish_reason=data.get("finish_reason"))

                except orjson.JSONDecodeError:
                    continue

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

        tool = ToolDefinition(
            name="extract_data",
            description=f"Extract structured data matching the {response_model.__name__} schema",
            parameters=schema,
        )

        for attempt in range(max_retries):
            try:
                response = await self.complete(
                    messages,
                    model=model,
                    temperature=temperature,
                    tools=[tool],
                    **kwargs,
                )

                if response.tool_calls:
                    data = response.tool_calls[0].arguments
                    return response_model.model_validate(data)

                raise ValueError("No tool call in response")

            except Exception as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )


class CohereEmbeddings(EmbeddingProvider):
    """
    Cohere embedding provider.

    Supports embed-english-v3.0, embed-multilingual-v3.0, and other models.

    Usage:
        from django_matt.ai import CohereEmbeddings

        embedder = CohereEmbeddings(api_key="...")

        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings
    """

    DIMENSIONS = {
        "embed-english-v3.0": 1024,
        "embed-multilingual-v3.0": 1024,
        "embed-english-light-v3.0": 384,
        "embed-multilingual-light-v3.0": 384,
    }

    @property
    def default_model(self) -> str:
        return "embed-english-v3.0"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS.get(self.model, 1024)

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        input_type: str = "search_document",
        **kwargs,
    ):
        """
        Initialize Cohere embeddings.

        Args:
            api_key: Cohere API key
            model: Embedding model
            base_url: API base URL
            input_type: Type of input - "search_document", "search_query",
                       "classification", or "clustering"
        """
        api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise ValueError("Cohere API key required. Pass api_key or set COHERE_API_KEY.")

        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = base_url or "https://api.cohere.ai/v1"
        self.input_type = input_type
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
        input_type: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """Generate embeddings for texts."""
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "texts": texts,
            "input_type": input_type or self.input_type,
        }

        response = await client.post("/embed", json=payload)
        response.raise_for_status()
        data = response.json()

        usage = None
        if "meta" in data and "billed_units" in data["meta"]:
            usage = Usage(
                prompt_tokens=data["meta"]["billed_units"].get("input_tokens", 0),
                total_tokens=data["meta"]["billed_units"].get("input_tokens", 0),
            )

        return EmbeddingResponse(
            embeddings=data["embeddings"],
            model=data.get("model", model or self.model),
            usage=usage,
        )


__all__ = [
    "CohereEmbeddings",
    "CohereProvider",
]
