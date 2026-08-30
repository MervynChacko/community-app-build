from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(
        String, default="general"
    )  # e.g., 'buy_sell', 'general', 'announcement'
    price = Column(String, nullable=True)  # Optional price tag for items for sale
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    community_id = Column(Integer, ForeignKey("communities.id", ondelete="CASCADE"), nullable=True)

    # Flagging and reporting fields
    report_count = Column(Integer, default=0, nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False)

    # Soft delete fields for resident delete, with deleted_at timestamp. 
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    author = relationship("User", back_populates="posts")
    community = relationship("Community", back_populates="posts")
