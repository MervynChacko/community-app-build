from enum import Enum
from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey, Enum as SqlEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class UserRole(str, Enum):
    RESIDENT = "resident"
    STAFF = "staff"

class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(10), unique=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    users = relationship("User", back_populates="community")
    posts = relationship("Post", back_populates="community")
    channels = relationship("Channel", back_populates="community")
    activation_codes = relationship("ActivationCode", back_populates="community")
    

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    apartment_number = Column(String, nullable=True)
    community_id = Column(Integer, ForeignKey("communities.id", ondelete="SET NULL"), nullable=True)
    # Added role with values to handle error due to SQLAlchemy's 
    # handling of Enum types in PostgreSQL. Default value picked is the role 
    # variable i.e. RESIDENT, STAFF and not the value
    role = Column(
        SqlEnum(UserRole, values_callable = lambda enum_cls: [e.value for e in enum_cls]),
        default=UserRole.RESIDENT, 
        nullable=False
        )
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    posts = relationship("Post", back_populates="author")
    community = relationship("Community", back_populates="users")


class ActivationCode(Base):
    """
    Staff-issued code that ties a new resident registration to a specific
    community. Unlike Community.code (a static, permanent identifier),
    an ActivationCode is:
      - scoped to one community
      - capped to a limited number of uses (e.g. residents of one unit)
      - revocable by staff (is_active)
      - optionally time-limited (expires_at)
 
    used_count is incremented atomically at registration time to avoid a
    race condition where two concurrent registrations both succeed past
    max_uses.
    """
    __tablename__ = "activation_codes"
 
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    community_id = Column(
        Integer, ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    apartment_number = Column(String(20), nullable=True)
 
    max_uses = Column(Integer, nullable=False, default=4)
    used_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    # Nullable + SET NULL so revoking/deleting a staff account doesn't
    # cascade-delete the codes they issued (keeps the audit trail intact).
    created_by_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
 
    # Relationships
    community = relationship("Community", back_populates="activation_codes")
    created_by = relationship("User")