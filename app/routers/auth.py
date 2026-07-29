from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse


# 1. Create a router instance to group authentication/user routes together
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    # Step A: Check if the email address is already registered in PostgreSQL
    existing_user = (
        db.query(User).filter(User.email == user_in.email).first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Step B: Hash the user's raw password
    hashed_pwd = hash_password(user_in.password)

    # Step C: Construct the SQLAlchemy User instance
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_pwd,
        full_name=user_in.full_name,
        apartment_number=user_in.apartment_number,
    )

    # Step D: Save the new user record into PostgreSQL
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # Refreshes instance with DB-generated fields (id, created_at)

    # Step E: Return the new user (Pydantic converts this to UserResponse automatically)
    return new_user

@router.post("/login", response_model=Token)
def login_user(credentials: UserLogin, db: Session = Depends(get_db)):
    # 1. Fetch user by email
    user = db.query(User).filter(User.email == credentials.email).first()

    # 2. Verify user exists and password matches the stored bcrypt hash
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 3. Generate signed JWT token containing user's unique ID
    access_token = create_access_token(data={"sub": str(user.id)})

    # 4. Return token to client
    return {"access_token": access_token, "token_type": "bearer"}
