"""
Vector store integrations.

Provides a unified interface for vector databases including:
- pgvector (PostgreSQL)
- Pinecone
- Qdrant
- In-memory (for development)
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from django_matt.ai.base import EmbeddingProvider


@dataclass
class Document:
    """
    A document with text, embedding, and metadata.

    Attributes:
        id: Unique identifier
        text: Document text content
        embedding: Vector embedding (optional, can be computed)
        metadata: Additional metadata
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """
    A search result from a vector query.

    Attributes:
        document: The matching document
        score: Similarity/distance score
        rank: Position in results
    """

    document: Document
    score: float
    rank: int = 0


class VectorStore(ABC):
    """
    Abstract base class for vector stores.

    Provides a unified interface for storing and querying vectors.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        collection_name: str = "documents",
        dimensions: int | None = None,
    ):
        """
        Initialize vector store.

        Args:
            embedding_provider: Provider for generating embeddings
            collection_name: Name of the collection/table
            dimensions: Vector dimensions (required if no provider)
        """
        self.embedding_provider = embedding_provider
        self.collection_name = collection_name
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        if self._dimensions:
            return self._dimensions
        if self.embedding_provider:
            return self.embedding_provider.dimensions
        raise ValueError("dimensions required if no embedding_provider")

    async def _ensure_embedding(self, doc: Document) -> list[float]:
        """Ensure document has an embedding."""
        if doc.embedding:
            return doc.embedding
        if not self.embedding_provider:
            raise ValueError("No embedding and no embedding_provider")
        return await self.embedding_provider.embed_single(doc.text)

    @abstractmethod
    async def add(self, documents: list[Document]) -> list[str]:
        """
        Add documents to the store.

        Args:
            documents: Documents to add (embeddings computed if missing)

        Returns:
            List of document IDs
        """

    @abstractmethod
    async def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            query: Query text or embedding vector
            top_k: Number of results to return
            filter: Metadata filter

        Returns:
            List of search results
        """

    @abstractmethod
    async def delete(self, ids: list[str]) -> int:
        """
        Delete documents by ID.

        Returns:
            Number of documents deleted
        """

    @abstractmethod
    async def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""

    async def search_text(
        self,
        query: str,
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search using text query (embedding computed automatically)."""
        return await self.search(query, top_k=top_k, filter=filter)

    async def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """
        Convenience method to add texts directly.

        Args:
            texts: Text contents
            metadatas: Optional metadata for each text
            ids: Optional IDs (generated if not provided)
        """
        metadatas = metadatas or [{} for _ in texts]
        ids = ids or [str(uuid.uuid4()) for _ in texts]

        documents = [
            Document(id=id_, text=text, metadata=meta)
            for id_, text, meta in zip(ids, texts, metadatas, strict=False)
        ]
        return await self.add(documents)


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store for development and testing.

    Usage:
        from django_matt.ai import InMemoryVectorStore, OpenAIEmbeddings

        store = InMemoryVectorStore(
            embedding_provider=OpenAIEmbeddings(),
        )

        # Add documents
        await store.add_texts(["Hello world", "Goodbye world"])

        # Search
        results = await store.search("greeting")
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._documents: dict[str, Document] = {}

    async def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the store."""
        ids = []
        for doc in documents:
            # Compute embedding if needed
            if not doc.embedding:
                doc.embedding = await self._ensure_embedding(doc)
            self._documents[doc.id] = doc
            ids.append(doc.id)
        return ids

    async def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        from django_matt.ai.embeddings import cosine_similarity

        # Get query embedding
        if isinstance(query, str):
            if not self.embedding_provider:
                raise ValueError("embedding_provider required for text queries")
            query_embedding = await self.embedding_provider.embed_single(query)
        else:
            query_embedding = query

        # Calculate similarities
        results = []
        for doc in self._documents.values():
            # Apply metadata filter
            if filter:
                match = all(doc.metadata.get(k) == v for k, v in filter.items())
                if not match:
                    continue

            if doc.embedding:
                score = cosine_similarity(query_embedding, doc.embedding)
                results.append((doc, score))

        # Sort by score and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return [
            SearchResult(document=doc, score=score, rank=i)
            for i, (doc, score) in enumerate(results[:top_k])
        ]

    async def delete(self, ids: list[str]) -> int:
        """Delete documents by ID."""
        count = 0
        for id_ in ids:
            if id_ in self._documents:
                del self._documents[id_]
                count += 1
        return count

    async def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""
        return [self._documents[id_] for id_ in ids if id_ in self._documents]

    def clear(self) -> None:
        """Clear all documents."""
        self._documents.clear()


class PgVectorStore(VectorStore):
    """
    PostgreSQL pgvector store.

    Requires pgvector extension and psycopg or asyncpg.

    Usage:
        from django_matt.ai import PgVectorStore, OpenAIEmbeddings

        store = PgVectorStore(
            embedding_provider=OpenAIEmbeddings(),
            connection_string="postgresql://...",
            collection_name="documents",
        )

        await store.create_table()
        await store.add_texts(["Hello", "World"])
        results = await store.search("greeting")
    """

    def __init__(
        self,
        connection_string: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.connection_string = connection_string
        self._pool = None

    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import asyncpg
            except ImportError:
                raise ImportError(
                    "asyncpg required for PgVectorStore. Install with: uv add asyncpg"
                )

            self._pool = await asyncpg.create_pool(self.connection_string)
        return self._pool

    async def create_table(self) -> None:
        """Create the vector table if it doesn't exist."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            # Ensure pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Create table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.collection_name} (
                    id TEXT PRIMARY KEY,
                    text TEXT,
                    embedding vector({self.dimensions}),
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create index for similarity search
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {self.collection_name}_embedding_idx
                ON {self.collection_name}
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

    async def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the store."""
        pool = await self._get_pool()
        ids = []

        async with pool.acquire() as conn:
            for doc in documents:
                embedding = await self._ensure_embedding(doc)
                embedding_str = f"[{','.join(str(x) for x in embedding)}]"

                await conn.execute(
                    f"""
                    INSERT INTO {self.collection_name} (id, text, embedding, metadata)
                    VALUES ($1, $2, $3::vector, $4::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    doc.id,
                    doc.text,
                    embedding_str,
                    __import__("json").dumps(doc.metadata),
                )
                ids.append(doc.id)

        return ids

    async def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        pool = await self._get_pool()

        # Get query embedding
        if isinstance(query, str):
            if not self.embedding_provider:
                raise ValueError("embedding_provider required for text queries")
            query_embedding = await self.embedding_provider.embed_single(query)
        else:
            query_embedding = query

        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        # Build filter clause
        filter_clause = ""
        params = [embedding_str, top_k]
        if filter:
            conditions = []
            for i, (key, value) in enumerate(filter.items(), start=3):
                conditions.append(f"metadata->>'{key}' = ${i}")
                params.append(str(value))
            if conditions:
                filter_clause = "WHERE " + " AND ".join(conditions)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, text, metadata, 1 - (embedding <=> $1::vector) as score
                FROM {self.collection_name}
                {filter_clause}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                *params,
            )

        return [
            SearchResult(
                document=Document(
                    id=row["id"],
                    text=row["text"],
                    metadata=__import__("json").loads(row["metadata"]) if row["metadata"] else {},
                ),
                score=float(row["score"]),
                rank=i,
            )
            for i, row in enumerate(rows)
        ]

    async def delete(self, ids: list[str]) -> int:
        """Delete documents by ID."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self.collection_name} WHERE id = ANY($1)",
                ids,
            )
            return int(result.split()[-1])

    async def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, text, metadata FROM {self.collection_name} WHERE id = ANY($1)",
                ids,
            )

        return [
            Document(
                id=row["id"],
                text=row["text"],
                metadata=__import__("json").loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]


class PineconeVectorStore(VectorStore):
    """
    Pinecone vector store.

    Usage:
        from django_matt.ai import PineconeVectorStore, OpenAIEmbeddings

        store = PineconeVectorStore(
            embedding_provider=OpenAIEmbeddings(),
            api_key="...",
            index_name="my-index",
        )

        await store.add_texts(["Hello", "World"])
        results = await store.search("greeting")
    """

    def __init__(
        self,
        api_key: str | None = None,
        index_name: str = "documents",
        namespace: str = "",
        **kwargs,
    ):
        super().__init__(collection_name=index_name, **kwargs)
        import os

        self.api_key = api_key or os.environ.get("PINECONE_API_KEY")
        self.namespace = namespace
        self._index = None

    def _get_index(self):
        """Get or create Pinecone index."""
        if self._index is None:
            try:
                from pinecone import Pinecone
            except ImportError:
                raise ImportError(
                    "pinecone-client required. Install with: uv add pinecone-client"
                )

            pc = Pinecone(api_key=self.api_key)
            self._index = pc.Index(self.collection_name)
        return self._index

    async def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the store."""
        index = self._get_index()
        vectors = []

        for doc in documents:
            embedding = await self._ensure_embedding(doc)
            vectors.append(
                {
                    "id": doc.id,
                    "values": embedding,
                    "metadata": {**doc.metadata, "text": doc.text},
                }
            )

        # Pinecone sync API (async wrapper would be better in production)
        index.upsert(vectors=vectors, namespace=self.namespace)
        return [doc.id for doc in documents]

    async def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        index = self._get_index()

        # Get query embedding
        if isinstance(query, str):
            if not self.embedding_provider:
                raise ValueError("embedding_provider required for text queries")
            query_embedding = await self.embedding_provider.embed_single(query)
        else:
            query_embedding = query

        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
            namespace=self.namespace,
        )

        return [
            SearchResult(
                document=Document(
                    id=match["id"],
                    text=match.get("metadata", {}).pop("text", ""),
                    metadata=match.get("metadata", {}),
                ),
                score=match["score"],
                rank=i,
            )
            for i, match in enumerate(results.get("matches", []))
        ]

    async def delete(self, ids: list[str]) -> int:
        """Delete documents by ID."""
        index = self._get_index()
        index.delete(ids=ids, namespace=self.namespace)
        return len(ids)

    async def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""
        index = self._get_index()
        results = index.fetch(ids=ids, namespace=self.namespace)

        return [
            Document(
                id=id_,
                text=vec.get("metadata", {}).pop("text", ""),
                metadata=vec.get("metadata", {}),
            )
            for id_, vec in results.get("vectors", {}).items()
        ]


class QdrantVectorStore(VectorStore):
    """
    Qdrant vector store.

    Usage:
        from django_matt.ai import QdrantVectorStore, OpenAIEmbeddings

        store = QdrantVectorStore(
            embedding_provider=OpenAIEmbeddings(),
            url="http://localhost:6333",
            collection_name="documents",
        )

        await store.create_collection()
        await store.add_texts(["Hello", "World"])
        results = await store.search("greeting")
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.url = url
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        """Get or create Qdrant client."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError("qdrant-client required. Install with: uv add qdrant-client")

            self._client = QdrantClient(url=self.url, api_key=self.api_key)
        return self._client

    async def create_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()

        collections = client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimensions,
                    distance=Distance.COSINE,
                ),
            )

    async def add(self, documents: list[Document]) -> list[str]:
        """Add documents to the store."""
        from qdrant_client.models import PointStruct

        client = self._get_client()
        points = []

        for doc in documents:
            embedding = await self._ensure_embedding(doc)
            points.append(
                PointStruct(
                    id=doc.id,
                    vector=embedding,
                    payload={"text": doc.text, **doc.metadata},
                )
            )

        client.upsert(collection_name=self.collection_name, points=points)
        return [doc.id for doc in documents]

    async def search(
        self,
        query: str | list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents."""
        client = self._get_client()

        # Get query embedding
        if isinstance(query, str):
            if not self.embedding_provider:
                raise ValueError("embedding_provider required for text queries")
            query_embedding = await self.embedding_provider.embed_single(query)
        else:
            query_embedding = query

        # Build filter
        qdrant_filter = None
        if filter:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
        )

        return [
            SearchResult(
                document=Document(
                    id=str(hit.id),
                    text=hit.payload.pop("text", "") if hit.payload else "",
                    metadata=hit.payload or {},
                ),
                score=hit.score,
                rank=i,
            )
            for i, hit in enumerate(results)
        ]

    async def delete(self, ids: list[str]) -> int:
        """Delete documents by ID."""
        from qdrant_client.models import PointIdsList

        client = self._get_client()
        client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=ids),
        )
        return len(ids)

    async def get(self, ids: list[str]) -> list[Document]:
        """Get documents by ID."""
        client = self._get_client()
        results = client.retrieve(
            collection_name=self.collection_name,
            ids=ids,
        )

        return [
            Document(
                id=str(point.id),
                text=point.payload.pop("text", "") if point.payload else "",
                metadata=point.payload or {},
            )
            for point in results
        ]


__all__ = [
    "Document",
    "InMemoryVectorStore",
    "PgVectorStore",
    "PineconeVectorStore",
    "QdrantVectorStore",
    "SearchResult",
    "VectorStore",
]
