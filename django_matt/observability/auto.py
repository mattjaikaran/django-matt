"""Auto-instrumentation that patches Django views, ORM, and cache with spans and metrics."""

from __future__ import annotations

import asyncio
import functools
import importlib
import inspect
import logging
import time
from typing import Any, Callable, TypeVar

from django_matt.observability.collectors import (
    CacheMetricsCollector,
    DatabaseMetricsCollector,
    RequestMetricsCollector,
    metrics_registry,
)
from django_matt.observability.spans import aspan, span

logger = logging.getLogger("django_matt.observability.auto")
F = TypeVar("F", bound=Callable[..., Any])

_instrumented: set[str] = set()


def _wrap_sync(func: F, span_name: str, tags: dict[str, Any] | None = None) -> F:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with span(span_name, tags=tags) as s:
            try:
                result = func(*args, **kwargs)
                s.set_tag("status", "ok")
                return result
            except Exception as exc:
                s.set_error(exc)
                raise

    return wrapper  # type: ignore[return-value]


def _wrap_async(func: F, span_name: str, tags: dict[str, Any] | None = None) -> F:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with aspan(span_name, tags=tags) as s:
            try:
                result = await func(*args, **kwargs)
                s.set_tag("status", "ok")
                return result
            except Exception as exc:
                s.set_error(exc)
                raise

    return wrapper  # type: ignore[return-value]


def _wrap_method(func: F, span_name: str, tags: dict[str, Any] | None = None) -> F:
    if asyncio.iscoroutinefunction(func):
        return _wrap_async(func, span_name, tags)
    return _wrap_sync(func, span_name, tags)


class AutoInstrumentor:
    def __init__(self) -> None:
        self._request_collector = RequestMetricsCollector()
        self._db_collector = DatabaseMetricsCollector()
        self._cache_collector = CacheMetricsCollector()
        self._original_methods: dict[str, Any] = {}

    def instrument_controllers(self) -> None:
        if "controllers" in _instrumented:
            return
        _instrumented.add("controllers")

        try:
            from django_matt.core.controller import APIController
        except ImportError:
            logger.debug("APIController not available, skipping controller instrumentation")
            return

        original_init_subclass = APIController.__init_subclass__

        @classmethod  # type: ignore[misc]
        def patched_init_subclass(cls: type, **kwargs: Any) -> None:
            original_init_subclass(**kwargs)
            _instrument_controller_class(cls)

        APIController.__init_subclass__ = patched_init_subclass  # type: ignore[assignment]
        logger.info("Controller auto-instrumentation enabled")

    def instrument_services(self, *service_modules: str) -> None:
        if "services" in _instrumented:
            return
        _instrumented.add("services")

        for module_path in service_modules:
            try:
                module = importlib.import_module(module_path)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if inspect.isclass(attr) and attr_name.endswith("Service"):
                        _instrument_service_class(attr)
                    elif inspect.isfunction(attr) and not attr_name.startswith("_"):
                        span_name = f"service.{module_path}.{attr_name}"
                        wrapped = _wrap_method(attr, span_name, tags={"component": "service"})
                        setattr(module, attr_name, wrapped)
            except ImportError:
                logger.warning(f"Could not import service module: {module_path}")

        logger.info("Service auto-instrumentation enabled")

    def instrument_db(self) -> None:
        if "db" in _instrumented:
            return
        _instrumented.add("db")

        metrics_registry.register(self._db_collector)

        try:
            from django.db import connection

            original_execute = connection.__class__.cursor

            db_collector = self._db_collector

            @functools.wraps(original_execute)
            def patched_cursor(conn_self: Any, *args: Any, **kwargs: Any) -> Any:
                cursor = original_execute(conn_self, *args, **kwargs)
                return _InstrumentedCursorWrapper(cursor, db_collector)

            self._original_methods["db_cursor"] = original_execute
            connection.__class__.cursor = patched_cursor  # type: ignore[assignment]
        except Exception as e:
            logger.warning(f"Could not instrument database: {e}")

        logger.info("Database auto-instrumentation enabled")

    def instrument_cache(self) -> None:
        if "cache" in _instrumented:
            return
        _instrumented.add("cache")

        metrics_registry.register(self._cache_collector)

        try:
            from django.core.cache import cache

            cache_collector = self._cache_collector

            original_get = cache.get
            original_set = cache.set
            original_delete = cache.delete

            @functools.wraps(original_get)
            def patched_get(
                key: str, default: Any = None, version: Any = None, **kwargs: Any
            ) -> Any:
                start = time.perf_counter()
                result = original_get(key, default, version=version, **kwargs)
                duration = time.perf_counter() - start
                if result is None and default is None:
                    cache_collector.record_miss(duration)
                else:
                    cache_collector.record_hit(duration)
                return result

            @functools.wraps(original_set)
            def patched_set(
                key: str, value: Any, timeout: Any = None, version: Any = None, **kwargs: Any
            ) -> None:
                start = time.perf_counter()
                result = original_set(key, value, timeout=timeout, version=version, **kwargs)
                duration = time.perf_counter() - start
                cache_collector.record_set(duration)
                return result

            @functools.wraps(original_delete)
            def patched_delete(key: str, version: Any = None, **kwargs: Any) -> bool:
                start = time.perf_counter()
                result = original_delete(key, version=version, **kwargs)
                duration = time.perf_counter() - start
                cache_collector.record_delete(duration)
                return result

            self._original_methods["cache_get"] = original_get
            self._original_methods["cache_set"] = original_set
            self._original_methods["cache_delete"] = original_delete

            cache.get = patched_get  # type: ignore[method-assign]
            cache.set = patched_set  # type: ignore[method-assign]
            cache.delete = patched_delete  # type: ignore[method-assign]

        except Exception as e:
            logger.warning(f"Could not instrument cache: {e}")

        logger.info("Cache auto-instrumentation enabled")

    def instrument_http(self) -> None:
        if "http" in _instrumented:
            return
        _instrumented.add("http")

        try:
            import urllib.request

            original_urlopen = urllib.request.urlopen

            @functools.wraps(original_urlopen)
            def patched_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
                url_str = url if isinstance(url, str) else getattr(url, "full_url", str(url))
                with span("http.outbound", tags={"http.url": url_str, "component": "http"}):
                    return original_urlopen(url, *args, **kwargs)

            self._original_methods["urlopen"] = original_urlopen
            urllib.request.urlopen = patched_urlopen  # type: ignore[assignment]
        except Exception as e:
            logger.warning(f"Could not instrument urllib: {e}")

        logger.info("HTTP auto-instrumentation enabled")

    def instrument_all(self, service_modules: list[str] | None = None) -> None:
        metrics_registry.register(self._request_collector)
        self.instrument_controllers()
        if service_modules:
            self.instrument_services(*service_modules)
        self.instrument_db()
        self.instrument_cache()
        self.instrument_http()
        logger.info("All auto-instrumentation enabled")

    @property
    def request_collector(self) -> RequestMetricsCollector:
        return self._request_collector

    @property
    def db_collector(self) -> DatabaseMetricsCollector:
        return self._db_collector

    @property
    def cache_collector(self) -> CacheMetricsCollector:
        return self._cache_collector


def _instrument_controller_class(cls: type) -> None:
    for attr_name in list(vars(cls)):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name)
        if not callable(attr):
            continue
        span_name = f"controller.{cls.__name__}.{attr_name}"
        tags = {"component": "controller", "controller": cls.__name__, "action": attr_name}
        wrapped = _wrap_method(attr, span_name, tags)
        setattr(cls, attr_name, wrapped)


def _instrument_service_class(cls: type) -> None:
    for attr_name in list(vars(cls)):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name)
        if not callable(attr):
            continue
        span_name = f"service.{cls.__name__}.{attr_name}"
        tags = {"component": "service", "service": cls.__name__, "action": attr_name}
        wrapped = _wrap_method(attr, span_name, tags)
        setattr(cls, attr_name, wrapped)


class _InstrumentedCursorWrapper:
    def __init__(self, cursor: Any, collector: DatabaseMetricsCollector) -> None:
        self._cursor = cursor
        self._collector = collector

    def execute(self, sql: str, params: Any = None) -> Any:
        operation = sql.strip().split()[0].upper() if sql.strip() else "UNKNOWN"
        table = _extract_table(sql)
        start = time.perf_counter()
        try:
            return self._cursor.execute(sql, params)
        finally:
            duration = time.perf_counter() - start
            self._collector.record(operation, table, duration, sql)

    def executemany(self, sql: str, param_list: Any) -> Any:
        operation = sql.strip().split()[0].upper() if sql.strip() else "UNKNOWN"
        table = _extract_table(sql)
        start = time.perf_counter()
        try:
            return self._cursor.executemany(sql, param_list)
        finally:
            duration = time.perf_counter() - start
            self._collector.record(operation, table, duration, sql)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)

    def __iter__(self) -> Any:
        return iter(self._cursor)

    def __enter__(self) -> _InstrumentedCursorWrapper:
        return self

    def __exit__(self, *args: Any) -> None:
        self._cursor.close()


def _extract_table(sql: str) -> str:
    sql_upper = sql.upper().strip()
    for keyword in (" FROM ", " INTO ", " UPDATE ", " JOIN "):
        if keyword in sql_upper:
            parts = sql_upper.split(keyword)
            if len(parts) > 1:
                table_part = parts[1].split()[0]
                return table_part.strip('`"[]').lower()
    return "unknown"


def reset_instrumentation() -> None:
    _instrumented.clear()


__all__ = [
    "AutoInstrumentor",
    "reset_instrumentation",
]
