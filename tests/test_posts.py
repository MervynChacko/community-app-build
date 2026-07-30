import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# Helper function to register and log in a user to obtain an auth token
def get_auth_headers():
    unique_email = f"post_tester_{uuid.uuid4().hex[:8]}@apartment.com"
    payload = {
        "email": unique_email,
        "full_name": "Post Tester",
        "apartment_number": "3B",
        "password": "securepassword123",
    }
    client.post("/auth/register", json=payload)
    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": "securepassword123"},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_post_success():
    headers = get_auth_headers()
    post_data = {
        "title": "Package Left at Lobby",
        "content": "There is a box for apartment 3B near the main entryway.",
        "category": "general",
    }
    response = client.post("/posts/", json=post_data, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == post_data["title"]
    assert data["content"] == post_data["content"]
    assert "id" in data
    assert "user_id" in data
    assert "author" in data


def test_create_post_unauthorized_fails():
    post_data = {
        "title": "Unauthorized Post",
        "content": "This should fail because no token is provided.",
        "category": "general",
    }
    # Send request without Authorization header
    response = client.post("/posts/", json=post_data)
    assert response.status_code == 401


def test_get_posts_authenticated():
    headers = get_auth_headers()
    response = client.get("/posts/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_post_masks_phone_number():
    headers = get_auth_headers()
    post_data = {
        "title": "Call me for the couch",
        "content": "Reach out at 555-867-5309 if interested!",
        "category": "buy_sell",
    }
    response = client.post("/posts/", json=post_data, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert "[PHONE REDACTED]" in data["content"]
    assert "555-867-5309" not in data["content"]


def test_create_post_redacts_prohibited_keywords():
    headers = get_auth_headers()
    post_data = {
        "title": "This is a scam warning",
        "content": "Avoid illegal wire transfer offers.",
        "category": "general",
    }
    response = client.post("/posts/", json=post_data, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert "****" in data["title"]
    assert "scam" not in data["title"].lower()
    assert "*******" in data["content"]
    assert "illegal" not in data["content"].lower()
