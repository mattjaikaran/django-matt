"""
Perplexity provider implementation.

Provides search-augmented LLM responses with real-time information access.
"""

import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import orjson
from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    LLMProvider,
    Message,
    Role,
    StreamChunk,
    StructuredOutputProvider,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class PerplexityProvider(LLMProvider, StructuredOutputProvider):
    """
    Perplexity LLM provider with search augmentation.

    Perplexity provides LLM responses augmented with real-time web search,
    making it ideal for questions about current events, facts, and up-to-date
    information.

    Usage:
        from django_matt.ai import PerplexityProvider, Message

        llm = PerplexityProvider(api_key="...")
        # Or use PERPLEXITY_API_KEY env var

        # Get answers with search-augmented responses
        response = await llm.complete([
            Message.user("What are the latest developments in AI?"),
        ])
        print(response.content)

        # Access citations if available
        if response.raw_response.get("citations"):
            print("Sources:", response.raw_response["citations"])

        # Streaming
        async for chunk in llm.stream([Message.user("Tell me about recent news")]):
            print(chunk.content, end="", flush=True)
    """

    MODELS = {
        "sonar": "Sonar (Online search, 127k context)",
        "sonar-pro": "Sonar Pro (Advanced search, 200k context)",
        "sonar-reasoning": "Sonar Reasoning (Chain of thought)",
        "sonar-reasoning-pro": "Sonar Reasoning Pro (Extended reasoning)",
    }

    @property
    def default_model(self) -> str:
        return "sonar"

    @property
    def provider_name(self) -> str:
        return "perplexity"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        return_citations: bool = True,
        return_images: bool = False,
        search_recency_filter: str | None = None,
        **kwargs,
    ):
        """
        Initialize Perplexity provider.

        Args:
            api_key: Perplexity API key
            model: Model to use (sonar, sonar-pro, etc.)
            base_url: API base URL
            return_citations: Include source citations in response
            return_images: Include related images in response
            search_recency_filter: Filter search by recency (hour, day, week, month)
        """
        api_key = api_key or os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("Perplexity API key required. Pass api_key or set PERPLEXITY_API_KEY.")

        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.perplexity.ai",
            **kwargs,
        )
        self.return_citations = return_citations
        self.return_images = return_images
        self.search_recency_filter = search_recency_filter
        self._client = None

    def _get_client(self):
        """Get or create the HTTP client."""
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError(
                    "httpx is required for Perplexity provider. Install with: uv add httpx"
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
            result.append(d)
        return result

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        return_citations: bool | None = None,
        return_images: bool | None = None,
        search_recency_filter: str | None = None,
        search_domain_filter: list[str] | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a search-augmented completion.

        Args:
            messages: Conversation history
            model: Model to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            return_citations: Include citations in response
            return_images: Include images in response
            search_recency_filter: Filter search by recency
            search_domain_filter: Limit search to specific domains
        """
        client = self._get_client()

        payload = {
            "model": model or self.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Search-specific options
        if return_citations is not None:
            payload["return_citations"] = return_citations
        elif self.return_citations:
            payload["return_citations"] = True

        if return_images is not None:
            payload["return_images"] = return_images
        elif self.return_images:
            payload["return_images"] = True

        recency = search_recency_filter or self.search_recency_filter
        if recency:
            payload["search_recency_filter"] = recency

        if search_domain_filter:
            payload["search_domain_filter"] = search_domain_filter

        payload.update(kwargs)

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

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
            usage=usage,
            raw_response=data,  # Contains citations and images
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
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
                    **kwargs,
                )

                # Extract JSON from response
                content = response.content.strip()
                # Handle potential markdown code blocks
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1])

                data = orjson.loads(content)
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

    async def search(
        self,
        query: str,
        *,
        model: str | None = None,
        search_recency_filter: str | None = None,
        search_domain_filter: list[str] | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Convenience method for search-style queries.

        Args:
            query: Search query
            model: Model to use
            search_recency_filter: Filter by recency (hour, day, week, month)
            search_domain_filter: Limit to specific domains
        """
        return await self.complete(
            [Message.user(query)],
            model=model,
            search_recency_filter=search_recency_filter,
            search_domain_filter=search_domain_filter,
            return_citations=True,
            **kwargs,
        )

    def get_citations(self, response: CompletionResponse) -> list[str]:
        """Extract citations from a response."""
        if response.raw_response:
            return response.raw_response.get("citations", [])
        return []

    def get_images(self, response: CompletionResponse) -> list[str]:
        """Extract images from a response."""
        if response.raw_response:
            return response.raw_response.get("images", [])
        return []

    @classmethod
    def list_models(cls) -> dict[str, str]:
        """List available Perplexity models."""
        return cls.MODELS.copy()


__all__ = [
    "PerplexityProvider",
]
