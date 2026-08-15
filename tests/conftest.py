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


def get_test_activation_code() -> str:
    """
    Lazily creates a throwaway community + activation code for pytest run.
    Going directly to database since there is no API endpoint for creating either.
    -- community is staff bootstrapped and activation code requires authenticated staff.
    Cached for remainder of the run.
    """
    if _test_activation_code_cache["code"] is not None:
        return _test_activation_code_cache["code"]

    db = SessionLocal()
    try:
        community_code = f"TESTCOMM-{uuid.uuid4().hex[:8].upper()}"
        community = Community(
            name=f"Pytest Community {community_code}",
            code=community_code,
        )
        db.add(community)
        db.flush()  # populate community.id

        activation_code = ActivationCode(
            code=f"TESTCODE-{uuid.uuid4().hex}",
            community_id=community.id,
            max_uses=10_000,  # effectively unlimited for one test run;
                               # the 1-4 cap is a staff-endpoint business
                               # rule, not enforced at the DB/model level
            used_count=0,
            is_active=True,
            expires_at=None,
        )
        db.add(activation_code)
        db.commit()

        _test_activation_code_cache["code"] = activation_code.code
        return activation_code.code
    finally:
        db.close()