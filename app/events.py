"""In-process pub/sub used to push live events to WebSocket clients."""
import asyncio
import logging

log = logging.getLogger("events")


class Hub:
    def __init__(self):
        self._subs: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subs.discard(q)

    def publish(self, event: str, data=None):
        msg = {"event": event, "data": data}
        for q in list(self._subs):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                log.warning("event queue full, dropping subscriber")
                self._subs.discard(q)


hub = Hub()
