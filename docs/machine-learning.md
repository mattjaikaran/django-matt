# Machine Learning & AI

Django Matt provides comprehensive AI/ML integration for building intelligent applications.

## Overview

The AI module (`django_matt.ai`) provides:

- **LLM Providers** - OpenAI, Anthropic, Gemini, Ollama (local)
- **Embeddings** - Text embedding with caching and batching
- **Vector Stores** - pgvector, Pinecone, Qdrant, in-memory
- **RAG Pipelines** - Retrieval-augmented generation
- **Structured Output** - Extract data with Pydantic models

## Quick Start

```python
from django_matt.ai import (
    OpenAIProvider,
    Message,
    InMemoryVectorStore,
    OpenAIEmbeddings,
    RAGChain,
)

# Simple completion
llm = OpenAIProvider()
response = await llm.complete([
    Message.system("You are a helpful assistant."),
    Message.user("What is Django?"),
])
print(response.content)

# RAG pipeline
embedder = OpenAIEmbeddings()
store = InMemoryVectorStore(embedding_provider=embedder)
await store.add_texts(["Django is a Python web framework..."])

rag = RAGChain(llm=llm, vector_store=store)
response = await rag.query("What is Django?")
print(response.answer)
```

## Local LLMs with Ollama

```python
from django_matt.ai import OllamaProvider

# Requires: ollama serve
llm = OllamaProvider(model="llama3.2")
response = await llm.complete([Message.user("Hello!")])
```

## AI IDE Integration

Django Matt can generate context files for AI coding assistants:

```bash
# Generate CLAUDE.md for Claude Code
python manage.py generate_ai_context --format claude

# Generate .cursorrules for Cursor
python manage.py generate_ai_context --format cursor
```

## Full Documentation

For comprehensive documentation, see:

- [AI Overview](./ai/overview.md) - Complete AI module documentation
- [LLM Providers](./ai/overview.md#llm-providers) - OpenAI, Anthropic, Gemini, Ollama
- [Embeddings](./ai/overview.md#embeddings) - Text embedding providers
- [Vector Stores](./ai/overview.md#vector-stores) - Storage backends
- [RAG Pipelines](./ai/overview.md#rag-pipeline) - Retrieval-augmented generation
