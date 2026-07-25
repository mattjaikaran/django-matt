# file-length-max: 550
"""
LLM Response Caching.

Provides caching for LLM responses to reduce costs and latency.
"""

import hashlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, TypeVar

import orjson
from pydantic import BaseModel

from django_matt.ai.base import (
    CompletionResponse,
    LLMProvider,
    Message,
    Role,
    StreamChunk,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


@dataclass
class CacheEntry:
    """A cached response entry."""

    response: CompletionResponse
    created_at: float
    ttl: int
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class CacheStats:
    """Statistics for cache performance."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.total_tokens_saved = 0
        self.estimated_cost_saved = 0.0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def record_hit(self, usage: Usage | None = None) -> None:
        self.hits += 1
        if usage:
            self.total_tokens_saved += usage.total_tokens

    def record_miss(self) -> None:
        self.misses += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "total_tokens_saved": self.total_tokens_saved,
            "estimated_cost_saved": self.estimated_cost_saved,
        }


class CachedLLM:
    """
    Wrapper that adds caching to any LLM provider.

    Caches responses to reduce API costs and improve latency for
    repeated queries.

    Usage:
        from django_matt.ai import CachedLLM, get_provider

        # Basic usage with in-memory cache
        provider = get_provider("openai")
        cached = CachedLLM(provider)

        # First call hits the API
        response = await cached.complete([Message.user("What is 2+2?")])

        # Second call returns cached result
        response = await cached.complete([Message.user("What is 2+2?")])

        # With Redis cache
        from django.core.cache import caches
        cached = CachedLLM(
            provider=get_provider("openai"),
            cache=caches["redis"],
            ttl=3600,
        )

        # Semantic caching (requires embeddings)
        from django_matt.ai import OpenAIEmbeddings
        cached = CachedLLM(
            provider=get_provider("openai"),
            embeddings=OpenAIEmbeddings(),
            similarity_threshold=0.95,
        )
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: Any | None = None,
        cache_prefix: str = "llm:",
        ttl: int = 3600,
        embeddings: Any | None = None,
        similarity_threshold: float = 0.95,
        max_cache_size: int = 10000,
        cost_per_1k_input: float = 0.0,
        cost_per_1k_output: float = 0.0,
    ):
        """
        Initialize cached LLM.

        Args:
            provider: Base LLM provider
            cache: Django cache backend (or None for in-memory)
            cache_prefix: Prefix for cache keys
            ttl: Cache TTL in seconds
            embeddings: Embedding provider for semantic caching
            similarity_threshold: Minimum similarity for semantic cache hit
            max_cache_size: Maximum entries in memory cache
            cost_per_1k_input: Cost per 1K input tokens (for stats)
            cost_per_1k_output: Cost per 1K output tokens (for stats)
        """
        self.provider = provider
        self.cache = cache
        self.cache_prefix = cache_prefix
        self.ttl = ttl
        self.embeddings = embeddings
        self.similarity_threshold = similarity_threshold
        self.max_cache_size = max_cache_size
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output

        self._local_cache: dict[str, CacheEntry] = {}
        self._embedding_cache: dict[str, tuple[list[float], str]] = {}
        self.stats = CacheStats()

    def _cache_key(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """Generate a cache key from messages and parameters."""
        model = model or self.provider.model

        # Create deterministic content hash
        content_parts = []
        for msg in messages:
            content_parts.append(f"{msg.role.value}:{msg.content}")

        content = "|".join(content_parts)
        params = orjson.dumps(
            {"model": model, "temperature": temperature, **kwargs}, option=orjson.OPT_SORT_KEYS
        ).decode()

        hash_input = f"{content}|{params}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()[:32]

        return f"{self.cache_prefix}{hash_val}"

    def _get_messages_text(self, messages: list[Message]) -> str:
        """Extract text content from messages for semantic comparison."""
        return " ".join(msg.content for msg in messages if msg.role in (Role.USER, Role.SYSTEM))

    async def _get_cached(self, key: str) -> CompletionResponse | None:
        """Get value from cache."""
        # Try local cache first
        if key in self._local_cache:
            entry = self._local_cache[key]
            if not entry.is_expired:
                entry.hit_count += 1
                return entry.response
            del self._local_cache[key]

        # Try external cache
        if self.cache:
            try:
                data = self.cache.get(key)
                if data:
                    response = CompletionResponse(
                        content=data["content"],
                        role=Role(data["role"]),
                        model=data.get("model", ""),
                        finish_reason=data.get("finish_reason"),
                        usage=Usage(**data["usage"]) if data.get("usage") else None,
                    )
                    # Store in local cache for faster subsequent access
                    self._local_cache[key] = CacheEntry(
                        response=response,
                        created_at=time.time(),
                        ttl=self.ttl,
                    )
                    return response
            except Exception:
                pass

        return None

    async def _set_cached(self, key: str, response: CompletionResponse) -> None:
        """Set value in cache."""
        # Evict oldest entries if cache is full
        if len(self._local_cache) >= self.max_cache_size:
            oldest_key = min(
                self._local_cache.keys(),
                key=lambda k: self._local_cache[k].created_at,
            )
            del self._local_cache[oldest_key]

        # Store in local cache
        self._local_cache[key] = CacheEntry(
            response=response,
            created_at=time.time(),
            ttl=self.ttl,
        )

        # Store in external cache
        if self.cache:
            try:
                data = {
                    "content": response.content,
                    "role": response.role.value,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                }
                if response.usage:
                    data["usage"] = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                self.cache.set(key, data, self.ttl)
            except Exception:
                pass

    async def _semantic_lookup(self, messages: list[Message]) -> CompletionResponse | None:
        """Look up similar prompts using embeddings."""
        if not self.embeddings or not self._embedding_cache:
            return None

        try:
            from django_matt.ai.embeddings import cosine_similarity

            query_text = self._get_messages_text(messages)
            query_embedding = await self.embeddings.embed_single(query_text)

            best_match = None
            best_similarity = 0.0

            for cache_key, (embedding, _) in self._embedding_cache.items():
                similarity = cosine_similarity(query_embedding, embedding)
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = cache_key

            if best_match:
                return await self._get_cached(best_match)

        except Exception:
            pass

        return None

    async def _store_embedding(self, key: str, messages: list[Message]) -> None:
        """Store embedding for semantic caching."""
        if not self.embeddings:
            return

        try:
            query_text = self._get_messages_text(messages)
            embedding = await self.embeddings.embed_single(query_text)
            self._embedding_cache[key] = (embedding, query_text)

            # Limit embedding cache size
            if len(self._embedding_cache) > self.max_cache_size:
                oldest = list(self._embedding_cache.keys())[0]
                del self._embedding_cache[oldest]

        except Exception:
            pass

    def _update_cost_stats(self, usage: Usage | None) -> None:
        """Update cost savings statistics."""
        if usage:
            cost = (usage.prompt_tokens / 1000) * self.cost_per_1k_input
            cost += (usage.completion_tokens / 1000) * self.cost_per_1k_output
            self.stats.estimated_cost_saved += cost

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        skip_cache: bool = False,
        **kwargs,
    ) -> CompletionResponse:
        """
        Generate a completion with caching.

        Args:
            messages: Conversation history
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            skip_cache: Bypass cache for this request
            **kwargs: Additional provider arguments
        """
        if skip_cache:
            return await self.provider.complete(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

        # Generate cache key
        cache_key = self._cache_key(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Try exact cache match
        cached = await self._get_cached(cache_key)
        if cached:
            self.stats.record_hit(cached.usage)
            self._update_cost_stats(cached.usage)
            return cached

        # Try semantic cache match
        if self.embeddings:
            cached = await self._semantic_lookup(messages)
            if cached:
                self.stats.record_hit(cached.usage)
                self._update_cost_stats(cached.usage)
                return cached

        # Cache miss - call provider
        self.stats.record_miss()
        response = await self.provider.complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Store in cache
        await self._set_cached(cache_key, response)
        await self._store_embedding(cache_key, messages)

        return response

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a completion (bypasses cache).

        Streaming responses are not cached as they are meant for
        real-time output.
        """
        async for chunk in self.provider.stream(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk

    async def complete_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        skip_cache: bool = False,
        **kwargs,
    ) -> T:
        """Generate a structured response with caching."""
        if skip_cache or not hasattr(self.provider, "complete_structured"):
            return await self.provider.complete_structured(
                messages,
                response_model,
                model=model,
                temperature=temperature,
                **kwargs,
            )

        # Create cache key including model name
        cache_key = self._cache_key(
            messages,
            model=model,
            temperature=temperature,
            response_model=response_model.__name__,
            **kwargs,
        )

        # Try cache
        cached = await self._get_cached(cache_key)
        if cached:
            self.stats.record_hit(cached.usage)
            self._update_cost_stats(cached.usage)
            # Parse cached content back to model
            try:
                data = orjson.loads(cached.content)
                return response_model.model_validate(data)
            except Exception:
                pass

        # Cache miss
        self.stats.record_miss()
        result = await self.provider.complete_structured(
            messages,
            response_model,
            model=model,
            temperature=temperature,
            **kwargs,
        )

        # Store as JSON in cache
        response = CompletionResponse(
            content=result.model_dump_json(),
            role=Role.ASSISTANT,
            model=model or self.provider.model,
        )
        await self._set_cached(cache_key, response)

        return result

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._local_cache.clear()
        self._embedding_cache.clear()

    def invalidate(self, messages: list[Message], **kwargs) -> None:
        """Invalidate a specific cache entry."""
        cache_key = self._cache_key(messages, **kwargs)
        self._local_cache.pop(cache_key, None)
        self._embedding_cache.pop(cache_key, None)
        if self.cache:
            try:
                self.cache.delete(cache_key)
            except Exception:
                pass

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self.stats.to_dict()

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = CacheStats()

    @property
    def model(self) -> str:
        return self.provider.model

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name


__all__ = [
    "CacheEntry",
    "CacheStats",
    "CachedLLM",
]
