"""
AI Provider implementations.

Provides LLM and embedding providers for:
- OpenAI (GPT-4, GPT-3.5, embeddings)
- Anthropic (Claude)
- Google (Gemini)
- Ollama (local models)
- Mistral (Mistral Large, Medium, Small)
- Cohere (Command R, R+, embeddings)
- Groq (fast inference for open models)
- Together AI (wide variety of open models)
- DeepSeek (DeepSeek V2, Coder)
- Perplexity (search-augmented responses)
"""

from django_matt.ai.providers.anthropic import AnthropicProvider
from django_matt.ai.providers.cohere import CohereEmbeddings, CohereProvider
from django_matt.ai.providers.deepseek import DeepSeekProvider
from django_matt.ai.providers.google import GeminiEmbeddings, GeminiProvider
from django_matt.ai.providers.groq import GroqProvider
from django_matt.ai.providers.mistral import MistralEmbeddings, MistralProvider
from django_matt.ai.providers.ollama import OllamaEmbeddings, OllamaProvider
from django_matt.ai.providers.openai import OpenAIEmbeddings, OpenAIProvider
from django_matt.ai.providers.perplexity import PerplexityProvider
from django_matt.ai.providers.together import TogetherEmbeddings, TogetherProvider

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
    # Mistral
    "MistralProvider",
    "MistralEmbeddings",
    # Cohere
    "CohereProvider",
    "CohereEmbeddings",
    # Groq
    "GroqProvider",
    # Together
    "TogetherProvider",
    "TogetherEmbeddings",
    # DeepSeek
    "DeepSeekProvider",
    # Perplexity
    "PerplexityProvider",
]
