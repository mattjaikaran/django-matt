"""
Database utilities for Django Matt.

This module provides database utilities for Django Matt, including:
- PostgreSQL support with pgvector
- Connection pooling
- Database inspection tools
- Query optimization
"""

from django.db import connection, connections
from django.db.models import ExpressionWrapper, F, Func, Q, Value
from django.db.models.functions import Cast, Coalesce

# Import PostgreSQL support if available
try:
    from .postgres import (
        HAS_PGVECTOR,
        CosineDistance,
        L2Distance,
        MaxInnerProduct,
        # Vector support
        VectorField,
        # PostgreSQL utilities
        check_postgres_connection,
        create_extension,
        create_vector_index,
        execute_sql,
        has_extension,
        is_postgres_version_compatible,
        list_extensions,
        setup_pgvector,
        vector_manager,
    )

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False
    HAS_PGVECTOR = False


def get_db_type():
    """
    Get the type of the default database connection.

    Returns:
        str: The database type ('postgresql', 'mysql', 'sqlite', etc.)
    """
    return connection.vendor


def is_postgres():
    """
    Check if the default database connection is PostgreSQL.

    Returns:
        bool: True if the connection is PostgreSQL, False otherwise.
    """
    return get_db_type() == "postgresql"


def is_mysql():
    """
    Check if the default database connection is MySQL.

    Returns:
        bool: True if the connection is MySQL, False otherwise.
    """
    return get_db_type() == "mysql"


def is_sqlite():
    """
    Check if the default database connection is SQLite.

    Returns:
        bool: True if the connection is SQLite, False otherwise.
    """
    return get_db_type() == "sqlite"


def get_db_version():
    """
    Get the version of the default database connection.

    Returns:
        str: The database version.
    """
    if is_postgres():
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version;")
            return cursor.fetchone()[0]
    elif is_mysql():
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION();")
            return cursor.fetchone()[0]
    elif is_sqlite():
        with connection.cursor() as cursor:
            cursor.execute("SELECT sqlite_version();")
            return cursor.fetchone()[0]
    else:
        return "Unknown"


def get_table_names():
    """
    Get the names of all tables in the default database.

    Returns:
        list: A list of table names.
    """
    return connection.introspection.table_names()


def get_table_description(table_name):
    """
    Get the description of a table in the default database.

    Args:
        table_name: The name of the table.

    Returns:
        list: A list of column descriptions.
    """
    with connection.cursor() as cursor:
        return connection.introspection.get_table_description(cursor, table_name)


def execute_raw_sql(sql, params=None, database="default"):
    """
    Execute raw SQL on a database connection.

    Args:
        sql: The SQL statement to execute.
        params: The parameters for the SQL statement.
        database: The name of the database connection to use.

    Returns:
        list: The result of the SQL statement.
    """
    conn = connections[database]
    with conn.cursor() as cursor:
        cursor.execute(sql, params or [])
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        return []


__all__ = [
    # Database type checks
    "get_db_type",
    "is_postgres",
    "is_mysql",
    "is_sqlite",
    "get_db_version",
    # Database introspection
    "get_table_names",
    "get_table_description",
    # SQL execution
    "execute_raw_sql",
    # PostgreSQL support
    "HAS_POSTGRES",
    "HAS_PGVECTOR",
]

# Add PostgreSQL-specific exports if available
if HAS_POSTGRES:
    __all__.extend(
        [
            # Vector support
            "VectorField",
            "L2Distance",
            "CosineDistance",
            "MaxInnerProduct",
            "setup_pgvector",
            "create_vector_index",
            "vector_manager",
            # PostgreSQL utilities
            "check_postgres_connection",
            "is_postgres_version_compatible",
            "create_extension",
            "list_extensions",
            "has_extension",
            "execute_sql",
        ]
    )
