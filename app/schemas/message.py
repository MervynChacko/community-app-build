from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict      # added ConfigDict due to pytest deprecation warning
from app.schemas.user import UserResponse


class DirectMessageCreate(BaseModel):
    receiver_id: int
    content: str = Field(..., min_length=1, max_length=2000)


class DirectMessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    created_at: datetime
    sender: UserResponse
    receiver: UserResponse

    # class Config:             -- update due to pytest deprecation warning
    #     from_attributes = True

    model_config = ConfigDict(from_attributes=True)
