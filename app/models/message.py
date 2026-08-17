from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    ForeignKey, 
    Text, 
    Boolean, 
    Enum as SQLEnum,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship

from app.database import Base


class ChannelType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"


class Channel(Base):
    """
    Represents a communication channel (either 1-1 Direct Message or Group Chat).
    """
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    community_id = Column(Integer, ForeignKey("communities.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=True)  # Optional channel name for 1-1 DMs, required/custom for Groups
    # Using values_callable here to manage SQLAlchemy's issue with member names
    type = Column(
        SQLEnum(ChannelType, values_callable = lambda enum_cls: [e.value for e in enum_cls]),
        default=ChannelType.DIRECT, 
        nullable=False
        )
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
        )

    # Relationships
    members = relationship("ChannelMember", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")
    community = relationship("Community", back_populates="channels")


class ChannelMember(Base):
    """
    Association table linking users to channels they participate in.
    """
    __tablename__ = "channel_members"
    __table_args__ = (
        # Prevents same user being added to the same channel
        UniqueConstraint("channel_id", "user_id", name="uq_channel_members_channel_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    channel = relationship("Channel", back_populates="members")
    user = relationship("User")


class Message(Base):
    """
    Stores text messages posted inside a specific channel.
    """
    __tablename__ = "messages"
    __table_args__ = (
        # Support for message history with newest first query pattern to be used by endpoint
        Index("ix_messages_channel_id_created_at", "channel_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User")
