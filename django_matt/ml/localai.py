"""
LocalAI provider implementation.

LocalAI is a self-hosted, OpenAI-compatible API for running LLMs locally with:
- OpenAI-compatible API endpoints
- Multi-modal support (image generation, audio, vision)
- Multiple backends (llama.cpp, diffusers, whisper, transformers)
- Grammar-constrained generation
- P2P federation support

Requires: uv add httpx
Docs: https://localai.io/
"""

import base64
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
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


# =============================================================================
# Types and Dataclasses
# =============================================================================


class LocalAIBackend(str, Enum):
    """Supported LocalAI backends."""

    LLAMA_CPP = "llama-cpp"
    DIFFUSERS = "diffusers"
    WHISPER = "whisper"
    TRANSFORMERS = "transformers"
    STABLEDIFFUSION = "stablediffusion"
    BARK = "bark"
    PIPER = "piper"
    VALL_E_X = "vall-e-x"


class ImageSize(str, Enum):
    """Standard image generation sizes."""

    SMALL = "256x256"
    MEDIUM = "512x512"
    LARGE = "1024x1024"


@dataclass
class ModelInfo:
    """Information about a loaded model."""

    id: str
    object: str = "model"
    owned_by: str = "localai"
    created: int = 0
    backend: str | None = None
    config: dict[str, Any] | None = None


@dataclass
class ImageGenerationResponse:
    """Response from image generation."""

    images: list[str]  # Base64 encoded images or URLs
    model: str
    created: int
    raw_response: Any | None = None


@dataclass
class TranscriptionResponse:
    """Response from audio transcription."""

    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[dict[str, Any]] | None = None
    raw_response: Any | None = None


@dataclass
class SpeechResponse:
    """Response from text-to-speech."""

    audio: bytes
    format: str = "wav"
    raw_response: Any | None = None


@dataclass
class VisionResponse:
    """Response from image-to-text (vision models)."""

    content: str
    model: str
    usage: Usage | None = None
    raw_response: Any | None = None


# =============================================================================
# LocalAI HTTP Client
# =============================================================================


class LocalAIClient:
    """
    HTTP client for LocalAI API communication.

    Handles all HTTP requests to LocalAI with async support.

    Usage:
        client = LocalAIClient(base_url="http://localhost:8080")
        response = await client.post("/v1/chat/completions", json=payload)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
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
                    "httpx is required for LocalAI provider. Install with: uv add httpx"
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

    async def get(self, path: str, **kwargs) -> Any:
        """Make a GET request."""
        client = self._get_client()
        response = await client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post(self, path: str, **kwargs) -> Any:
        """Make a POST request."""
        client = self._get_client()
        response = await client.post(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post_raw(self, path: str, **kwargs) -> bytes:
        """Make a POST request and return raw bytes."""
        client = self._get_client()
        response = await client.post(path, **kwargs)
        response.raise_for_status()
        return response.content

    async def post_stream(self, path: str, **kwargs) -> AsyncIterator[str]:
        """Make a streaming POST request."""
        client = self._get_client()
        async with client.stream("POST", path, **kwargs) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield line

    async def delete(self, path: str, **kwargs) -> Any:
        """Make a DELETE request."""
        client = self._get_client()
        response = await client.delete(path, **kwargs)
        response.raise_for_status()
        if response.content:
            return response.json()
        return None

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# LocalAI Provider
# =============================================================================


class LocalAIProvider(LLMProvider, StructuredOutputProvider):
    """
    LocalAI LLM provider for self-hosted inference.

    Supports OpenAI-compatible API endpoints with additional LocalAI features
    like grammar-constrained generation and multi-modal capabilities.

    Usage:
        from django_matt.ml import LocalAIProvider, Message

        # Basic usage
        llm = LocalAIProvider(base_url="http://localhost:8080")

        response = await llm.complete([
            Message.system("You are helpful."),
            Message.user("Hello!"),
        ])
        print(response.content)

        # Streaming
        async for chunk in llm.stream([Message.user("Tell me a story")]):
            print(chunk.content, end="", flush=True)

        # Text generation (non-chat)
        response = await llm.generate("Once upon a time")

        # Grammar-constrained generation
        response = await llm.complete(
            [Message.user("What is 2+2?")],
            grammar="root ::= [0-9]+"  # Only numbers
        )

        # Function calling
        response = await llm.complete(
            [Message.user("What's the weather?")],
            tools=[weather_tool],
        )

        # Model management
        models = await llm.list_models()
        await llm.load_model("llama-3-8b")
        status = await llm.model_status("llama-3-8b")
    """

    @property
    def default_model(self) -> str:
        return "gpt-3.5-turbo"  # LocalAI default alias

    @property
    def provider_name(self) -> str:
        return "localai"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
        **kwargs,
    ):
        base_url = base_url or os.environ.get("LOCALAI_BASE_URL", "http://localhost:8080")
        api_key = api_key or os.environ.get("LOCALAI_API_KEY")

        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs,
        )

        self._client = LocalAIClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

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

    # =========================================================================
    # Core LLM Methods
    # =========================================================================

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
        grammar: str | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a chat completion.

        Args:
            messages: Conversation history
            model: Model to use (overrides default)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences
            tools: Available tools/functions
            tool_choice: How to select tools ("auto", "none", or specific)
            grammar: BNF grammar for constrained generation (LocalAI-specific)
            **kwargs: Additional LocalAI-specific options
        """
        payload = {
            "model": model or self.model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop

        # Function calling
        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        # LocalAI-specific: grammar-constrained generation
        if grammar:
            payload["grammar"] = grammar

        payload.update(kwargs)

        data = await self._client.post("/v1/chat/completions", json=payload)

        choice = data["choices"][0]
        message = choice["message"]

        # Parse tool calls if present
        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc.get("id", str(i)),
                    name=tc["function"]["name"],
                    arguments=(
                        orjson.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"]
                    ),
                )
                for i, tc in enumerate(message["tool_calls"])
            ]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"].get("prompt_tokens", 0),
                completion_tokens=data["usage"].get("completion_tokens", 0),
                total_tokens=data["usage"].get("total_tokens", 0),
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

    async def chat(
        self,
        messages: list[Message],
        **kwargs,
    ) -> CompletionResponse:
        """
        Alias for complete() for chat completions.

        Usage:
            response = await llm.chat([
                Message.system("You are helpful."),
                Message.user("Hello!"),
            ])
        """
        return await self.complete(messages, **kwargs)

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        grammar: str | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a chat completion.

        Yields StreamChunk objects as they arrive.

        Usage:
            async for chunk in llm.stream([Message.user("Tell a story")]):
                print(chunk.content, end="", flush=True)
        """
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
        if grammar:
            payload["grammar"] = grammar

        payload.update(kwargs)

        async for line in self._client.post_stream("/v1/chat/completions", json=payload):
            if line == "data: [DONE]":
                continue

            if line.startswith("data: "):
                try:
                    data = orjson.loads(line[6:])
                    choice = data["choices"][0]
                    delta = choice.get("delta", {})

                    yield StreamChunk(
                        content=delta.get("content", ""),
                        role=Role(delta["role"]) if "role" in delta else None,
                        finish_reason=choice.get("finish_reason"),
                    )
                except orjson.JSONDecodeError:
                    continue

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        grammar: str | None = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate text completion (non-chat endpoint).

        Useful for models that don't support chat format.

        Usage:
            response = await llm.generate("Once upon a time")
        """
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop:
            payload["stop"] = stop
        if grammar:
            payload["grammar"] = grammar

        payload.update(kwargs)

        data = await self._client.post("/v1/completions", json=payload)

        choice = data["choices"][0]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"].get("prompt_tokens", 0),
                completion_tokens=data["usage"].get("completion_tokens", 0),
                total_tokens=data["usage"].get("total_tokens", 0),
            )

        return CompletionResponse(
            content=choice.get("text", ""),
            role=Role.ASSISTANT,
            model=data.get("model", model or self.model),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            raw_response=data,
        )

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_retries: int = 3,
        use_grammar: bool = True,
        **kwargs,
    ) -> T:
        """
        Generate a structured response matching the Pydantic model.

        Uses LocalAI's grammar feature for more reliable JSON output.

        Args:
            messages: Conversation history
            response_model: Pydantic model class for the response
            model: Model to use
            temperature: Lower is more deterministic
            max_retries: Retries on validation failure
            use_grammar: Use BNF grammar for JSON constraint
        """
        schema = response_model.model_json_schema()
        schema_str = orjson.dumps(schema, option=orjson.OPT_INDENT_2).decode()

        system_msg = Message.system(
            f"You must respond with valid JSON matching this schema:\n{schema_str}\n"
            "Do not include any other text, only the JSON object."
        )

        augmented_messages = [system_msg] + messages

        # Build JSON grammar from schema if enabled
        grammar = None
        if use_grammar:
            grammar = _generate_json_grammar(schema)

        for attempt in range(max_retries):
            try:
                response = await self.complete(
                    augmented_messages,
                    model=model,
                    temperature=temperature,
                    grammar=grammar,
                    **kwargs,
                )

                # Parse and validate
                data = orjson.loads(response.content)
                return response_model.model_validate(data)

            except (orjson.JSONDecodeError, Exception) as e:
                if attempt == max_retries - 1:
                    raise ValueError(
                        f"Failed to get valid structured response after {max_retries} attempts: {e}"
                    )
                # Add error context for retry
                augmented_messages.append(
                    Message.assistant(response.content if "response" in dir() else "")
                )
                augmented_messages.append(
                    Message.user(f"That was invalid. Error: {e}. Please try again with valid JSON.")
                )

    # =========================================================================
    # Multi-Modal Support
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        *,
        model: str | None = None,
        size: str | ImageSize = ImageSize.MEDIUM,
        n: int = 1,
        response_format: str = "b64_json",
        **kwargs,
    ) -> ImageGenerationResponse:
        """
        Generate images using Stable Diffusion or other diffusion models.

        Args:
            prompt: Text description of the image
            model: Model to use (e.g., "stablediffusion", "sdxl")
            size: Image size ("256x256", "512x512", "1024x1024")
            n: Number of images to generate
            response_format: "b64_json" for base64, "url" for URLs

        Usage:
            response = await llm.generate_image(
                "A beautiful sunset over mountains",
                size="512x512",
            )
            for img_b64 in response.images:
                # Save or display image
                pass
        """
        size_str = size.value if isinstance(size, ImageSize) else size

        payload = {
            "prompt": prompt,
            "n": n,
            "size": size_str,
            "response_format": response_format,
        }

        if model:
            payload["model"] = model

        payload.update(kwargs)

        data = await self._client.post("/v1/images/generations", json=payload)

        images = []
        for item in data.get("data", []):
            if response_format == "b64_json":
                images.append(item.get("b64_json", ""))
            else:
                images.append(item.get("url", ""))

        return ImageGenerationResponse(
            images=images,
            model=model or "stablediffusion",
            created=data.get("created", 0),
            raw_response=data,
        )

    async def analyze_image(
        self,
        image: str | bytes | Path,
        prompt: str = "Describe this image in detail.",
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> VisionResponse:
        """
        Analyze an image using vision models (LLaVA, BakLLaVA, etc.).

        Args:
            image: Image as base64 string, bytes, file path, or URL
            prompt: Question or instruction about the image
            model: Vision model to use (e.g., "llava", "bakllava")
            max_tokens: Maximum tokens in response

        Usage:
            # From file
            response = await llm.analyze_image("/path/to/image.jpg", "What's in this image?")

            # From URL
            response = await llm.analyze_image("https://example.com/image.jpg")

            # From bytes
            response = await llm.analyze_image(image_bytes, "Describe the scene")
        """
        # Convert image to base64 if needed
        if isinstance(image, Path):
            image_data = image.read_bytes()
            image_b64 = base64.b64encode(image_data).decode()
        elif isinstance(image, bytes):
            image_b64 = base64.b64encode(image).decode()
        elif image.startswith(("http://", "https://")):
            # URL - pass directly
            image_b64 = None
            image_url = image
        elif len(image) > 1000:  # Assume base64
            image_b64 = image
        else:
            # Assume file path
            image_data = Path(image).read_bytes()
            image_b64 = base64.b64encode(image_data).decode()

        # Build content array for multimodal
        content = [{"type": "text", "text": prompt}]

        if image_b64:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                }
            )
        else:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                }
            )

        payload = {
            "model": model or "llava",
            "messages": [{"role": "user", "content": content}],
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        payload.update(kwargs)

        data = await self._client.post("/v1/chat/completions", json=payload)

        choice = data["choices"][0]
        message = choice["message"]

        usage = None
        if "usage" in data:
            usage = Usage(
                prompt_tokens=data["usage"].get("prompt_tokens", 0),
                completion_tokens=data["usage"].get("completion_tokens", 0),
                total_tokens=data["usage"].get("total_tokens", 0),
            )

        return VisionResponse(
            content=message.get("content", ""),
            model=data.get("model", model or "llava"),
            usage=usage,
            raw_response=data,
        )

    async def transcribe(
        self,
        audio: str | bytes | Path,
        *,
        model: str = "whisper-1",
        language: str | None = None,
        response_format: str = "json",
        **kwargs,
    ) -> TranscriptionResponse:
        """
        Transcribe audio using Whisper.

        Args:
            audio: Audio file path, bytes, or base64 string
            model: Whisper model to use
            language: Language code (e.g., "en", "es")
            response_format: "json", "text", "srt", "verbose_json", "vtt"

        Usage:
            response = await llm.transcribe("/path/to/audio.mp3")
            print(response.text)
        """
        # Prepare audio file
        if isinstance(audio, Path):
            audio_path = audio
            audio_bytes = audio.read_bytes()
        elif isinstance(audio, bytes):
            audio_bytes = audio
            audio_path = None
        else:
            audio_path = Path(audio)
            audio_bytes = audio_path.read_bytes()

        # Build multipart form data
        files = {
            "file": (
                audio_path.name if audio_path else "audio.mp3",
                audio_bytes,
                "audio/mpeg",
            )
        }

        data = {"model": model, "response_format": response_format}
        if language:
            data["language"] = language

        data.update(kwargs)

        # Use form data endpoint
        client = self._client._get_client()
        response = await client.post(
            "/v1/audio/transcriptions",
            files=files,
            data=data,
        )
        response.raise_for_status()
        result = response.json()

        return TranscriptionResponse(
            text=result.get("text", ""),
            language=result.get("language"),
            duration=result.get("duration"),
            segments=result.get("segments"),
            raw_response=result,
        )

    async def speak(
        self,
        text: str,
        *,
        model: str = "tts-1",
        voice: str = "alloy",
        response_format: str = "wav",
        speed: float = 1.0,
        **kwargs,
    ) -> SpeechResponse:
        """
        Convert text to speech using TTS models (Bark, Piper, VALL-E-X).

        Args:
            text: Text to convert to speech
            model: TTS model to use
            voice: Voice ID to use
            response_format: Audio format ("wav", "mp3", "opus", "flac")
            speed: Speech speed multiplier

        Usage:
            response = await llm.speak("Hello, how are you?")
            with open("output.wav", "wb") as f:
                f.write(response.audio)
        """
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
            "speed": speed,
        }
        payload.update(kwargs)

        audio_bytes = await self._client.post_raw("/v1/audio/speech", json=payload)

        return SpeechResponse(
            audio=audio_bytes,
            format=response_format,
            raw_response=None,
        )

    # =========================================================================
    # Model Management
    # =========================================================================

    async def list_models(self) -> list[ModelInfo]:
        """
        List all available models.

        Usage:
            models = await llm.list_models()
            for model in models:
                print(f"{model.id}: {model.backend}")
        """
        data = await self._client.get("/v1/models")

        models = []
        for item in data.get("data", []):
            models.append(
                ModelInfo(
                    id=item["id"],
                    object=item.get("object", "model"),
                    owned_by=item.get("owned_by", "localai"),
                    created=item.get("created", 0),
                    backend=item.get("backend"),
                    config=item.get("config"),
                )
            )
        return models

    async def load_model(
        self,
        model: str,
        *,
        config: dict[str, Any] | None = None,
        **kwargs,
    ) -> bool:
        """
        Load a specific model.

        Args:
            model: Model name or path
            config: Model configuration overrides

        Usage:
            success = await llm.load_model("llama-3-8b")
        """
        payload = {"model": model}
        if config:
            payload.update(config)
        payload.update(kwargs)

        try:
            await self._client.post("/models/apply", json=payload)
            return True
        except Exception:
            return False

    async def model_status(self, model: str) -> dict[str, Any]:
        """
        Check if a model is loaded and get its status.

        Usage:
            status = await llm.model_status("llama-3-8b")
            if status.get("loaded"):
                print("Model is ready")
        """
        try:
            data = await self._client.get(f"/models/{model}/status")
            return data
        except Exception:
            return {"loaded": False, "error": "Model not found"}

    async def install_model_from_gallery(
        self,
        name: str,
        *,
        gallery_url: str | None = None,
    ) -> bool:
        """
        Install a model from the LocalAI model gallery.

        Args:
            name: Model name in the gallery
            gallery_url: Custom gallery URL (optional)

        Usage:
            success = await llm.install_model_from_gallery("llama-3-8b")
        """
        payload = {"name": name}
        if gallery_url:
            payload["url"] = gallery_url

        try:
            await self._client.post("/models/apply", json=payload)
            return True
        except Exception:
            return False

    # =========================================================================
    # LocalAI-Specific Features
    # =========================================================================

    async def get_backend_info(self) -> dict[str, Any]:
        """
        Get information about available backends.

        Usage:
            info = await llm.get_backend_info()
            print(info)
        """
        try:
            return await self._client.get("/v1/backends")
        except Exception:
            return {}

    async def configure_gpu(
        self,
        model: str,
        *,
        gpu_layers: int = -1,
        main_gpu: int = 0,
        tensor_split: list[float] | None = None,
    ) -> bool:
        """
        Configure GPU settings for a model.

        Args:
            model: Model to configure
            gpu_layers: Number of layers to offload to GPU (-1 for all)
            main_gpu: Main GPU index
            tensor_split: GPU memory split ratios

        Usage:
            await llm.configure_gpu("llama-3-8b", gpu_layers=40)
        """
        config = {
            "name": model,
            "parameters": {
                "model": model,
                "gpu_layers": gpu_layers,
                "main_gpu": main_gpu,
            },
        }
        if tensor_split:
            config["parameters"]["tensor_split"] = tensor_split

        try:
            await self._client.post("/models/apply", json=config)
            return True
        except Exception:
            return False

    async def p2p_status(self) -> dict[str, Any]:
        """
        Get P2P federation status (if enabled).

        LocalAI supports distributed inference via P2P networking.

        Usage:
            status = await llm.p2p_status()
            print(f"Connected peers: {status.get('peers', [])}")
        """
        try:
            return await self._client.get("/p2p/status")
        except Exception:
            return {"enabled": False, "peers": []}

    async def close(self):
        """Close the HTTP client."""
        await self._client.close()


# =============================================================================
# LocalAI Embeddings
# =============================================================================


class LocalAIEmbeddings(EmbeddingProvider):
    """
    LocalAI embedding provider.

    Supports various embedding models running locally.

    Usage:
        from django_matt.ml import LocalAIEmbeddings

        embedder = LocalAIEmbeddings(
            base_url="http://localhost:8080",
            model="text-embedding-ada-002"  # Or local model name
        )

        response = await embedder.embed(["Hello", "World"])
        vectors = response.embeddings
    """

    DIMENSIONS = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "nomic-embed-text": 768,
        "all-minilm-l6-v2": 384,
        "bge-base-en-v1.5": 768,
        "bge-large-en-v1.5": 1024,
    }

    @property
    def default_model(self) -> str:
        return "text-embedding-ada-002"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS.get(self.model, 1536)

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        timeout: float = 120.0,
        **kwargs,
    ):
        base_url = base_url or os.environ.get("LOCALAI_BASE_URL", "http://localhost:8080")
        api_key = api_key or os.environ.get("LOCALAI_API_KEY")

        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = base_url
        self._dimensions = dimensions
        self._client = LocalAIClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Model to use (overrides default)
        """
        payload = {
            "model": model or self.model,
            "input": texts,
        }

        if self._dimensions:
            payload["dimensions"] = self._dimensions

        payload.update(kwargs)

        data = await self._client.post("/v1/embeddings", json=payload)

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

    async def close(self):
        """Close the HTTP client."""
        await self._client.close()


# =============================================================================
# Helper Functions
# =============================================================================


def _generate_json_grammar(schema: dict[str, Any]) -> str:
    """
    Generate a simple BNF grammar for JSON output from a JSON schema.

    This is a simplified grammar generator. For complex schemas,
    LocalAI's built-in schema support should be used.
    """
    # Basic JSON grammar
    grammar = """
root ::= object
object ::= "{" ws members ws "}"
members ::= pair ("," ws pair)*
pair ::= string ":" ws value
array ::= "[" ws values ws "]"
values ::= value ("," ws value)*
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\\"" chars "\\""
chars ::= char*
char ::= [^"\\\\] | "\\\\" escape
escape ::= ["\\\\nrt]
number ::= int frac? exp?
int ::= "-"? ("0" | [1-9] [0-9]*)
frac ::= "." [0-9]+
exp ::= [eE] [+-]? [0-9]+
ws ::= [ \\t\\n]*
""".strip()
    return grammar


def get_localai_provider(
    base_url: str | None = None,
    **kwargs,
) -> LocalAIProvider:
    """
    Factory function to create a LocalAI provider.

    Usage:
        from django_matt.ml import get_localai_provider

        llm = get_localai_provider(base_url="http://localhost:8080")
    """
    return LocalAIProvider(base_url=base_url, **kwargs)


def get_localai_embeddings(
    base_url: str | None = None,
    **kwargs,
) -> LocalAIEmbeddings:
    """
    Factory function to create LocalAI embeddings provider.

    Usage:
        from django_matt.ml import get_localai_embeddings

        embedder = get_localai_embeddings()
    """
    return LocalAIEmbeddings(base_url=base_url, **kwargs)


__all__ = [
    # Main classes
    "LocalAIProvider",
    "LocalAIEmbeddings",
    "LocalAIClient",
    # Types
    "LocalAIBackend",
    "ImageSize",
    "ModelInfo",
    "ImageGenerationResponse",
    "TranscriptionResponse",
    "SpeechResponse",
    "VisionResponse",
    # Factory functions
    "get_localai_provider",
    "get_localai_embeddings",
]
