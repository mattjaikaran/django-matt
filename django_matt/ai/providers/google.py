"""
Google Gemini provider implementation.

Supports Gemini 1.5 Pro, Gemini 1.5 Flash, and embedding models.
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


class GeminiProvider(LLMProvider, StructuredOutputProvider):
    """
    Google Gemini LLM provider.

    Supports Gemini 1.5 Pro, Gemini 1.5 Flash, and other Gemini models.

    Usage:
        from django_matt.ai import GeminiProvider, Message

        llm = GeminiProvider(api_key="...")
        # Or use GOOGLE_API_KEY env var

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
        return "gemini-1.5-pro"

    @property
    def provider_name(self) -> str:
        return "google"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key required. Pass api_key or set GOOGLE_API_KEY.")

        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://generativelanguage.googleapis.com/v1beta",
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
                    "httpx is required for Gemini provider. Install with: pip install httpx"
                )

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        return self._client

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Convert messages to Gemini format.

        Returns (system_instruction, contents).
        """
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_instruction = msg.content
            elif msg.role == Role.USER:
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": msg.content}],
                    }
                )
            elif msg.role == Role.ASSISTANT:
                contents.append(
                    {
                        "role": "model",
                        "parts": [{"text": msg.content}],
                    }
                )
            elif msg.role == Role.TOOL:
                contents.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.name or "tool",
                                    "response": {"result": msg.content},
                                }
                            }
                        ],
                    }
                )

        return system_instruction, contents

    def _convert_tools(self, tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
        """Convert tools to Gemini format."""
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            # Convert JSON Schema to Gemini schema format
            params = tool.parameters.copy()
            # Gemini uses different property names
            function_declarations.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": params,
                }
            )

        return [{"functionDeclarations": function_declarations}]

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

        system_instruction, contents = self._convert_messages(messages)
        model_name = model or self.model

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if stop:
            payload["generationConfig"]["stopSequences"] = stop

        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools

        payload.update(kwargs)

        url = f"/models/{model_name}:generateContent?key={self.api_key}"
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Parse response
        candidates = data.get("candidates", [])
        if not candidates:
            return CompletionResponse(content="", role=Role.ASSISTANT)

        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])

        content = ""
        tool_calls = []

        for part in content_parts:
            if "text" in part:
                content += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=fc.get("name", ""),  # Gemini doesn't have IDs
                        name=fc["name"],
                        arguments=fc.get("args", {}),
                    )
                )

        usage = None
        if "usageMetadata" in data:
            meta = data["usageMetadata"]
            usage = Usage(
                prompt_tokens=meta.get("promptTokenCount", 0),
                completion_tokens=meta.get("candidatesTokenCount", 0),
                total_tokens=meta.get("totalTokenCount", 0),
            )

        return CompletionResponse(
            content=content,
            role=Role.ASSISTANT,
            model=model_name,
            finish_reason=candidate.get("finishReason"),
            tool_calls=tool_calls if tool_calls else None,
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

        system_instruction, contents = self._convert_messages(messages)
        model_name = model or self.model

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if stop:
            payload["generationConfig"]["stopSequences"] = stop

        payload.update(kwargs)

        url = f"/models/{model_name}:streamGenerateContent?key={self.api_key}&alt=sse"

        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                data = json.loads(line[6:])
                candidates = data.get("candidates", [])

                if candidates:
                    candidate = candidates[0]
                    content_parts = candidate.get("content", {}).get("parts", [])

                    for part in content_parts:
                        if "text" in part:
                            yield StreamChunk(
                                content=part["text"],
                                finish_reason=candidate.get("finishReason"),
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
            "Do not include any other text, markdown formatting, or code blocks. Only output the raw JSON object."
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

                # Clean up response - remove markdown code blocks if present
                content = response.content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1])

                data = json.loads(content)
                return response_model.model_validate(data)

            except (json.JSONDecodeError, Exception) as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )


class GeminiEmbeddings(EmbeddingProvider):
    """
    Google Gemini embedding provider.

    Supports text-embedding-004 and other embedding models.

    Usage:
        from django_matt.ai import GeminiEmbeddings

        embedder = GeminiEmbeddings(api_key="...")

        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings
    """

    @property
    def default_model(self) -> str:
        return "text-embedding-004"

    @property
    def dimensions(self) -> int:
        return 768

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key required. Pass api_key or set GOOGLE_API_KEY.")

        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError("httpx is required. Install with: pip install httpx")

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=60.0,
            )
        return self._client

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Generate embeddings for texts.

        Args:
            texts: Texts to embed
            model: Model to use
            task_type: Task type (RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY,
                       SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING)
        """
        client = self._get_client()
        model_name = model or self.model

        # Gemini requires individual requests for each text
        # or use batchEmbedContents
        payload = {
            "requests": [
                {
                    "model": f"models/{model_name}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                }
                for text in texts
            ]
        }

        url = f"/models/{model_name}:batchEmbedContents?key={self.api_key}"
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        embeddings = [item["values"] for item in data.get("embeddings", [])]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
        )


__all__ = [
    "GeminiEmbeddings",
    "GeminiProvider",
]
