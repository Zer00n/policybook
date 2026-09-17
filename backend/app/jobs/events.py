import asyncio
import json
from typing import Any, AsyncGenerator


class JobEventBroadcaster:
    def __init__(self):
        # job_id -> list of asyncio.Queue
        self._listeners: dict[str, list[asyncio.Queue]] = {}
        # job_id -> list of (event_type, data)
        self._history: dict[str, list[tuple[str, dict[str, Any]]]] = {}

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
        # 记录最近事件历史（上限 200 条）
        if job_id not in self._history:
            self._history[job_id] = []
        self._history[job_id].append((event_type, data))
        if len(self._history[job_id]) > 200:
            self._history[job_id] = self._history[job_id][-200:]

        queues = self._listeners.get(job_id, [])
        for q in queues:
            await q.put((event_type, data))

    def get_history(self, job_id: str) -> list[tuple[str, dict[str, Any]]]:
        return list(self._history.get(job_id, []))


broadcaster = JobEventBroadcaster()


async def job_event_generator(
    job_id: str,
    initial_snapshot: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    q = broadcaster.subscribe(job_id)
    try:
        # 1. 立即推送 snapshot 初始状态
        if initial_snapshot:
            yield f"event: snapshot\ndata: {json.dumps(initial_snapshot, ensure_ascii=False)}\n\n"
            if initial_snapshot.get("status") in ("succeeded", "failed"):
                return

        # 2. 持续读取广播队列，增加心跳机制保活
        while True:
            try:
                # 3 秒超时未收到事件则发送心跳注释，防止反向代理/浏览器断连
                event_type, data = await asyncio.wait_for(q.get(), timeout=3.0)
                yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                if event_type in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # 发送 SSE 注释心跳保活
                yield ": ping\n\n"
    finally:
        broadcaster.unsubscribe(job_id, q)
