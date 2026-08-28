import asyncio
from unittest.mock import AsyncMock

from app.core.sockets import ConnectionManager


def test_connection_manager_broadcast_dispatches_to_correct_users():
    """
    Direct unit test of the broadcast dispatch logic using fake
    WebSocket objects, rather than real connections via TestClient.

    This avoids a real limitation of FastAPI's TestClient: each
    simultaneous websocket_connect() call runs on its OWN separate
    background event loop ("portal"). A message sent from one
    connection's server-side task to a DIFFERENT connection's WebSocket
    object doesn't reliably propagate across that boundary in tests --
    even though it works correctly in real deployment, where a single
    shared uvicorn event loop serves every connection. This test
    verifies the dispatch logic itself, decoupled from that testing
    artifact.
    """
    manager = ConnectionManager()

    ws_a = AsyncMock()
    ws_b = AsyncMock()
    ws_c = AsyncMock()  # not a member of the broadcast group below

    manager.connect(1, ws_a)
    manager.connect(2, ws_b)
    manager.connect(3, ws_c)

    payload = {"type": "message", "content": "hello"}

    asyncio.run(manager.broadcast_to_users([1, 2], payload))

    ws_a.send_json.assert_awaited_once_with(payload)
    ws_b.send_json.assert_awaited_once_with(payload)
    ws_c.send_json.assert_not_awaited()


def test_connection_manager_supports_multiple_connections_per_user():
    """A user connected from two devices (e.g. phone + laptop) should
    receive a broadcast on both connections."""
    manager = ConnectionManager()

    ws_phone = AsyncMock()
    ws_laptop = AsyncMock()
    manager.connect(1, ws_phone)
    manager.connect(1, ws_laptop)

    payload = {"type": "message", "content": "hi"}
    asyncio.run(manager.send_to_user(1, payload))

    ws_phone.send_json.assert_awaited_once_with(payload)
    ws_laptop.send_json.assert_awaited_once_with(payload)


def test_connection_manager_drops_dead_connection_on_send_failure():
    """A broken/closed connection shouldn't prevent delivery to a
    user's other connections, and should be pruned from the registry
    rather than left around."""
    manager = ConnectionManager()

    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = RuntimeError("connection closed")
    ws_alive = AsyncMock()

    manager.connect(1, ws_dead)
    manager.connect(1, ws_alive)

    payload = {"type": "message", "content": "hi"}
    asyncio.run(manager.send_to_user(1, payload))

    ws_alive.send_json.assert_awaited_once_with(payload)
    assert manager.is_online(1) is True  # ws_alive is still registered
    assert ws_dead not in manager._connections.get(1, [])


def test_connection_manager_disconnect_removes_user_entirely_when_last_connection_closes():
    manager = ConnectionManager()
    ws = AsyncMock()
    manager.connect(1, ws)
    assert manager.is_online(1) is True

    manager.disconnect(1, ws)
    assert manager.is_online(1) is False