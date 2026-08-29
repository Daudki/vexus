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
        self.db.commit()
        # Load the role after creation
        self.db.refresh(user)
        return user

    def update_last_login(self, user: User, timestamp: datetime) -> User:
        """Update user's last login timestamp."""
        # Query the user fresh to avoid stale data issues
        fresh_user = self.get_by_id(user.id)
        if fresh_user:
            fresh_user.last_login = timestamp
            self.db.commit()
            return fresh_user
        return user

    def update_role(self, user: User, role: Role) -> User:
        # Setting only the FK column would leave the already-loaded
        # `.role` relationship pointing at the old Role instance for
        # the rest of this session (SQLAlchemy doesn't re-resolve a
        # populated relationship just because the FK column changed).
        # Assigning the relationship itself keeps both in sync.
        user.role = role
        user.role_id = role.id
        self.db.commit()
        return user

    def list_all(self) -> List[User]:
        return self.db.query(User).options(joinedload(User.role)).all()

    def count_active_admins(self, exclude_user_id: Optional[str] = None) -> int:
        """Count active users with the ADMIN role.

        Used to prevent an admin from deactivating/deleting/demoting
        the last remaining admin account and locking everyone out.
        `exclude_user_id` lets a caller ask "how many *other* active
        admins are there besides this one".
        """
        query = (
            self.db.query(User)
            .join(Role)
            .filter(Role.name == RoleName.ADMIN, User.is_active.is_(True))
        )
        if exclude_user_id is not None:
            query = query.filter(User.id != exclude_user_id)
        return query.count()

    def set_active(self, user: User, is_active: bool) -> User:
        user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()