"""
Database connection pool pre-warming for Stage 18D.

Opens connections at startup so the first request doesn't pay
the connection-establishment penalty. Only meaningful when
Django's CONN_MAX_AGE > 0 or psycopg3 pool is enabled.

Usage:
    Setting MATT_DB_POOL_WARMUP to an integer > 0 in your
    DJANGO_MATT dict enables startup pre-warming with that
    many connections. Example:

        DJANGO_MATT = {
            "MATT_DB_POOL_WARMUP": 10,
        }

    Or set it in your Django settings directly as a module-level
    variable (same key, same value).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import connections

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper

logger = logging.getLogger("django_matt.db")


def prewarm_connections(n: int = 10, *, database: str = "default") -> None:
    """
    Open *n* connections to ``database``, then close them immediately.

    This primes the psycopg3 connection pool (or server-side caches)
    so that real request-handler connections acquire faster.

    Errors on any single connection are logged as warnings and do
    not prevent the remaining connections from being warmed.

    Args:
        n: Number of connections to open (default 10).
        database: Django database alias (default ``"default"``).
    """
    if n <= 0:
        return

    conn: BaseDatabaseWrapper = connections[database]
    vendor: str = getattr(conn, "vendor", "unknown")

    logger.info(
        "Pre-warming %d database connection(s) for alias=%r (vendor=%s).",
        n,
        database,
        vendor,
    )

    success = 0
    failures = 0

    for i in range(n):
        try:
            conn.ensure_connection()
            success += 1
            conn.close()
        except Exception:
            failures += 1
            logger.warning(
                "Failed to pre-warm connection %d/%d for alias=%r.",
                i + 1,
                n,
                database,
                exc_info=True,
            )

    logger.info(
        "Connection pre-warming complete: %d succeeded, %d failed (alias=%r).",
        success,
        failures,
        database,
    )


def warmup_if_configured() -> None:
    """
    Read ``MATT_DB_POOL_WARMUP`` from Django settings and, if set to
    a positive integer, invoke :func:`prewarm_connections`.

    Designed to be called from :meth:`DjangoMattConfig.ready` so
    pre-warming happens once at startup.
    """
    try:
        from django.conf import settings

        n = getattr(settings, "MATT_DB_POOL_WARMUP", None)
        if n is None:
            matt_config = getattr(settings, "DJANGO_MATT", {})
            n = matt_config.get("MATT_DB_POOL_WARMUP")

        if n is None:
            # Not configured — nothing to do
            return

        try:
            n = int(n)
        except (TypeError, ValueError):
            logger.warning(
                "MATT_DB_POOL_WARMUP must be an integer; got %r — skipping.",
                n,
            )
            return

        if n <= 0:
            return

        prewarm_connections(n)
    except Exception:
        logger.warning(
            "Unexpected error during connection pool pre-warming.",
            exc_info=True,
        )
