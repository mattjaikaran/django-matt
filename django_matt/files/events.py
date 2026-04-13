"""
Storage events for audit trail integration.

Emits events when files are uploaded, downloaded, deleted, moved, copied,
or processed. Integrates with django_matt.events bus when available,
falls back to Django signals.
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Any

import django.dispatch

logger = logging.getLogger("django_matt.files.events")


class FileEvent(enum.Enum):
    """Types of file storage events."""

    UPLOADED = "file.uploaded"
    DOWNLOADED = "file.downloaded"
    DELETED = "file.deleted"
    MOVED = "file.moved"
    COPIED = "file.copied"
    METADATA_EXTRACTED = "file.metadata_extracted"
    PROCESSED = "file.processed"


# Django signals for file events
file_uploaded = django.dispatch.Signal()
file_deleted = django.dispatch.Signal()
file_accessed = django.dispatch.Signal()
file_moved = django.dispatch.Signal()
file_copied = django.dispatch.Signal()
file_processed = django.dispatch.Signal()

_SIGNAL_MAP: dict[FileEvent, django.dispatch.Signal] = {
    FileEvent.UPLOADED: file_uploaded,
    FileEvent.DOWNLOADED: file_accessed,
    FileEvent.DELETED: file_deleted,
    FileEvent.MOVED: file_moved,
    FileEvent.COPIED: file_copied,
    FileEvent.PROCESSED: file_processed,
}


_background_tasks: set[Any] = set()


def _try_emit_bus_event(
    event_type: FileEvent,
    key: str,
    metadata: dict[str, Any] | None,
) -> bool:
    """Try to emit via django_matt.events EventBus. Returns True if successful."""
    try:
        from django_matt.events.bus import Event, EventBus

        bus = EventBus()

        class FileStorageEvent(Event):
            __event_type__: str = event_type.value
            key: str = ""
            file_metadata: dict[str, Any] = {}

        evt = FileStorageEvent(
            key=key,
            file_metadata=metadata or {},
        )

        import asyncio

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(bus.emit(evt))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            # No running loop, run synchronously
            asyncio.run(bus.emit(evt))

        return True
    except ImportError:
        return False
    except Exception:
        logger.debug("Failed to emit event via EventBus", exc_info=True)
        return False


def emit_file_event(
    event: FileEvent,
    key: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Emit a file storage event.

    First tries the django_matt.events bus for rich event handling.
    Always fires the corresponding Django signal as a fallback/supplement.

    Args:
        event: The type of file event.
        key: The storage key/path of the file.
        metadata: Optional dict of additional context (size, content_type, etc.).
    """
    event_data = {
        "event": event.value,
        "key": key,
        "timestamp": time.time(),
        **(metadata or {}),
    }

    # Try event bus integration
    _try_emit_bus_event(event, key, metadata)

    # Always fire Django signal
    signal = _SIGNAL_MAP.get(event)
    if signal is not None:
        signal.send(sender=None, key=key, metadata=metadata, **event_data)
    else:
        # For events without a dedicated signal (METADATA_EXTRACTED), use file_accessed
        file_accessed.send(sender=None, key=key, metadata=metadata, **event_data)

    logger.debug("File event %s: key=%s", event.value, key)
