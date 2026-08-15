from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ActivationCodeCreate(BaseModel):
    apartment_number: Optional[str] = Field(None, max_length=20)
    max_uses: int = Field(4, ge=1, le=4, description="Number of residents allowed to use this code (1-4)")
    expires_at: Optional[datetime] = Field(None, description="Optional expiry timestamp")


class ActivationCodeResponse(BaseModel):
    id: int
    code: str
    community_id: int
    apartment_number: Optional[str] = None
    max_uses: int
    used_count: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)