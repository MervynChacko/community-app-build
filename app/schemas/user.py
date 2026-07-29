from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# 1. Shared fields across all User operations
class UserBase(BaseModel):
    email: EmailStr  # Automatically checks for valid email format (e.g., user@domain.com)
    full_name: str = Field(..., min_length=2, max_length=100)
    apartment_number: Optional[str] = Field(None, max_length=20)


# 2. Schema required when registering a new user
class UserCreate(UserBase):
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters"
    )


# 3. Schema returned to clients (excludes sensitive password fields)
class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True  # Allows Pydantic to read ORM objects directly from SQLAlchemy

# Schema for login credentials
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# Schema returned upon successful authentication
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
