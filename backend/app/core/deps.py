"""
Shared FastAPI dependencies: DB session passthrough, current-user
resolution from the access token, and role-based access control.

Every protected route enforces permissions here, at the router boundary,
never deep inside service logic — this keeps RBAC auditable in one place.
"""
from typing import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.session import get_db
from app.users.models import RoleName, User
from app.users.repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    claims = decode_token(token)
    if claims is None or claims.get("type") != "access":
        raise credentials_error

    user_id = claims.get("sub")
    if user_id is None:
        raise credentials_error

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error

    return user


def require_role(*allowed_roles: RoleName):
    """Dependency factory: `Depends(require_role(RoleName.ADMIN))`."""

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return _check


def require_any_role(current_user: User = Depends(get_current_user)) -> User:
    """Just requires authentication, any role — used for read-mostly endpoints."""
    return current_user
