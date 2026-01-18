"""
Django Matt AI - Machine Learning & LLM Integration.

A comprehensive AI toolkit for Django applications with:
- Unified LLM provider interface (OpenAI, Anthropic, Gemini, Ollama)
- Embedding utilities with caching
- Vector store integrations (pgvector, Pinecone, Qdrant)
- RAG (Retrieval Augmented Generation) pipelines
- Structured output extraction with Pydantic

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
"""

# Base classes and types
from django_matt.ai.base import (
    Role,
    Message,
    ToolDefinition,
    ToolCall,
    Usage,
    CompletionResponse,
    StreamChunk,
    EmbeddingResponse,
    LLMProvider,
    EmbeddingProvider,
    StructuredOutputProvider,
    messages_to_prompt,
)

# Providers
from django_matt.ai.providers import (
    OpenAIProvider,
    OpenAIEmbeddings,
    AnthropicProvider,
    GeminiProvider,
    GeminiEmbeddings,
    OllamaProvider,
    OllamaEmbeddings,
)

# Embeddings utilities
from django_matt.ai.embeddings import (
    CachedEmbeddings,
    BatchEmbeddings,
    cosine_similarity,
    euclidean_distance,
    dot_product,
    normalize_vector,
    find_most_similar,
)

# Vector stores
from django_matt.ai.vectorstore import (
    Document,
    SearchResult,
    VectorStore,
    InMemoryVectorStore,
    PgVectorStore,
    PineconeVectorStore,
    QdrantVectorStore,
)

# RAG utilities
from django_matt.ai.rag import (
    Chunk,
    TextSplitter,
    CharacterSplitter,
    RecursiveSplitter,
    SentenceSplitter,
    ConversationMemory,
    SummaryMemory,
    RAGResponse,
    RAGChain,
    MultiQueryRAG,
)


# Convenience function for getting a provider
def get_provider(
    name: str,
    **kwargs,
) -> LLMProvider:
    """
    Get an LLM provider by name.

    Args:
        name: Provider name (openai, anthropic, gemini, ollama)
        **kwargs: Provider-specific arguments

    Usage:
        llm = get_provider("openai")
        llm = get_provider("anthropic", model="claude-3-opus-20240229")
        llm = get_provider("ollama", model="llama3.2")
    """
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "ollama": OllamaProvider,
    }

    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(
            f"Unknown provider: {name}. "
            f"Available: {', '.join(providers.keys())}"
        )

    return provider_class(**kwargs)


def get_embeddings(
    name: str,
    **kwargs,
) -> EmbeddingProvider:
    """
    Get an embedding provider by name.

    Args:
        name: Provider name (openai, gemini, ollama)
        **kwargs: Provider-specific arguments

    Usage:
        embedder = get_embeddings("openai")
        embedder = get_embeddings("ollama", model="nomic-embed-text")
    """
    providers = {
        "openai": OpenAIEmbeddings,
        "gemini": GeminiEmbeddings,
        "google": GeminiEmbeddings,
        "ollama": OllamaEmbeddings,
    }

    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(
            f"Unknown embedding provider: {name}. "
            f"Available: {', '.join(providers.keys())}"
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
    # Providers - Embeddings
    "OpenAIEmbeddings",
    "GeminiEmbeddings",
    "OllamaEmbeddings",
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
    # RAG - Memory
    "ConversationMemory",
    "SummaryMemory",
    # RAG - Chain
    "RAGResponse",
    "RAGChain",
    "MultiQueryRAG",
    # Utilities
    "messages_to_prompt",
    "get_provider",
    "get_embeddings",
]
