"""
AI Provider implementations.

Provides LLM and embedding providers for:
- OpenAI (GPT-4, GPT-3.5, embeddings)
- Anthropic (Claude)
- Google (Gemini)
- Ollama (local models)
"""

from django_matt.ai.providers.openai import OpenAIProvider, OpenAIEmbeddings
from django_matt.ai.providers.anthropic import AnthropicProvider
from django_matt.ai.providers.google import GeminiProvider, GeminiEmbeddings
from django_matt.ai.providers.ollama import OllamaProvider, OllamaEmbeddings


__all__ = [
    # OpenAI
    "OpenAIProvider",
    "OpenAIEmbeddings",
    # Anthropic
    "AnthropicProvider",
    # Google
    "GeminiProvider",
    "GeminiEmbeddings",
    # Ollama
    "OllamaProvider",
    "OllamaEmbeddings",
]
