import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, ActivationCode
from app.schemas.activation_code import ActivationCodeCreate, ActivationCodeResponse
from app.routers.deps import get_current_staff_user

router = APIRouter(prefix="/staff", tags=["Staff"])

# How many times to retry generating a code if we hit a (very unlikely)
# uniqueness collision, before giving up.
MAX_CODE_GENERATION_ATTEMPTS = 5


def _generate_unique_code(db: Session) -> str:
    for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
        candidate = secrets.token_urlsafe(9)  # ~12 char URL-safe token
        exists = db.query(ActivationCode).filter(ActivationCode.code == candidate).first()
        if not exists:
            return candidate
    # Astronomically unlikely with token_urlsafe(9), but fail loudly
    # rather than silently returning a colliding code.
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not generate a unique activation code, please retry",
    )


@router.post("/activation-codes", response_model=ActivationCodeResponse, status_code=status.HTTP_201_CREATED)
def create_activation_code(
    payload: ActivationCodeCreate,
    db: Session = Depends(get_db),
    staff_user: User = Depends(get_current_staff_user),
):
    """
    Issue a new activation code, scoped to the staff member's own
    community. community_id is deliberately never taken from the request
    body -- it's always derived from staff_user, so a staff account can
    only ever issue codes for the community they themselves belong to.
    """
    new_code = ActivationCode(
        code=_generate_unique_code(db),
        community_id=staff_user.community_id,
        apartment_number=payload.apartment_number,
        max_uses=payload.max_uses,
        expires_at=payload.expires_at,
        created_by_id=staff_user.id,
    )
    db.add(new_code)
    db.commit()
    db.refresh(new_code)
    return new_code


@router.get("/activation-codes", response_model=List[ActivationCodeResponse])
def list_activation_codes(
    db: Session = Depends(get_db),
    staff_user: User = Depends(get_current_staff_user),
):
    """
    List activation codes for the staff member's own community only.
    """
    return (
        db.query(ActivationCode)
        .filter(ActivationCode.community_id == staff_user.community_id)
        .order_by(ActivationCode.created_at.desc())
        .all()
    )


@router.post("/activation-codes/{code_id}/revoke", response_model=ActivationCodeResponse)
def revoke_activation_code(
    code_id: int,
    db: Session = Depends(get_db),
    staff_user: User = Depends(get_current_staff_user),
):
    """
    Revoke a code early (e.g. a lease fell through). Scoped by
    community_id in the same query as the lookup -- same pattern as the
    posts.py fix -- so staff can never revoke (or discover the existence
    of) a code belonging to another community via a guessed code_id.
    """
    code = (
        db.query(ActivationCode)
        .filter(
            ActivationCode.id == code_id,
            ActivationCode.community_id == staff_user.community_id,
        )
        .first()
    )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activation code not found",
        )

    code.is_active = False
    db.commit()
    db.refresh(code)
    return code