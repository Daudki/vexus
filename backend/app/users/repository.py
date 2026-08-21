from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.models import Role, RoleName, User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        return list(self.db.scalars(select(User).limit(limit).offset(offset)))

    def create(self, *, username: str, email: str, password_hash: str, role_id: str) -> User:
        user = User(username=username, email=email, password_hash=password_hash, role_id=role_id)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_role_by_name(self, name: RoleName) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))

    def update_last_login(self, user: User, when) -> None:
        user.last_login = when
        self.db.commit()

    def update_role(self, user: User, role: Role) -> User:
        user.role = role
        self.db.commit()
        self.db.refresh(user)
        return user
