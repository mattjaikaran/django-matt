"""
Embedding utilities.

Provides caching, batching, and helper functions for embeddings.
"""

import hashlib
from typing import Any

from django_matt.ai.base import EmbeddingProvider, EmbeddingResponse


class CachedEmbeddings:
    """
    Wrapper that adds caching to any embedding provider.

    Caches embeddings to avoid redundant API calls for the same text.

    Usage:
        from django_matt.ai import OpenAIEmbeddings, CachedEmbeddings

        base_embedder = OpenAIEmbeddings()
        embedder = CachedEmbeddings(base_embedder, cache=my_cache)

        # First call hits the API
        v1 = await embedder.embed_single("Hello world")

        # Second call returns cached result
        v2 = await embedder.embed_single("Hello world")
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        cache: Any | None = None,
        cache_prefix: str = "embed:",
        ttl: int = 86400 * 7,  # 1 week default
    ):
        """
        Initialize cached embeddings.

        Args:
            provider: Base embedding provider
            cache: Django cache instance (or None for in-memory)
            cache_prefix: Prefix for cache keys
            ttl: Cache TTL in seconds
        """
        self.provider = provider
        self.cache = cache
        self.cache_prefix = cache_prefix
        self.ttl = ttl
        self._local_cache: dict[str, list[float]] = {}

    def _cache_key(self, text: str, model: str | None = None) -> str:
        """Generate a cache key for text."""
        model = model or self.provider.model
        content = f"{model}:{text}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{self.cache_prefix}{hash_val}"

    async def _get_cached(self, key: str) -> list[float] | None:
        """Get value from cache."""
        # Try local cache first
        if key in self._local_cache:
            return self._local_cache[key]

        # Try Django cache
        if self.cache:
            value = self.cache.get(key)
            if value:
                self._local_cache[key] = value
                return value

        return None

    async def _set_cached(self, key: str, value: list[float]) -> None:
        """Set value in cache."""
        self._local_cache[key] = value
        if self.cache:
            self.cache.set(key, value, self.ttl)

    async def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Generate embeddings with caching.

        Cached embeddings are returned from cache, uncached ones
        are fetched from the provider and then cached.
        """
        results: dict[int, list[float]] = {}
        uncached_texts: list[tuple[int, str]] = []

        # Check cache for each text
        for i, text in enumerate(texts):
            key = self._cache_key(text, model)
            cached = await self._get_cached(key)
            if cached:
                results[i] = cached
            else:
                uncached_texts.append((i, text))

        # Fetch uncached embeddings
        if uncached_texts:
            indices, texts_to_embed = zip(*uncached_texts, strict=False)
            response = await self.provider.embed(list(texts_to_embed), model=model, **kwargs)

            # Cache and store results
            for idx, (original_idx, text) in enumerate(uncached_texts):
                embedding = response.embeddings[idx]
                key = self._cache_key(text, model)
                await self._set_cached(key, embedding)
                results[original_idx] = embedding

        # Reconstruct ordered results
        embeddings = [results[i] for i in range(len(texts))]

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model or self.provider.model,
        )

    async def embed_single(self, text: str, **kwargs) -> list[float]:
        """Embed a single text with caching."""
        response = await self.embed([text], **kwargs)
        return response.embeddings[0]

    def clear_cache(self) -> None:
        """Clear the local cache."""
        self._local_cache.clear()

    @property
    def model(self) -> str:
        return self.provider.model

    @property
    def dimensions(self) -> int:
        return self.provider.dimensions


class BatchEmbeddings:
    """
    Utility for efficiently embedding large numbers of texts.

    Automatically batches requests to stay within API limits.

    Usage:
        from django_matt.ai import OpenAIEmbeddings, BatchEmbeddings

        embedder = OpenAIEmbeddings()
        batch = BatchEmbeddings(embedder, batch_size=100)

        # Embed 10,000 texts efficiently
        texts = ["text 1", "text 2", ..., "text 10000"]
        embeddings = await batch.embed_all(texts)
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        batch_size: int = 100,
        max_concurrent: int = 5,
    ):
        """
        Initialize batch embeddings.

        Args:
            provider: Base embedding provider
            batch_size: Texts per batch
            max_concurrent: Maximum concurrent requests
        """
        self.provider = provider
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

    async def embed_all(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        show_progress: bool = False,
        **kwargs,
    ) -> list[list[float]]:
        """
        Embed all texts in batches.

        Args:
            texts: Texts to embed
            model: Model to use
            show_progress: Print progress (requires tqdm)
            **kwargs: Additional provider arguments
        """
        import asyncio

        all_embeddings: list[list[float] | None] = [None] * len(texts)

        # Create batches
        batches = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            batches.append((i, batch_texts))

        # Process with progress tracking
        iterator = batches
        if show_progress:
            try:
                from tqdm import tqdm

                iterator = tqdm(batches, desc="Embedding", unit="batch")
            except ImportError:
                pass

        # Process batches with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_batch(start_idx: int, batch_texts: list[str]):
            async with semaphore:
                response = await self.provider.embed(batch_texts, model=model, **kwargs)
                for j, embedding in enumerate(response.embeddings):
                    all_embeddings[start_idx + j] = embedding

        tasks = [process_batch(i, batch) for i, batch in iterator]
        await asyncio.gather(*tasks)

        return all_embeddings  # type: ignore


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Returns a value between -1 and 1, where 1 means identical direction.
    """
    import math

    dot_product = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Calculate Euclidean distance between two vectors."""
    import math

    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=False)))


def dot_product(a: list[float], b: list[float]) -> float:
    """Calculate dot product between two vectors."""
    return sum(x * y for x, y in zip(a, b, strict=False))


def normalize_vector(v: list[float]) -> list[float]:
    """Normalize a vector to unit length."""
    import math

    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0:
        return v
    return [x / norm for x in v]


def find_most_similar(
    query_embedding: list[float],
    embeddings: list[list[float]],
    top_k: int = 5,
    metric: str = "cosine",
) -> list[tuple[int, float]]:
    """
    Find the most similar embeddings to a query.

    Args:
        query_embedding: Query vector
        embeddings: List of vectors to search
        top_k: Number of results to return
        metric: Similarity metric ("cosine", "euclidean", "dot")

    Returns:
        List of (index, score) tuples, sorted by similarity
    """
    if metric == "cosine":
        scores = [(i, cosine_similarity(query_embedding, e)) for i, e in enumerate(embeddings)]
        scores.sort(key=lambda x: x[1], reverse=True)
    elif metric == "euclidean":
        scores = [(i, euclidean_distance(query_embedding, e)) for i, e in enumerate(embeddings)]
        scores.sort(key=lambda x: x[1])  # Lower is better
    elif metric == "dot":
        scores = [(i, dot_product(query_embedding, e)) for i, e in enumerate(embeddings)]
        scores.sort(key=lambda x: x[1], reverse=True)
    else:
        raise ValueError(f"Unknown metric: {metric}")

    return scores[:top_k]


__all__ = [
    "BatchEmbeddings",
    "CachedEmbeddings",
    "cosine_similarity",
    "dot_product",
    "euclidean_distance",
    "find_most_similar",
    "normalize_vector",
]
