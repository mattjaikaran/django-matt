"""
Django Matt ML - Machine Learning Integration Module.

Provides local LLM inference with multi-modal capabilities:
- llama.cpp integration via llama-cpp-python (direct GGUF model loading)
- vLLM integration for high-throughput serving
- LocalAI integration for self-hosted inference
- OpenAI-compatible API
- Multi-modal support (images, audio, vision)
- Grammar-constrained generation (GBNF)
- Guided decoding (JSON schema, regex, grammar)
- Batch inference with priority queuing
- Model management

llama.cpp (Direct GGUF Model Loading):
    from django_matt.ml import LlamaCppProvider, Message

    # Load a local GGUF model
    llm = LlamaCppProvider(
        model_path="/path/to/model.gguf",
        n_ctx=4096,
        n_gpu_layers=-1,  # Use all GPU layers
    )

    response = await llm.complete([
        Message.system("You are helpful."),
        Message.user("What is Python?"),
    ])
    print(response.content)

    # Streaming
    async for chunk in llm.stream([Message.user("Tell a story")]):
        print(chunk.content, end="", flush=True)

    # Grammar-constrained output
    response = await llm.complete(
        [Message.user("List 3 colors")],
        grammar="json",  # Force JSON output
    )

    # Structured output with Pydantic
    from pydantic import BaseModel

    class Colors(BaseModel):
        colors: list[str]

    colors = await llm.complete_structured(
        [Message.user("List 3 colors")],
        response_model=Colors,
    )

    # Using LlamaCppModel directly
    from django_matt.ml import LlamaCppModel

    model = LlamaCppModel.from_file("model.gguf")
    print(f"Quantization: {model.quantization}")
    print(f"VRAM: {model.estimate_vram_mb()} MB")

    # Embeddings
    from django_matt.ml import LlamaCppEmbeddings

    embedder = LlamaCppEmbeddings(model_path="embedding-model.gguf")
    vectors = await embedder.embed(["Hello", "World"])

vLLM (High-Throughput Serving):
    from django_matt.ml import VLLMProvider, VLLMClient
    from django_matt.ai import Message

    # High-level provider interface
    llm = VLLMProvider(base_url="http://localhost:8000")

    response = await llm.complete([
        Message.system("You are helpful."),
        Message.user("Hello!"),
    ])

    # Streaming
    async for chunk in llm.stream([Message.user("Tell a story")]):
        print(chunk.content, end="", flush=True)

    # Guided decoding (JSON schema)
    response = await llm.complete(
        [Message.user("Extract: John is 30")],
        guided_json={"type": "object", "properties": {"name": {"type": "string"}}},
    )

    # Batch processing
    results = await llm.batch_generate(["prompt1", "prompt2", "prompt3"])

    # Health and metrics
    health = await llm.health_check()
    metrics = await llm.get_metrics()

LocalAI (Self-Hosted):
    from django_matt.ml import LocalAIProvider, Message

    # Basic usage
    llm = LocalAIProvider(base_url="http://localhost:8080")

    response = await llm.complete([
        Message.system("You are helpful."),
        Message.user("Hello!"),
    ])
    print(response.content)

    # Streaming
    async for chunk in llm.stream([Message.user("Tell a story")]):
        print(chunk.content, end="", flush=True)

Multi-Modal:
    # Image generation
    response = await llm.generate_image("A sunset over mountains")

    # Vision (image analysis)
    response = await llm.analyze_image("/path/to/image.jpg", "What's in this image?")

    # Speech-to-text
    response = await llm.transcribe("/path/to/audio.mp3")

    # Text-to-speech
    response = await llm.speak("Hello, how are you?")

Embeddings:
    from django_matt.ml import LocalAIEmbeddings

    embedder = LocalAIEmbeddings()
    response = await embedder.embed(["Hello", "World"])
    vectors = response.embeddings

Model Management:
    models = await llm.list_models()
    await llm.load_model("llama-3-8b")
    status = await llm.model_status("llama-3-8b")

Installation for llama.cpp:
    pip install llama-cpp-python

    # For GPU support:
    # macOS: Metal is auto-enabled on Apple Silicon
    # NVIDIA: CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
    # AMD: CMAKE_ARGS="-DLLAMA_HIPBLAS=on" pip install llama-cpp-python
"""

from django_matt.ai.base import (
    CompletionResponse,
    EmbeddingResponse,
    LLMProvider,
    Message,
    Role,
    StreamChunk,
    ToolCall,
    ToolDefinition,
    Usage,
)

# llama.cpp imports (with graceful fallback if not installed)
try:
    from django_matt.ml.llamacpp import (
        # Main classes
        LlamaCppProvider,
        LlamaCppEmbeddings,
        LlamaCppModel,
        # Configuration
        LlamaCppModelConfig,
        SamplingParams as LlamaCppSamplingParams,
        # Enums
        QuantizationLevel,
        GPUBackend,
        ChatTemplate,
        # Chat templates
        CHAT_TEMPLATES,
        apply_chat_template,
        # Grammar
        GBNF_GRAMMARS,
        create_grammar,
        pydantic_to_gbnf,
        # Utilities
        detect_quantization,
        estimate_memory_usage,
        get_optimal_threads,
        detect_gpu_backend,
        list_available_models,
        # Availability flag
        LLAMA_CPP_AVAILABLE,
    )
except ImportError:
    # llama-cpp-python not installed
    LLAMA_CPP_AVAILABLE = False
    LlamaCppProvider = None  # type: ignore
    LlamaCppEmbeddings = None  # type: ignore
    LlamaCppModel = None  # type: ignore
    LlamaCppModelConfig = None  # type: ignore
    LlamaCppSamplingParams = None  # type: ignore
    QuantizationLevel = None  # type: ignore
    GPUBackend = None  # type: ignore
    ChatTemplate = None  # type: ignore
    CHAT_TEMPLATES = {}  # type: ignore
    apply_chat_template = None  # type: ignore
    GBNF_GRAMMARS = {}  # type: ignore
    create_grammar = None  # type: ignore
    pydantic_to_gbnf = None  # type: ignore
    detect_quantization = None  # type: ignore
    estimate_memory_usage = None  # type: ignore
    get_optimal_threads = None  # type: ignore
    detect_gpu_backend = None  # type: ignore
    list_available_models = None  # type: ignore

from django_matt.ml.localai import (
    ImageGenerationResponse,
    ImageSize,
    LocalAIBackend,
    LocalAIClient,
    LocalAIEmbeddings,
    LocalAIProvider,
    ModelInfo,
    SpeechResponse,
    TranscriptionResponse,
    VisionResponse,
    get_localai_embeddings,
    get_localai_provider,
)
from django_matt.ml.vllm import (
    BatchRequest,
    BatchResult,
    GuidedDecodingParams,
    GuidedDecodingType,
    LoRAConfig,
    ModelInfo as VLLMModelInfo,
    SamplingParams,
    ServerMetrics,
    VLLMClient,
    VLLMProvider,
)

__all__ = [
    # Re-exported from ai.base for convenience
    "Message",
    "Role",
    "Usage",
    "CompletionResponse",
    "StreamChunk",
    "EmbeddingResponse",
    "LLMProvider",
    "ToolDefinition",
    "ToolCall",
    # llama.cpp
    "LlamaCppProvider",
    "LlamaCppEmbeddings",
    "LlamaCppModel",
    "LlamaCppModelConfig",
    "LlamaCppSamplingParams",
    "QuantizationLevel",
    "GPUBackend",
    "ChatTemplate",
    "CHAT_TEMPLATES",
    "apply_chat_template",
    "GBNF_GRAMMARS",
    "create_grammar",
    "pydantic_to_gbnf",
    "detect_quantization",
    "estimate_memory_usage",
    "get_optimal_threads",
    "detect_gpu_backend",
    "list_available_models",
    "LLAMA_CPP_AVAILABLE",
    # vLLM
    "VLLMProvider",
    "VLLMClient",
    "SamplingParams",
    "GuidedDecodingParams",
    "GuidedDecodingType",
    "LoRAConfig",
    "BatchRequest",
    "BatchResult",
    "ServerMetrics",
    "VLLMModelInfo",
    # LocalAI
    "LocalAIProvider",
    "LocalAIEmbeddings",
    "LocalAIClient",
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
