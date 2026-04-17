"""Query coalescer — batch database loads within the same event loop tick.

Instead of issuing individual ``SELECT ... WHERE id = ?`` queries, the
coalescer collects all ``load()`` calls made before the event loop yields
and fires a single ``SELECT ... WHERE id IN (...)`` query.

Usage::

    coalescer = QueryCoalescer()

    # These two loads are coalesced into one query:
    user = await coalescer.load(User, 1)
    org = await coalescer.load(Organization, 5)

    # Explicit batch:
    users = await coalescer.load_many(User, [1, 2, 3])
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from asgiref.sync import sync_to_async

logger = logging.getLogger("django_matt.batch.coalescer")


class _BatchEntry:
    """A pending load request."""

    __slots__ = ("pk", "future")

    def __init__(self, pk: Any) -> None:
        self.pk = pk
        self.future: asyncio.Future = asyncio.get_running_loop().create_future()


class QueryCoalescer:
    """Automatic query batching within a single event loop tick.

    Collects ``load()`` calls and defers the actual database query until
    the event loop tick completes, then fires a single bulk query.

    Args:
        window_ms: Coalescing window in milliseconds. ``0`` means
                   same-tick coalescing (deferred to the next microtask).
    """

    def __init__(self, window_ms: float = 0.0) -> None:
        self._window_ms = window_ms
        self._pending: dict[str, list[_BatchEntry]] = defaultdict(list)
        self._scheduled: set[str] = set()
        self._stats = {"coalesced_queries": 0, "total_loads": 0}

    async def load(self, model: type, pk: Any) -> Any:
        """Load a single model instance by primary key.

        The actual query is deferred until the coalescing window closes,
        then all pending loads for the same model are batched.
        """
        from django.db import models as django_models

        key = f"{model._meta.app_label}.{model._meta.model_name}"
        entry = _BatchEntry(pk)
        self._pending[key].append(entry)
        self._stats["total_loads"] += 1

        # Schedule the batch flush if not already scheduled
        if key not in self._scheduled:
            self._scheduled.add(key)
            if self._window_ms <= 0:
                # Same-tick: schedule as a microtask
                asyncio.get_running_loop().call_soon(
                    lambda k=key, m=model: asyncio.ensure_future(self._flush(k, m))
                )
            else:
                asyncio.get_running_loop().call_later(
                    self._window_ms / 1000.0,
                    lambda k=key, m=model: asyncio.ensure_future(self._flush(k, m)),
                )

        return await entry.future

    async def load_many(self, model: type, pks: list[Any]) -> list[Any]:
        """Load multiple model instances by primary key.

        All PKs are batched into a single query.
        """
        if not pks:
            return []
        tasks = [self.load(model, pk) for pk in pks]
        return await asyncio.gather(*tasks)

    async def _flush(self, key: str, model: type) -> None:
        """Execute the batched query for a model and resolve futures."""
        self._scheduled.discard(key)
        entries = self._pending.pop(key, [])
        if not entries:
            return

        pks = [e.pk for e in entries]
        pk_field = model._meta.pk.name if model._meta.pk else "pk"
        self._stats["coalesced_queries"] += 1

        try:
            objects = await sync_to_async(
                lambda: {
                    getattr(obj, pk_field): obj
                    for obj in model.objects.filter(**{f"{pk_field}__in": pks})
                },
                thread_sensitive=True,
            )()

            for entry in entries:
                obj = objects.get(entry.pk)
                if obj is not None:
                    entry.future.set_result(obj)
                else:
                    entry.future.set_exception(
                        model.DoesNotExist(
                            f"{model.__name__} with pk={entry.pk!r} does not exist"
                        )
                    )
        except Exception as e:
            for entry in entries:
                if not entry.future.done():
                    entry.future.set_exception(e)

    @property
    def stats(self) -> dict[str, int]:
        """Return coalescing statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        self._stats = {"coalesced_queries": 0, "total_loads": 0}
