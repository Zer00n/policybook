import asyncio
import json
from typing import Any, AsyncGenerator


class JobEventBroadcaster:
    def __init__(self):
        # job_id -> list of asyncio.Queue
        self._listeners: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if job_id not in self._listeners:
            self._listeners[job_id] = []
        self._listeners[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        if job_id in self._listeners:
            if q in self._listeners[job_id]:
                self._listeners[job_id].remove(q)
            if not self._listeners[job_id]:
                del self._listeners[job_id]

    async def broadcast(self, job_id: str, event_type: str, data: dict[str, Any]) -> None:
        queues = self._listeners.get(job_id, [])
        for q in queues:
            await q.put((event_type, data))


broadcaster = JobEventBroadcaster()


async def job_event_generator(job_id: str) -> AsyncGenerator[str, None]:
    q = broadcaster.subscribe(job_id)
    try:
        while True:
            event_type, data = await q.get()
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            if event_type in ("done", "error"):
                break
    finally:
        broadcaster.unsubscribe(job_id, q)
