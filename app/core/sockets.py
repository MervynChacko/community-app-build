from typing import Dict, List
from fastapi import WebSocket


class ConnectionManager:
    """
    In-memory registry of active WebSocket connections, keyed by
    user_id. Supports multiple simultaneous connections per user (e.g.
    the same resident connected from both a phone and a laptop).

    NOTE: in-memory means this only works correctly with a SINGLE
    backend process. In case of multiple instances,broadcasting will 
    need to move to a shared pub/sub layer (e.g.Redis) instead 
    -- a message received on server A wouldn't reach a
    user connected to server B otherwise.
    """

    def __init__(self):
        self._connections: Dict[int, List[WebSocket]] = {}

    def connect(self, user_id: int, websocket: WebSocket) -> None:
        """
        Registers an ALREADY-ACCEPTED websocket. Accepting happens in
        the route handler itself, before authentication, since we need
        to be able to receive the client's first (auth) message.
        """
        self._connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict) -> None:
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                # Connection is dead/broken -- drop it rather than
                # letting one bad socket break delivery to everyone else
                # in the broadcast.
                self.disconnect(user_id, ws)

    async def broadcast_to_users(self, user_ids, message: dict) -> None:
        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))


# Single shared instance for the whole app process.
manager = ConnectionManager()