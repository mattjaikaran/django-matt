"""
Ollama provider implementation.

Supports local LLMs via Ollama including Llama, Mistral, CodeLlama, etc.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

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


class OllamaProvider(LLMProvider, StructuredOutputProvider):
    """
    Ollama LLM provider for local models.

    Supports any model available in Ollama (Llama 3, Mistral, CodeLlama, etc.)

    Usage:
        from django_matt.ai import OllamaProvider, Message

        # Ensure Ollama is running: ollama serve
        llm = OllamaProvider(model="llama3.2")

        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ])
        print(response.content)

        # Streaming
        async for chunk in llm.stream([Message.user("Tell me a story")]):
            print(chunk.content, end="", flush=True)

        # List available models
        models = await llm.list_models()

        # Pull a model
        await llm.pull_model("llama3.2:latest")
    """

    @property
    def default_model(self) -> str:
        return "llama3.2"

    @property
    def provider_name(self) -> str:
        return "ollama"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        super().__init__(
            api_key=None,  # Ollama doesn't require an API key
            model=model,
            base_url=base_url,
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
                    "httpx is required for Ollama provider. Install with: uv add httpx"
                )

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        return self._client

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to Ollama format."""
        result = []
        for msg in messages:
            result.append(
                {
                    "role": msg.role.value,
                    "content": msg.content,
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
        format: str | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """Generate a completion."""
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "messages": self._convert_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if stop:
            payload["options"]["stop"] = stop

        if format:
            payload["format"] = format

        # Ollama supports tools in newer versions
        if tools:
            payload["tools"] = [
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

        payload.update(kwargs)

        response = await client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})

        # Parse tool calls if present
        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=str(i),
                    name=tc["function"]["name"],
                    arguments=tc["function"].get("arguments", {}),
                )
                for i, tc in enumerate(message["tool_calls"])
            ]

        # Calculate usage from response times/tokens
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = Usage(
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            )

        return CompletionResponse(
            content=message.get("content", ""),
            role=Role.ASSISTANT,
            model=data.get("model", model or self.model),
            finish_reason="stop" if data.get("done") else None,
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
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if stop:
            payload["options"]["stop"] = stop

        payload.update(kwargs)

        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                data = json.loads(line)
                message = data.get("message", {})

                yield StreamChunk(
                    content=message.get("content", ""),
                    finish_reason="stop" if data.get("done") else None,
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
                    format="json",  # Ollama JSON mode
                    **kwargs,
                )

                data = json.loads(response.content)
                return response_model.model_validate(data)

            except (json.JSONDecodeError, Exception) as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )

    # Ollama-specific methods

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        client = self._get_client()
        response = await client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])

    async def pull_model(
        self,
        model: str,
        *,
        insecure: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Pull a model from the Ollama library.

        Yields progress updates as the model downloads.
        """
        client = self._get_client()

        payload = {
            "name": model,
            "insecure": insecure,
            "stream": True,
        }

        async with client.stream("POST", "/api/pull", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    yield json.loads(line)

    async def delete_model(self, model: str) -> bool:
        """Delete a model."""
        client = self._get_client()
        response = await client.delete("/api/delete", json={"name": model})
        return response.status_code == 200

    async def show_model(self, model: str) -> dict[str, Any]:
        """Get model information."""
        client = self._get_client()
        response = await client.post("/api/show", json={"name": model})
        response.raise_for_status()
        return response.json()

    async def generate_raw(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        template: str | None = None,
        context: list[int] | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate using the raw /api/generate endpoint.

        Useful for models that don't support chat format.
        """
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
        }

        if system:
            payload["system"] = system
        if template:
            payload["template"] = template
        if context:
            payload["context"] = context

        payload.update(kwargs)

        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()

        return CompletionResponse(
            content=data.get("response", ""),
            role=Role.ASSISTANT,
            model=data.get("model", model or self.model),
            finish_reason="stop" if data.get("done") else None,
            raw_response=data,
        )


class OllamaEmbeddings(EmbeddingProvider):
    """
    Ollama embedding provider.

    Supports embedding models like nomic-embed-text, mxbai-embed-large.

    Usage:
        from django_matt.ai import OllamaEmbeddings

        embedder = OllamaEmbeddings(model="nomic-embed-text")

        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings
    """

    DIMENSIONS = {
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        "all-minilm": 384,
    }

    @property
    def default_model(self) -> str:
        return "nomic-embed-text"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS.get(self.model, 768)

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        super().__init__(api_key=None, model=model, **kwargs)
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError("httpx is required. Install with: uv add httpx")

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=120.0,  # Embeddings can be slow locally
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
        model_name = model or self.model

        # Ollama processes one text at a time
        embeddings = []
        for text in texts:
            response = await client.post(
                "/api/embeddings",
                json={"model": model_name, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embedding"])

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
        )


__all__ = [
    "OllamaEmbeddings",
    "OllamaProvider",
]
