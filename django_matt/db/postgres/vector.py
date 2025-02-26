"""
PostgreSQL vector support for Django Matt.

This module provides utilities for working with pgvector in Django.
It requires the pgvector extension to be installed in PostgreSQL
and the django-pgvector package to be installed in Python.

Usage:
    from django_matt.db.postgres.vector import VectorField, L2Distance, CosineDistance, MaxInnerProduct

    class Document(models.Model):
        content = models.TextField()
        embedding = VectorField(dimensions=1536)  # OpenAI embedding dimensions

    # Query by vector similarity
    query_embedding = get_embedding("What is Django Matt?")
    similar_docs = Document.objects.order_by(CosineDistance('embedding', query_embedding))[:10]
"""

try:
    from pgvector.django import CosineDistance, L2Distance, MaxInnerProduct, VectorField

    HAS_PGVECTOR = True
except ImportError:
    # Create placeholder classes if pgvector is not installed
    HAS_PGVECTOR = False

    class VectorField:
        """Placeholder for pgvector's VectorField."""

        def __init__(self, *args, **kwargs):
            raise ImportError("pgvector is not installed. Install it with: pip install django-pgvector")

    class L2Distance:
        """Placeholder for pgvector's L2Distance."""

        def __init__(self, *args, **kwargs):
            raise ImportError("pgvector is not installed. Install it with: pip install django-pgvector")

    class CosineDistance:
        """Placeholder for pgvector's CosineDistance."""

        def __init__(self, *args, **kwargs):
            raise ImportError("pgvector is not installed. Install it with: pip install django-pgvector")

    class MaxInnerProduct:
        """Placeholder for pgvector's MaxInnerProduct."""

        def __init__(self, *args, **kwargs):
            raise ImportError("pgvector is not installed. Install it with: pip install django-pgvector")


def setup_pgvector():
    """
    Set up pgvector in the database.

    This function should be called in a migration to ensure the pgvector extension is created.

    Example:
        # In a migration file
        from django.db import migrations
        from django_matt.db.postgres.vector import setup_pgvector

        class Migration(migrations.Migration):
            operations = [
                migrations.RunPython(setup_pgvector),
                # ... other operations
            ]
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def create_vector_index(model, field_name, index_type="ivfflat", lists=100):
    """
    Create a vector index on a field.

    Args:
        model: The Django model class
        field_name: The name of the VectorField
        index_type: The type of index ('ivfflat', 'hnsw', or None for exact search)
        lists: The number of lists for ivfflat index

    Example:
        from django_matt.db.postgres.vector import create_vector_index
        from myapp.models import Document

        create_vector_index(Document, 'embedding', index_type='ivfflat', lists=100)
    """
    from django.db import connection

    table_name = model._meta.db_table

    with connection.cursor() as cursor:
        if index_type == "ivfflat":
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {table_name}_{field_name}_ivfflat_idx
                ON {table_name} USING ivfflat ({field_name} vector_l2_ops)
                WITH (lists = {lists});
            """)
        elif index_type == "hnsw":
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {table_name}_{field_name}_hnsw_idx
                ON {table_name} USING hnsw ({field_name} vector_l2_ops);
            """)
        else:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {table_name}_{field_name}_idx
                ON {table_name} USING btree ({field_name});
            """)


class VectorManager:
    """
    Utility class for working with vector operations.

    This class provides methods for common vector operations like similarity search.
    """

    @staticmethod
    def similarity_search(queryset, field_name, query_vector, distance_func="cosine", limit=10):
        """
        Perform a similarity search on a queryset.

        Args:
            queryset: The Django queryset to search
            field_name: The name of the VectorField
            query_vector: The query vector to search for
            distance_func: The distance function to use ('cosine', 'l2', or 'dot')
            limit: The maximum number of results to return

        Returns:
            A queryset ordered by similarity
        """
        if not HAS_PGVECTOR:
            raise ImportError("pgvector is not installed. Install it with: pip install django-pgvector")

        if distance_func == "cosine":
            distance = CosineDistance(field_name, query_vector)
        elif distance_func == "l2":
            distance = L2Distance(field_name, query_vector)
        elif distance_func == "dot":
            distance = MaxInnerProduct(field_name, query_vector)
        else:
            raise ValueError(f"Unknown distance function: {distance_func}")

        return queryset.order_by(distance)[:limit]


# Create a singleton instance
vector_manager = VectorManager()


__all__ = [
    "VectorField",
    "L2Distance",
    "CosineDistance",
    "MaxInnerProduct",
    "setup_pgvector",
    "create_vector_index",
    "vector_manager",
    "HAS_PGVECTOR",
]
