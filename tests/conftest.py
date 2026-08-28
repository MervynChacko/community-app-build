"""
Shared pytest fixtures/helpers used across test files.

Kept as a plain importable function (not a pytest fixture) because
test_posts.py and test_auth.py each build their own request payloads
around it (inside their own get_auth_headers() / payload dicts), rather
than receiving it as an injected fixture argument.
"""
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import Community, ActivationCode

client = TestClient(app)

# Cached across the whole pytest run (shared by every test file that
# imports this function, since Python only loads this module once per
# process) so we don't create a new Community/ActivationCode row on
# every single call.
_test_activation_code_cache = {"code": None}
_second_test_activation_code_cache = {"code": None}


def create_test_activation_code(prefix: str) -> str:
    db = SessionLocal()
    try:
        community_code = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        community = Community(
            name=f"Pytest Community {community_code}",
            code=community_code,
        )
        db.add(community)
        db.flush()  # populate community.id
 
        activation_code = ActivationCode(
            code=f"{prefix}-{uuid.uuid4().hex}",
            community_id=community.id,
            max_uses=10000,  # effectively unlimited for one test run
            used_count=0,
            is_active=True,
            expires_at=None,
        )
        db.add(activation_code)
        db.commit()
        return activation_code.code
    finally:
        db.close()
 
 
def get_test_activation_code() -> str:
    """
    Lazily creates one throwaway Community + ActivationCode for this
    pytest run, going directly through the DB rather than the API --
    there's no registration-time endpoint for creating either, since
    communities are staff-bootstrapped and activation codes require an
    authenticated staff user, which tests don't have.
    """
    if _test_activation_code_cache["code"] is None:
        _test_activation_code_cache["code"] = create_test_activation_code("TESTCOMM")
    return _test_activation_code_cache["code"]
 
 
def get_second_test_activation_code() -> str:
    """
    Creates a SECOND, entirely separate throwaway community + activation
    code. Used specifically for cross-community isolation tests -- e.g.
    verifying a user in Community B cannot view/edit/delete a post that
    belongs to Community A.
    """
    if _second_test_activation_code_cache["code"] is None:
        _second_test_activation_code_cache["code"] = create_test_activation_code("TESTCOMM2")
    return _second_test_activation_code_cache["code"]


def register_and_login(activation_code: str = None):
    """
    Registers and logs in frest user, returning both auth headers and 
    new user id. Shared bu test_channels.py and test_websockets.py 
    - both need recipient_id/member_ids/user_id, not just headers
    """
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
        json={
            "email": unique_email,
            "password": "securepassword123"
        },
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id