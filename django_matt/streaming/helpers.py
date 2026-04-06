from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from django_matt.streaming.sse import SSEEvent


def event(
    data: str | bytes | dict[str, Any] | list[Any] | None = None,
    *,
    event_type: str | None = None,
    id: str | None = None,
    retry: int | None = None,
    comment: str | None = None,
) -> SSEEvent:
    return SSEEvent(data=data, event=event_type, id=id, retry=retry, comment=comment)


async def heartbeat(interval: float = 15) -> AsyncIterator[SSEEvent]:
    while True:
        await asyncio.sleep(interval)
        yield SSEEvent(comment="heartbeat")


async def with_heartbeat(
    generator: AsyncIterator[SSEEvent],
    interval: float = 15,
) -> AsyncIterator[SSEEvent]:
    heartbeat_task: asyncio.Task[None] | None = None
    queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()

    async def _producer() -> None:
        async for ev in generator:
            await queue.put(ev)
        await queue.put(None)

    async def _heartbeat() -> None:
        while True:
            await asyncio.sleep(interval)
            await queue.put(SSEEvent(comment="heartbeat"))

    producer_task = asyncio.ensure_future(_producer())
    heartbeat_task = asyncio.ensure_future(_heartbeat())

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        heartbeat_task.cancel()
        producer_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        try:
            await producer_task
        except asyncio.CancelledError:
            pass
