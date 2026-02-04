"""
vLLM provider implementation.

Provides integration with vLLM inference servers using the OpenAI-compatible API.
Supports text generation, chat completions, streaming, batch inference,
guided decoding (JSON schema, regex, grammar), and vLLM-specific features.

Requirements:
    pip install httpx

vLLM Server Setup:
    # Install vLLM
    pip install vllm

    # Start server (OpenAI-compatible API)
    python -m vllm.entrypoints.openai.api_server \
        --model meta-llama/Llama-3.1-8B-Instruct \
        --port 8000

    # With tensor parallelism for large models
    python -m vllm.entrypoints.openai.api_server \
        --model meta-llama/Llama-3.1-70B-Instruct \
        --tensor-parallel-size 4 \
        --port 8000

    # With quantization
    python -m vllm.entrypoints.openai.api_server \
        --model meta-llama/Llama-3.1-8B-Instruct \
        --quantization awq \
        --port 8000

Usage:
    from django_matt.ml import VLLMProvider, VLLMClient
    from django_matt.ai import Message

    # Using the provider (high-level interface)
    llm = VLLMProvider(base_url="http://localhost:8000")

    # Chat completion
    response = await llm.complete([
        Message.system("You are helpful."),
        Message.user("Hello!"),
    ])
    print(response.content)

    # Streaming
    async for chunk in llm.stream([Message.user("Tell a story")]):
        print(chunk.content, end="", flush=True)

    # Guided decoding with JSON schema
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }
    response = await llm.complete(
        [Message.user("Extract info: John is 30 years old")],
        guided_json=schema,
    )

    # Regex-guided generation
    response = await llm.complete(
        [Message.user("Generate an email address")],
        guided_regex=r"[a-z]+@[a-z]+\\.com",
    )

    # Batch inference
    prompts = ["Hello", "Hi there", "Greetings"]
    results = await llm.batch_generate(prompts)

    # Using the client (low-level interface)
    client = VLLMClient(base_url="http://localhost:8000")

    # Health check
    health = await client.health_check()
    print(f"Server healthy: {health['status']}")

    # List models
    models = await client.list_models()
    print(f"Available models: {[m['id'] for m in models['data']]}")

    # Get model info
    info = await client.get_model_info("meta-llama/Llama-3.1-8B-Instruct")
    print(f"Model info: {info}")
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
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


# =============================================================================
# vLLM-specific Types
# =============================================================================


class GuidedDecodingType(str, Enum):
    """Types of guided decoding supported by vLLM."""

    JSON = "json"
    REGEX = "regex"
    GRAMMAR = "grammar"
    CHOICE = "choice"


@dataclass
class SamplingParams:
    """
    vLLM sampling parameters.

    These map directly to vLLM's SamplingParams class.
    """

    # Basic parameters
    temperature: float = 1.0
    top_p: float = 1.0
    top_k: int = -1  # -1 means disabled
    min_p: float = 0.0

    # Length control
    max_tokens: int | None = None
    min_tokens: int = 0
    stop: list[str] | None = None
    stop_token_ids: list[int] | None = None
    include_stop_str_in_output: bool = False

    # Repetition control
    repetition_penalty: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    # Beam search
    use_beam_search: bool = False
    best_of: int = 1
    n: int = 1  # Number of completions to generate
    early_stopping: bool | str = False  # True, False, or "never"
    length_penalty: float = 1.0

    # Advanced
    seed: int | None = None
    logprobs: int | None = None
    prompt_logprobs: int | None = None
    skip_special_tokens: bool = True
    spaces_between_special_tokens: bool = True
    ignore_eos: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None and value != getattr(SamplingParams(), key, None):
                result[key] = value
        return result


@dataclass
class GuidedDecodingParams:
    """
    Parameters for guided decoding (constrained generation).

    vLLM supports multiple types of guided decoding:
    - JSON: Generate valid JSON matching a schema
    - Regex: Generate text matching a regular expression
    - Grammar: Generate text following a BNF grammar (EBNF-style)
    - Choice: Generate one of a set of choices
    """

    # JSON schema guided generation
    json_schema: dict[str, Any] | None = None
    json_object: bool = False  # Force JSON output without schema

    # Regex guided generation
    regex: str | None = None

    # Grammar guided generation (EBNF-style)
    grammar: str | None = None

    # Choice guided generation
    choice: list[str] | None = None

    # Backend selection
    backend: str | None = None  # "outlines", "lm-format-enforcer"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {}
        if self.json_schema:
            result["guided_json"] = self.json_schema
        if self.json_object:
            result["response_format"] = {"type": "json_object"}
        if self.regex:
            result["guided_regex"] = self.regex
        if self.grammar:
            result["guided_grammar"] = self.grammar
        if self.choice:
            result["guided_choice"] = self.choice
        if self.backend:
            result["guided_decoding_backend"] = self.backend
        return result


@dataclass
class LoRAConfig:
    """
    LoRA adapter configuration.

    vLLM supports dynamic LoRA loading for fine-tuned models.
    """

    # LoRA adapter path or name
    lora_path: str | None = None
    lora_name: str | None = None

    # LoRA request ID (for multi-adapter serving)
    lora_request_id: str | None = None

    # Local rank (for multi-LoRA)
    lora_local_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {}
        if self.lora_path:
            result["lora_path"] = self.lora_path
        if self.lora_name:
            result["lora_name"] = self.lora_name
        if self.lora_request_id:
            result["lora_request_id"] = self.lora_request_id
        if self.lora_local_path:
            result["lora_local_path"] = self.lora_local_path
        return result


@dataclass
class BatchRequest:
    """A request in a batch inference job."""

    id: str
    prompt: str | list[Message]
    params: SamplingParams | None = None
    guided_params: GuidedDecodingParams | None = None
    priority: int = 0  # Higher priority = processed first
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of a batch inference request."""

    id: str
    response: CompletionResponse | None = None
    error: str | None = None
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerMetrics:
    """vLLM server metrics."""

    # Request metrics
    num_requests_running: int = 0
    num_requests_swapped: int = 0
    num_requests_waiting: int = 0

    # GPU metrics
    gpu_cache_usage_perc: float = 0.0
    cpu_cache_usage_perc: float = 0.0

    # Throughput
    avg_prompt_throughput: float = 0.0
    avg_generation_throughput: float = 0.0

    # Timing
    timestamp: float = field(default_factory=time.time)


@dataclass
class ModelInfo:
    """Information about a loaded model."""

    id: str
    created: int = 0
    owned_by: str = "vllm"
    root: str = ""
    parent: str | None = None

    # vLLM-specific info
    max_model_len: int | None = None
    tensor_parallel_size: int = 1
    pipeline_parallel_size: int = 1
    quantization: str | None = None
    dtype: str = "float16"

    # LoRA adapters
    lora_adapters: list[str] = field(default_factory=list)


# =============================================================================
# vLLM HTTP Client
# =============================================================================


class VLLMClient:
    """
    Low-level HTTP client for vLLM server.

    Provides direct access to vLLM's OpenAI-compatible API endpoints
    and vLLM-specific extensions.

    Usage:
        client = VLLMClient(base_url="http://localhost:8000")

        # Health check
        health = await client.health_check()

        # List models
        models = await client.list_models()

        # Chat completion
        response = await client.chat_completions({
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "messages": [{"role": "user", "content": "Hello"}],
        })

        # Streaming
        async for chunk in client.chat_completions_stream({...}):
            print(chunk)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        """
        Initialize the vLLM client.

        Args:
            base_url: vLLM server URL (e.g., "http://localhost:8000")
            api_key: Optional API key (if vLLM server requires auth)
            timeout: Request timeout in seconds
            max_retries: Number of retries for failed requests
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("VLLM_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

    def _get_client(self):
        """Get or create the HTTP client."""
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError(
                    "httpx is required for VLLMClient. Install with: pip install httpx"
                )

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # -------------------------------------------------------------------------
    # Health & Info Endpoints
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """
        Check server health.

        Returns:
            Health status dict with 'status' key
        """
        client = self._get_client()
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                return {"status": "healthy", "code": 200}
            return {"status": "unhealthy", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def list_models(self) -> dict[str, Any]:
        """
        List available models.

        Returns:
            OpenAI-compatible model list response
        """
        client = self._get_client()
        response = await client.get("/v1/models")
        response.raise_for_status()
        return response.json()

    async def get_model_info(self, model_id: str) -> ModelInfo | None:
        """
        Get detailed information about a specific model.

        Args:
            model_id: Model identifier

        Returns:
            ModelInfo object or None if not found
        """
        models = await self.list_models()
        for model in models.get("data", []):
            if model.get("id") == model_id:
                return ModelInfo(
                    id=model.get("id", ""),
                    created=model.get("created", 0),
                    owned_by=model.get("owned_by", "vllm"),
                    root=model.get("root", ""),
                    parent=model.get("parent"),
                    max_model_len=model.get("max_model_len"),
                    tensor_parallel_size=model.get("tensor_parallel_size", 1),
                    pipeline_parallel_size=model.get("pipeline_parallel_size", 1),
                    quantization=model.get("quantization"),
                    dtype=model.get("dtype", "float16"),
                    lora_adapters=model.get("lora_adapters", []),
                )
        return None

    async def get_metrics(self) -> ServerMetrics | None:
        """
        Get server metrics (if enabled).

        Note: Requires vLLM server to be started with metrics enabled.

        Returns:
            ServerMetrics object or None if metrics not available
        """
        client = self._get_client()
        try:
            response = await client.get("/metrics")
            if response.status_code == 200:
                # Parse Prometheus-style metrics
                text = response.text
                metrics = ServerMetrics()

                # Extract relevant metrics from Prometheus format
                for line in text.split("\n"):
                    if line.startswith("vllm:num_requests_running"):
                        metrics.num_requests_running = int(float(line.split()[-1]))
                    elif line.startswith("vllm:num_requests_swapped"):
                        metrics.num_requests_swapped = int(float(line.split()[-1]))
                    elif line.startswith("vllm:num_requests_waiting"):
                        metrics.num_requests_waiting = int(float(line.split()[-1]))
                    elif line.startswith("vllm:gpu_cache_usage_perc"):
                        metrics.gpu_cache_usage_perc = float(line.split()[-1])
                    elif line.startswith("vllm:cpu_cache_usage_perc"):
                        metrics.cpu_cache_usage_perc = float(line.split()[-1])
                    elif line.startswith("vllm:avg_prompt_throughput"):
                        metrics.avg_prompt_throughput = float(line.split()[-1])
                    elif line.startswith("vllm:avg_generation_throughput"):
                        metrics.avg_generation_throughput = float(line.split()[-1])

                return metrics
        except Exception:
            pass
        return None

    # -------------------------------------------------------------------------
    # Completion Endpoints
    # -------------------------------------------------------------------------

    async def completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Call the /v1/completions endpoint (text completion).

        Args:
            payload: Request payload with model, prompt, etc.

        Returns:
            Completion response dict
        """
        client = self._get_client()
        response = await client.post("/v1/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def completions_stream(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """
        Stream from /v1/completions endpoint.

        Args:
            payload: Request payload (stream=True will be added)

        Yields:
            Streamed completion chunks
        """
        client = self._get_client()
        payload = {**payload, "stream": True}

        async with client.stream("POST", "/v1/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    async def chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Call the /v1/chat/completions endpoint.

        Args:
            payload: Request payload with model, messages, etc.

        Returns:
            Chat completion response dict
        """
        client = self._get_client()
        response = await client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    async def chat_completions_stream(
        self, payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream from /v1/chat/completions endpoint.

        Args:
            payload: Request payload (stream=True will be added)

        Yields:
            Streamed chat completion chunks
        """
        client = self._get_client()
        payload = {**payload, "stream": True}

        async with client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    # -------------------------------------------------------------------------
    # LoRA Endpoints (if supported)
    # -------------------------------------------------------------------------

    async def load_lora_adapter(
        self,
        lora_name: str,
        lora_path: str,
        lora_local_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Load a LoRA adapter dynamically.

        Note: Requires vLLM server to be started with --enable-lora.

        Args:
            lora_name: Name to identify the adapter
            lora_path: Path or HuggingFace repo of the adapter
            lora_local_path: Local path (for multi-node)

        Returns:
            Response dict
        """
        client = self._get_client()
        payload = {
            "lora_name": lora_name,
            "lora_path": lora_path,
        }
        if lora_local_path:
            payload["lora_local_path"] = lora_local_path

        response = await client.post("/v1/load_lora_adapter", json=payload)
        response.raise_for_status()
        return response.json()

    async def unload_lora_adapter(self, lora_name: str) -> dict[str, Any]:
        """
        Unload a LoRA adapter.

        Args:
            lora_name: Name of the adapter to unload

        Returns:
            Response dict
        """
        client = self._get_client()
        response = await client.post(
            "/v1/unload_lora_adapter",
            json={"lora_name": lora_name},
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# VLLMProvider - High-level LLM Provider
# =============================================================================


class VLLMProvider(LLMProvider, StructuredOutputProvider):
    """
    vLLM LLM provider.

    Provides a high-level interface to vLLM inference servers using
    the OpenAI-compatible API with vLLM-specific extensions.

    Features:
    - Chat completions and text generation
    - Streaming responses
    - Guided decoding (JSON schema, regex, grammar, choice)
    - Batch inference with priority queuing
    - LoRA adapter support
    - Beam search and advanced sampling
    - Token usage tracking

    Usage:
        from django_matt.ml import VLLMProvider
        from django_matt.ai import Message

        llm = VLLMProvider(base_url="http://localhost:8000")

        # Basic completion
        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ])

        # With guided decoding
        response = await llm.complete(
            [Message.user("Generate JSON: {name, age}")],
            guided_json={"type": "object", "properties": {...}},
        )

        # Streaming
        async for chunk in llm.stream([Message.user("Tell a story")]):
            print(chunk.content, end="", flush=True)

        # Batch processing
        results = await llm.batch_generate(["prompt1", "prompt2", "prompt3"])

        # Structured output
        class Person(BaseModel):
            name: str
            age: int

        person = await llm.complete_structured(
            [Message.user("John is 30")],
            response_model=Person,
        )
    """

    @property
    def default_model(self) -> str:
        """Default model (discovered from server or placeholder)."""
        return self._default_model

    @property
    def provider_name(self) -> str:
        return "vllm"

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        # Default sampling parameters
        default_temperature: float = 0.7,
        default_max_tokens: int = 2048,
        # vLLM-specific defaults
        guided_decoding_backend: str | None = None,
        **kwargs,
    ):
        """
        Initialize the vLLM provider.

        Args:
            base_url: vLLM server URL
            api_key: Optional API key
            model: Model to use (auto-discovered if not set)
            timeout: Request timeout
            max_retries: Retry count
            default_temperature: Default sampling temperature
            default_max_tokens: Default max tokens
            guided_decoding_backend: Backend for guided decoding ("outlines", "lm-format-enforcer")
        """
        self._base_url = base_url
        self._default_model = model or "auto"
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._guided_backend = guided_decoding_backend

        # Initialize client
        self._client = VLLMClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

        # Token tracking
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0

        # Batch processing
        self._batch_queue: list[BatchRequest] = []
        self._batch_semaphore = asyncio.Semaphore(10)  # Max concurrent batch requests

        # Call parent init
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs,
        )

    async def _ensure_model(self) -> str:
        """Ensure we have a valid model name."""
        if self._default_model != "auto":
            return self._default_model

        # Auto-discover model from server
        try:
            models = await self._client.list_models()
            if models.get("data"):
                self._default_model = models["data"][0]["id"]
                return self._default_model
        except Exception:
            pass

        return "default"

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
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

    def _track_usage(self, usage_data: dict[str, Any] | None):
        """Track token usage."""
        if usage_data:
            self._total_prompt_tokens += usage_data.get("prompt_tokens", 0)
            self._total_completion_tokens += usage_data.get("completion_tokens", 0)

    def get_usage_stats(self) -> dict[str, int]:
        """Get cumulative token usage statistics."""
        return {
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
        }

    def reset_usage_stats(self):
        """Reset token usage statistics."""
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0

    # -------------------------------------------------------------------------
    # Text Generation (Completions API)
    # -------------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        # vLLM-specific
        sampling_params: SamplingParams | None = None,
        guided_json: dict[str, Any] | None = None,
        guided_regex: str | None = None,
        guided_grammar: str | None = None,
        guided_choice: list[str] | None = None,
        lora_config: LoRAConfig | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate text completion.

        Args:
            prompt: Text prompt
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            sampling_params: vLLM sampling parameters
            guided_json: JSON schema for guided decoding
            guided_regex: Regex for guided decoding
            guided_grammar: Grammar for guided decoding
            guided_choice: Choices for guided decoding
            lora_config: LoRA adapter configuration
            **kwargs: Additional parameters

        Returns:
            CompletionResponse with generated text
        """
        model_name = model or await self._ensure_model()

        payload = {
            "model": model_name,
            "prompt": prompt,
            "temperature": temperature or self._default_temperature,
            "max_tokens": max_tokens or self._default_max_tokens,
        }

        if stop:
            payload["stop"] = stop

        # Add sampling params
        if sampling_params:
            payload.update(sampling_params.to_dict())

        # Add guided decoding
        if guided_json:
            payload["guided_json"] = guided_json
        if guided_regex:
            payload["guided_regex"] = guided_regex
        if guided_grammar:
            payload["guided_grammar"] = guided_grammar
        if guided_choice:
            payload["guided_choice"] = guided_choice
        if self._guided_backend:
            payload["guided_decoding_backend"] = self._guided_backend

        # Add LoRA config
        if lora_config:
            payload.update(lora_config.to_dict())

        payload.update(kwargs)

        data = await self._client.completions(payload)
        self._track_usage(data.get("usage"))

        choice = data["choices"][0]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"]["prompt_tokens"],
                completion_tokens=data["usage"]["completion_tokens"],
                total_tokens=data["usage"]["total_tokens"],
            )

        return CompletionResponse(
            content=choice.get("text", ""),
            role=Role.ASSISTANT,
            model=data.get("model", model_name),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            raw_response=data,
        )

    # -------------------------------------------------------------------------
    # Chat Completions
    # -------------------------------------------------------------------------

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
        # vLLM-specific
        sampling_params: SamplingParams | None = None,
        guided_json: dict[str, Any] | None = None,
        guided_regex: str | None = None,
        guided_grammar: str | None = None,
        guided_choice: list[str] | None = None,
        lora_config: LoRAConfig | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a chat completion.

        Args:
            messages: Conversation history
            model: Model to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            tools: Available tools/functions
            tool_choice: How to select tools
            sampling_params: vLLM sampling parameters
            guided_json: JSON schema for guided decoding
            guided_regex: Regex for guided decoding
            guided_grammar: Grammar for guided decoding
            guided_choice: Choices for guided decoding
            lora_config: LoRA adapter configuration
            **kwargs: Additional parameters

        Returns:
            CompletionResponse with generated content
        """
        model_name = model or await self._ensure_model()

        payload = {
            "model": model_name,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens or self._default_max_tokens,
        }

        if stop:
            payload["stop"] = stop

        # Add tools
        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        # Add sampling params
        if sampling_params:
            payload.update(sampling_params.to_dict())

        # Add guided decoding
        if guided_json:
            payload["guided_json"] = guided_json
        if guided_regex:
            payload["guided_regex"] = guided_regex
        if guided_grammar:
            payload["guided_grammar"] = guided_grammar
        if guided_choice:
            payload["guided_choice"] = guided_choice
        if self._guided_backend:
            payload["guided_decoding_backend"] = self._guided_backend

        # Add LoRA config
        if lora_config:
            payload.update(lora_config.to_dict())

        payload.update(kwargs)

        data = await self._client.chat_completions(payload)
        self._track_usage(data.get("usage"))

        choice = data["choices"][0]
        message = choice["message"]

        # Parse tool calls if present
        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                    if isinstance(tc["function"]["arguments"], str)
                    else tc["function"]["arguments"],
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
            model=data.get("model", model_name),
            finish_reason=choice.get("finish_reason"),
            tool_calls=tool_calls,
            usage=usage,
            raw_response=data,
        )

    async def chat(
        self,
        messages: list[Message],
        **kwargs,
    ) -> CompletionResponse:
        """
        Alias for complete() for chat completions.

        Args:
            messages: Conversation history
            **kwargs: Additional parameters

        Returns:
            CompletionResponse
        """
        return await self.complete(messages, **kwargs)

    # -------------------------------------------------------------------------
    # Streaming
    # -------------------------------------------------------------------------

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        # vLLM-specific
        guided_json: dict[str, Any] | None = None,
        guided_regex: str | None = None,
        guided_grammar: str | None = None,
        guided_choice: list[str] | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a chat completion.

        Args:
            messages: Conversation history
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            stop: Stop sequences
            guided_json: JSON schema for guided decoding
            guided_regex: Regex for guided decoding
            guided_grammar: Grammar for guided decoding
            guided_choice: Choices for guided decoding
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects as they arrive
        """
        model_name = model or await self._ensure_model()

        payload = {
            "model": model_name,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens or self._default_max_tokens,
        }

        if stop:
            payload["stop"] = stop

        # Add guided decoding
        if guided_json:
            payload["guided_json"] = guided_json
        if guided_regex:
            payload["guided_regex"] = guided_regex
        if guided_grammar:
            payload["guided_grammar"] = guided_grammar
        if guided_choice:
            payload["guided_choice"] = guided_choice
        if self._guided_backend:
            payload["guided_decoding_backend"] = self._guided_backend

        payload.update(kwargs)

        async for chunk_data in self._client.chat_completions_stream(payload):
            choice = chunk_data.get("choices", [{}])[0]
            delta = choice.get("delta", {})

            yield StreamChunk(
                content=delta.get("content", ""),
                role=Role(delta["role"]) if "role" in delta else None,
                finish_reason=choice.get("finish_reason"),
            )

    async def stream_generate(
        self,
        prompt: str,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream text generation.

        Args:
            prompt: Text prompt
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects
        """
        model_name = kwargs.pop("model", None) or await self._ensure_model()

        payload = {
            "model": model_name,
            "prompt": prompt,
            "max_tokens": kwargs.pop("max_tokens", self._default_max_tokens),
            "temperature": kwargs.pop("temperature", self._default_temperature),
            **kwargs,
        }

        async for chunk_data in self._client.completions_stream(payload):
            choice = chunk_data.get("choices", [{}])[0]

            yield StreamChunk(
                content=choice.get("text", ""),
                finish_reason=choice.get("finish_reason"),
            )

    # -------------------------------------------------------------------------
    # Structured Output
    # -------------------------------------------------------------------------

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

        Uses vLLM's guided decoding for reliable JSON generation.

        Args:
            messages: Conversation history
            response_model: Pydantic model for response
            model: Model to use
            temperature: Sampling temperature (lower = more deterministic)
            max_retries: Retries on validation failure
            **kwargs: Additional parameters

        Returns:
            Instance of response_model
        """
        schema = response_model.model_json_schema()

        for attempt in range(max_retries):
            try:
                response = await self.complete(
                    messages,
                    model=model,
                    temperature=temperature,
                    guided_json=schema,
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

    # -------------------------------------------------------------------------
    # Batch Inference
    # -------------------------------------------------------------------------

    async def batch_generate(
        self,
        prompts: list[str],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_concurrent: int = 10,
        **kwargs,
    ) -> list[BatchResult]:
        """
        Process multiple prompts in batch.

        Args:
            prompts: List of text prompts
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
            max_concurrent: Maximum concurrent requests
            **kwargs: Additional parameters

        Returns:
            List of BatchResult objects
        """
        requests = [
            BatchRequest(
                id=str(uuid.uuid4()),
                prompt=prompt,
            )
            for prompt in prompts
        ]

        return await self.batch_process(
            requests,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_concurrent=max_concurrent,
            **kwargs,
        )

    async def batch_chat(
        self,
        message_lists: list[list[Message]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_concurrent: int = 10,
        **kwargs,
    ) -> list[BatchResult]:
        """
        Process multiple chat conversations in batch.

        Args:
            message_lists: List of message lists (conversations)
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
            max_concurrent: Maximum concurrent requests
            **kwargs: Additional parameters

        Returns:
            List of BatchResult objects
        """
        requests = [
            BatchRequest(
                id=str(uuid.uuid4()),
                prompt=messages,
            )
            for messages in message_lists
        ]

        return await self.batch_process(
            requests,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_concurrent=max_concurrent,
            use_chat=True,
            **kwargs,
        )

    async def batch_process(
        self,
        requests: list[BatchRequest],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_concurrent: int = 10,
        use_chat: bool = False,
        **kwargs,
    ) -> list[BatchResult]:
        """
        Process a batch of requests with priority queuing.

        Args:
            requests: List of BatchRequest objects
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
            max_concurrent: Maximum concurrent requests
            use_chat: Use chat completions API
            **kwargs: Additional parameters

        Returns:
            List of BatchResult objects (in same order as requests)
        """
        # Sort by priority (higher first)
        sorted_requests = sorted(requests, key=lambda r: -r.priority)

        semaphore = asyncio.Semaphore(max_concurrent)
        results: dict[str, BatchResult] = {}

        async def process_one(request: BatchRequest) -> None:
            async with semaphore:
                start_time = time.time()
                try:
                    # Determine parameters
                    params = SamplingParams(
                        temperature=temperature or self._default_temperature,
                        max_tokens=max_tokens or self._default_max_tokens,
                    )
                    if request.params:
                        params = request.params

                    if use_chat or isinstance(request.prompt, list):
                        # Chat completion
                        messages = (
                            request.prompt
                            if isinstance(request.prompt, list)
                            else [Message.user(request.prompt)]
                        )
                        response = await self.complete(
                            messages,
                            model=model,
                            temperature=params.temperature,
                            max_tokens=params.max_tokens,
                            sampling_params=params,
                            guided_json=request.guided_params.json_schema
                            if request.guided_params
                            else None,
                            guided_regex=request.guided_params.regex
                            if request.guided_params
                            else None,
                            **kwargs,
                        )
                    else:
                        # Text completion
                        response = await self.generate(
                            request.prompt,
                            model=model,
                            temperature=params.temperature,
                            max_tokens=params.max_tokens,
                            sampling_params=params,
                            guided_json=request.guided_params.json_schema
                            if request.guided_params
                            else None,
                            guided_regex=request.guided_params.regex
                            if request.guided_params
                            else None,
                            **kwargs,
                        )

                    results[request.id] = BatchResult(
                        id=request.id,
                        response=response,
                        latency_ms=(time.time() - start_time) * 1000,
                        metadata=request.metadata,
                    )

                except Exception as e:
                    results[request.id] = BatchResult(
                        id=request.id,
                        error=str(e),
                        latency_ms=(time.time() - start_time) * 1000,
                        metadata=request.metadata,
                    )

        # Process all requests
        await asyncio.gather(*[process_one(req) for req in sorted_requests])

        # Return in original order
        return [results[req.id] for req in requests]

    # -------------------------------------------------------------------------
    # Health & Monitoring
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """
        Check vLLM server health.

        Returns:
            Health status dict
        """
        return await self._client.health_check()

    async def get_model_info(self, model_id: str | None = None) -> ModelInfo | None:
        """
        Get model information.

        Args:
            model_id: Model to get info for (uses default if not specified)

        Returns:
            ModelInfo or None
        """
        model_name = model_id or await self._ensure_model()
        return await self._client.get_model_info(model_name)

    async def list_models(self) -> list[dict[str, Any]]:
        """
        List available models.

        Returns:
            List of model info dicts
        """
        response = await self._client.list_models()
        return response.get("data", [])

    async def get_metrics(self) -> ServerMetrics | None:
        """
        Get server metrics.

        Returns:
            ServerMetrics or None if not available
        """
        return await self._client.get_metrics()

    # -------------------------------------------------------------------------
    # LoRA Management
    # -------------------------------------------------------------------------

    async def load_lora(
        self,
        name: str,
        path: str,
        local_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Load a LoRA adapter.

        Args:
            name: Adapter name
            path: Path or HuggingFace repo
            local_path: Local path (for multi-node)

        Returns:
            Response dict
        """
        return await self._client.load_lora_adapter(name, path, local_path)

    async def unload_lora(self, name: str) -> dict[str, Any]:
        """
        Unload a LoRA adapter.

        Args:
            name: Adapter name

        Returns:
            Response dict
        """
        return await self._client.unload_lora_adapter(name)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def close(self):
        """Close the provider and cleanup resources."""
        await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Provider
    "VLLMProvider",
    # Client
    "VLLMClient",
    # Types
    "SamplingParams",
    "GuidedDecodingParams",
    "GuidedDecodingType",
    "LoRAConfig",
    "BatchRequest",
    "BatchResult",
    "ServerMetrics",
    "ModelInfo",
]
