import asyncio
from typing import Dict, Set
from fastapi import WebSocket


class EventBus:
    """
    In-memory async pub-sub system for streaming live simulation events over WebSockets.
    """

    def __init__(self):
        self._listeners: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            if run_id not in self._listeners:
                self._listeners[run_id] = set()
            self._listeners[run_id].add(websocket)

    async def disconnect(self, run_id: str, websocket: WebSocket):
        async with self._lock:
            if run_id in self._listeners:
                self._listeners[run_id].discard(websocket)
                if not self._listeners[run_id]:
                    del self._listeners[run_id]

    async def broadcast(self, run_id: str, event_type: str, payload: dict):
        async with self._lock:
            listeners = set(self._listeners.get(run_id, []))

        if not listeners:
            return

        message = {"type": event_type, "run_id": run_id, "data": payload}
        stale = set()

        for ws in listeners:
            try:
                await ws.send_json(message)
            except Exception:
                stale.add(ws)

        if stale:
            async with self._lock:
                if run_id in self._listeners:
                    self._listeners[run_id].difference_update(stale)


event_bus = EventBus()
