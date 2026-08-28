from fastapi.testclient import TestClient

from app.main import app
from conftest import register_and_login

client = TestClient(app)


def token_from_headers(headers: dict) -> str:
    return headers["Authorization"].split(" ")[1]


def test_ws_auth_success():
    headers, user_id = register_and_login()
    token = token_from_headers(headers)

    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": token})
        resp = ws.receive_json()
        assert resp["type"] == "auth_success"
        assert resp["user_id"] == user_id


def test_ws_auth_invalid_token_fails():
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": "not-a-real-token"})
        resp = ws.receive_json()
        assert resp["type"] == "auth_error"


def test_ws_first_message_must_be_auth():
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "message", "channel_id": 1, "content": "too early"})
        resp = ws.receive_json()
        assert resp["type"] == "auth_error"


def test_ws_send_and_broadcast_to_channel_member():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()
    token_a = token_from_headers(headers_a)
    token_b = token_from_headers(headers_b)

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    with client.websocket_connect("/ws/chat", timeout=10) as ws_a, client.websocket_connect("/ws/chat", timeout=10) as ws_b:
        ws_a.send_json({"type": "auth", "token": token_a})
        assert ws_a.receive_json()["type"] == "auth_success"

        ws_b.send_json({"type": "auth", "token": token_b})
        assert ws_b.receive_json()["type"] == "auth_success"

        ws_a.send_json({"type": "message", "channel_id": channel_id, "content": "Hello via websocket"})

        # The recipient, currently connected, should receive the broadcast
        received = ws_b.receive_json()
        assert received["type"] == "message"
        assert received["content"] == "Hello via websocket"
        assert received["sender_id"] == user_a_id
        assert received["channel_id"] == channel_id

    # And it was actually persisted, not just broadcast in-memory
    get_res = client.get(f"/channels/{channel_id}/messages", headers=headers_a)
    contents = [m["content"] for m in get_res.json()]
    assert "Hello via websocket" in contents


def test_ws_send_to_non_member_channel_fails():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()
    headers_c, user_c_id = register_and_login()  # not a member of the channel below
    token_c = token_from_headers(headers_c)

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    with client.websocket_connect("/ws/chat") as ws_c:
        ws_c.send_json({"type": "auth", "token": token_c})
        assert ws_c.receive_json()["type"] == "auth_success"

        ws_c.send_json({"type": "message", "channel_id": channel_id, "content": "sneaky"})
        resp = ws_c.receive_json()
        assert resp["type"] == "error"
        assert resp["detail"] == "Channel not found"


def test_ws_malformed_message_returns_error():
    headers, user_id = register_and_login()
    token = token_from_headers(headers)

    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "auth_success"

        # channel_id missing entirely
        ws.send_json({"type": "message", "content": "no channel specified"})
        resp = ws.receive_json()
        assert resp["type"] == "error"