"""
PostgreSQL support for Django Matt.

This module provides utilities for working with PostgreSQL in Django Matt.
It includes support for pgvector, connection pooling, and other PostgreSQL-specific features.
"""

from django.db import connection

try:
    from .vector import (
        HAS_PGVECTOR,
        CosineDistance,
        L2Distance,
        MaxInnerProduct,
        VectorField,
        create_vector_index,
        setup_pgvector,
        vector_manager,
    )
except ImportError:
    HAS_PGVECTOR = False


def check_postgres_connection():
    """
    Check if the current connection is PostgreSQL.

    Returns:
        bool: True if the connection is PostgreSQL, False otherwise.
    """
    return connection.vendor == "postgresql"


def is_postgres_version_compatible(min_version="12.0"):
    """
    Check if the PostgreSQL version is compatible.

    Args:
        min_version: The minimum required PostgreSQL version.

    Returns:
        bool: True if the PostgreSQL version is compatible, False otherwise.
    """
    if not check_postgres_connection():
        return False

    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version;")
        version = cursor.fetchone()[0]

        # Parse version string
        major_version = version.split(".")[0]
        if "." not in min_version:
            min_major_version = min_version
        else:
            min_major_version = min_version.split(".")[0]

        return int(major_version) >= int(min_major_version)


def create_extension(extension_name):
    """
    Create a PostgreSQL extension.

    Args:
        extension_name: The name of the extension to create.
    """
    if not check_postgres_connection():
        raise ValueError("Current connection is not PostgreSQL")

    with connection.cursor() as cursor:
        cursor.execute(f"CREATE EXTENSION IF NOT EXISTS {extension_name};")


def list_extensions():
    """
    List all installed PostgreSQL extensions.

    Returns:
        list: A list of installed extensions.
    """
    if not check_postgres_connection():
        raise ValueError("Current connection is not PostgreSQL")

    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension;")
        return [row[0] for row in cursor.fetchall()]


def has_extension(extension_name):
    """
    Check if a PostgreSQL extension is installed.

    Args:
        extension_name: The name of the extension to check.

    Returns:
        bool: True if the extension is installed, False otherwise.
    """
    return extension_name in list_extensions()


def execute_sql(sql, params=None):
    """
    Execute raw SQL on the PostgreSQL connection.

    Args:
        sql: The SQL statement to execute.
        params: The parameters for the SQL statement.

    Returns:
        list: The result of the SQL statement.
    """
    if not check_postgres_connection():
        raise ValueError("Current connection is not PostgreSQL")

    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        return []


__all__ = [
    # Vector support
    "VectorField",
    "L2Distance",
    "CosineDistance",
    "MaxInnerProduct",
    "setup_pgvector",
    "create_vector_index",
    "vector_manager",
    "HAS_PGVECTOR",
    # PostgreSQL utilities
    "check_postgres_connection",
    "is_postgres_version_compatible",
    "create_extension",
    "list_extensions",
    "has_extension",
    "execute_sql",
]
