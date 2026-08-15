import uuid
from fastapi.testclient import TestClient
from app.main import app
from conftest import get_test_activation_code

client = TestClient(app)

# Generate unique email for each test session run and then add to payload below
UNIQUE_EMAIL = f"testuser_{uuid.uuid4().hex[:8]}@apartment.com"

def test_register_user_success():
    payload = {
        "email": UNIQUE_EMAIL,
        "full_name": "Test User",
        "apartment_number": "1A",
        "password": "testpassword123",
        "activation_code": get_test_activation_code(),
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data
    assert "password" not in data  # Ensure password hash is not leaked


def test_register_duplicate_email_fails():
    payload = {
        "email": UNIQUE_EMAIL,
        "full_name": "Duplicate User",
        "apartment_number": "1A",
        "password": "testpassword123",
        "activation_code": get_test_activation_code(),
    }
    # Second registration attempt with the same email
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400
    assert (
        response.json()["detail"] == "A user with this email address already exists."
    )


def test_login_success():
    payload = {
        "email": UNIQUE_EMAIL,
        "password": "testpassword123",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_incorrect_password_fails():
    payload = {
        "email": UNIQUE_EMAIL,
        "password": "wrongpassword!",
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
