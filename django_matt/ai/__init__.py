# file-length-max: 450
"""
Django Matt AI - Machine Learning & LLM Integration.

A comprehensive AI toolkit for Django applications with:
- Unified LLM provider interface (OpenAI, Anthropic, Gemini, Ollama, Mistral, Cohere, Groq, Together, DeepSeek, Perplexity)
- Embedding utilities with caching
- Vector store integrations (pgvector, Pinecone, Qdrant)
- RAG (Retrieval Augmented Generation) pipelines
- Structured output extraction with Pydantic
- LLM Router for failover and load balancing
- Response caching for cost reduction
- Streaming utilities with SSE support

Quick Start:
    from django_matt.ai import (
        OpenAIProvider,
        Message,
        InMemoryVectorStore,
        RAGChain,
    )

    # Simple completion
    llm = OpenAIProvider()  # Uses OPENAI_API_KEY env var
    response = await llm.complete([
        Message.system("You are helpful."),
        Message.user("Hello!"),
    ])
    print(response.content)

    # Streaming
    async for chunk in llm.stream([Message.user("Tell a story")]):
        print(chunk.content, end="", flush=True)

    # Structured output
    from pydantic import BaseModel

    class Person(BaseModel):
        name: str
        age: int

    person = await llm.complete_structured(
        [Message.user("Extract: John is 30")],
        response_model=Person,
    )

    # RAG pipeline
    from django_matt.ai import OpenAIEmbeddings

    embedder = OpenAIEmbeddings()
    store = InMemoryVectorStore(embedding_provider=embedder)
    await store.add_texts(["Python is a language", "Django is a framework"])

    rag = RAGChain(llm=llm, vector_store=store)
    response = await rag.query("What is Django?")
    print(response.answer)

Local LLMs with Ollama:
    from django_matt.ai import OllamaProvider

    llm = OllamaProvider(model="llama3.2")  # Requires: ollama serve
    response = await llm.complete([Message.user("Hello!")])

    # List available models
    models = await llm.list_models()

    # Pull a new model
    async for progress in llm.pull_model("mistral"):
        print(progress)

Fast Inference with Groq:
    from django_matt.ai import GroqProvider

    llm = GroqProvider()  # Uses GROQ_API_KEY env var
    response = await llm.complete([Message.user("Hello!")])
    # Extremely fast inference for open models

Search-Augmented with Perplexity:
    from django_matt.ai import PerplexityProvider

    llm = PerplexityProvider()  # Uses PERPLEXITY_API_KEY env var
    response = await llm.search("What happened in tech news today?")
    citations = llm.get_citations(response)  # Get sources

LLM Router with Failover:
    from django_matt.ai import LLMRouter

    router = LLMRouter(
        primary="groq",  # Fast
        fallback=["anthropic", "openai"],  # Reliable
    )
    response = await router.complete([Message.user("Hello!")])

Cached Responses:
    from django_matt.ai import CachedLLM, get_provider

    cached = CachedLLM(
        provider=get_provider("openai"),
        ttl=3600,  # Cache for 1 hour
    )
    response = await cached.complete([Message.user("FAQ answer")])
    # Second call returns cached result

Streaming with SSE:
    from django_matt.ai import StreamingLLM
    from django.http import StreamingHttpResponse

    streaming = StreamingLLM(get_provider("openai"))

    async def chat_stream(request):
        return StreamingHttpResponse(
            streaming.stream_sse([Message.user(request.GET["prompt"])]),
            content_type="text/event-stream",
        )
"""

# Base classes and types
# Agents
from django_matt.ai.agents import Agent, AgentConfig, AgentResponse
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
    messages_to_prompt,
)

# Cache utilities
from django_matt.ai.cache import (
    CachedLLM,
    CacheEntry,
    CacheStats,
)

# Embeddings utilities
from django_matt.ai.embeddings import (
    BatchEmbeddings,
    CachedEmbeddings,
    cosine_similarity,
    dot_product,
    euclidean_distance,
    find_most_similar,
    normalize_vector,
)

# Observability
from django_matt.ai.observability import (
    AgentEvent,
    CallbackHook,
    CompositeHook,
    EventType,
    LoggingHook,
    ObservabilityHook,
)

# Providers
from django_matt.ai.providers import (
    AnthropicProvider,
    CohereEmbeddings,
    CohereProvider,
    DeepSeekProvider,
    GeminiEmbeddings,
    GeminiProvider,
    GroqProvider,
    MistralEmbeddings,
    MistralProvider,
    OllamaEmbeddings,
    OllamaProvider,
    OpenAIEmbeddings,
    OpenAIProvider,
    PerplexityProvider,
    TogetherEmbeddings,
    TogetherProvider,
)

# RAG utilities
from django_matt.ai.rag import (
    CharacterSplitter,
    Chunk,
    ConversationMemory,
    MultiQueryRAG,
    RAGChain,
    RAGResponse,
    RecursiveSplitter,
    SentenceSplitter,
    SummaryMemory,
    TextSplitter,
    TokenSplitter,
)

# Router
from django_matt.ai.router import (
    LLMRouter,
    ProviderConfig,
    ProviderMetrics,
    RouterConfig,
    RoutingStrategy,
)

# Streaming utilities
from django_matt.ai.streaming import (
    StreamingConfig,
    StreamingLLM,
    StreamStats,
    TokenCounter,
    create_sse_response,
)

# Tools
from django_matt.ai.tools import ToolRegistry, is_tool, tool

# Vector stores
from django_matt.ai.vectorstore import (
    Document,
    InMemoryVectorStore,
    PgVectorStore,
    PineconeVectorStore,
    QdrantVectorStore,
    SearchResult,
    VectorStore,
)


# Convenience function for getting a provider
def get_provider(
    name: str,
    **kwargs,
) -> LLMProvider:
    """
    Get an LLM provider by name.

    Args:
        name: Provider name (openai, anthropic, gemini, ollama, mistral,
              cohere, groq, together, deepseek, perplexity)
        **kwargs: Provider-specific arguments

    Usage:
        llm = get_provider("openai")
        llm = get_provider("anthropic", model="claude-3-opus-20240229")
        llm = get_provider("groq", model="llama-3.1-70b-versatile")
        llm = get_provider("perplexity")  # Search-augmented
    """
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "ollama": OllamaProvider,
        "mistral": MistralProvider,
        "cohere": CohereProvider,
        "groq": GroqProvider,
        "together": TogetherProvider,
        "deepseek": DeepSeekProvider,
        "perplexity": PerplexityProvider,
    }

    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {name}. Available: {', '.join(providers.keys())}")

    return provider_class(**kwargs)


def get_embeddings(
    name: str,
    **kwargs,
) -> EmbeddingProvider:
    """
    Get an embedding provider by name.

    Args:
        name: Provider name (openai, gemini, ollama, mistral, cohere, together)
        **kwargs: Provider-specific arguments

    Usage:
        embedder = get_embeddings("openai")
        embedder = get_embeddings("cohere", input_type="search_document")
        embedder = get_embeddings("mistral")
    """
    providers = {
        "openai": OpenAIEmbeddings,
        "gemini": GeminiEmbeddings,
        "google": GeminiEmbeddings,
        "ollama": OllamaEmbeddings,
        "mistral": MistralEmbeddings,
        "cohere": CohereEmbeddings,
        "together": TogetherEmbeddings,
    }

    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(
            f"Unknown embedding provider: {name}. Available: {', '.join(providers.keys())}"
        )

    return provider_class(**kwargs)


__all__ = [
    # Base types
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
    # Providers - LLM
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OllamaProvider",
    "MistralProvider",
    "CohereProvider",
    "GroqProvider",
    "TogetherProvider",
    "DeepSeekProvider",
    "PerplexityProvider",
    # Providers - Embeddings
    "OpenAIEmbeddings",
    "GeminiEmbeddings",
    "OllamaEmbeddings",
    "MistralEmbeddings",
    "CohereEmbeddings",
    "TogetherEmbeddings",
    # Embedding utilities
    "CachedEmbeddings",
    "BatchEmbeddings",
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    "normalize_vector",
    "find_most_similar",
    # Vector stores
    "Document",
    "SearchResult",
    "VectorStore",
    "InMemoryVectorStore",
    "PgVectorStore",
    "PineconeVectorStore",
    "QdrantVectorStore",
    # RAG - Chunking
    "Chunk",
    "TextSplitter",
    "CharacterSplitter",
    "RecursiveSplitter",
    "SentenceSplitter",
    "TokenSplitter",
    # RAG - Memory
    "ConversationMemory",
    "SummaryMemory",
    # RAG - Chain
    "RAGResponse",
    "RAGChain",
    "MultiQueryRAG",
    # Router
    "LLMRouter",
    "RouterConfig",
    "RoutingStrategy",
    "ProviderConfig",
    "ProviderMetrics",
    # Cache
    "CachedLLM",
    "CacheEntry",
    "CacheStats",
    # Streaming
    "StreamingLLM",
    "StreamingConfig",
    "StreamStats",
    "TokenCounter",
    "create_sse_response",
    # Agents
    "Agent",
    "AgentConfig",
    "AgentResponse",
    # Tools
    "tool",
    "ToolRegistry",
    "is_tool",
    # Observability
    "ObservabilityHook",
    "CallbackHook",
    "CompositeHook",
    "LoggingHook",
    "AgentEvent",
    "EventType",
    # Utilities
    "messages_to_prompt",
    "get_provider",
    "get_embeddings",
]
