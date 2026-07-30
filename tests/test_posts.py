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

# Post reporting test
def test_report_post_increments_count():
    headers = get_auth_headers()
    # Create a post
    post_res = client.post(
        "/posts/",
        json={"title":"Annoying Post", "content":"Just testing reporting."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    # Report post once
    report_res = client.post(f"/posts/{post_id}/report", headers=headers)
    assert report_res.status_code == 200
    data = report_res.json()
    assert data["report_count"] == 1
    assert data["is_flagged"] is False


def test_post_auto_flagged_and_hidden_after_threshold():
    headers = get_auth_headers()
    # Create a post
    post_res = client.post(
        "/posts/",
        json={"title": "Spam Post", "content": "This post should get flagged."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    # Report 3 times to hit threshold
    for _ in range(3):
        client.post(f"/posts/{post_id}/report", headers=headers)

    # Verify post drops off the public GET /posts/ feed
    feed_res = client.get("/posts/", headers=headers)
    feed_posts = feed_res.json()
    post_ids = [p["id"] for p in feed_posts]
    assert post_id not in post_ids