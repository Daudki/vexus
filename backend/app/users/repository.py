from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.users.models import User, Role, RoleName


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID with role preloaded."""
        return self.db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username with role preloaded."""
        return self.db.query(User).options(joinedload(User.role)).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email with role preloaded."""
        return self.db.query(User).options(joinedload(User.role)).filter(User.email == email).first()

    def get_role_by_name(self, name: RoleName) -> Optional[Role]:
        return self.db.query(Role).filter(Role.name == name).first()

    def create(self, username: str, email: str, password_hash: str, role_id: UUID) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role_id=role_id,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        # Load the role after creation
        self.db.refresh(user)
        return user

    def update_last_login(self, user: User, timestamp: datetime) -> User:
        """Update user's last login timestamp."""
        # Query the user fresh to avoid stale data issues
        fresh_user = self.get_by_id(user.id)
        if fresh_user:
            fresh_user.last_login = timestamp
            self.db.flush()
            return fresh_user
        return user

    def update_role(self, user: User, role: Role) -> User:
        user.role_id = role.id
        self.db.flush()
        return user

    def list_all(self) -> List[User]:
        return self.db.query(User).options(joinedload(User.role)).all()