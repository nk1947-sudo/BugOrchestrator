import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("api.ws")


class ConnectionManager:
    """In-process broadcast to connected dashboard clients.

    Single-instance assumption: this holds live WebSocket connections in
    memory, so it only fans out to clients connected to *this* process. A
    horizontally-scaled deployment would replace this with Redis pub/sub
    (REDIS_URL is already provisioned for that) - not needed for a single
    API replica.
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, event_type: str, data: dict) -> None:
        if not self._connections:
            return
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()
