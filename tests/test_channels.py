import uuid
from fastapi.testclient import TestClient
from app.main import app
from conftest import get_test_activation_code, get_second_test_activation_code

client = TestClient(app)


def register_and_login(activation_code: str = None):
    """Like get_auth_headers() in test_posts.py, but also returns the
    new user's id -- channel tests need recipient_id/member_ids."""
    unique_email = f"chat_tester_{uuid.uuid4().hex[:8]}@apartment.com"
    payload = {
        "email": unique_email,
        "full_name": "Chat Tester",
        "apartment_number": "4C",
        "password": "securepassword123",
        "activation_code": activation_code or get_test_activation_code(),
    }
    register_res = client.post("/auth/register", json=payload)
    assert register_res.status_code == 201, f"Registration failed: {register_res.text}"
    user_id = register_res.json()["id"]

    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": "securepassword123"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


# ---- direct channel tests ----

def test_create_direct_channel_success():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()

    res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "direct"
    assert len(data["members"]) == 2
    member_ids = {m["user_id"] for m in data["members"]}
    assert member_ids == {user_a_id, user_b_id}


def test_create_direct_channel_reuses_existing():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()

    first_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    second_res = client.post("/channels/direct", json={"recipient_id": user_a_id}, headers=headers_b)

    assert first_res.status_code == 200
    assert second_res.status_code == 200
    assert first_res.json()["id"] == second_res.json()["id"]
    # Still exactly 2 members -- confirms no duplicate ChannelMember rows
    assert len(second_res.json()["members"]) == 2


def test_create_direct_channel_with_self_fails():
    headers_a, user_a_id = register_and_login()

    res = client.post("/channels/direct", json={"recipient_id": user_a_id}, headers=headers_a)
    assert res.status_code == 400


def test_create_direct_channel_cross_community_fails():
    headers_a, user_a_id = register_and_login()  # community A
    headers_b, user_b_id = register_and_login(get_second_test_activation_code())  # community B

    res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    assert res.status_code == 404


def test_create_direct_channel_unauthorized_fails():
    _, user_b_id = register_and_login()
    res = client.post("/channels/direct", json={"recipient_id": user_b_id})
    assert res.status_code == 401


# ---- group channel tests ----

def test_create_group_channel_success():
    headers_a, user_a_id = register_and_login()
    _, user_b_id = register_and_login()
    _, user_c_id = register_and_login()

    res = client.post(
        "/channels/group",
        json={"name": "Book Club", "member_ids": [user_b_id, user_c_id]},
        headers=headers_a,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["type"] == "group"
    assert data["name"] == "Book Club"
    member_ids = {m["user_id"] for m in data["members"]}
    assert member_ids == {user_a_id, user_b_id, user_c_id}


def test_create_group_channel_invalid_member_fails():
    headers_a, _ = register_and_login()
    _, other_community_user_id = register_and_login(get_second_test_activation_code())

    res = client.post(
        "/channels/group",
        json={"name": "Cross Community Group", "member_ids": [other_community_user_id]},
        headers=headers_a,
    )
    assert res.status_code == 400


def test_create_group_channel_no_members_fails():
    headers_a, user_a_id = register_and_login()

    # Only including self (which gets filtered out) leaves zero members
    res = client.post(
        "/channels/group",
        json={"name": "Solo Group", "member_ids": [user_a_id]},
        headers=headers_a,
    )
    assert res.status_code == 400


# ---- list channels ----

def test_list_channels_returns_only_my_channels():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()
    headers_c, _ = register_and_login()  # not part of any channel below

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    list_res_a = client.get("/channels/", headers=headers_a)
    list_res_c = client.get("/channels/", headers=headers_c)

    assert list_res_a.status_code == 200
    a_channel_ids = [c["id"] for c in list_res_a.json()]
    assert channel_id in a_channel_ids

    assert list_res_c.status_code == 200
    c_channel_ids = [c["id"] for c in list_res_c.json()]
    assert channel_id not in c_channel_ids


# ---- messages ----

def test_send_and_get_messages_success():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    send_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Hey, is the couch still available?"},
        headers=headers_a,
    )
    assert send_res.status_code == 201
    sent = send_res.json()
    assert sent["content"] == "Hey, is the couch still available?"
    assert sent["sender_id"] == user_a_id
    assert sent["sender"]["id"] == user_a_id

    # Recipient can read it too
    get_res = client.get(f"/channels/{channel_id}/messages", headers=headers_b)
    assert get_res.status_code == 200
    messages = get_res.json()
    assert any(m["content"] == "Hey, is the couch still available?" for m in messages)


def test_send_message_non_member_fails():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()
    headers_c, _ = register_and_login()  # not a member

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "I shouldn't be able to send this"},
        headers=headers_c,
    )
    assert res.status_code == 404


def test_get_messages_non_member_fails():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()
    headers_c, _ = register_and_login()  # not a member

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    res = client.get(f"/channels/{channel_id}/messages", headers=headers_c)
    assert res.status_code == 404


def test_send_message_unauthorized_fails():
    headers_a, user_a_id = register_and_login()
    headers_b, user_b_id = register_and_login()

    create_res = client.post("/channels/direct", json={"recipient_id": user_b_id}, headers=headers_a)
    channel_id = create_res.json()["id"]

    res = client.post(f"/channels/{channel_id}/messages", json={"content": "no token"})
    assert res.status_code == 401