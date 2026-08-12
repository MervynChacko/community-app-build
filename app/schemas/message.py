from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.message import ChannelType
from app.schemas.user import UserResponse


class DirectChatCreate(BaseModel):
    """Payload to initiate or fetch a 1-1 direct message channel with another resident."""
    recipient_id: int


class GroupChatCreate(BaseModel):
    """Payload to create a new group chat channel."""
    name: str = Field(..., min_length=1, max_length=100)
    member_ids: List[int]  # List of resident IDs to include


class MessageCreate(BaseModel):
    """Payload for posting a new message to an existing channel."""
    content: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    """DTO returned when fetching messages in a chat thread."""
    id: int
    channel_id: int
    sender_id: int
    content: str
    created_at: datetime
    sender: UserResponse

    model_config = ConfigDict(from_attributes=True)


class ChannelMemberResponse(BaseModel):
    """DTO representing a member in a channel."""
    id: int
    user_id: int
    joined_at: datetime
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


class ChannelResponse(BaseModel):
    """DTO returned when listing active chat channels."""
    id: int
    name: Optional[str] = None
    type: ChannelType
    created_at: datetime
    members: List[ChannelMemberResponse]

    model_config = ConfigDict(from_attributes=True)
