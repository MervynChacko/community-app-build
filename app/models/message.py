from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
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
    name = Column(String(100), nullable=True)  # Optional for 1-1 DMs, required/custom for Groups
    type = Column(SQLEnum(ChannelType), default=ChannelType.DIRECT, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    members = relationship("ChannelMember", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")


class ChannelMember(Base):
    """
    Association table linking users to channels they participate in.
    """
    __tablename__ = "channel_members"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    channel = relationship("Channel", back_populates="members")
    user = relationship("User")


class Message(Base):
    """
    Stores text messages posted inside a specific channel.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User")
