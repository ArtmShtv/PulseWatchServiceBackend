import asyncio
from collections import defaultdict

from fastapi import WebSocket

SEND_TIMEOUT = 5


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        self._connections[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        sockets.discard(ws)
        if not sockets:
            del self._connections[user_id]

    @property
    def active_connections(self) -> int:
        return sum(len(s) for s in self._connections.values())

    async def send_to_user(self, user_id: int, message: str) -> None:
        sockets = list(self._connections.get(user_id, ()))
        if not sockets:
            return
        results = await asyncio.gather(*(self._send(ws, message) for ws in sockets))
        for ws, ok in zip(sockets, results):
            if not ok:
                self.disconnect(user_id, ws)

    @staticmethod
    async def _send(ws: WebSocket, message: str) -> bool:
        try:
            await asyncio.wait_for(ws.send_text(message), timeout=SEND_TIMEOUT)
            return True
        except Exception: # noqa: BLE001  any send failure means a dead socket; drop it, keep fan-out going
            return False


manager = ConnectionManager()