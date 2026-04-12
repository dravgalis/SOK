import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import suppress


class SupportEventsHub:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue[dict[str, str]]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict[str, str]]]:
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._clients.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._clients.discard(queue)

    async def emit_support_message(self, hh_id: str) -> None:
        event = {'type': 'support_message', 'chatId': hh_id}
        async with self._lock:
            listeners = list(self._clients)

        for queue in listeners:
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    _ = queue.get_nowait()
            with suppress(asyncio.QueueFull):
                queue.put_nowait(event)


support_events_hub = SupportEventsHub()
