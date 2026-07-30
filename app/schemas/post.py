from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict # added ConfigDict due to pytest deprecation warning
from app.schemas.user import UserResponse


# 1. Base properties shared when creating or viewing a post
class PostBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    content: str = Field(..., min_length=10)
    category: Optional[str] = Field(
        default="general", description="e.g., buy_sell, general, announcement"
    )
    price: Optional[str] = Field(
        None, max_length=50
    )  # Used for buy/sell listings


# 2. Schema used when creating a new post
class PostCreate(PostBase):
    pass


# 3. Schema returned when viewing a post (includes author details)
class PostResponse(PostBase):
    id: int
    user_id: int
    created_at: datetime
    author: UserResponse  # Embeds user information directly inside the post response!

    # class Config:             -- update due to pytest deprecation warning
    #     from_attributes = True

    model_config = ConfigDict(from_attributes=True)