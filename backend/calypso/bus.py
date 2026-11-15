"""In-process event bus: `emit()` fans out `{stage, ts, payload}` to every subscriber.

The dashboard listens through `GET /stream` (server-sent events). `emit` is safe
to call from sync route handlers (FastAPI runs those in a thread pool).
"""
import asyncio
import json
import logging
import threading
from collections import deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from .timeutil import now_iso

_log = logging.getLogger("calypso.bus")


def _put(queue: asyncio.Queue, event: dict) -> None:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        _log.warning("dropping event for a slow subscriber: %s", event.get("stage"))


class Bus:
    def __init__(self, recent: int = 1000) -> None:  # room for a call's history even with puck uploads
        self._subs: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._lock = threading.Lock()
        self.recent: deque[dict] = deque(maxlen=recent)

    def emit(self, stage: str, payload: dict[str, Any] | None = None) -> dict:
        event = {"stage": stage, "ts": now_iso(), "payload": payload or {}}
        with self._lock:
            self.recent.append(event)
            subs = list(self._subs)
        for loop, queue in subs:
            try:
                loop.call_soon_threadsafe(_put, queue, event)
            except RuntimeError:  # that subscriber's loop is closed
                pass
        return event

    @asynccontextmanager
    async def subscribe(self, maxsize: int = 1000) -> AsyncIterator[asyncio.Queue]:
        sub = (asyncio.get_running_loop(), asyncio.Queue(maxsize))
        with self._lock:
            self._subs.add(sub)
        try:
            yield sub[1]
        finally:
            with self._lock:
                self._subs.discard(sub)


bus = Bus()


def emit(stage: str, payload: dict[str, Any] | None = None) -> dict:
    return bus.emit(stage, payload)


async def sse_events(b: Bus, limit: int | None = None, ping_s: float = 15.0) -> AsyncIterator[str]:
    """Server-sent events: one `data: {json}` per event, plus keep-alive comments."""
    async with b.subscribe() as queue:
        yield ": connected\n\n"
        sent = 0
        while limit is None or sent < limit:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=ping_s)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(event)}\n\n"
            sent += 1
