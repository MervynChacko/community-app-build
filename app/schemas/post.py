from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator 
# 07302026(1) added ConfigDict due to pytest deprecation warning
# 07302026(2) added field_validator to implement rules on posts
from app.schemas.user import UserResponse
import re

# prohibited keyword list
PROHIBITED = ["kill","illegal","scam"]

def sanitize_text(text:str):
    """
    1. Mask phone number formats (123-456-7890, (123) 456-7890, 1234567890)
    2. Redactions (illegal -> *******)
    """
    if not text:
        return text

    # US numbers regex
    phone_pattern = r"\(?\b\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    sanitized = re.sub(phone_pattern, "[PHONE REDACTED]", text)

    # Redact prohibted words
    for word in PROHIBITED:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        sanitized = pattern.sub("*" * len(word), sanitized)

    return sanitized

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
    @field_validator("title", "content", mode="before")
    @classmethod
    def moderate_content(cls, value:str) -> str:
        if isinstance(value, str):
            return sanitize_text(value)
        return value


# 2. Schema used when creating a new post
class PostCreate(PostBase):
    pass


# 3. Schema returned when viewing a post (includes author details)
class PostResponse(PostBase):
    id: int
    user_id: int
    report_count: int
    is_flagged: bool
    created_at: datetime
    author: UserResponse  # Embeds user information directly inside the post response!

    # class Config:             -- update due to pytest deprecation warning
    #     from_attributes = True

    model_config = ConfigDict(from_attributes=True)