"""
Anthropic provider implementation.

Supports Claude 3.5 Sonnet, Claude 3 Opus, and other Claude models.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
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


class AnthropicProvider(LLMProvider, StructuredOutputProvider):
    """
    Anthropic LLM provider.

    Supports Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku.

    Usage:
        from django_matt.ai import AnthropicProvider, Message

        llm = AnthropicProvider(api_key="sk-ant-...")
        # Or use ANTHROPIC_API_KEY env var

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
        return "claude-sonnet-4-20250514"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key required. Pass api_key or set ANTHROPIC_API_KEY.")

        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.anthropic.com",
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
                    "httpx is required for Anthropic provider. Install with: uv add httpx"
                )

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Convert messages to Anthropic format.

        Returns (system_message, messages) since Anthropic handles
        system messages separately.
        """
        system_content = None
        converted = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_content = msg.content
            elif msg.role == Role.TOOL:
                # Anthropic uses tool_result for tool responses
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            else:
                converted.append(
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                    }
                )

        return system_content, converted

    def _convert_tools(self, tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
        """Convert tools to Anthropic format."""
        if not tools:
            return None
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
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

        system_content, converted_messages = self._convert_messages(messages)

        payload = {
            "model": model or self.model,
            "messages": converted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,  # Anthropic requires max_tokens
        }

        if system_content:
            payload["system"] = system_content

        if stop:
            payload["stop_sequences"] = stop

        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools
            if tool_choice:
                if tool_choice == "auto":
                    payload["tool_choice"] = {"type": "auto"}
                elif tool_choice == "none":
                    payload["tool_choice"] = {"type": "none"}
                elif tool_choice == "any":
                    payload["tool_choice"] = {"type": "any"}
                else:
                    payload["tool_choice"] = {"type": "tool", "name": tool_choice}

        payload.update(kwargs)

        response = await client.post("/v1/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        # Parse content - Anthropic can return multiple content blocks
        content = ""
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block["input"],
                    )
                )

        usage = Usage(
            prompt_tokens=data["usage"]["input_tokens"],
            completion_tokens=data["usage"]["output_tokens"],
            total_tokens=data["usage"]["input_tokens"] + data["usage"]["output_tokens"],
        )

        return CompletionResponse(
            content=content,
            role=Role.ASSISTANT,
            model=data.get("model", model or self.model),
            finish_reason=data.get("stop_reason"),
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

        system_content, converted_messages = self._convert_messages(messages)

        payload = {
            "model": model or self.model,
            "messages": converted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            "stream": True,
        }

        if system_content:
            payload["system"] = system_content

        if stop:
            payload["stop_sequences"] = stop

        payload.update(kwargs)

        async with client.stream("POST", "/v1/messages", json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    event_type = data.get("type")

                    if event_type == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield StreamChunk(content=delta.get("text", ""))

                    elif event_type == "message_delta":
                        yield StreamChunk(finish_reason=data.get("delta", {}).get("stop_reason"))

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
        # Use tool calling for structured output
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
                    tool_choice="extract_data",
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


__all__ = [
    "AnthropicProvider",
]
