"""
OpenAI provider implementation.

Supports GPT-4, GPT-3.5-turbo, and embedding models.
"""

import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional, Type, TypeVar

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


class OpenAIProvider(LLMProvider, StructuredOutputProvider):
    """
    OpenAI LLM provider.

    Supports GPT-4o, GPT-4, GPT-3.5-turbo and other OpenAI models.

    Usage:
        from django_matt.ai import OpenAIProvider, Message

        llm = OpenAIProvider(api_key="sk-...")
        # Or use OPENAI_API_KEY env var

        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ])
        print(response.content)

        # Streaming
        async for chunk in llm.stream([Message.user("Tell me a story")]):
            print(chunk.content, end="", flush=True)

        # Structured output
        class Person(BaseModel):
            name: str
            age: int

        person = await llm.complete_structured(
            [Message.user("Extract: John is 30 years old")],
            response_model=Person,
        )
    """

    @property
    def default_model(self) -> str:
        return "gpt-4o"

    @property
    def provider_name(self) -> str:
        return "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Pass api_key or set OPENAI_API_KEY."
            )

        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.openai.com/v1",
            **kwargs,
        )
        self.organization = organization or os.environ.get("OPENAI_ORGANIZATION")
        self._client = None

    def _get_client(self):
        """Get or create the HTTP client."""
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError(
                    "httpx is required for OpenAI provider. "
                    "Install with: pip install httpx"
                )

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            if self.organization:
                headers["OpenAI-Organization"] = self.organization

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to OpenAI format."""
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

    def _convert_tools(
        self, tools: Optional[List[ToolDefinition]]
    ) -> Optional[List[Dict[str, Any]]]:
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
        messages: List[Message],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[str] = None,
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
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                )
                for tc in message["tool_calls"]
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
        messages: List[Message],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
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
                    data = json.loads(line[6:])
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})

                    yield StreamChunk(
                        content=delta.get("content", ""),
                        role=Role(delta["role"]) if "role" in delta else None,
                        finish_reason=choice.get("finish_reason"),
                    )

    async def complete_structured(
        self,
        messages: List[Message],
        response_model: Type[T],
        *,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        **kwargs,
    ) -> T:
        """Generate a structured response matching the Pydantic model."""
        # Add JSON mode instruction
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)

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

                # Parse and validate
                data = json.loads(response.content)
                return response_model.model_validate(data)

            except (json.JSONDecodeError, Exception) as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )
                # Add error context for retry
                augmented_messages.append(
                    Message.assistant(response.content if 'response' in dir() else "")
                )
                augmented_messages.append(
                    Message.user(f"That was invalid. Error: {e}. Please try again with valid JSON.")
                )


class OpenAIEmbeddings(EmbeddingProvider):
    """
    OpenAI embedding provider.

    Supports text-embedding-3-small, text-embedding-3-large, and ada-002.

    Usage:
        from django_matt.ai import OpenAIEmbeddings

        embedder = OpenAIEmbeddings(api_key="sk-...")

        # Embed multiple texts
        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings

        # Embed single text
        vector = await embedder.embed_single("Hello world")
    """

    DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    @property
    def default_model(self) -> str:
        return "text-embedding-3-small"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS.get(self.model, 1536)

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Pass api_key or set OPENAI_API_KEY."
            )

        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = base_url or "https://api.openai.com/v1"
        self._dimensions = dimensions
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError("httpx is required. Install with: pip install httpx")

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
        texts: List[str],
        *,
        model: Optional[str] = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """Generate embeddings for texts."""
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "input": texts,
        }

        # Support dimension reduction for text-embedding-3 models
        if self._dimensions and "text-embedding-3" in (model or self.model):
            payload["dimensions"] = self._dimensions

        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        embeddings = [item["embedding"] for item in data["data"]]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"]["prompt_tokens"],
                total_tokens=data["usage"]["total_tokens"],
            )

        return EmbeddingResponse(
            embeddings=embeddings,
            model=data.get("model", model or self.model),
            usage=usage,
        )


__all__ = [
    "OpenAIProvider",
    "OpenAIEmbeddings",
]
