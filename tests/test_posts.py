import uuid
from fastapi.testclient import TestClient

from app.main import app
from conftest import get_test_activation_code, get_second_test_activation_code
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.post import Post

client = TestClient(app)

# Helper function to register and log in a user to obtain an auth token
# activation_code defaults to the shared test community;
# pass get_second_test_activation_code() to get a user in a different community
# for cross-community isolation tests.

def get_auth_headers(activation_code: str = None):
    unique_email = f"post_tester_{uuid.uuid4().hex[:8]}@apartment.com"
    payload = {
        "email": unique_email,
        "full_name": "Post Tester",
        "apartment_number": "3B",
        "password": "securepassword123",
        "activation_code": activation_code or get_test_activation_code(),
    }
    register_res = client.post("/auth/register", json=payload)
    # FAIL with real error instead of confusing downstream KeyError('id') two calls later
    assert register_res.status_code == 201, f"Registration failed: {register_res.text}"
    # client.post("/auth/register", json=payload)
    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": "securepassword123"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
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


def test_update_post_success():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Original title", "content": "Original content here."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    update_res = client.patch(
        f"/posts/{post_id}",
        json={"title": "Updated title"},
        headers=headers,
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["title"] == "Updated title"
    # Field not included in patch, body should be left unchanged
    assert data["content"] == "Original content here."


def test_update_post_applies_moderation():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Couch for sale", "content":"Great condition couch."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    update_res = client.patch(
        f"/posts/{post_id}",
        json={"content": "Call 555-867-5309 for details, avoid scam offers."},
        headers=headers,
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert "[PHONE REDACTED]" in data["content"]
    assert "555-867-5309" not in data["content"]
    assert "****" in data["content"]
    assert "scam" not in data["content"].lower()

def test_update_post_not_owner_fails():
    owner_headers = get_auth_headers()
    other_headers = get_auth_headers()  #different user in same community

    post_res = client.post(
        "/posts/",
        json={"title": "Owners Post", "content": "This belongs to owner."},
        headers=owner_headers,
    )
    post_id = post_res.json()["id"]

    update_res = client.patch(
        f"/posts/{post_id}",
        json={"title": "Hijacked title"},
        headers=other_headers,
    )
    assert update_res.status_code == 403


def test_update_post_cross_community_fails():
    community_a_headers = get_auth_headers()
    community_b_headers = get_auth_headers(get_second_test_activation_code())

    post_res = client.post(
        "/posts/",
        json={"title": "Community A post", "content": "Only visible in Community A."},
        headers=community_a_headers,
    )
    post_id = post_res.json()["id"]

    update_res = client.patch(
        f"/posts/{post_id}",
        json={"title": "Cross Community Hijack"},
        headers=community_b_headers,
    )
    assert update_res.status_code == 404    #post in another community must look non-existent


def test_update_post_cannot_reset_flag_status():
    # A flagged post should not be unflagged via UPDATE
    headers = get_auth_headers()
    post_res = client.post(
        "/posts",
        json={"title": "Spam Post to Flag", "content": "This will get reported."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    for _ in range(3):
        client.post(f"/posts/{post_id}/report", headers=headers)

    update_res = client.patch(
        f"/posts/{post_id}",
        json={"title": "Trying to sneak past moderation", "is_flagged": False},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["is_flagged"] is True


def test_update_post_unauthorized_fails():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Some post", "content": "Some content for test"},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    update_res = client.patch(
        f"/posts/{post_id}",
        json={"title": "No Token"}
    )
    assert update_res.status_code == 401


def test_delete_post_success():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Post to Delete", "content": "Post to be deleted"},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    delete_res = client.delete(
        f"/posts/{post_id}",
        headers=headers
    )
    assert delete_res.status_code == 204

    feed_res = client.get("/posts/", headers=headers)
    post_ids = [p["id"] for p in feed_res.json()]
    assert post_id not in post_ids  # remove from feed


def test_delete_post_not_owner_fails():
    owner_headers = get_auth_headers()
    other_headers = get_auth_headers()

    post_res = client.post(
        "/posts/",
        json={"title": "Protected post", "content": "Other users should not be able to delete post"},
        headers=owner_headers,
    )
    post_id = post_res.json()["id"]

    delete_res = client.delete(
        f"/posts/{post_id}",
        headers=other_headers
    )
    assert delete_res.status_code == 403

    feed_res = client.get("/posts/", headers=owner_headers)
    post_ids = [p["id"] for p in feed_res.json()]
    assert post_id in post_ids


def test_delete_post_cross_community_fails():
    community_a_headers = get_auth_headers()
    community_b_headers = get_auth_headers(get_second_test_activation_code())

    post_res = client.post(
        "/posts/",
        json={"title": "Community A post only", "content": "Should not be visible in Community B"},
        headers=community_a_headers,
    )
    post_id = post_res.json()["id"]

    delete_res = client.delete(
        f"/posts/{post_id}",
        headers=community_b_headers
    )
    assert delete_res.status_code == 404


def test_delete_post_unauthorized_fails():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Another Post", "content": "For unauthorized delete test"},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    delete_res = client.delete(f"/posts/{post_id}")
    assert delete_res.status_code == 401


# ---- soft delete and staff moderation ----

def test_soft_delete_marks_post_as_deleted():
    """Deleting a post soft-deletes it rather than hard-deleting it."""
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "To Delete", "content": "This will be soft-deleted."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    delete_res = client.delete(f"/posts/{post_id}", headers=headers)
    assert delete_res.status_code == 204

    db = SessionLocal()
    try:
        post_row = db.query(Post).filter(Post.id == post_id).first()
        assert post_row is not None       # still exists in DB
        assert post_row.is_deleted is True
        assert post_row.deleted_at is not None
    finally:
        db.close()


def test_deleted_posts_hidden_from_residents():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Hidden Post", "content": "Will be deleted."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    feed_before = [p["id"] for p in client.get("/posts/", headers=headers).json()]
    assert post_id in feed_before

    client.delete(f"/posts/{post_id}", headers=headers)

    feed_after = [p["id"] for p in client.get("/posts/", headers=headers).json()]
    assert post_id not in feed_after


def test_cannot_edit_deleted_post():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Editable", "content": "Original content."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    client.delete(f"/posts/{post_id}", headers=headers)

    edit_res = client.patch(
        f"/posts/{post_id}",
        json={"title": "Hacked Title"},
        headers=headers,
    )
    assert edit_res.status_code == 404


def test_cannot_report_deleted_post():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "To Report", "content": "Some content here."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    client.delete(f"/posts/{post_id}", headers=headers)

    report_res = client.post(f"/posts/{post_id}/report", headers=headers)
    assert report_res.status_code == 404


def test_staff_can_delete_other_residents_posts():
    db = SessionLocal()
    try:
        resident_headers = get_auth_headers()
        staff_headers = get_auth_headers()

        # Extract staff user's id from their JWT
        from app.core.security import decode_access_token
        staff_token = staff_headers["Authorization"].split(" ")[1]
        staff_id = int(decode_access_token(staff_token)["sub"])

        # Elevate to staff directly in DB
        staff_user = db.query(User).filter(User.id == staff_id).first()
        staff_user.role = UserRole.STAFF
        db.commit()

        post_res = client.post(
            "/posts/",
            json={"title": "Staff Override Test", "content": "Deletable by staff."},
            headers=resident_headers,
        )
        post_id = post_res.json()["id"]

        delete_res = client.delete(f"/posts/{post_id}", headers=staff_headers)
        assert delete_res.status_code == 204

        feed = [p["id"] for p in client.get("/posts/", headers=resident_headers).json()]
        assert post_id not in feed
    finally:
        db.close()


def test_resident_cannot_delete_other_residents_posts():
    resident_1_headers = get_auth_headers()
    resident_2_headers = get_auth_headers()

    post_res = client.post(
        "/posts/",
        json={"title": "Protected Post", "content": "Resident 2 can't delete this."},
        headers=resident_1_headers,
    )
    post_id = post_res.json()["id"]

    delete_res = client.delete(f"/posts/{post_id}", headers=resident_2_headers)
    assert delete_res.status_code == 403

    feed = [p["id"] for p in client.get("/posts/", headers=resident_1_headers).json()]
    assert post_id in feed


def test_cannot_delete_already_deleted_post():
    headers = get_auth_headers()
    post_res = client.post(
        "/posts/",
        json={"title": "Delete Twice", "content": "Some content here."},
        headers=headers,
    )
    post_id = post_res.json()["id"]

    assert client.delete(f"/posts/{post_id}", headers=headers).status_code == 204
    assert client.delete(f"/posts/{post_id}", headers=headers).status_code == 404