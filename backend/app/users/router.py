from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.deps import get_current_user, require_role
from app.core.security import hash_password
from app.database.session import get_db
from app.users.models import RoleName, User
from app.users.repository import UserRepository
from app.users.schemas import UserCreate, UserRead, UserUpdateRole

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_role(RoleName.ADMIN))])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    return [_to_read(u) for u in UserRepository(db).list_all()]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> UserRead:
    repo = UserRepository(db)

    if repo.get_by_username(payload.username) or repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists.")

    role = repo.get_role_by_name(payload.role)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role.")

    user = repo.create(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role_id=role.id,
    )

    AuditService(db).record(
        action="user.create",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        detail=f"Created user '{user.username}' with role {role.name.value}",
        ip_address=request.client.host,
    )

    return _to_read(user)


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserRead:
    return _to_read(current_user)


@router.patch("/{user_id}/role", response_model=UserRead)
def update_role(
    user_id: str,
    payload: UserUpdateRole,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> UserRead:
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    role = repo.get_role_by_name(payload.role)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role.")

    previous_role = user.role.name.value
    updated = repo.update_role(user, role)

    AuditService(db).record(
        action="user.role_change",
        actor=current_user,
        target_type="user",
        target_id=user.id,
        detail=f"Role changed from {previous_role} to {role.name.value}",
        ip_address=request.client.host,
    )

    return _to_read(updated)
