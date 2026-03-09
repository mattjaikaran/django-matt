"""
Base classes for AI/LLM integration.

Provides abstract base classes and common types for LLM providers,
embeddings, and AI utilities.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Literal,
    TypeVar,
    Union,
)

from pydantic import BaseModel

# =============================================================================
# Types and Enums
# =============================================================================


class Role(str, Enum):
    """Message role in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A message in a conversation."""

    role: Role
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str, tool_calls: list[dict] | None = None) -> "Message":
        return cls(role=Role.ASSISTANT, content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str) -> "Message":
        return cls(role=Role.TOOL, content=content, tool_call_id=tool_call_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to provider-agnostic dict format."""
        d = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class ToolDefinition:
    """Definition of a tool/function that can be called by the LLM."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    @classmethod
    def from_function(
        cls,
        func: Callable,
        description: str | None = None,
    ) -> "ToolDefinition":
        """Create a tool definition from a function with type hints."""
        import inspect
        from typing import get_type_hints

        hints = get_type_hints(func)
        sig = inspect.signature(func)

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = hints.get(param_name, Any)
            prop = _python_type_to_json_schema(param_type)

            # Add description from docstring if available
            properties[param_name] = prop

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        return cls(
            name=func.__name__,
            description=description or func.__doc__ or "",
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
        )


@dataclass
class ToolCall:
    """A tool call made by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Usage:
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CompletionResponse:
    """Response from a completion request."""

    content: str
    role: Role = Role.ASSISTANT
    model: str = ""
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: Usage | None = None
    raw_response: Any | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""

    content: str = ""
    role: Role | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass
class EmbeddingResponse:
    """Response from an embedding request."""

    embeddings: list[list[float]]
    model: str = ""
    usage: Usage | None = None


# =============================================================================
# Base Classes
# =============================================================================


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implementations should handle provider-specific API calls while
    conforming to this unified interface.

    Usage:
        from django_matt.ai import OpenAIProvider

        llm = OpenAIProvider(api_key="...")
        response = await llm.complete([
            Message.system("You are a helpful assistant."),
            Message.user("Hello!"),
        ])
        print(response.content)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        **kwargs,
    ):
        self.api_key = api_key
        self.model = model or self.default_model
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_kwargs = kwargs

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model for this provider."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider."""

    @abstractmethod
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
        """
        Generate a completion for the given messages.

        Args:
            messages: Conversation history
            model: Model to use (overrides default)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            tools: Available tools/functions
            tool_choice: How to select tools ("auto", "none", or specific)
            **kwargs: Provider-specific options
        """

    @abstractmethod
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
        """
        Stream a completion for the given messages.

        Yields StreamChunk objects as they arrive.
        """

    def complete_sync(
        self,
        messages: list[Message],
        **kwargs,
    ) -> CompletionResponse:
        """Synchronous version of complete()."""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.complete(messages, **kwargs))
        finally:
            loop.close()

    def stream_sync(
        self,
        messages: list[Message],
        **kwargs,
    ) -> Iterator[StreamChunk]:
        """Synchronous version of stream()."""
        import asyncio

        async def collect():
            chunks = []
            async for chunk in self.stream(messages, **kwargs):
                chunks.append(chunk)
            return chunks

        loop = asyncio.new_event_loop()
        try:
            chunks = loop.run_until_complete(collect())
        finally:
            loop.close()
        yield from chunks


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    Usage:
        from django_matt.ai import OpenAIEmbeddings

        embedder = OpenAIEmbeddings(api_key="...")
        embeddings = await embedder.embed(["Hello", "World"])
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs,
    ):
        self.api_key = api_key
        self.model = model or self.default_model
        self.extra_kwargs = kwargs

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default embedding model."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding dimensions for the default model."""

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Generate embeddings for the given texts.

        Args:
            texts: List of texts to embed
            model: Model to use (overrides default)
        """

    async def embed_single(
        self,
        text: str,
        **kwargs,
    ) -> list[float]:
        """Embed a single text and return the vector."""
        response = await self.embed([text], **kwargs)
        return response.embeddings[0]

    def embed_sync(
        self,
        texts: list[str],
        **kwargs,
    ) -> EmbeddingResponse:
        """Synchronous version of embed()."""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.embed(texts, **kwargs))
        finally:
            loop.close()


T = TypeVar("T", bound=BaseModel)


class StructuredOutputProvider(ABC):
    """
    Mixin for providers that support structured output.

    Enables extracting Pydantic models from LLM responses.
    """

    @abstractmethod
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
        """
        Generate a structured response matching the Pydantic model.

        Args:
            messages: Conversation history
            response_model: Pydantic model class for the response
            model: Model to use
            temperature: Lower is more deterministic
            max_retries: Retries on validation failure
        """


# =============================================================================
# Utilities
# =============================================================================


def _python_type_to_json_schema(python_type: Any) -> dict[str, Any]:
    """Convert a Python type hint to JSON Schema."""

    origin = getattr(python_type, "__origin__", None)

    if python_type == str:
        return {"type": "string"}
    if python_type == int:
        return {"type": "integer"}
    if python_type == float:
        return {"type": "number"}
    if python_type == bool:
        return {"type": "boolean"}
    if origin == list or origin == list:
        args = getattr(python_type, "__args__", (Any,))
        return {
            "type": "array",
            "items": _python_type_to_json_schema(args[0]) if args else {},
        }
    if origin == dict or origin == dict:
        return {"type": "object"}
    if origin == Union:
        args = getattr(python_type, "__args__", ())
        # Handle Optional (Union[X, None])
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _python_type_to_json_schema(non_none[0])
        return {"anyOf": [_python_type_to_json_schema(a) for a in non_none]}
    if origin == Literal:
        args = getattr(python_type, "__args__", ())
        return {"enum": list(args)}
    return {"type": "string"}  # Fallback


def messages_to_prompt(messages: list[Message], format: str = "chatml") -> str:
    """
    Convert messages to a prompt string.

    Formats:
        - chatml: ChatML format (<|im_start|>role\n...<|im_end|>)
        - llama: Llama format ([INST]...[/INST])
        - simple: Simple format (Role: content)
    """
    if format == "chatml":
        parts = []
        for msg in messages:
            parts.append(f"<|im_start|>{msg.role.value}\n{msg.content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    if format == "llama":
        parts = []
        system_msg = None
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_msg = msg.content
            elif msg.role == Role.USER:
                if system_msg:
                    parts.append(f"[INST] <<SYS>>\n{system_msg}\n<</SYS>>\n\n{msg.content} [/INST]")
                    system_msg = None
                else:
                    parts.append(f"[INST] {msg.content} [/INST]")
            elif msg.role == Role.ASSISTANT:
                parts.append(msg.content)
        return "\n".join(parts)

    # simple
    parts = []
    for msg in messages:
        role_name = msg.role.value.capitalize()
        parts.append(f"{role_name}: {msg.content}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


__all__ = [
    # Types
    "Role",
    "Message",
    "ToolDefinition",
    "ToolCall",
    "Usage",
    "CompletionResponse",
    "StreamChunk",
    "EmbeddingResponse",
    # Base classes
    "LLMProvider",
    "EmbeddingProvider",
    "StructuredOutputProvider",
    # Utilities
    "messages_to_prompt",
]
