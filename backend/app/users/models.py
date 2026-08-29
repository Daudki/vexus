"""
User models.
"""
from datetime import datetime
from typing import Optional
import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text, Float
from sqlalchemy.orm import relationship

from app.database.base import Base


class RoleName(str, enum.Enum):
    """User roles.

    Member names (ADMIN, SECURITY_ANALYST, ...) match the Postgres enum
    labels created in the initial migration. Member values are the
    lowercase strings sent over the API / JWT and expected by the
    frontend (see frontend/src/services/auth.ts).
    """
    ADMIN = "admin"
    SECURITY_ANALYST = "security_analyst"
    NETWORK_ADMINISTRATOR = "network_administrator"
    VIEWER = "viewer"


class Role(Base):
    __tablename__ = "roles"

    # IDs are plain strings platform-wide (see UUIDPrimaryKeyMixin in
    # app/database/base.py and every alembic migration, which declares
    # `id` as sa.String()) rather than a Postgres-native UUID column,
    # so the same model code works against SQLite in tests/dev and
    # Postgres in production.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Enum(RoleName), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    role_id = Column(String, ForeignKey("roles.id"), nullable=False)
    role = relationship("Role", back_populates="users")
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"