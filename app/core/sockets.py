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

    -- Update: 08282026; added WS DEBUG - temp stepwise diagonistic logging into broadcast
    path. This is due to the prolonged execution with the test case - test_ws_send_and_broadcast_to_channel_member
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
        print(f"[WS DEBUG] connect: user_id = {user_id}, total_connections = {len(self._connections[user_id])}", flush=True)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict) -> None:
        conns = list(self._connections.get(user_id, []))
        print(f"[WS DEBUG] send_to_user START: user_id = {user_id}, connection_count = {len(conns)}", flush=True)
        for ws in conns:
            try:
                print(f"[WS DEBUG] about to call ws.send_json for user_id = {user_id}", flush=True)
                await ws.send_json(message)
                print(f"[WS DEBUG] ws.send_json RETURNED for user_id = {user_id}", flush=True)
            except Exception as e:
                # Connection is dead/broken -- drop it rather than
                # letting one bad socket break delivery to everyone else
                # in the broadcast.
                print(f"[WS DEBUG] send_json failed for user_id = {user_id}: {e!r}", flush=True)
                self.disconnect(user_id, ws)
        print(f"[WS DEBUG] send_to_user END: user_id = {user_id}", flush=True)

    async def broadcast_to_users(self, user_ids, message: dict) -> None:
        print(f"[WS DEBUG] broadcast_to_users START: user_id = {list(user_ids)}", flush=True)
        for user_id in user_ids:
            await self.send_to_user(user_id, message)
            print(f"[WS DEBUG] broadcast_to_users END", flush=True)

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))


# Single shared instance for the whole app process.
manager = ConnectionManager()