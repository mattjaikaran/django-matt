"""Built-in health check functions for database, cache, Redis, Celery, storage, and email."""

from __future__ import annotations

import logging

from django_matt.introspection.registry import ComponentInfo, ComponentStatus

logger = logging.getLogger("django_matt.introspection")


async def check_database() -> ComponentInfo:
    """Check database connectivity by executing a simple query."""
    info = ComponentInfo(name="database", component_type="database")
    try:
        backend, name = await _db_ping()
        info.status = ComponentStatus.HEALTHY
        info.details["backend"] = backend
        info.details["name"] = name
    except Exception as e:
        info.status = ComponentStatus.UNHEALTHY
        info.error = str(e)
    return info


async def _db_ping() -> tuple[str, str]:
    from asgiref.sync import sync_to_async

    def _ping() -> tuple[str, str]:
        from django.db import connection

        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return (
            connection.settings_dict.get("ENGINE", "unknown"),
            connection.settings_dict.get("NAME", "unknown"),
        )

    return await sync_to_async(_ping, thread_sensitive=False)()


async def check_cache() -> ComponentInfo:
    """Check cache backend by writing and reading back a test key."""
    from django.core.cache import cache

    info = ComponentInfo(name="cache", component_type="cache")
    try:
        from asgiref.sync import sync_to_async

        test_key = "_matt_health_check"

        async def _test_cache() -> None:
            await sync_to_async(cache.set)(test_key, "ok", 10)
            value = await sync_to_async(cache.get)(test_key)
            if value != "ok":
                raise RuntimeError("Cache read-back mismatch")
            await sync_to_async(cache.delete)(test_key)

        await _test_cache()
        info.status = ComponentStatus.HEALTHY
        backend_cls = type(cache).__name__
        info.details["backend"] = backend_cls
    except Exception as e:
        info.status = ComponentStatus.UNHEALTHY
        info.error = str(e)
    return info


async def check_redis() -> ComponentInfo:
    """Check Redis connectivity via PING and retrieve server version."""
    info = ComponentInfo(name="redis", component_type="cache")
    try:
        from django.conf import settings

        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            cache_conf = getattr(settings, "CACHES", {}).get("default", {})
            if "redis" not in cache_conf.get("BACKEND", "").lower():
                info.status = ComponentStatus.UNKNOWN
                info.details["reason"] = "no redis configured"
                return info

        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url or "redis://localhost:6379/0")
        try:
            pong = await client.ping()
            info.status = ComponentStatus.HEALTHY if pong else ComponentStatus.UNHEALTHY
            redis_info = await client.info("server")
            info.version = redis_info.get("redis_version")
        finally:
            await client.aclose()
    except ImportError:
        info.status = ComponentStatus.UNKNOWN
        info.details["reason"] = "redis package not installed"
    except Exception as e:
        info.status = ComponentStatus.UNHEALTHY
        info.error = str(e)
    return info


async def check_celery() -> ComponentInfo:
    """Check Celery task queue by inspecting active workers."""
    info = ComponentInfo(name="celery", component_type="task_queue", critical=False)
    try:
        from asgiref.sync import sync_to_async
        from celery import current_app

        def _inspect() -> dict:
            inspector = current_app.control.inspect(timeout=2.0)
            active = inspector.active()
            return {"workers": list(active.keys()) if active else []}

        result = await sync_to_async(_inspect)()
        if result["workers"]:
            info.status = ComponentStatus.HEALTHY
            info.details["workers"] = result["workers"]
        else:
            info.status = ComponentStatus.DEGRADED
            info.details["reason"] = "no active workers"
    except ImportError:
        info.status = ComponentStatus.UNKNOWN
        info.details["reason"] = "celery not installed"
    except Exception as e:
        info.status = ComponentStatus.UNHEALTHY
        info.error = str(e)
    return info


async def check_storage() -> ComponentInfo:
    """Check default file storage backend accessibility."""
    from django.core.files.storage import default_storage

    info = ComponentInfo(name="storage", component_type="storage", critical=False)
    try:
        from asgiref.sync import sync_to_async

        backend_name = type(default_storage).__name__
        info.details["backend"] = backend_name

        exists = await sync_to_async(default_storage.exists)("_matt_health_probe")
        info.status = ComponentStatus.HEALTHY
        info.details["probe_exists"] = exists
    except Exception as e:
        info.status = ComponentStatus.UNHEALTHY
        info.error = str(e)
    return info


async def check_email() -> ComponentInfo:
    """Check email backend connectivity."""
    from django.conf import settings

    info = ComponentInfo(name="email", component_type="email", critical=False)
    try:
        backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.locmem.EmailBackend")
        info.details["backend"] = backend

        if "console" in backend or "locmem" in backend or "filebased" in backend or "dummy" in backend:
            info.status = ComponentStatus.HEALTHY
            info.details["note"] = "non-production backend"
        else:
            from django.core.mail import get_connection

            from asgiref.sync import sync_to_async

            def _test_connection() -> None:
                conn = get_connection(fail_silently=False)
                conn.open()
                conn.close()

            await sync_to_async(_test_connection)()
            info.status = ComponentStatus.HEALTHY
    except Exception as e:
        info.status = ComponentStatus.UNHEALTHY
        info.error = str(e)
    return info


def auto_register(reg: object | None = None) -> None:
    """Register all built-in health checks with the given (or default) registry."""
    from django_matt.introspection.registry import registry as default_registry

    target = reg or default_registry
    target.register("database", "database", check_database, critical=True)
    target.register("cache", "cache", check_cache, critical=False)
    target.register("storage", "storage", check_storage, critical=False)
    target.register("email", "email", check_email, critical=False)
