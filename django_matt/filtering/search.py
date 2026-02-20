"""
Advanced search backends for django-matt.

Provides full-text search integration with:
- PostgreSQL full-text search
- Elasticsearch
- Meilisearch
"""

from abc import ABC, abstractmethod
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest

from .base import BaseFilterBackend


class BaseSearchEngine(ABC):
    """Base class for search engine integrations."""

    @abstractmethod
    def search(self, query: str, **kwargs) -> list[Any]:
        """
        Perform a search and return matching IDs or documents.

        Args:
            query: Search query string
            **kwargs: Additional search parameters

        Returns:
            List of matching document IDs or documents
        """

    @abstractmethod
    def index(self, documents: list[dict], **kwargs) -> None:
        """
        Index documents in the search engine.

        Args:
            documents: List of documents to index
            **kwargs: Additional indexing parameters
        """

    def delete(self, document_ids: list[Any], **kwargs) -> None:
        """Delete documents from the index."""


class PostgresSearchBackend(BaseFilterBackend):
    """
    PostgreSQL full-text search backend.

    Uses Django's SearchVector and SearchQuery for efficient full-text search.

    Usage:
        class ArticleListView:
            search_fields = ['title', 'content', 'tags']
            filter_backends = [PostgresSearchBackend()]

        # Query with ranking
        GET /api/articles?search=django+rest+api

    Configuration:
        search_param: Query parameter name (default: 'search')
        search_type: PostgreSQL search type ('plain', 'phrase', 'raw', 'websearch')
        config: Text search configuration (default: 'english')
        rank_field: Add search rank to results

    Requirements:
        - PostgreSQL database
        - django.contrib.postgres in INSTALLED_APPS
    """

    search_param: str = "search"
    search_type: str = "websearch"  # plain, phrase, raw, websearch
    config: str = "english"
    rank_field: str | None = "search_rank"

    def __init__(
        self,
        search_param: str | None = None,
        search_type: str | None = None,
        config: str | None = None,
        rank_field: str | None = None,
    ):
        if search_param:
            self.search_param = search_param
        if search_type:
            self.search_type = search_type
        if config:
            self.config = config
        if rank_field is not None:
            self.rank_field = rank_field

    def get_search_fields(self, view: Any) -> list[str]:
        """Get search fields from view."""
        return getattr(view, "search_fields", [])

    def filter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Apply PostgreSQL full-text search to queryset.
        """
        query = request.GET.get(self.search_param, "").strip()
        if not query:
            return queryset

        search_fields = self.get_search_fields(view)
        if not search_fields:
            return queryset

        try:
            from django.contrib.postgres.search import (
                SearchQuery,
                SearchRank,
                SearchVector,
            )
        except ImportError:
            # Fall back to basic search if postgres not available
            from django.db.models import Q

            q = Q()
            for field in search_fields:
                q |= Q(**{f"{field}__icontains": query})
            return queryset.filter(q)

        # Build search vector from fields
        vector = None
        for field in search_fields:
            field_vector = SearchVector(field, config=self.config)
            if vector is None:
                vector = field_vector
            else:
                vector = vector + field_vector

        # Build search query
        search_query = SearchQuery(
            query,
            config=self.config,
            search_type=self.search_type,
        )

        # Apply search
        queryset = queryset.annotate(search=vector).filter(search=search_query)

        # Add ranking if requested
        if self.rank_field:
            queryset = queryset.annotate(
                **{self.rank_field: SearchRank(vector, search_query)}
            ).order_by(f"-{self.rank_field}")

        return queryset

    def get_schema_fields(self, view: Any = None) -> list[dict[str, Any]]:
        """Get OpenAPI schema for search parameter."""
        return [
            {
                "name": self.search_param,
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": "Full-text search query",
            }
        ]


class ElasticsearchEngine(BaseSearchEngine):
    """
    Elasticsearch search engine integration.

    Usage:
        engine = ElasticsearchEngine(
            hosts=['http://localhost:9200'],
            index_name='articles',
        )

        # Search
        results = engine.search('django rest api', size=20)

        # Index documents
        engine.index([
            {'id': 1, 'title': 'Django Guide', 'content': '...'},
            {'id': 2, 'title': 'REST API', 'content': '...'},
        ])

    Requirements:
        uv add elasticsearch
    """

    def __init__(
        self,
        hosts: list[str] | None = None,
        index_name: str = "documents",
        **client_kwargs,
    ):
        self.hosts = hosts or ["http://localhost:9200"]
        self.index_name = index_name
        self.client_kwargs = client_kwargs
        self._client = None

    @property
    def client(self):
        """Lazy load Elasticsearch client."""
        if self._client is None:
            try:
                from elasticsearch import Elasticsearch

                self._client = Elasticsearch(self.hosts, **self.client_kwargs)
            except ImportError:
                raise ImportError(
                    "elasticsearch package is required. Install with: uv add elasticsearch"
                )
        return self._client

    def search(
        self,
        query: str,
        fields: list[str] | None = None,
        size: int = 20,
        offset: int = 0,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Perform an Elasticsearch search.

        Args:
            query: Search query string
            fields: Fields to search (default: all)
            size: Number of results to return
            offset: Offset for pagination

        Returns:
            Dict with hits and total count
        """
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": fields or ["*"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
            "from": offset,
            "size": size,
        }

        response = self.client.search(index=self.index_name, body=search_body)

        return {
            "hits": [hit["_source"] for hit in response["hits"]["hits"]],
            "total": response["hits"]["total"]["value"],
            "scores": [hit["_score"] for hit in response["hits"]["hits"]],
        }

    def index(
        self,
        documents: list[dict],
        id_field: str = "id",
        refresh: bool = False,
        **kwargs,
    ) -> None:
        """
        Index documents in Elasticsearch.

        Args:
            documents: List of documents to index
            id_field: Field to use as document ID
            refresh: Whether to refresh index after indexing
        """
        from elasticsearch.helpers import bulk

        actions = [
            {
                "_index": self.index_name,
                "_id": doc.get(id_field),
                "_source": doc,
            }
            for doc in documents
        ]

        bulk(self.client, actions, refresh=refresh)

    def delete(self, document_ids: list[Any], **kwargs) -> None:
        """Delete documents from Elasticsearch."""
        from elasticsearch.helpers import bulk

        actions = [
            {
                "_op_type": "delete",
                "_index": self.index_name,
                "_id": doc_id,
            }
            for doc_id in document_ids
        ]

        bulk(self.client, actions, ignore=[404])


class MeilisearchEngine(BaseSearchEngine):
    """
    Meilisearch search engine integration.

    Meilisearch is a fast, typo-tolerant search engine.

    Usage:
        engine = MeilisearchEngine(
            url='http://localhost:7700',
            api_key='your-api-key',
            index_name='articles',
        )

        # Search
        results = engine.search('django rest api', limit=20)

        # Index documents
        engine.index([
            {'id': 1, 'title': 'Django Guide', 'content': '...'},
            {'id': 2, 'title': 'REST API', 'content': '...'},
        ])

    Requirements:
        uv add meilisearch
    """

    def __init__(
        self,
        url: str = "http://localhost:7700",
        api_key: str | None = None,
        index_name: str = "documents",
    ):
        self.url = url
        self.api_key = api_key
        self.index_name = index_name
        self._client = None
        self._index = None

    @property
    def client(self):
        """Lazy load Meilisearch client."""
        if self._client is None:
            try:
                import meilisearch

                self._client = meilisearch.Client(self.url, self.api_key)
            except ImportError:
                raise ImportError(
                    "meilisearch package is required. Install with: uv add meilisearch"
                )
        return self._client

    @property
    def index(self):
        """Get or create Meilisearch index."""
        if self._index is None:
            self._index = self.client.index(self.index_name)
        return self._index

    def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        filter: str | None = None,
        sort: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Perform a Meilisearch search.

        Args:
            query: Search query string
            limit: Number of results to return
            offset: Offset for pagination
            filter: Filter expression
            sort: Sort fields

        Returns:
            Dict with hits and metadata
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        if filter:
            params["filter"] = filter
        if sort:
            params["sort"] = sort

        response = self.index.search(query, params)

        return {
            "hits": response["hits"],
            "total": response.get("estimatedTotalHits", len(response["hits"])),
            "processing_time_ms": response.get("processingTimeMs", 0),
        }

    def index(
        self,
        documents: list[dict],
        primary_key: str = "id",
        **kwargs,
    ) -> None:
        """
        Index documents in Meilisearch.

        Args:
            documents: List of documents to index
            primary_key: Primary key field name
        """
        self.index.add_documents(documents, primary_key=primary_key)

    def delete(self, document_ids: list[Any], **kwargs) -> None:
        """Delete documents from Meilisearch."""
        self.index.delete_documents(document_ids)

    def update_settings(self, settings: dict) -> None:
        """
        Update index settings.

        Example:
            engine.update_settings({
                'searchableAttributes': ['title', 'content'],
                'filterableAttributes': ['category', 'author'],
                'sortableAttributes': ['created_at', 'title'],
            })
        """
        self.index.update_settings(settings)


class SearchEngineBackend(BaseFilterBackend):
    """
    Generic search backend that uses an external search engine.

    Usage:
        engine = MeilisearchEngine(url='http://localhost:7700', index_name='articles')

        class ArticleListView:
            filter_backends = [SearchEngineBackend(engine=engine)]

        # Query
        GET /api/articles?search=django+rest+api
    """

    search_param: str = "search"

    def __init__(
        self,
        engine: BaseSearchEngine,
        search_param: str | None = None,
        id_field: str = "id",
    ):
        self.engine = engine
        self.id_field = id_field
        if search_param:
            self.search_param = search_param

    def filter_queryset(
        self,
        request: HttpRequest,
        queryset: QuerySet,
        view: Any = None,
    ) -> QuerySet:
        """
        Filter queryset using search engine results.

        Performs search in external engine, then filters Django queryset
        to only include matching IDs.
        """
        query = request.GET.get(self.search_param, "").strip()
        if not query:
            return queryset

        # Get search results from engine
        results = self.engine.search(query)
        hits = results.get("hits", [])

        if not hits:
            return queryset.none()

        # Extract IDs from search results
        ids = [hit.get(self.id_field) for hit in hits if hit.get(self.id_field)]

        if not ids:
            return queryset.none()

        # Filter queryset to only include matching IDs
        # Preserve search engine ordering
        from django.db.models import Case, When

        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        return queryset.filter(pk__in=ids).order_by(preserved_order)

    def get_schema_fields(self, view: Any = None) -> list[dict[str, Any]]:
        """Get OpenAPI schema for search parameter."""
        return [
            {
                "name": self.search_param,
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
                "description": "Search query",
            }
        ]
