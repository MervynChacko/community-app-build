"""
Shared pytest fixtures/helpers used across test files.

Kept as a plain importable function (not a pytest fixture) because
test_posts.py and test_auth.py each build their own request payloads
around it (inside their own get_auth_headers() / payload dicts), rather
than receiving it as an injected fixture argument.
"""
import uuid

from app.database import SessionLocal
from app.models.user import Community, ActivationCode

# Cached across the whole pytest run (shared by every test file that
# imports this function, since Python only loads this module once per
# process) so we don't create a new Community/ActivationCode row on
# every single call.
_test_activation_code_cache = {"code": None}
_second_test_activation_code_cache = {"code": None}


def _create_test_activation_code(prefix: str) -> str:
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
            max_uses=10_000,  # effectively unlimited for one test run
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
        _test_activation_code_cache["code"] = _create_test_activation_code("TESTCOMM")
    return _test_activation_code_cache["code"]
 
 
def get_second_test_activation_code() -> str:
    """
    Creates a SECOND, entirely separate throwaway community + activation
    code. Used specifically for cross-community isolation tests -- e.g.
    verifying a user in Community B cannot view/edit/delete a post that
    belongs to Community A.
    """
    if _second_test_activation_code_cache["code"] is None:
        _second_test_activation_code_cache["code"] = _create_test_activation_code("TESTCOMM2")
    return _second_test_activation_code_cache["code"]